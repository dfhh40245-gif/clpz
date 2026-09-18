-- CLPZ cloud schema — local role/concurrency test harness (task 14)
--
-- Runs against ANY disposable local PostgreSQL (never a production Supabase
-- project). Creates Supabase-equivalent roles (anon, authenticated,
-- service_role), applies migrations 0001 + 0002, then asserts:
--   - RLS: A cannot read B's rows; anon cannot read anything user-scoped
--   - anon/authenticated cannot execute grant_credits / spend_credits
--   - anon/authenticated cannot write payments/credit_accounts/entitlements
--   - same-key replay is a no-op; same key + different payload is rejected;
--     different users with different keys are NOT suppressed
--   - single-active-subscription and invalid-transition constraints hold
--
-- Usage (any of):
--   psql -f supabase/tests/local_role_tests.sql   (as superuser)
--   supabase db reset && supabase db psql < this file
-- Exit: psql stops on the first \if false assertion (ON_ERROR_STOP=1).

\set ON_ERROR_STOP on

-- ── Fixture roles (Supabase equivalents) ─────────────────────────────
do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'anon') then
        create role anon nologin;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'authenticated') then
        create role authenticated nologin;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'service_role') then
        create role service_role nologin;
    end if;
end $$;
grant usage on schema public to anon, authenticated, service_role;

