-- Private saved document questions and revision-bound review results.
begin;
create table if not exists public.document_test_questions (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references public.documents(id) on delete cascade,
    question text not null check (length(btrim(question)) between 1 and 4000),
    expected text not null default '' check (length(expected) <= 2000),
    scope_type text not null check (scope_type in ('vehicle', 'category')),
    scope_id uuid not null,
    active boolean not null default true,
    version integer not null default 1 check (version > 0),
    created_by uuid not null references public.app_users(id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists document_test_questions_document on public.document_test_questions(document_id);

create table if not exists public.document_test_runs (
    id uuid primary key,
    document_id uuid not null references public.documents(id) on delete cascade,
    question_id uuid not null references public.document_test_questions(id) on delete cascade,
    source_revision uuid not null,
    question_version integer not null check (question_version > 0),
    question_snapshot jsonb not null check (jsonb_typeof(question_snapshot) = 'object'),
    context_label text not null,
    context_fingerprint text not null check (length(context_fingerprint) = 64),
    source_verified boolean not null,
    status text not null default 'running' check (status in ('running', 'completed', 'failed', 'stale')),
    result jsonb check (result is null or jsonb_typeof(result) = 'object'),
    error text,
    decision text not null default 'not_reviewed' check (decision in ('not_reviewed', 'passed', 'needs_fixing')),
    review_note text not null default '' check (length(review_note) <= 2000),
    review_version integer not null default 1 check (review_version > 0),
    reviewed_by uuid references public.app_users(id),
    reviewed_at timestamptz,
    started_by uuid not null references public.app_users(id),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists document_test_runs_recent on public.document_test_runs(document_id, started_at desc);

do $$
declare name text;
begin
    foreach name in array array['document_test_questions', 'document_test_runs'] loop
        execute format('alter table public.%I enable row level security', name);
        execute format('revoke all on public.%I from public, anon, authenticated, service_role', name);
        execute format('grant select, insert, update, delete on public.%I to service_role', name);
        execute format('drop trigger if exists content_updated_at on public.%I', name);
        execute format('create trigger content_updated_at before update on public.%I for each row execute function public.content_updated_at()', name);
    end loop;
end;
$$;
commit;
