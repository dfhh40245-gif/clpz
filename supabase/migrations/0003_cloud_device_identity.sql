-- R08: browser-verified Supabase identity -> Windows device handoff.
-- Apply after 0002. Only the website service role may write or read these
-- bearer-secret hashes; clients have no table policy or RPC execution right.
create table if not exists public.cloud_device_links (
    code_hash text primary key check (code_hash ~ '^[a-f0-9]{64}$'),
    state_hash text not null check (state_hash ~ '^[a-f0-9]{64}$'),
    user_id uuid not null references auth.users(id) on delete cascade,
    expires_at timestamptz not null,
    used_at timestamptz,
    created_at timestamptz not null default now()
);
create index if not exists cloud_device_links_expiry on public.cloud_device_links(expires_at);
alter table public.cloud_device_links enable row level security;
revoke all on public.cloud_device_links from public, anon, authenticated;
grant select, insert, update, delete on public.cloud_device_links to service_role;

create table if not exists public.cloud_device_sessions (
    token_hash text primary key check (token_hash ~ '^[a-f0-9]{64}$'),
    user_id uuid not null references auth.users(id) on delete cascade,
    expires_at timestamptz not null,
    revoked_at timestamptz,
    created_at timestamptz not null default now()
);
create index if not exists cloud_device_sessions_user on public.cloud_device_sessions(user_id);
alter table public.cloud_device_sessions enable row level security;
revoke all on public.cloud_device_sessions from public, anon, authenticated;
grant select, insert, update, delete on public.cloud_device_sessions to service_role;

-- One transaction claims the code and creates its device credential. A wrong
-- state, expired code, or concurrent replay updates zero rows.
create or replace function public.redeem_cloud_device_link(
    p_code_hash text, p_state_hash text, p_token_hash text
) returns uuid
language plpgsql security definer set search_path = ''
as $$
declare v_user_id uuid;
begin
    if p_code_hash !~ '^[a-f0-9]{64}$' or
       p_state_hash !~ '^[a-f0-9]{64}$' or
       p_token_hash !~ '^[a-f0-9]{64}$' then
        return null;
    end if;
    update public.cloud_device_links
       set used_at = now()
     where code_hash = p_code_hash and state_hash = p_state_hash
       and used_at is null and expires_at > now()
    returning user_id into v_user_id;
    if v_user_id is null then return null; end if;
    insert into public.cloud_device_sessions(token_hash, user_id, expires_at)
    values (p_token_hash, v_user_id, now() + interval '30 days');
    return v_user_id;
end $$;
revoke execute on function public.redeem_cloud_device_link(text,text,text)
    from public, anon, authenticated;
grant execute on function public.redeem_cloud_device_link(text,text,text)
    to service_role;