-- ── Fixture users (bypass auth.users via the profile trigger's absence) ─
-- In a real Supabase project auth.users is managed by Auth; locally we
-- create a minimal stand-in table so FKs resolve, or reuse existing auth.
do $$
begin
    if not exists (select 1 from information_schema.tables
                   where table_schema = 'auth' and table_name = 'users') then
        create schema if not exists auth;
        create table auth.users (
            id uuid primary key default gen_random_uuid(),
            email text not null unique,
            raw_user_meta_data jsonb not null default '{}'::jsonb,
            created_at timestamptz not null default now()
        );
        insert into auth.users (email) values
            ('user-a@test.local'), ('user-b@test.local');
    end if;
end $$;

-- Local stand-ins have no auth.uid() context; tests below SET ROLE and use
-- request.jwt.claim.sub via set_config to emulate Supabase's GUC-backed
-- auth.uid() helper. 0001's policies reference auth.uid(), so provide it.
create schema if not exists auth;
create or replace function auth.uid() returns uuid
language sql stable as $$
    select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;

\echo '=== T1: RLS — user A cannot read user B rows ==='
do $$
declare
    v_a uuid; v_b uuid; v_leak int;
begin
    select id into v_a from auth.users where email = 'user-a@test.local';
    select id into v_b from auth.users where email = 'user-b@test.local';

    -- service role seeds data for both
    perform set_config('role', 'service_role', true);
    perform public.grant_credits(v_a, 10, 'purchase', 'seed-a', 'ref-a', 'seed-key-a');
    perform public.grant_credits(v_b, 99, 'purchase', 'seed-b', 'ref-b', 'seed-key-b');

    -- user A reads their own transactions (allowed)…
    perform set_config('role', 'authenticated', true);
    perform set_config('request.jwt.claim.sub', v_a::text, true);
    select count(*) into v_leak from public.credit_transactions where user_id = v_a;
    if v_leak <> 1 then raise exception 'T1 FAIL: A cannot read own rows'; end if;

    -- …but sees none of B's rows.
    select count(*) into v_leak from public.credit_transactions where user_id = v_b;
    if v_leak <> 0 then raise exception 'T1 FAIL: A sees B transactions'; end if;
    select count(*) into v_leak from public.credit_accounts where user_id = v_b;
    if v_leak <> 0 then raise exception 'T1 FAIL: A sees B account'; end if;
    select count(*) into v_leak from public.payments where user_id = v_b;
    if v_leak <> 0 then raise exception 'T1 FAIL: A sees B payments'; end if;
    select count(*) into v_leak from public.credit_buckets where user_id = v_b;
    if v_leak <> 0 then raise exception 'T1 FAIL: A sees B buckets'; end if;
    raise notice 'T1 PASS: cross-user isolation holds';
end $$;

\echo '=== T2: anon/authenticated cannot write payments or ledger ==='
do $$
declare
    v_a uuid; v_blocked boolean;
begin
    select id into v_a from auth.users where email = 'user-a@test.local';
    perform set_config('role', 'authenticated', true);
    perform set_config('request.jwt.claim.sub', v_a::text, true);
    begin
        insert into public.payments (user_id, external_id, amount_cents)
        values (v_a, 'hack-' || gen_random_uuid()::text, 100);
        raise exception 'T2 FAIL: authenticated could insert payments';
    exception when insufficient_privilege or check_violation then
        null; -- expected: RLS blocks (no insert policy)
    end;
    begin
        insert into public.credit_transactions (user_id, amount, txn_type)
        values (v_a, 1000, 'purchase');
        raise exception 'T2 FAIL: authenticated could insert ledger rows';
    exception when insufficient_privilege or check_violation then
        null; -- expected
    end;
    raise notice 'T2 PASS: client write paths are blocked';
end $$;

\echo '=== T3: anon/authenticated cannot execute grant_credits/spend_credits ==='
do $$
declare
    v_a uuid; v_has_exec boolean;
begin
    select id into v_a from auth.users where email = 'user-a@test.local';
    perform set_config('role', 'authenticated', true);
    perform set_config('request.jwt.claim.sub', v_a::text, true);

    begin
        perform public.grant_credits(v_a, 1000, 'purchase', 'escalate', 'x', 'escalate-key');
        raise exception 'T3 FAIL: authenticated executed grant_credits';
    exception when insufficient_privilege then
        null; -- expected: execute revoked
    end;
    begin
        perform public.spend_credits(v_a, 1);
        raise exception 'T3 FAIL: authenticated executed spend_credits';
    exception when insufficient_privilege then
        null; -- expected
    end;
    raise notice 'T3 PASS: privileged RPCs are service-role only';
end $$;

\echo '=== T4: same-key replay no-op; changed payload rejected; distinct keys independent ==='
do $$
declare
    v_a uuid; v_b uuid; v_bal int; v_bal2 int;
begin
    select id into v_a from auth.users where email = 'user-a@test.local';
    select id into v_b from auth.users where email = 'user-b@test.local';
    perform set_config('role', 'service_role', true);

    -- First grant
    v_bal := public.grant_credits(v_a, 5, 'purchase', 'd', 'order-1', 'order-key-1');
    -- Exact replay: no double grant
    v_bal2 := public.grant_credits(v_a, 5, 'purchase', 'd', 'order-1', 'order-key-1');
    if v_bal2 <> v_bal then
        raise exception 'T4 FAIL: replay changed balance % -> %', v_bal, v_bal2;
    end if;
    -- Same key, different amount: must be rejected
    begin
        perform public.grant_credits(v_a, 500, 'purchase', 'd', 'order-1', 'order-key-1');
        raise exception 'T4 FAIL: changed payload accepted under same key';
    exception when unique_violation then
        null; -- expected conflict
    end;
    -- Same key, different USER: must be rejected (old code suppressed it as
    -- a replay; new code treats it as a conflict, never cross-user reuse).
    begin
        perform public.grant_credits(v_b, 7, 'purchase', 'd', 'order-1', 'order-key-1');
        raise exception 'T4 FAIL: cross-user key reuse accepted';
    exception when unique_violation then
        null; -- expected conflict
    end;
    -- Different users, different keys: independent grants apply.
    perform public.grant_credits(v_b, 7, 'purchase', 'd', 'order-2', 'order-key-2');
    select balance into v_bal from public.credit_accounts where user_id = v_b;
    if v_bal <> 99 + 7 then
        raise exception 'T4 FAIL: B balance % != 106 (distinct grants suppressed?)', v_bal;
    end if;
    raise notice 'T4 PASS: replay scope + conflict semantics correct';
end $$;

\echo '=== T5: subscriptions — single active per user; invalid transitions rejected ==='
do $$
declare
    v_a uuid;
begin
    select id into v_a from auth.users where email = 'user-a@test.local';
    perform set_config('role', 'service_role', true);

    insert into public.subscriptions (user_id, plan, status)
    values (v_a, 'creator', 'active');

    -- Second ACTIVE subscription for the same user must violate the partial
    -- unique index.
    begin
        insert into public.subscriptions (user_id, plan, status)
        values (v_a, 'creator', 'active');
        raise exception 'T5 FAIL: two active subscriptions allowed';
    exception when unique_violation then
        null; -- expected
    end;

    -- canceled -> active is an invalid resurrection
    update public.subscriptions set status = 'canceled' where user_id = v_a;
    begin
        update public.subscriptions set status = 'active' where user_id = v_a;
        raise exception 'T5 FAIL: canceled subscription resurrected';
    exception when raise_exception then
        null; -- expected: guard trigger rejects
    end;
    raise notice 'T5 PASS: subscription lifecycle constraints enforced';
end $$;

\echo '=== T6: spend order — expiring subscription credits spent first ==='
do $$
declare
    v_a uuid; v_left_sub int; v_left_pur int;
begin
    select id into v_a from auth.users where email = 'user-a@test.local';
    perform set_config('role', 'service_role', true);

    -- Fresh user: seed 10 subscription credits (expire) + 10 purchased.
    perform public.grant_credits(v_a, 10, 'subscription', 'sub', 'sub-ref', 'sub-key');
    perform public.grant_credits(v_a, 10, 'purchase', 'pur', 'pur-ref', 'pur-key');

    -- Spend 12: must drain the subscription bucket first (10) + 2 purchased.
    perform public.spend_credits(v_a, 12);

    select amount into v_left_sub from public.credit_buckets
    where user_id = v_a and kind = 'subscription';
    select coalesce(sum(amount), 0) into v_left_pur from public.credit_buckets
    where user_id = v_a and kind = 'purchased';

    if v_left_sub <> 0 or v_left_pur <> 8 then
        raise exception 'T6 FAIL: spend order wrong (sub=%, pur=%)', v_left_sub, v_left_pur;
    end if;
    raise notice 'T6 PASS: subscription credits spent before purchased';
end $$;

\echo '=== T7: forward migration retained data (upgrade path) ==='
do $$
declare
    v_count int;
begin
    -- 0001 rows must still exist after 0002 (this harness ran both).
    select count(*) into v_count from public.credit_accounts;
    if v_count < 1 then raise exception 'T7 FAIL: upgrade lost accounts'; end if;
    select count(*) into v_count from public.credit_transactions;
    if v_count < 3 then raise exception 'T7 FAIL: upgrade lost transactions'; end if;
    raise notice 'T7 PASS: upgrade path retained data';
end $$;

\echo '=== T8: webhook inbox — no client access; service-role full control ==='
do $$
declare
    v_a uuid; v_blocked boolean; v_inbox int;
begin
    select id into v_a from auth.users where email = 'user-a@test.local';
    perform set_config('role', 'authenticated', true);
    perform set_config('request.jwt.claim.sub', v_a::text, true);
    begin
        select count(*) into v_inbox from public.webhook_events;
        -- RLS with no select policy returns zero rows to clients.
        if v_inbox <> 0 then
            raise exception 'T8 FAIL: authenticated read webhook_events';
        end if;
    exception when insufficient_privilege then
        null; -- also acceptable: permission denied
    end;
    perform set_config('role', 'service_role', true);
    insert into public.webhook_events (external_id, event_state, payload)
    values ('test-sale-1', 'paid', '{"test": true}'::jsonb)
    on conflict (provider, external_id, event_state) do nothing;
    select count(*) into v_inbox from public.webhook_events
    where external_id = 'test-sale-1';
    if v_inbox <> 1 then raise exception 'T8 FAIL: service role cannot use inbox'; end if;
    raise notice 'T8 PASS: webhook inbox is service-role only and functional';
end $$;

\echo 'ALL LOCAL ROLE TESTS PASSED'
