-- Private checklists and resume position for each admin and source revision.
begin;
create table if not exists public.document_review_progress (
    id uuid primary key,
    document_id uuid not null references public.documents(id) on delete cascade,
    source_revision uuid not null,
    reviewer_id uuid not null references public.app_users(id) on delete cascade,
    decisions jsonb not null default '{}' check (jsonb_typeof(decisions) = 'object'),
    current_element_id text check (length(current_element_id) <= 100),
    source_page integer check (source_page between 1 and 100000),
    version integer not null default 1 check (version > 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(document_id, source_revision, reviewer_id)
);
alter table public.document_review_progress enable row level security;
revoke all on public.document_review_progress from public, anon, authenticated, service_role;
grant select, insert, update, delete on public.document_review_progress to service_role;
drop trigger if exists content_updated_at on public.document_review_progress;
create trigger content_updated_at before update on public.document_review_progress
    for each row execute function public.content_updated_at();
commit;
