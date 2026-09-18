-- R08 contract, disposable local PostgreSQL only. Requires 0001-0003
-- and fixture auth.users email user-a@test.local from local_role_tests.sql.
\set ON_ERROR_STOP on
-- The disposable fixture role in local_role_tests.sql lacks Supabase's
-- built-in BYPASSRLS flag; give it the same behavior for this local test.
alter role service_role bypassrls;
begin;
do $$
declare
    v_user uuid;
    v_claim uuid;
    v_visible integer;
    v_code text := repeat('a', 64);
    v_state text := repeat('b', 64);
    v_token text := repeat('c', 64);
begin
    select id into v_user from auth.users where email = 'user-a@test.local';
    if v_user is null then raise exception 'fixture user missing'; end if;
    perform set_config('role', 'service_role', true);
    insert into public.cloud_device_links(code_hash,state_hash,user_id,expires_at)
    values(v_code,v_state,v_user,now() + interval '5 minutes');
    v_claim := public.redeem_cloud_device_link(v_code,repeat('d',64),v_token);
    if v_claim is not null then raise exception 'wrong state accepted'; end if;
    v_claim := public.redeem_cloud_device_link(v_code,v_state,v_token);
    if v_claim is distinct from v_user then raise exception 'valid link rejected'; end if;
    v_claim := public.redeem_cloud_device_link(v_code,v_state,repeat('e',64));
    if v_claim is not null then raise exception 'replayed link accepted'; end if;
    select count(*) into v_visible from public.cloud_device_sessions
     where token_hash = v_token and user_id = v_user;
    if v_visible <> 1 then raise exception 'session not created atomically'; end if;
    insert into public.cloud_device_links(code_hash,state_hash,user_id,expires_at)
    values(repeat('f',64),v_state,v_user,now() - interval '1 second');
    if public.redeem_cloud_device_link(repeat('f',64),v_state,repeat('1',64)) is not null then
        raise exception 'expired link accepted';
    end if;
    perform set_config('role', 'authenticated', true);
    perform set_config('request.jwt.claim.sub', v_user::text, true);
    begin
        perform public.redeem_cloud_device_link(v_code,v_state,repeat('2',64));
        raise exception 'client executed service-only RPC';
    exception when insufficient_privilege then null;
    end;
    begin
        select count(*) into v_visible from public.cloud_device_sessions;
        if v_visible <> 0 then raise exception 'client read device secrets'; end if;
    exception when insufficient_privilege then null;
    end;
end $$;
rollback;
