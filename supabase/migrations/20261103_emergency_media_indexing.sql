begin;
create table if not exists public.emergency_media_assets (
    id uuid primary key default gen_random_uuid(),
    playbook_id uuid not null references public.emergency_playbooks(id) on delete cascade,
    step_id uuid not null,
    storage_path text not null unique,
    kind text not null check (kind in ('image', 'video')),
    mime_type text not null,
    size_bytes bigint not null check (size_bytes > 0),
    sha256 text not null check (sha256 ~ '^[a-f0-9]{64}$'),
    created_at timestamptz not null default now()
);
create index if not exists emergency_media_assets_playbook on public.emergency_media_assets(playbook_id);
alter table public.emergency_media_assets enable row level security;
revoke all on public.emergency_media_assets from public, anon, authenticated;
grant select, insert, update, delete on public.emergency_media_assets to service_role;
create table if not exists public.emergency_indexes (
    id uuid primary key references public.emergency_playbooks(id) on delete cascade,
    content_hash uuid not null,
    source_revision uuid not null,
    status text not null default 'awaiting_index' check (status in ('awaiting_index', 'processed', 'failed')),
    chunk_count integer not null default 0 check (chunk_count >= 0),
    extraction_storage_path text,
    media jsonb not null default '[]'::jsonb,
    videos jsonb not null default '[]'::jsonb,
    warnings jsonb not null default '[]'::jsonb,
    error text,
    created_at timestamptz not null default now(),
    indexed_at timestamptz
);
alter table public.emergency_indexes enable row level security;
revoke all on public.emergency_indexes from public, anon, authenticated;
grant select, insert, update, delete on public.emergency_indexes to service_role;
notify pgrst, 'reload schema';
commit;
