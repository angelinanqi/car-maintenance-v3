-- Complete fresh-install application schema, consolidated 2 November 2026.
-- Run the ENTIRE file ONCE in a fresh Supabase project's SQL Editor.
-- Not an upgrade/reset script: existing application objects cause failure and rollback.
-- Never run this against a populated installation. No live data is included.
-- Supabase must already supply public, auth.users, storage.buckets and the
-- anon/authenticated/service_role roles. Managed infrastructure is not recreated.
-- gen_random_uuid() is built into supported PostgreSQL versions (13+);
-- no additional extensions, custom enums, views or database roles are required.
-- The retained column-specific ON DELETE SET NULL syntax requires PostgreSQL 15+.
-- Historical sources and upgrade guidance: README.md in this directory.

begin;

-- 1. Managed schemas and built-in UUID generation: prerequisites above.

-- 2. Custom types and enums: none (existing text CHECK constraints retained).

-- 3. Tables, constraints and column comments.

-- Supabase owns credentials; business-data ownership uses stable app_users IDs.
create table public.app_users (
    id uuid primary key default gen_random_uuid(),
    email text not null unique check (email = lower(trim(email)) and length(email) > 0),
    display_name text not null check (length(trim(display_name)) > 0),
    password_hash text check (length(password_hash) > 0),
    auth_user_id uuid unique references auth.users(id) on delete restrict,
    mfa_required boolean not null default false,
    role text not null default 'user' check (role in ('user', 'admin')),
    active_vehicle_id text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.app_sessions (
    -- SHA-256 digest; never a raw session token.
    id text primary key check (id ~ '^[0-9a-f]{64}$'),
    user_id uuid not null references public.app_users(id) on delete cascade,
    csrf_token text not null check (length(csrf_token) > 0),
    created_at timestamptz not null default now(),
    expires_at timestamptz not null check (expires_at > created_at)
);

-- Shared vehicle catalogue and reusable maintenance items.
create table public.vehicle_manufacturers (
    id uuid primary key default gen_random_uuid(),
    name text not null check (length(trim(name)) > 0),
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.vehicle_models (
    id uuid primary key default gen_random_uuid(),
    manufacturer_id uuid not null references public.vehicle_manufacturers(id) on delete restrict,
    name text not null check (length(trim(name)) > 0),
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.knowledge_vehicles (
    id uuid primary key default gen_random_uuid(),
    code text not null unique check (code ~ '^[a-z0-9]+(-[a-z0-9]+)*$' and code <> 'general'),
    name text not null check (length(trim(name)) > 0),
    -- Knowledge-only scopes can lack a model; mobile registration requires one.
    model_id uuid references public.vehicle_models(id) on delete restrict,
    year text not null default '',
    engine text not null default '',
    variant text not null default '',
    powertrain text not null default 'petrol' check (powertrain in ('petrol', 'diesel')),
    active boolean not null default true,
    published boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (model_id is null or (year ~ '^[0-9]{4}$' and year between '1900' and '2100'))
);

create table public.maintenance_items (
    id uuid primary key default gen_random_uuid(),
    title text not null check (length(trim(title)) > 0),
    category text not null default '',
    description text not null default '',
    action text not null check (action in ('inspect', 'replace', 'service')),
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Private source files, extraction revisions and confirmed remote indexing.
-- Applicability lives in document_vehicles/document_categories, not a model label.
create table public.documents (
    id uuid primary key default gen_random_uuid(),
    name text not null check (length(trim(name)) > 0),
    tags text[] not null default '{}',
    document_type text not null default 'other_reference'
        check (document_type in ('owners_manual', 'maintenance_booklet', 'service_manual', 'other_reference')),
    original_filename text not null check (length(trim(original_filename)) > 0),
    source_type text not null check (source_type in ('pdf', 'md')),
    storage_path text not null unique check (length(storage_path) > 0),
    size_bytes bigint not null check (size_bytes > 0),
    status text not null default 'uploaded'
        check (status in ('uploaded', 'processing', 'awaiting_confirmation', 'awaiting_index', 'processed', 'failed')),
    error text,
    source_revision uuid not null default gen_random_uuid(),
    processing_started_at timestamptz,
    processed_at timestamptz,
    extraction_storage_path text,
    extraction_completed_at timestamptz,
    indexed_revision uuid,
    indexed_at timestamptz,
    chunk_count integer not null default 0 check (chunk_count >= 0),
    source_fidelity_verified boolean not null default false,
    -- Source qualifiers are evidence metadata, not catalogue identity copies.
    year text not null default '',
    engine text not null default '',
    variant text not null default '',
    vehicle_independent boolean not null default false,
    published boolean not null default false,
    mobile_visible boolean not null default false,
    replacement_for_id uuid references public.documents(id) on delete restrict,
    superseded_by_id uuid references public.documents(id) on delete restrict,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (replacement_for_id is distinct from id),
    check (superseded_by_id is distinct from id),
    constraint documents_index_confirmation check (
        (indexed_revision is null and indexed_at is null and chunk_count = 0 and status <> 'processed')
        or (indexed_revision is not null and indexed_revision = source_revision
            and indexed_at is not null and chunk_count > 0 and status = 'processed')
    ),
    constraint publication_requires_index check (
        not published or (status = 'processed' and indexed_revision is not null
            and indexed_revision = source_revision and chunk_count > 0 and superseded_by_id is null)
    ),
    check (not mobile_visible or published),
    check (not source_fidelity_verified or extraction_storage_path is not null)
);

comment on column public.documents.source_revision is 'Rotated for each source replacement or extraction attempt.';

comment on column public.documents.indexed_revision is 'Set only after the private RAG service confirms this source revision.';

-- Learning content. Small ordered link lists and rich rules are edited atomically.
-- FastAPI validates IDs inside arrays/JSON and blocks referenced source deletion.
create table public.guide_categories (
    id uuid primary key default gen_random_uuid(),
    name text not null check (length(trim(name)) > 0),
    description text not null default '',
    display_order integer not null default 0 check (display_order >= 0),
    published boolean not null default true,
    knowledge_published boolean not null default false,
    archived boolean not null default false,
    constraint archived_categories_hidden check (not archived or (not published and not knowledge_published)),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.guides (
    id uuid primary key default gen_random_uuid(),
    title text not null check (length(trim(title)) > 0),
    description text not null default '',
    display_order integer not null default 0 check (display_order >= 0),
    category_id uuid references public.guide_categories(id) on delete restrict,
    content text not null default '<p></p>',
    reading_minutes integer check (reading_minutes > 0),
    related_lesson_ids uuid[] not null default '{}',
    maintenance_item_ids uuid[] not null default '{}',
    status text not null default 'draft' check (status in ('draft', 'published')),
    published_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    beginner_friendly boolean not null default false,
    featured_in_companion boolean not null default false,
    learning_outcomes text[] not null default '{}',
    exploration jsonb,
    media jsonb not null default '[]'::jsonb check (jsonb_typeof(media) = 'array'),
    check ((status = 'published') = (published_at is not null)),
    check (not (id = any(related_lesson_ids))),
    check (array_position(related_lesson_ids, null) is null),
    check (array_position(maintenance_item_ids, null) is null)
);

create table public.guide_indexes (
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

create table public.guide_images (
    id uuid primary key default gen_random_uuid(),
    guide_id uuid not null references public.guides(id) on delete cascade,
    storage_path text not null unique check (length(storage_path) > 0),
    created_at timestamptz not null default now()
);

-- These junctions reflect real many-to-many applicability. Surrogate IDs support
-- generic CRUD/pagination; pair uniqueness prevents duplicate assignments.
create table public.document_vehicles (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references public.documents(id) on delete cascade,
    vehicle_id uuid not null references public.knowledge_vehicles(id) on delete restrict,
    created_at timestamptz not null default now(),
    unique(document_id, vehicle_id)
);

create table public.document_categories (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references public.documents(id) on delete cascade,
    category_id uuid not null references public.guide_categories(id) on delete cascade,
    created_at timestamptz not null default now(),
    unique(document_id, category_id)
);

create table public.manufacturer_schedules (
    id uuid primary key default gen_random_uuid(),
    vehicle_id uuid not null references public.knowledge_vehicles(id) on delete restrict,
    revision integer not null default 1 check (revision > 0),
    status text not null default 'draft' check (status in ('draft', 'published', 'superseded')),
    entries jsonb not null default '[]' check (jsonb_typeof(entries) = 'array'),
    admin_note text not null default '' check (length(admin_note) <= 4000),
    work_context jsonb not null default '{}' check (jsonb_typeof(work_context) = 'object'),
    verified_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(vehicle_id, revision),
    check (status <> 'published' or (verified_at is not null and jsonb_array_length(entries) > 0))
);

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

-- Saved channel sources and resumable ingestion requests.
create table public.youtube_channels (
    id uuid primary key default gen_random_uuid(),
    url text not null unique check (length(url) between 1 and 500),
    channel_id text check (channel_id ~ '^UC[A-Za-z0-9_-]{22}$'),
    channel_title text not null default '',
    status text not null default 'queued' check (status in ('queued', 'syncing', 'ready', 'failed')),
    sync_id uuid not null default gen_random_uuid(),
    summary jsonb not null default '{}'::jsonb check (jsonb_typeof(summary) = 'object'),
    error text,
    last_synced_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.knowledge_videos (
    id uuid primary key default gen_random_uuid(),
    video_id text not null check (video_id ~ '^[A-Za-z0-9_-]{11}$'),
    vehicle_id uuid references public.knowledge_vehicles(id) on delete restrict,
    category_id uuid references public.guide_categories(id) on delete cascade,
    created_at timestamptz not null default now(),
    check (num_nonnulls(vehicle_id, category_id) = 1)
);

-- Reviewed emergency protocols and shared contacts.
create table public.emergency_playbooks (
    id uuid primary key default gen_random_uuid(),
    title text not null check (length(trim(title)) > 0),
    category text not null default '',
    description text not null default '',
    safety_warnings text not null default '',
    display_order integer not null default 0 check (display_order >= 0),
    steps jsonb not null default '[]' check (jsonb_typeof(steps) = 'array'),
    scenario_key text unique check (scenario_key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    source text not null default '',
    status text not null default 'draft' check (status in ('draft', 'published')),
    reviewed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint emergency_publication_complete check (
        status <> 'published' or (scenario_key is not null and length(trim(source)) > 0
            and reviewed_at is not null and jsonb_array_length(steps) > 0)
    )
);

create table public.emergency_images (
    id uuid primary key default gen_random_uuid(),
    playbook_id uuid not null references public.emergency_playbooks(id) on delete cascade,
    storage_path text not null unique check (length(storage_path) > 0),
    created_at timestamptz not null default now()
);
create index emergency_images_playbook on public.emergency_images(playbook_id);

create table public.emergency_contacts (
    id uuid primary key default gen_random_uuid(),
    name text not null check (length(trim(name)) > 0),
    description text not null default '',
    display_order integer not null default 0 check (display_order >= 0),
    phone text not null check (phone ~ '^[+0-9[:space:]().-]+$' and length(regexp_replace(phone, '[^0-9]', '', 'g')) >= 3),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Client-generated personal IDs are scoped to the authenticated account.
create table public.user_vehicles (
    user_id uuid not null references public.app_users(id) on delete cascade,
    id text not null check (length(id) between 1 and 200 and id ~ '^[A-Za-z0-9_:-]+$'),
    catalogue_id uuid not null references public.knowledge_vehicles(id) on delete restrict,
    name text not null default '',
    plate_number text not null default '',
    mileage integer not null check (mileage >= 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key(user_id, id)
);

-- The account's active vehicle is the only circular FK dependency.
alter table public.app_users add constraint user_active_vehicle_fk
    foreign key(id, active_vehicle_id) references public.user_vehicles(user_id, id)
    on delete set null(active_vehicle_id);

create table public.user_tasks (
    user_id uuid not null,
    id text not null check (length(id) between 1 and 200 and id ~ '^[A-Za-z0-9_:-]+$'),
    vehicle_id text not null,
    item_id uuid references public.maintenance_items(id) on delete restrict,
    -- Only custom tasks store text/action. Standard tasks use maintenance_items.
    title text check (length(trim(title)) > 0),
    category text,
    action text check (action in ('inspect', 'replace', 'service')),
    schedule_source text not null check (schedule_source in ('none', 'custom', 'manufacturer')),
    custom_rule jsonb check (custom_rule is null or jsonb_typeof(custom_rule) = 'object'),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key(user_id, id),
    unique(user_id, vehicle_id, id),
    foreign key(user_id, vehicle_id) references public.user_vehicles(user_id, id) on delete cascade,
    check ((item_id is not null and title is null and category is null and action is null)
        or (item_id is null and title is not null and category is not null and action is not null)),
    check (schedule_source <> 'custom' or custom_rule is not null),
    check (schedule_source <> 'manufacturer' or item_id is not null)
);

create table public.service_records (
    user_id uuid not null,
    id text not null check (length(id) between 1 and 200 and id ~ '^[A-Za-z0-9_:-]+$'),
    vehicle_id text not null,
    task_id text,
    -- Historical text survives task deletion and catalogue edits.
    title text not null check (length(trim(title)) > 0),
    category text not null default '',
    mileage integer not null check (mileage >= 0),
    performed_at date not null,
    notes text not null default '',
    workshop_name text not null default '' check (length(workshop_name) <= 200),
    performed_by text check (performed_by in ('self', 'mechanic')),
    cost numeric check (cost >= 0 and cost <> 'NaN'::numeric and cost <> 'Infinity'::numeric),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key(user_id, id),
    foreign key(user_id, vehicle_id) references public.user_vehicles(user_id, id) on delete cascade,
    foreign key(user_id, vehicle_id, task_id) references public.user_tasks(user_id, vehicle_id, id) on delete set null(task_id)
);

create table public.learning_progress (
    user_id uuid not null references public.app_users(id) on delete cascade,
    id uuid not null references public.guides(id) on delete cascade,
    completed boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    current_step_id text,
    guide_revision text,
    completed_at timestamptz,
    primary key(user_id, id)
);

create table public.learning_recaps (
    user_id uuid not null references public.app_users(id) on delete cascade,
    id uuid not null references public.guide_categories(id) on delete cascade,
    created_at timestamptz not null default now(),
    primary key(user_id, id)
);

create table public.incident_records (
    user_id uuid not null references public.app_users(id) on delete cascade,
    id text not null check (length(id) between 1 and 200 and id ~ '^[A-Za-z0-9_:-]+$'),
    -- Versioned incident form; photo bytes stay on the device.
    payload jsonb not null check (jsonb_typeof(payload) = 'object' and not (payload ? 'id')
        and not (payload ? 'cloudRevision') and not (payload ? 'pendingSync')),
    revision integer not null check (revision > 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key(user_id, id)
);

create table public.chat_sessions (
    id uuid primary key default gen_random_uuid(),
    token_hash text not null check (token_hash ~ '^[0-9a-f]{64}$'),
    user_id uuid not null references public.app_users(id) on delete cascade,
    user_vehicle_id text,
    automatic boolean not null default false,
    vehicle_id uuid references public.knowledge_vehicles(id) on delete restrict,
    category_id uuid references public.guide_categories(id) on delete restrict,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    activity jsonb,
    constraint chat_sessions_context_check check (
        (automatic and category_id is null and ((vehicle_id is null) = (user_vehicle_id is null))) or
        (not automatic and num_nonnulls(vehicle_id, category_id) = 1)
    ),
    -- Delete context-bound chats when their personal vehicle is deleted.
    foreign key(user_id, user_vehicle_id) references public.user_vehicles(user_id, id) on delete cascade
);

create table public.chat_messages (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.chat_sessions(id) on delete cascade,
    role text not null check (role in ('user', 'assistant')),
    content text not null,
    created_at timestamptz not null default now(),
    reply jsonb
);

create table public.chat_settings (
    id text primary key check (id = 'default'),
    starter_questions text[] not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    mechanic_template jsonb,
    mechanic_details text[] not null default '{}'
);

-- Review decisions are private working notes, never source approval.
create table public.document_review_progress (
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

-- Personal service plans and saved learning resources.
create table public.service_plans (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.app_users(id) on delete cascade,
    vehicle_id text not null,
    fingerprint text not null check (fingerprint ~ '^[a-f0-9]{64}$'),
    snapshot jsonb not null check (jsonb_typeof(snapshot) = 'object'),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key(user_id, vehicle_id) references public.user_vehicles(user_id, id) on delete cascade,
    unique(user_id, vehicle_id, fingerprint)
);

create table public.saved_items (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.app_users(id) on delete cascade,
    kind text not null check (kind in ('guide', 'explanation', 'plan', 'notes')),
    title text not null check (length(trim(title)) between 1 and 300),
    vehicle_id text,
    guide_id uuid references public.guides(id) on delete set null,
    message_id uuid references public.chat_messages(id) on delete set null,
    plan_id uuid references public.service_plans(id) on delete set null,
    payload jsonb not null default '{}' check (jsonb_typeof(payload) = 'object'),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key(user_id, vehicle_id) references public.user_vehicles(user_id, id) on delete cascade
);

-- Private saved document questions and revision-bound review results.

create table public.document_test_questions (
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

create table public.document_test_runs (
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

-- 4. Indexes.

create index app_sessions_user on public.app_sessions(user_id);

create index app_sessions_expiry on public.app_sessions(expires_at);

create unique index manufacturer_name_unique on public.vehicle_manufacturers(lower(trim(name)));

create unique index model_identity_unique on public.vehicle_models(manufacturer_id, lower(trim(name)));

create unique index vehicle_identity_unique on public.knowledge_vehicles(
    model_id, year, lower(trim(engine)), lower(trim(variant)), powertrain
) where model_id is not null;

create unique index maintenance_item_identity_unique on public.maintenance_items(lower(trim(title)), action);

create index documents_awaiting_index on public.documents(created_at, id) where status = 'awaiting_index';

create index documents_replacement on public.documents(replacement_for_id) where replacement_for_id is not null;

create index documents_superseded on public.documents(superseded_by_id) where superseded_by_id is not null;

create unique index guide_categories_name_unique on public.guide_categories(lower(trim(name)));

create index guides_category on public.guides(category_id);

create index guides_publication_order on public.guides(status, display_order, created_at, id);

create index guide_images_guide on public.guide_images(guide_id);

create index document_vehicles_vehicle on public.document_vehicles(vehicle_id, document_id);

create index document_categories_category on public.document_categories(category_id, document_id);

create unique index one_published_vehicle_schedule on public.manufacturer_schedules(vehicle_id) where status = 'published';

create index admin_questions_document on public.admin_review_questions(document_id, status);

create index admin_questions_vehicle on public.admin_review_questions(vehicle_id, status);

create index youtube_channels_pending on public.youtube_channels(status, created_at, id);

create unique index knowledge_vehicle_video on public.knowledge_videos(vehicle_id, video_id) where vehicle_id is not null;

create unique index knowledge_category_video on public.knowledge_videos(category_id, video_id) where category_id is not null;

create index emergency_playbooks_order on public.emergency_playbooks(status, display_order, created_at, id);

create index emergency_contacts_order on public.emergency_contacts(display_order, created_at, id);

create index user_vehicles_catalogue on public.user_vehicles(catalogue_id);

create unique index user_standard_item_unique on public.user_tasks(user_id, vehicle_id, item_id) where item_id is not null;

create index user_tasks_item on public.user_tasks(item_id) where item_id is not null;

create index service_vehicle_history on public.service_records(user_id, vehicle_id, performed_at desc);

create index service_records_task on public.service_records(user_id, vehicle_id, task_id) where task_id is not null;

create index learning_progress_guide on public.learning_progress(id);

create index chat_sessions_owner_vehicle on public.chat_sessions(user_id, user_vehicle_id);

create index chat_sessions_vehicle on public.chat_sessions(vehicle_id) where vehicle_id is not null;

create index chat_sessions_category on public.chat_sessions(category_id) where category_id is not null;

create index chat_messages_session on public.chat_messages(session_id, created_at, id);

create index service_plans_owner on public.service_plans(user_id, vehicle_id, created_at);

create index saved_items_owner on public.saved_items(user_id, created_at);

create index document_test_questions_document on public.document_test_questions(document_id);

create index document_test_runs_recent on public.document_test_runs(document_id, started_at desc);

create index document_test_runs_question_recent on public.document_test_runs(question_id, started_at desc, id desc);

-- 5. Functions. SECURITY INVOKER; empty search_path is retained.

-- Shared timestamp handling and immutable conversation identity.
create function public.content_updated_at() returns trigger
language plpgsql set search_path = '' as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create function public.chat_scope_immutable() returns trigger
language plpgsql set search_path = '' as $$
begin
    if new.automatic is distinct from old.automatic
        or new.vehicle_id is distinct from old.vehicle_id or new.category_id is distinct from old.category_id
        or new.user_id is distinct from old.user_id or new.user_vehicle_id is distinct from old.user_vehicle_id then
        raise exception 'Start a new chat to change owner or knowledge scope';
    end if;
    return new;
end;
$$;

-- Atomic publication after FastAPI validation and explicit human review.
-- SECURITY INVOKER (default): neither function elevates caller permissions.
create function public.publish_document(document_id uuid) returns public.documents
language plpgsql set search_path = '' as $$
declare candidate public.documents; previous public.documents;
begin
    select * into candidate from public.documents where id = document_id for update;
    if not found then raise exception 'Document missing'; end if;
    if candidate.superseded_by_id is not null then raise exception 'Document superseded'; end if;
    if candidate.status <> 'processed' or candidate.indexed_revision is distinct from candidate.source_revision or candidate.chunk_count < 1 then
        raise exception 'Indexing not confirmed';
    end if;
    if not exists (select 1 from public.document_vehicles dv where dv.document_id = candidate.id)
        and not exists (select 1 from public.document_categories dc where dc.document_id = candidate.id) then
        raise exception 'Associate the document with a vehicle or category before publication';
    end if;
    if candidate.replacement_for_id is not null then
        select * into previous from public.documents where id = candidate.replacement_for_id for update;
        if not found then raise exception 'Replacement source missing'; end if;
        if previous.superseded_by_id is not null and previous.superseded_by_id <> candidate.id then
            raise exception 'Replacement source already superseded';
        end if;
        update public.documents set published = false, mobile_visible = false, superseded_by_id = candidate.id where id = previous.id;
    end if;
    update public.documents set published = true, mobile_visible = true where id = candidate.id returning * into candidate;
    return candidate;
end;
$$;

create function public.publish_manufacturer_schedule(schedule_id uuid, expected_updated_at timestamptz) returns public.manufacturer_schedules
language plpgsql set search_path = '' as $$
declare candidate public.manufacturer_schedules;
begin
    select * into candidate from public.manufacturer_schedules where id = schedule_id;
    if not found then raise exception 'Schedule missing'; end if;
    -- Lock the vehicle first to serialize competing revisions.
    perform 1 from public.knowledge_vehicles where id = candidate.vehicle_id for update;
    select * into candidate from public.manufacturer_schedules where id = schedule_id for update;
    if not found then raise exception 'Schedule missing'; end if;
    if expected_updated_at is null or candidate.updated_at <> expected_updated_at then
        raise exception 'Schedule changed. Reload and review its latest version.';
    end if;
    if candidate.status = 'superseded' then raise exception 'Schedule superseded'; end if;
    update public.manufacturer_schedules set status = 'superseded'
        where vehicle_id = candidate.vehicle_id and status = 'published' and id <> schedule_id;
    update public.manufacturer_schedules set status = 'published', verified_at = now()
        where id = schedule_id returning * into candidate;
    return candidate;
end;
$$;

-- Admin-only preview. The fingerprint binds deletion to what was shown in the dialog.
create or replace function public.category_removal_impact(p_category_id uuid) returns jsonb
language plpgsql set search_path = '' as $$
declare
    candidate public.guide_categories;
    result jsonb;
begin
    select * into candidate from public.guide_categories where id = p_category_id;
    if not found then raise exception using errcode = 'PT404', message = 'This category no longer exists.'; end if;
    select jsonb_build_object(
        'category', to_jsonb(candidate),
        'guides', coalesce((select jsonb_agg(jsonb_build_object('id', id, 'title', title,
            'status', status, 'updated_at', updated_at) order by id)
            from public.guides where category_id = p_category_id), '[]'::jsonb),
        'chat_count', (select count(*) from public.chat_sessions where category_id = p_category_id),
        'document_links', coalesce((select jsonb_agg(jsonb_build_object('id', link.id,
            'document_id', doc.id, 'name', doc.name) order by link.id)
            from public.document_categories link join public.documents doc on doc.id = link.document_id
            where link.category_id = p_category_id), '[]'::jsonb),
        'video_links', coalesce((select jsonb_agg(jsonb_build_object('id', id, 'video_id', video_id) order by id)
            from public.knowledge_videos where category_id = p_category_id), '[]'::jsonb),
        'recap_count', (select count(*) from public.learning_recaps where id = p_category_id)
    ) into result;
    return result || jsonb_build_object('fingerprint', md5(result::text));
end;
$$;

-- A single RPC keeps all guide moves and the category deletion in one transaction.
create or replace function public.remove_category(p_category_id uuid, p_expected_impact text,
    p_target_category_id uuid default null) returns void
language plpgsql set search_path = '' as $$
declare
    impact jsonb;
    destination public.guide_categories;
begin
    if p_target_category_id = p_category_id then
        raise exception using errcode = 'PT422', message = 'Choose a different category for the guides.';
    end if;
    -- Lock both category rows in a consistent order. FK inserts into either wait.
    perform id from public.guide_categories
        where id = p_category_id or id = p_target_category_id order by id for update;
    perform id from public.guides where category_id = p_category_id order by id for update;
    perform id from public.document_categories where category_id = p_category_id order by id for update;
    perform id from public.knowledge_videos where category_id = p_category_id order by id for update;
    perform user_id from public.learning_recaps where id = p_category_id order by user_id for update;
    impact := public.category_removal_impact(p_category_id);
    if p_expected_impact is null or impact->>'fingerprint' <> p_expected_impact then
        raise exception using errcode = 'PT409', message = 'This category changed. Refresh the removal details and review them again.';
    end if;
    if (impact->>'chat_count')::bigint > 0 or (impact->>'recap_count')::bigint > 0 then
        raise exception using errcode = 'PT409', message = 'This category has saved chat or learning history. Archive it to preserve those references.';
    end if;
    if jsonb_array_length(impact->'guides') > 0 and p_target_category_id is null then
        raise exception using errcode = 'PT409', message = 'Choose a category to move all guides into before deleting this category.';
    end if;
    if p_target_category_id is not null then
        select * into destination from public.guide_categories where id = p_target_category_id;
        if not found or destination.archived then
            raise exception using errcode = 'PT422', message = 'Choose an active destination category.';
        end if;
        if not destination.published and exists(
            select 1 from public.guides where category_id = p_category_id and status = 'published') then
            raise exception using errcode = 'PT409', message = 'Choose a published destination so published guides remain available.';
        end if;
        update public.guides set category_id = p_target_category_id where category_id = p_category_id;
    end if;
    -- FK cascades remove topic assignments only; original documents remain intact.
    delete from public.guide_categories where id = p_category_id;
end;
$$;

revoke all on function public.category_removal_impact(uuid), public.remove_category(uuid, text, uuid)
    from public, anon, authenticated;
grant execute on function public.category_removal_impact(uuid), public.remove_category(uuid, text, uuid)
    to service_role;


-- 6. Triggers.

create trigger chat_scope_immutable before update on public.chat_sessions
    for each row execute function public.chat_scope_immutable();

create trigger service_plans_updated before update on public.service_plans
    for each row execute function public.content_updated_at();

create trigger saved_items_updated before update on public.saved_items
    for each row execute function public.content_updated_at();

do $$
declare application_table text;
begin
    foreach application_table in array array[
        'app_users',
        'vehicle_manufacturers',
        'vehicle_models',
        'knowledge_vehicles',
        'maintenance_items',
        'documents',
        'guide_categories',
        'guides',
        'manufacturer_schedules',
        'maintenance_assistance',
        'admin_review_questions',
        'youtube_channels',
        'emergency_playbooks',
        'emergency_contacts',
        'user_vehicles',
        'user_tasks',
        'service_records',
        'learning_progress',
        'incident_records',
        'chat_sessions',
        'chat_settings',
        'document_review_progress',
        'document_test_questions',
        'document_test_runs'
    ] loop
        execute format('create trigger content_updated_at before update on public.%I for each row execute function public.content_updated_at()', application_table);
    end loop;
end;
$$;

-- 7. Row Level Security. No direct-client policies are defined.

do $$
declare application_table text;
begin
    foreach application_table in array array[
        'app_users', 'app_sessions', 'vehicle_manufacturers', 'vehicle_models',
        'knowledge_vehicles', 'maintenance_items', 'documents', 'guide_categories',
        'guides', 'guide_images', 'emergency_images', 'document_vehicles', 'document_categories',
        'manufacturer_schedules', 'maintenance_assistance', 'admin_review_questions', 'document_review_progress', 'knowledge_videos', 'youtube_channels', 'emergency_playbooks',
        'emergency_contacts', 'user_vehicles', 'user_tasks', 'service_records',
        'learning_progress', 'incident_records', 'chat_sessions', 'chat_messages', 'chat_settings', 'document_test_questions', 'document_test_runs'
    ] loop
        execute format('alter table public.%I enable row level security', application_table);
    end loop;
end;
$$;

alter table public.service_plans enable row level security;

alter table public.saved_items enable row level security;

alter table public.learning_recaps enable row level security;

-- 8. Grants and permissions. Server access follows FastAPI authorization.

do $$
declare application_table text;
begin
    foreach application_table in array array[
        'app_users', 'app_sessions', 'vehicle_manufacturers', 'vehicle_models',
        'knowledge_vehicles', 'maintenance_items', 'documents', 'guide_categories',
        'guides', 'guide_images', 'emergency_images', 'document_vehicles', 'document_categories',
        'manufacturer_schedules', 'maintenance_assistance', 'admin_review_questions', 'document_review_progress', 'knowledge_videos', 'youtube_channels', 'emergency_playbooks',
        'emergency_contacts', 'user_vehicles', 'user_tasks', 'service_records',
        'learning_progress', 'incident_records', 'chat_sessions', 'chat_messages', 'chat_settings', 'document_test_questions', 'document_test_runs'
    ] loop
        execute format('revoke all on public.%I from public, anon, authenticated, service_role', application_table);
        execute format('grant select, insert, update, delete on public.%I to service_role', application_table);
    end loop;
end;
$$;

-- Direct API roles get no table access. FastAPI checks accounts, ownership,
-- admin privileges and public-content visibility before using service_role.
-- The explicit application list avoids touching Supabase-managed objects.
grant usage on schema public to service_role;

revoke all on function public.content_updated_at(), public.chat_scope_immutable(),
    public.publish_document(uuid), public.publish_manufacturer_schedule(uuid, timestamptz) from public, anon, authenticated;

grant execute on function public.content_updated_at(), public.chat_scope_immutable(),
    public.publish_document(uuid), public.publish_manufacturer_schedule(uuid, timestamptz) to service_role;

-- Personal APIs use the server service role after account/ownership validation.
revoke all on public.service_plans, public.saved_items from anon, authenticated;

grant all on public.service_plans, public.saved_items to service_role;

revoke all on public.learning_recaps from public, anon, authenticated;

grant all on public.learning_recaps to service_role;

-- 9. Supabase Storage buckets. No direct-client Storage policies.

-- Storage is Supabase-managed. No client upload/list/delete policies are needed.
-- Images are intentionally public by URL, including uploaded draft-guide assets.
-- Originals/extractions stay private; the backend authorizes downloads/signatures.
-- Change these IDs before running if the backend uses custom bucket names.
insert into storage.buckets(id, name, public) values
    ('documents', 'documents', false), ('content-images', 'content-images', true)
on conflict (id) do nothing;

-- 10. Essential editable starter presets only.

-- Configurable presets only; no demo vehicles, accounts or safety content.
insert into public.chat_settings(id, starter_questions) values ('default', array[
    'How do I check tyre pressure?',
    'What should I check before a long drive?',
    'How do I check my engine oil?'
]);

-- Persistent website PDF imports.

alter table public.documents add column if not exists source_metadata jsonb;
alter table public.documents add constraint documents_source_metadata_object
    check (source_metadata is null or jsonb_typeof(source_metadata) = 'object');

create table public.website_import_jobs (
    id uuid primary key default gen_random_uuid(),
    requested_by uuid not null references public.app_users(id),
    idempotency_key uuid not null,
    submitted_url text not null check (length(submitted_url) between 1 and 2048),
    url_key text not null,
    capture_options jsonb not null default '{"media":"screen"}',
    status text not null default 'queued' check (status in
        ('queued','capturing','captured','storing','retry_wait','completed','failed','cancelled')),
    attempt_count integer not null default 0,
    next_attempt_at timestamptz not null default now(),
    claim_token uuid,
    lease_expires_at timestamptz,
    heartbeat_at timestamptz,
    target_document_id uuid not null default gen_random_uuid() unique,
    document_id uuid references public.documents(id) on delete set null,
    artifact_path text,
    artifact_sha256 text,
    artifact_size bigint,
    page_count integer,
    source_metadata jsonb,
    error_code text,
    error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz,
    unique (requested_by, idempotency_key),
    check (jsonb_typeof(capture_options) = 'object'),
    check (source_metadata is null or jsonb_typeof(source_metadata) = 'object'),
    check (artifact_sha256 is null or artifact_sha256 ~ '^[0-9a-f]{64}$'),
    check (artifact_size is null or artifact_size > 0),
    check (page_count is null or page_count > 0)
);
create unique index website_import_active_url on public.website_import_jobs(requested_by, url_key)
    where status in ('queued','capturing','captured','storing','retry_wait');
create index website_import_queue on public.website_import_jobs(next_attempt_at, created_at)
    where status in ('queued','capturing','captured','storing','retry_wait');
create trigger website_import_updated before update on public.website_import_jobs
    for each row execute function public.content_updated_at();
alter table public.website_import_jobs enable row level security;
revoke all on public.website_import_jobs from public, anon, authenticated;
grant select, insert, update, delete on public.website_import_jobs to service_role;

create function public.create_website_import(p_user uuid, p_key uuid, p_url text, p_url_key text,
    p_options jsonb) returns jsonb language plpgsql set search_path = public as $$
declare job public.website_import_jobs;
begin
    perform pg_advisory_xact_lock(hashtextextended(p_user::text, 0));
    select * into job from public.website_import_jobs where requested_by=p_user and idempotency_key=p_key;
    if found then
        if job.submitted_url <> p_url or job.capture_options <> p_options then
            raise exception using errcode='PT409', message='This request key belongs to another import. Start a new request.';
        end if;
        return to_jsonb(job);
    end if;
    select * into job from public.website_import_jobs where requested_by=p_user and url_key=p_url_key
        and status in ('queued','capturing','captured','storing','retry_wait');
    if found then return to_jsonb(job); end if;
    insert into public.website_import_jobs(requested_by,idempotency_key,submitted_url,url_key,capture_options,status)
        values(p_user,p_key,p_url,p_url_key,p_options,case when p_options->>'manual'='true' then 'cancelled' else 'queued' end) returning * into job;
    return to_jsonb(job);
end;
$$;

create function public.claim_website_import(p_token uuid) returns jsonb
language plpgsql set search_path = public as $$
declare job public.website_import_jobs;
begin
    update public.website_import_jobs set status='failed',error_code='interrupted',
        error='Capture was interrupted repeatedly. Retry this import.',claim_token=null,lease_expires_at=null
        where status in ('capturing','captured','storing') and lease_expires_at < now() and attempt_count >= 3;
    select * into job from public.website_import_jobs
        where ((status in ('queued','retry_wait') and next_attempt_at <= now())
            or (status in ('capturing','captured','storing') and lease_expires_at < now()))
        order by created_at,id for update skip locked limit 1;
    if not found then return null; end if;
    update public.website_import_jobs set status=case when artifact_path is null then 'capturing' else 'storing' end,
        claim_token=p_token, lease_expires_at=now()+interval '180 seconds', heartbeat_at=now(),
        attempt_count=attempt_count+1,error_code=null,error=null where id=job.id returning * into job;
    return to_jsonb(job);
end;
$$;

create function public.heartbeat_website_import(p_id uuid,p_token uuid) returns boolean
language plpgsql set search_path = public as $$
begin
    update public.website_import_jobs set heartbeat_at=now(),lease_expires_at=now()+interval '180 seconds'
        where id=p_id and claim_token=p_token and lease_expires_at>now()
            and status in ('capturing','captured','storing');
    return found;
end;
$$;

create function public.update_website_import(p_id uuid,p_token uuid,p_values jsonb) returns jsonb
language plpgsql set search_path = public as $$
declare job public.website_import_jobs;
begin
    if p_values ? 'status' and p_values->>'status' not in ('captured','storing','retry_wait','failed') then
        raise exception using errcode='PT422',message='Invalid import transition.';
    end if;
    update public.website_import_jobs set
        status=coalesce(p_values->>'status',status),
        artifact_path=coalesce(p_values->>'artifact_path',artifact_path),
        artifact_sha256=coalesce(p_values->>'artifact_sha256',artifact_sha256),
        artifact_size=coalesce((p_values->>'artifact_size')::bigint,artifact_size),
        page_count=coalesce((p_values->>'page_count')::integer,page_count),
        source_metadata=coalesce(p_values->'source_metadata',source_metadata),
        error_code=case when p_values ? 'error_code' then p_values->>'error_code' else error_code end,
        error=case when p_values ? 'error' then p_values->>'error' else error end,
        next_attempt_at=coalesce((p_values->>'next_attempt_at')::timestamptz,next_attempt_at),
        claim_token=case when p_values->>'status' in ('failed','retry_wait') then null else claim_token end,
        lease_expires_at=case when p_values->>'status' in ('failed','retry_wait') then null else lease_expires_at end
        where id=p_id and claim_token=p_token and lease_expires_at>now()
            and status in ('capturing','captured','storing') returning * into job;
    if not found then raise exception using errcode='PT409',message='This import attempt no longer owns the job.'; end if;
    return to_jsonb(job);
end;
$$;

create function public.finalize_website_import(p_id uuid,p_token uuid) returns jsonb
language plpgsql set search_path = public as $$
declare job public.website_import_jobs;
begin
    select * into job from public.website_import_jobs where id=p_id for update;
    if not found then raise exception using errcode='PT404',message='Import not found.'; end if;
    if job.status='completed' then return to_jsonb(job); end if;
    if job.claim_token is distinct from p_token or job.lease_expires_at<=now() or job.status<>'storing' then
        raise exception using errcode='PT409',message='This import attempt no longer owns the job.';
    end if;
    if job.artifact_path is null or job.artifact_sha256 is null or job.artifact_size is null
        or job.source_metadata is null or job.page_count is null
        or job.artifact_path not like 'documents/'||job.target_document_id::text||'/captures/%' then
        raise exception using errcode='PT422',message='The saved PDF is incomplete.';
    end if;
    insert into public.documents(id,name,original_filename,source_type,storage_path,size_bytes,source_metadata)
        values(job.target_document_id,left(coalesce(nullif(job.source_metadata->>'article_title',''),'Website PDF'),300),
            'website-'||job.id::text||'.pdf','pdf',job.artifact_path,job.artifact_size,job.source_metadata);
    update public.website_import_jobs set status='completed',document_id=target_document_id,
        completed_at=now(),claim_token=null,lease_expires_at=null,error=null,error_code=null
        where id=p_id returning * into job;
    return to_jsonb(job);
end;
$$;

create function public.control_website_import(p_id uuid,p_action text) returns jsonb
language plpgsql set search_path = public as $$
declare job public.website_import_jobs;
begin
    select * into job from public.website_import_jobs where id=p_id for update;
    if not found then raise exception using errcode='PT404',message='Import not found.'; end if;
    if p_action='cancel' then
        if job.status='completed' then raise exception using errcode='PT409',message='This import is already saved.'; end if;
        update public.website_import_jobs set status='cancelled',claim_token=null,lease_expires_at=null where id=p_id returning * into job;
    elsif p_action='retry' then
        if job.status not in ('failed','cancelled') then raise exception using errcode='PT409',message='Only stopped imports can be retried.'; end if;
        if exists(select 1 from public.website_import_jobs where requested_by=job.requested_by and url_key=job.url_key
            and id<>job.id and status in ('queued','capturing','captured','storing','retry_wait')) then
            raise exception using errcode='PT409',message='Another import for this URL is active. Open that import.';
        end if;
        update public.website_import_jobs set status='queued',attempt_count=0,next_attempt_at=now(),
            claim_token=null,lease_expires_at=null,error=null,error_code=null where id=p_id returning * into job;
    else raise exception using errcode='PT422',message='Invalid import action.';
    end if;
    return to_jsonb(job);
end;
$$;

create function public.manual_website_import(p_id uuid,p_token uuid) returns jsonb
language plpgsql set search_path = public as $$
declare job public.website_import_jobs;
begin
    select * into job from public.website_import_jobs where id=p_id for update;
    if not found then raise exception using errcode='PT404',message='Import not found.'; end if;
    if job.status not in ('failed','cancelled') then
        raise exception using errcode='PT409',message='Cancel the active capture before attaching a saved PDF.';
    end if;
    update public.website_import_jobs set status='storing',claim_token=p_token,
        lease_expires_at=now()+interval '180 seconds',heartbeat_at=now(),attempt_count=0,
        artifact_path=null,artifact_sha256=null,artifact_size=null,page_count=null,source_metadata=null,
        error=null,error_code=null where id=p_id returning * into job;
    return to_jsonb(job);
end;
$$;

create function public.release_website_import(p_id uuid,p_token uuid) returns boolean
language plpgsql set search_path = public as $$
begin
    update public.website_import_jobs set status='queued',next_attempt_at=now(),
        attempt_count=greatest(0,attempt_count-1),claim_token=null,lease_expires_at=null
        where id=p_id and claim_token=p_token and lease_expires_at>now()
            and status in ('capturing','captured','storing');
    return found;
end;
$$;

revoke all on function public.create_website_import(uuid,uuid,text,text,jsonb),
    public.claim_website_import(uuid), public.heartbeat_website_import(uuid,uuid),
    public.update_website_import(uuid,uuid,jsonb),public.finalize_website_import(uuid,uuid),
    public.control_website_import(uuid,text),public.manual_website_import(uuid,uuid),public.release_website_import(uuid,uuid)
    from public, anon, authenticated;
grant execute on function public.create_website_import(uuid,uuid,text,text,jsonb),
    public.claim_website_import(uuid), public.heartbeat_website_import(uuid,uuid),
    public.update_website_import(uuid,uuid,jsonb),public.finalize_website_import(uuid,uuid),
    public.control_website_import(uuid,text),public.manual_website_import(uuid,uuid),public.release_website_import(uuid,uuid) to service_role;
notify pgrst, 'reload schema';

-- Catalogue deletion functions.
create index if not exists document_test_vehicle_scope on public.document_test_questions(scope_id)
    where scope_type = 'vehicle';
create index if not exists document_test_run_vehicle_scope on public.document_test_runs(lower(question_snapshot->>'scope_id'))
    where question_snapshot->>'scope_type' = 'vehicle';

create or replace function public.catalogue_removal_impact(p_kind text, p_record_id uuid) returns jsonb
language plpgsql set search_path = '' as $$
declare entry jsonb; refs jsonb; result jsonb; related jsonb := '{}'::jsonb;
begin
    case p_kind
    when 'manufacturers' then
        select to_jsonb(row) into entry from public.vehicle_manufacturers row where id = p_record_id;
        refs := jsonb_build_object('models', (select count(*) from public.vehicle_models where manufacturer_id = p_record_id));
    when 'models' then
        select to_jsonb(row) into entry from public.vehicle_models row where id = p_record_id;
        refs := jsonb_build_object('vehicles', (select count(*) from public.knowledge_vehicles where model_id = p_record_id));
    when 'vehicles' then
        select to_jsonb(row) into entry from public.knowledge_vehicles row where id = p_record_id;
        refs := jsonb_build_object(
            'documents', (select count(*) from public.document_vehicles where vehicle_id = p_record_id),
            'schedules', (select count(*) from public.manufacturer_schedules where vehicle_id = p_record_id),
            'videos', (select count(*) from public.knowledge_videos where vehicle_id = p_record_id),
            'user_vehicles', (select count(*) from public.user_vehicles where catalogue_id = p_record_id),
            'review_questions', (select count(*) from public.admin_review_questions where vehicle_id = p_record_id),
            'chats', (select count(*) from public.chat_sessions where vehicle_id = p_record_id),
            'test_questions', (select count(*) from public.document_test_questions where scope_type = 'vehicle' and scope_id = p_record_id),
            'test_runs', (select count(*) from public.document_test_runs where question_snapshot->>'scope_type' = 'vehicle'
                and lower(question_snapshot->>'scope_id') = p_record_id::text));
        related := jsonb_build_object(
            'documents', coalesce((select jsonb_agg(to_jsonb(r)) from (
                select d.id, d.name from public.document_vehicles link
                join public.documents d on d.id = link.document_id
                where link.vehicle_id = p_record_id order by d.id limit 5) r), '[]'::jsonb),
            'test_documents', coalesce((select jsonb_agg(to_jsonb(r)) from (
                select d.id, d.name from public.documents d where d.id in (
                    select document_id from public.document_test_questions where scope_type = 'vehicle' and scope_id = p_record_id
                    union select document_id from public.document_test_runs where question_snapshot->>'scope_type' = 'vehicle'
                        and lower(question_snapshot->>'scope_id') = p_record_id::text)
                order by d.id limit 5) r), '[]'::jsonb),
            'videos', coalesce((select jsonb_agg(to_jsonb(r)) from (
                select video_id from public.knowledge_videos where vehicle_id = p_record_id order by id limit 5) r), '[]'::jsonb));
    else
        raise exception using errcode = 'PT422', message = 'Choose vehicles, models or manufacturers.';
    end case;
    if entry is null then raise exception using errcode = 'PT404', message = 'This catalogue entry no longer exists.'; end if;
    result := jsonb_build_object('kind', p_kind, 'entry', entry, 'references', refs, 'related', related,
        'deletable', not exists(select 1 from jsonb_each_text(refs) where value::bigint > 0));
    return result || jsonb_build_object('fingerprint', md5(result::text));
end;
$$;

-- Enforce the same rule for direct database deletes, including non-FK test history.
create or replace function public.guard_catalogue_deletion() returns trigger
language plpgsql set search_path = '' as $$
declare kind text; impact jsonb;
begin
    kind := case tg_table_name when 'vehicle_manufacturers' then 'manufacturers'
        when 'vehicle_models' then 'models' else 'vehicles' end;
    impact := public.catalogue_removal_impact(kind, old.id);
    if not (impact->>'deletable')::boolean then
        raise exception using errcode = 'PT409', message = 'This catalogue entry is still in use. Review its linked records or deactivate it.';
    end if;
    return old;
end;
$$;

create or replace function public.remove_catalogue_entry(p_kind text, p_record_id uuid, p_expected_impact text) returns void
language plpgsql set search_path = '' as $$
declare impact jsonb;
begin
    -- FK inserts and test-scope guards take KEY SHARE on this row. Lock before
    -- rechecking usage so a new reference cannot race with the confirmed delete.
    case p_kind
    when 'manufacturers' then perform id from public.vehicle_manufacturers where id = p_record_id for update;
    when 'models' then perform id from public.vehicle_models where id = p_record_id for update;
    when 'vehicles' then perform id from public.knowledge_vehicles where id = p_record_id for update;
    else raise exception using errcode = 'PT422', message = 'Choose vehicles, models or manufacturers.';
    end case;
    impact := public.catalogue_removal_impact(p_kind, p_record_id);
    if p_expected_impact is null or impact->>'fingerprint' <> p_expected_impact then
        raise exception using errcode = 'PT409', message = 'This entry or its usage changed. Refresh the deletion details and review them again.';
    end if;
    if not (impact->>'deletable')::boolean then
        raise exception using errcode = 'PT409', message = 'This catalogue entry is still in use. Deactivate it to preserve its linked records.';
    end if;
    case p_kind
    when 'manufacturers' then delete from public.vehicle_manufacturers where id = p_record_id;
    when 'models' then delete from public.vehicle_models where id = p_record_id;
    when 'vehicles' then delete from public.knowledge_vehicles where id = p_record_id;
    end case;
end;
$$;

-- Polymorphic document-test scopes have no FK. Protect both live questions and
-- immutable run snapshots, including a run whose question was later retargeted.
create or replace function public.guard_catalogue_test_scope() returns trigger
language plpgsql set search_path = '' as $$
declare kind text; identity uuid;
begin
    if tg_table_name = 'document_test_questions' then
        kind := new.scope_type; identity := new.scope_id;
    else
        kind := new.question_snapshot->>'scope_type';
        if kind = 'vehicle' then identity := (new.question_snapshot->>'scope_id')::uuid; end if;
    end if;
    if kind = 'vehicle' then
        perform id from public.knowledge_vehicles where id = identity for key share;
        if not found then
            raise exception using errcode = '23503', message = 'The vehicle for this saved document test no longer exists.';
        end if;
    end if;
    return new;
end;
$$;

drop trigger if exists catalogue_delete_guard on public.vehicle_manufacturers;
create trigger catalogue_delete_guard before delete on public.vehicle_manufacturers
    for each row execute function public.guard_catalogue_deletion();
drop trigger if exists catalogue_delete_guard on public.vehicle_models;
create trigger catalogue_delete_guard before delete on public.vehicle_models
    for each row execute function public.guard_catalogue_deletion();
drop trigger if exists catalogue_delete_guard on public.knowledge_vehicles;
create trigger catalogue_delete_guard before delete on public.knowledge_vehicles
    for each row execute function public.guard_catalogue_deletion();
drop trigger if exists catalogue_scope_guard on public.document_test_questions;
create trigger catalogue_scope_guard before insert or update of scope_type, scope_id on public.document_test_questions
    for each row execute function public.guard_catalogue_test_scope();
drop trigger if exists catalogue_scope_guard on public.document_test_runs;
create trigger catalogue_scope_guard before insert or update of question_snapshot on public.document_test_runs
    for each row execute function public.guard_catalogue_test_scope();

revoke all on function public.catalogue_removal_impact(text, uuid), public.remove_catalogue_entry(text, uuid, text),
    public.guard_catalogue_deletion(), public.guard_catalogue_test_scope() from public, anon, authenticated;
grant execute on function public.catalogue_removal_impact(text, uuid), public.remove_catalogue_entry(text, uuid, text),
    public.guard_catalogue_deletion(), public.guard_catalogue_test_scope() to service_role;

-- Emergency step uploads and shared index handoffs.
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

commit;
