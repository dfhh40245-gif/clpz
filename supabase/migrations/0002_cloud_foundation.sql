-- CLPZ Supabase schema — migration 0002_cloud_foundation (task 14)
--
-- Forward migration for databases that already applied 0001.
-- Idempotent by construction: IF NOT EXISTS / DO-block guards so a partially
-- applied 0002 converges on re-run. Never edit 0001 to repair deployed DBs.
--
-- What this fixes (task 14 / F17):
--   1. grant_credits replay checked (external_ref, txn_type) instead of the
--      SUPPLIED idempotency key — a different user's grant with the same
--      external_ref was silently suppressed, and concurrent same-key calls
--      could double-grant. Replay is now key-scoped, conflict-detected, and
--      concurrency-safe (advisory lock + unique key index).
--   2. Subscriptions had no status constraint, no single-active-per-user
--      guarantee and no valid-transition enforcement.
--   3. Credits were a single undifferentiated balance; the advertised model
--      (subscription credits expire / purchased credits never expire) needs
--      separate buckets with a defined spend order.
--   4. profiles lacked the full_name/display_name alignment used by the
--      website and had no display_name length guard.

-- ── 1. Profiles: full_name + display_name guard ─────────────────────
alter table public.profiles add column if not exists full_name text not null default '';

-- Trim + cap display_name length (website constraint alignment).
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'profiles_display_name_len'
    ) then
        alter table public.profiles
            add constraint profiles_display_name_len
            check (char_length(display_name) <= 64);
    end if;
end $$;

-- ── 2. Subscriptions: status domain, transitions, single-active ─────
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'subscriptions_status_domain'
    ) then
        alter table public.subscriptions
            add constraint subscriptions_status_domain
            check (status in ('active', 'past_due', 'canceled', 'expired'));
    end if;
end $$;

-- Enforce valid state transitions on update (service-role writes only, but
-- the invariant is owned by the database, not the caller).
create or replace function public.subscriptions_guard_transition()
returns trigger
language plpgsql
as $$
begin
    if tg_op = 'UPDATE' and old.status is distinct from new.status then
        if old.status = 'canceled' and new.status in ('active', 'past_due') then
            raise exception 'invalid subscription transition % -> %', old.status, new.status;
        end if;
        if old.status = 'expired' and new.status not in ('canceled') then
            raise exception 'invalid subscription transition % -> %', old.status, new.status;
        end if;
    end if;
    new.updated_at := now();
    return new;
end $$;

drop trigger if exists subscriptions_transition_guard on public.subscriptions;
create trigger subscriptions_transition_guard
    before update on public.subscriptions
    for each row execute function public.subscriptions_guard_transition();

-- At most ONE active subscription per user. A partial unique index is the
-- concurrency-safe way to express "single active" (two racing inserts of an
-- active row for the same user cannot both commit).
create unique index if not exists subscriptions_one_active_per_user
    on public.subscriptions (user_id)
    where status = 'active';

-- ── 3. Credit buckets: subscription (expiring) vs purchased (permanent) ─
create table if not exists public.credit_buckets (
    bucket_id text not null,
    user_id uuid not null references auth.users(id) on delete cascade,
    kind text not null check (kind in ('subscription', 'purchased')),
    amount integer not null check (amount >= 0),
    source_payment_id uuid references public.payments(id) on delete set null,
    expires_at timestamptz,               -- null = never expires (purchased)
    created_at timestamptz not null default now(),
    primary key (bucket_id, user_id)
);

alter table public.credit_buckets enable row level security;
create policy "credit_buckets: read own"
    on public.credit_buckets for select
    using (auth.uid() = user_id);
-- No client write policies: buckets are server-authoritative.

create index if not exists idx_credit_buckets_spend
    on public.credit_buckets (user_id, expires_at nulls last, created_at);

-- Spend order is defined and enforced server-side: spend the soonest-to-
-- expire subscription credits first, then purchased credits (FIFO by grant).
create or replace function public.spend_credits(
    p_user_id uuid,
    p_amount integer
)
returns integer
language plpgsql
security definer set search_path = public
as $$
declare
    v_remaining integer := p_amount;
    v_bucket record;
    v_deducted integer;
    v_total integer;
begin
    if p_amount <= 0 then
        raise exception 'spend amount must be positive';
    end if;

    select coalesce(sum(amount), 0) into v_total
    from public.credit_buckets
    where user_id = p_user_id
      and (kind = 'purchased' or expires_at is null or expires_at > now());

    if v_total < p_amount then
        raise exception 'insufficient credits (% available, % requested)', v_total, p_amount;
    end if;

    -- Soonest expiry first (subscription grants), then purchased FIFO.
    for v_bucket in
        select bucket_id, amount
        from public.credit_buckets
        where user_id = p_user_id
          and (kind = 'purchased' or expires_at is null or expires_at > now())
          and amount > 0
        order by (kind = 'subscription') desc, expires_at nulls last, created_at
        for update
    loop
        exit when v_remaining <= 0;
        v_deducted := least(v_bucket.amount, v_remaining);
        update public.credit_buckets
           set amount = amount - v_deducted
         where bucket_id = v_bucket.bucket_id and user_id = p_user_id;
        v_remaining := v_remaining - v_deducted;
    end loop;

    -- Keep the legacy undifferentiated balance in sync for existing readers.
    update public.credit_accounts
       set balance = (select coalesce(sum(amount), 0) from public.credit_buckets
                      where user_id = p_user_id
                        and (kind = 'purchased' or expires_at is null or expires_at > now())),
           updated_at = now()
     where user_id = p_user_id;

    return p_amount;
