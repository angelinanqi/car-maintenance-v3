-- Additive migration for existing installations. No extraction or RAG changes.
begin;
create table public.maintenance_assistance (
    id uuid primary key,
    document_id uuid not null references public.documents(id) on delete cascade,
    source_revision uuid not null,
    catalogue jsonb not null check (jsonb_typeof(catalogue) = 'object'),
    selections jsonb not null default '[]' check (jsonb_typeof(selections) = 'array'),
    suggestions jsonb not null default '[]' check (jsonb_typeof(suggestions) = 'array'),
    bookmarks jsonb not null default '[]' check (jsonb_typeof(bookmarks) = 'array'),
    version integer not null default 1 check (version > 0),
    reviewed_by uuid references public.app_users(id) on delete set null,
    reviewed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(document_id, source_revision)
);
alter table public.maintenance_assistance enable row level security;
revoke all on public.maintenance_assistance from public, anon, authenticated, service_role;
grant select, insert, update, delete on public.maintenance_assistance to service_role;
create trigger content_updated_at before update on public.maintenance_assistance
    for each row execute function public.content_updated_at();
commit;
