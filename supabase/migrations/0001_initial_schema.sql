-- CLPZ Supabase schema — migration 0001_initial
-- Cloud account/business data ONLY. The desktop app's SQLite stays local.
--
-- Relationships:
--   auth.users (Supabase Auth)
--     └─ profiles            (1:1, id == auth.users.id)
--         ├─ subscriptions   (1:N, one active per user)
--         ├─ payments        (1:N, external provider records)
--         ├─ credit_accounts (1:1)
--         │   └─ credit_transactions (1:N, append-only ledger)
--         └─ entitlements    (1:N)
--   releases / download_events are global (not user-scoped).
--
-- SECURITY MODEL:
--   - RLS is ENABLED on every user-scoped table.
--   - Users can read their own rows; inserts to the credit ledger and
--     payments are FORBIDDEN from the client — only the server (service
--     role) may write. Never trust balance/status from the browser.

-- ── profiles ────────────────────────────────────────────────────────
create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text not null,
    display_name text not null default '',
    created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "profiles: read own"
    on public.profiles for select
    using (auth.uid() = id);

create policy "profiles: update own display name"
    on public.profiles for update
    using (auth.uid() = id)
    with check (auth.uid() = id and email = (select email from public.profiles where id = auth.uid()));

-- Auto-create a profile whenever a user signs up.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
    insert into public.profiles (id, email, display_name)
    values (new.id, new.email, coalesce(new.raw_user_meta_data->>'display_name', ''))
    on conflict (id) do nothing;
    -- Seed a zero-balance credit account for the new user.
    insert into public.credit_accounts (user_id, balance)
    values (new.id, 0)
    on conflict (user_id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- ── subscriptions ───────────────────────────────────────────────────
create table if not exists public.subscriptions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    plan text not null default 'free',
    status text not null default 'active',
    provider text not null default 'gumroad',
    external_id text not null default '',
    current_period_end timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (provider, external_id)
);

alter table public.subscriptions enable row level security;

create policy "subscriptions: read own"
    on public.subscriptions for select
    using (auth.uid() = user_id);

-- ── payments ────────────────────────────────────────────────────────
create table if not exists public.payments (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users(id) on delete set null,
    provider text not null default 'gumroad',
    external_id text not null,
    product_id text not null default '',
    amount_cents integer not null default 0,
    currency text not null default 'usd',
    status text not null default 'paid',
    created_at timestamptz not null default now(),
    unique (provider, external_id)
);

alter table public.payments enable row level security;

create policy "payments: read own"
    on public.payments for select
    using (auth.uid() = user_id);
-- No insert/update policies: only the service role (webhook server) writes.

-- ── credit_accounts ─────────────────────────────────────────────────
create table if not exists public.credit_accounts (
    user_id uuid primary key references auth.users(id) on delete cascade,
    balance integer not null default 0 check (balance >= 0),
    updated_at timestamptz not null default now()
);

alter table public.credit_accounts enable row level security;

create policy "credit_accounts: read own"
    on public.credit_accounts for select
    using (auth.uid() = user_id);
-- No insert/update policies: balance is server-authoritative only.

-- ── credit_transactions (append-only ledger) ────────────────────────
create table if not exists public.credit_transactions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    amount integer not null,
    txn_type text not null,
    description text not null default '',
    external_ref text not null default '',
    idempotency_key text unique,
    created_at timestamptz not null default now()
);

create index if not exists idx_credit_txns_user
    on public.credit_transactions(user_id, created_at desc);

alter table public.credit_transactions enable row level security;

create policy "credit_transactions: read own"
    on public.credit_transactions for select
    using (auth.uid() = user_id);
-- No insert/update/delete policies: the ledger is append-only via the server.

-- ── entitlements ────────────────────────────────────────────────────
create table if not exists public.entitlements (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    feature text not null,
    granted_by text not null default 'purchase',
    external_ref text not null default '',
    expires_at timestamptz,
    created_at timestamptz not null default now(),
    unique (user_id, feature)
);

alter table public.entitlements enable row level security;

create policy "entitlements: read own"
    on public.entitlements for select
    using (auth.uid() = user_id);

-- ── releases (public product metadata) ──────────────────────────────
create table if not exists public.releases (
    id uuid primary key default gen_random_uuid(),
    version text not null,
    platform text not null,
    channel text not null default 'stable',
    url text not null,
    sha256 text not null default '',
    size_bytes bigint not null default 0,
    release_notes text not null default '',
    published boolean not null default false,
    created_at timestamptz not null default now(),
    unique (version, platform, channel)
);

alter table public.releases enable row level security;

create policy "releases: public read of published"
    on public.releases for select
    using (published = true);

-- ── download_events (anonymous, insert-only analytics) ──────────────
create table if not exists public.download_events (
    id uuid primary key default gen_random_uuid(),
    release_id uuid references public.releases(id) on delete set null,
    platform text not null,
    created_at timestamptz not null default now()
);

alter table public.download_events enable row level security;

create policy "download_events: anyone can insert"
    on public.download_events for insert
    with check (true);
-- No select policy: analytics rows are write-only from clients.

-- ── Server-side credit grant function (service-role only) ───────────
-- The Gumroad webhook server calls this via the service role key. It is
-- the ONLY way credits change in the cloud — no client path exists.
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
begin
    -- Idempotency: if this external ref was already processed, no-op.
    if p_idempotency_key is not null then
        if exists (
            select 1 from public.credit_transactions
            where external_ref = p_external_ref and txn_type = p_txn_type
        ) then
            select balance into v_new_balance
            from public.credit_accounts where user_id = p_user_id;
            return coalesce(v_new_balance, 0);
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

    return v_new_balance;
end;
$$;

-- Only the service role may execute the grant function.
revoke execute on function public.grant_credits(uuid, integer, text, text, text, text) from anon, authenticated;
revoke execute on function public.grant_credits(uuid, integer, text, text, text, text) from public;
grant execute on function public.grant_credits(uuid, integer, text, text, text, text) to service_role;
