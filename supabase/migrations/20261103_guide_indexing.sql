-- Durable handoffs for guides using the existing RAG index worker.
begin;
create table if not exists public.guide_indexes (
    id uuid primary key references public.guides(id) on delete cascade,
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
alter table public.guide_indexes enable row level security;
revoke all on public.guide_indexes from public, anon, authenticated;
grant select, insert, update, delete on public.guide_indexes to service_role;
notify pgrst, 'reload schema';
commit;
