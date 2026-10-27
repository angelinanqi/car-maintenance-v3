-- Additive admin-only clarification and saved-work context. Keeps existing data.
begin;
alter table public.manufacturer_schedules
    add column admin_note text not null default '' check (length(admin_note) <= 4000),
    add column work_context jsonb not null default '{}' check (jsonb_typeof(work_context) = 'object');

create table public.admin_review_questions (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references public.documents(id) on delete restrict,
    source_revision uuid not null,
    vehicle_id uuid references public.knowledge_vehicles(id) on delete restrict,
    schedule_id uuid references public.manufacturer_schedules(id) on delete set null,
    item_id uuid references public.maintenance_items(id) on delete restrict,
    source_page integer check (source_page > 0),
    title text not null check (length(trim(title)) between 1 and 300),
    question text not null check (length(trim(question)) between 1 and 4000),
    excerpt text not null default '' check (length(excerpt) <= 2000),
    status text not null default 'open' check (status in ('open', 'resolved')),
    resolution text not null default '' check (length(resolution) <= 4000),
    version integer not null default 1 check (version > 0),
    created_by uuid references public.app_users(id) on delete set null,
    resolved_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (schedule_id is null or vehicle_id is not null),
    check (item_id is null or vehicle_id is not null),
    check ((status = 'resolved') = (resolved_at is not null)),
    check (status <> 'resolved' or length(trim(resolution)) > 0)
);
create index admin_questions_document on public.admin_review_questions(document_id, status);
create index admin_questions_vehicle on public.admin_review_questions(vehicle_id, status);
alter table public.admin_review_questions enable row level security;
revoke all on public.admin_review_questions from public, anon, authenticated, service_role;
grant select, insert, update, delete on public.admin_review_questions to service_role;
create trigger content_updated_at before update on public.admin_review_questions
    for each row execute function public.content_updated_at();
commit;
