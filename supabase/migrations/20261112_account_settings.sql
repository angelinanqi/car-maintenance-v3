begin;

-- Auth owns email uniqueness for linked accounts. Keep legacy records available
-- for manual linking without letting them block a confirmed Auth email change.
alter table public.app_users drop constraint app_users_email_key;
create unique index app_users_legacy_email on public.app_users(email)
    where auth_user_id is null;

update public.app_users as p
set email = lower(btrim(u.email))
from auth.users as u
where p.auth_user_id = u.id and btrim(u.email) <> '' and u.email_confirmed_at is not null
    and p.email is distinct from lower(btrim(u.email));

create function public.sync_account_email() returns trigger
    language plpgsql security definer set search_path = '' as $$
begin
    update public.app_users set email = lower(btrim(new.email))
    where auth_user_id = new.id and email is distinct from lower(btrim(new.email));
    return new;
end;
$$;
revoke all on function public.sync_account_email() from public, anon, authenticated;
create trigger sync_account_email after update of email on auth.users
    for each row when (btrim(new.email) <> '' and new.email_confirmed_at is not null
        and old.email is distinct from new.email)
    execute function public.sync_account_email();

-- Delete personal data with the Auth user, keeping shared work without attribution.
alter table public.app_users drop constraint app_users_auth_user_id_fkey,
    add foreign key (auth_user_id) references auth.users(id) on delete cascade;
alter table public.document_test_questions alter column created_by drop not null,
    drop constraint document_test_questions_created_by_fkey,
    add foreign key (created_by) references public.app_users(id) on delete set null;
alter table public.document_test_runs alter column started_by drop not null,
    drop constraint document_test_runs_started_by_fkey,
    drop constraint document_test_runs_reviewed_by_fkey,
    add foreign key (started_by) references public.app_users(id) on delete set null,
    add foreign key (reviewed_by) references public.app_users(id) on delete set null;
alter table public.website_import_jobs alter column requested_by drop not null,
    drop constraint website_import_jobs_requested_by_fkey,
    add foreign key (requested_by) references public.app_users(id) on delete set null;

-- Only FastAPI can call these functions. It supplies both IDs from verified claims.
create function public.account_sessions(p_user uuid, p_current uuid)
    returns table (id uuid, user_agent text, last_active_at timestamptz)
    language sql stable security definer set search_path = '' as $$
        select s.id, left(s.user_agent, 512),
            coalesce(s.refreshed_at at time zone 'UTC', s.created_at)
        from auth.sessions as s
        where s.user_id = p_user and (s.not_after is null or s.not_after > now())
            and exists (select 1 from auth.sessions where id = p_current and user_id = p_user)
        order by (s.id = p_current) desc, 3 desc, s.id;
$$;

create function public.revoke_account_session(p_user uuid, p_current uuid, p_target uuid)
    returns boolean language sql security definer set search_path = '' as $$
        with removed as (
            delete from auth.sessions as s
            where s.id = p_target and s.user_id = p_user and s.id <> p_current
                and exists (select 1 from auth.sessions where id = p_current and user_id = p_user)
            returning 1
        )
        select exists (select 1 from removed);
$$;
revoke all on function public.account_sessions(uuid, uuid),
    public.revoke_account_session(uuid, uuid, uuid) from public, anon, authenticated;
grant execute on function public.account_sessions(uuid, uuid),
    public.revoke_account_session(uuid, uuid, uuid) to service_role;

commit;