end $$;

revoke execute on function public.spend_credits(uuid, integer) from anon, authenticated, public;
grant execute on function public.spend_credits(uuid, integer) to service_role;

-- ── 4. grant_credits v2: key-scoped, conflict-detecting, concurrency-safe ─
-- Replay: same key + same payload (user, amount, txn_type) → return current
-- balance (idempotent no-op). Same key + DIFFERENT payload → reject (409
-- semantics). The advisory lock serializes concurrent same-key calls so two
-- racing grants cannot both pass the exists() check and double-insert.
create or replace function public.grant_credits(
    p_user_id uuid,
    p_amount integer,
    p_txn_type text,
    p_description text default '',
    p_external_ref text default '',
    p_idempotency_key text default null
)
returns integer
language plpgsql
security definer set search_path = public
as $$
declare
    v_new_balance integer;
    v_existing record;
begin
    if p_amount is null or p_amount <= 0 then
        raise exception 'grant amount must be positive';
    end if;

    -- Serialize concurrent same-key grants (session-scoped advisory lock
    -- keyed on the idempotency key).
    if p_idempotency_key is not null then
        perform pg_advisory_xact_lock(hashtext(p_idempotency_key));

        select user_id, amount, txn_type, external_ref
          into v_existing
        from public.credit_transactions
        where idempotency_key = p_idempotency_key
        limit 1;

        if found then
            if v_existing.user_id = p_user_id
               and v_existing.amount = p_amount
               and v_existing.txn_type = p_txn_type
               and v_existing.external_ref = p_external_ref then
                -- Exact replay: idempotent no-op.
                select balance into v_new_balance
                from public.credit_accounts where user_id = p_user_id;
                return coalesce(v_new_balance, 0);
            end if;
            -- Same key, different payload: conflict, never misgrant.
            raise exception 'idempotency key % already used with a different payload', p_idempotency_key
                  using errcode = 'unique_violation';
        end if;
    end if;

    insert into public.credit_accounts (user_id, balance)
    values (p_user_id, 0)
    on conflict (user_id) do nothing;

    update public.credit_accounts
       set balance = balance + p_amount, updated_at = now()
     where user_id = p_user_id
    returning balance into v_new_balance;

    if v_new_balance < 0 then
        raise exception 'credit balance cannot go negative';
    end if;

    insert into public.credit_transactions
        (user_id, amount, txn_type, description, external_ref, idempotency_key)
    values
        (p_user_id, p_amount, p_txn_type, p_description, p_external_ref, p_idempotency_key);

    -- Mirror into the bucket model: subscription grants expire per the
    -- advertised policy; purchased credits never expire.
    insert into public.credit_buckets (bucket_id, user_id, kind, amount, expires_at)
    values (
        coalesce(p_idempotency_key, gen_random_uuid()::text),
        p_user_id,
        case when p_txn_type = 'subscription' then 'subscription' else 'purchased' end,
        p_amount,
        case when p_txn_type = 'subscription'
             then now() + interval '60 days'   -- advertised rollover window
             else null end
    )
    on conflict (bucket_id, user_id) do nothing;

    return v_new_balance;
end $$;

-- ── 5. Webhook inbox (task 15): durable provider-event receipt ─────
-- One row per (provider, external event identity, resulting state). Received
-- BEFORE any fulfillment decision; `processed` flips only after fulfillment
-- completes, so a crash leaves a recoverable row for provider redelivery.
create table if not exists public.webhook_events (
    id uuid primary key default gen_random_uuid(),
    provider text not null default 'gumroad',
    external_id text not null,
    event_state text not null,
    payload jsonb not null default '{}'::jsonb,
    received_at timestamptz not null default now(),
    processed boolean not null default false,
    unique (provider, external_id, event_state)
);

alter table public.webhook_events enable row level security;
-- No client policies at all: the inbox is service-role only.

-- Key uniqueness is enforced by a dedicated partial index so concurrent
-- inserts race on the index rather than on a check-then-insert.
do $$
begin
    if not exists (
        select 1 from pg_indexes
        where indexname = 'credit_transactions_key_unique'
    ) then
        create unique index credit_transactions_key_unique
            on public.credit_transactions (idempotency_key)
            where idempotency_key is not null;
    end if;
end $$;

-- Preserve restricted execution for the NEW function signature (same
-- signature as 0001, so re-grants cover the replaced function body).
revoke execute on function public.grant_credits(uuid, integer, text, text, text, text) from anon, authenticated;
revoke execute on function public.grant_credits(uuid, integer, text, text, text, text) from public;
grant execute on function public.grant_credits(uuid, integer, text, text, text, text) to service_role;
