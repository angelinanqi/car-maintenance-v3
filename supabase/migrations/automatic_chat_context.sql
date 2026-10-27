-- Preserve existing scoped sessions; new mobile chats use automatic context.
begin;
alter table public.chat_sessions
    add column if not exists automatic boolean not null default false;

-- The original schema used an unnamed scope check. Find that exact check so
-- this migration also works where PostgreSQL assigned a different name.
do $$
declare item record;
begin
    for item in select conname from pg_constraint
        where conrelid = 'public.chat_sessions'::regclass and contype = 'c'
          and pg_get_constraintdef(oid) like '%num_nonnulls(vehicle_id, category_id)%'
    loop
        execute format('alter table public.chat_sessions drop constraint %I', item.conname);
    end loop;
end;
$$;
alter table public.chat_sessions add constraint chat_sessions_context_check check (
    (automatic and category_id is null and ((vehicle_id is null) = (user_vehicle_id is null))) or
    (not automatic and num_nonnulls(vehicle_id, category_id) = 1)
);

create or replace function public.chat_scope_immutable() returns trigger
language plpgsql set search_path = '' as $$
begin
    if new.automatic is distinct from old.automatic
        or new.vehicle_id is distinct from old.vehicle_id
        or new.category_id is distinct from old.category_id
        or new.user_id is distinct from old.user_id
        or new.user_vehicle_id is distinct from old.user_vehicle_id then
        raise exception 'Start a new chat to change owner or knowledge scope';
    end if;
    return new;
end;
$$;

-- Upgrade only the original presets; preserve administrator customisation.
update public.chat_settings set starter_questions = array[
    'How do I check tyre pressure?',
    'What should I check before a long drive?',
    'How do I check my engine oil?'
] where id = 'default' and starter_questions = array[
    'Understanding my service records',
    'Finding the correct owner manual',
    'Understanding tyre pressure labels'
];
commit;
