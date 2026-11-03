-- Emergency media is stored inside the existing steps JSONB value.
begin;

alter table public.guides
    add column if not exists media jsonb not null default '[]'::jsonb
    check (jsonb_typeof(media) = 'array');

create table if not exists public.emergency_images (
    id uuid primary key default gen_random_uuid(),
    playbook_id uuid not null references public.emergency_playbooks(id) on delete cascade,
    storage_path text not null unique check (length(storage_path) > 0),
    created_at timestamptz not null default now()
);
create index if not exists emergency_images_playbook on public.emergency_images(playbook_id);
alter table public.emergency_images enable row level security;
revoke all on public.emergency_images from public, anon, authenticated, service_role;
grant select, insert, update, delete on public.emergency_images to service_role;

notify pgrst, 'reload schema';
commit;
