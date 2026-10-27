-- Fresh Supabase project only. Run the entire file once; see README.md.
-- This script never drops existing objects or deletes application data.
begin;

-- Accounts use FastAPI authentication, not auth.users or Supabase Auth JWTs.
create table public.app_users (
    id uuid primary key default gen_random_uuid(),
    email text not null unique check (email = lower(trim(email)) and length(email) > 0),
    display_name text not null check (length(trim(display_name)) > 0),
    password_hash text not null check (length(password_hash) > 0),
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
create index app_sessions_user on public.app_sessions(user_id);
create index app_sessions_expiry on public.app_sessions(expires_at);

-- Shared vehicle catalogue and reusable maintenance items.
create table public.vehicle_manufacturers (
    id uuid primary key default gen_random_uuid(),
    name text not null check (length(trim(name)) > 0),
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index manufacturer_name_unique on public.vehicle_manufacturers(lower(trim(name)));
create table public.vehicle_models (
    id uuid primary key default gen_random_uuid(),
    manufacturer_id uuid not null references public.vehicle_manufacturers(id) on delete restrict,
    name text not null check (length(trim(name)) > 0),
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index model_identity_unique on public.vehicle_models(manufacturer_id, lower(trim(name)));
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
create unique index vehicle_identity_unique on public.knowledge_vehicles(
    model_id, year, lower(trim(engine)), lower(trim(variant)), powertrain
) where model_id is not null;
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
create unique index maintenance_item_identity_unique on public.maintenance_items(lower(trim(title)), action);

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
        check (status in ('uploaded', 'processing', 'awaiting_index', 'processed', 'failed')),
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
create index documents_awaiting_index on public.documents(created_at, id) where status = 'awaiting_index';
create index documents_replacement on public.documents(replacement_for_id) where replacement_for_id is not null;
create index documents_superseded on public.documents(superseded_by_id) where superseded_by_id is not null;
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
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index guide_categories_name_unique on public.guide_categories(lower(trim(name)));
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
    check ((status = 'published') = (published_at is not null)),
    check (not (id = any(related_lesson_ids))),
    check (array_position(related_lesson_ids, null) is null),
    check (array_position(maintenance_item_ids, null) is null)
);
create index guides_category on public.guides(category_id);
create index guides_publication_order on public.guides(status, display_order, created_at, id);
create table public.guide_images (
    id uuid primary key default gen_random_uuid(),
    guide_id uuid not null references public.guides(id) on delete cascade,
    storage_path text not null unique check (length(storage_path) > 0),
    created_at timestamptz not null default now()
);
create index guide_images_guide on public.guide_images(guide_id);

-- These junctions reflect real many-to-many applicability. Surrogate IDs support
-- generic CRUD/pagination; pair uniqueness prevents duplicate assignments.
create table public.document_vehicles (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references public.documents(id) on delete cascade,
    vehicle_id uuid not null references public.knowledge_vehicles(id) on delete cascade,
    created_at timestamptz not null default now(),
    unique(document_id, vehicle_id)
);
create index document_vehicles_vehicle on public.document_vehicles(vehicle_id, document_id);
create table public.document_categories (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references public.documents(id) on delete cascade,
    category_id uuid not null references public.guide_categories(id) on delete cascade,
    created_at timestamptz not null default now(),
    unique(document_id, category_id)
);
create index document_categories_category on public.document_categories(category_id, document_id);
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
create unique index one_published_vehicle_schedule on public.manufacturer_schedules(vehicle_id) where status = 'published';
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
create index admin_questions_document on public.admin_review_questions(document_id, status);
create index admin_questions_vehicle on public.admin_review_questions(vehicle_id, status);

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
create index youtube_channels_pending on public.youtube_channels(status, created_at, id);

create table public.knowledge_videos (
    id uuid primary key default gen_random_uuid(),
    video_id text not null check (video_id ~ '^[A-Za-z0-9_-]{11}$'),
    vehicle_id uuid references public.knowledge_vehicles(id) on delete cascade,
    category_id uuid references public.guide_categories(id) on delete cascade,
    created_at timestamptz not null default now(),
    check (num_nonnulls(vehicle_id, category_id) = 1)
);
create unique index knowledge_vehicle_video on public.knowledge_videos(vehicle_id, video_id) where vehicle_id is not null;
create unique index knowledge_category_video on public.knowledge_videos(category_id, video_id) where category_id is not null;

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
create index emergency_playbooks_order on public.emergency_playbooks(status, display_order, created_at, id);
create table public.emergency_contacts (
    id uuid primary key default gen_random_uuid(),
    name text not null check (length(trim(name)) > 0),
    description text not null default '',
    display_order integer not null default 0 check (display_order >= 0),
    phone text not null check (phone ~ '^[+0-9[:space:]().-]+$' and length(regexp_replace(phone, '[^0-9]', '', 'g')) >= 3),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index emergency_contacts_order on public.emergency_contacts(display_order, created_at, id);

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
create index user_vehicles_catalogue on public.user_vehicles(catalogue_id);
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
create unique index user_standard_item_unique on public.user_tasks(user_id, vehicle_id, item_id) where item_id is not null;
create index user_tasks_item on public.user_tasks(item_id) where item_id is not null;
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
    cost numeric check (cost >= 0 and cost <> 'NaN'::numeric and cost <> 'Infinity'::numeric),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key(user_id, id),
    foreign key(user_id, vehicle_id) references public.user_vehicles(user_id, id) on delete cascade,
    foreign key(user_id, vehicle_id, task_id) references public.user_tasks(user_id, vehicle_id, id) on delete set null(task_id)
);
create index service_vehicle_history on public.service_records(user_id, vehicle_id, performed_at desc);
create index service_records_task on public.service_records(user_id, vehicle_id, task_id) where task_id is not null;
create table public.learning_progress (
    user_id uuid not null references public.app_users(id) on delete cascade,
    id uuid not null references public.guides(id) on delete cascade,
    completed boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key(user_id, id)
);
create index learning_progress_guide on public.learning_progress(id);
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
    constraint chat_sessions_context_check check (
        (automatic and category_id is null and ((vehicle_id is null) = (user_vehicle_id is null))) or
        (not automatic and num_nonnulls(vehicle_id, category_id) = 1)
    ),
    -- Delete context-bound chats when their personal vehicle is deleted.
    foreign key(user_id, user_vehicle_id) references public.user_vehicles(user_id, id) on delete cascade
);
create index chat_sessions_owner_vehicle on public.chat_sessions(user_id, user_vehicle_id);
create index chat_sessions_vehicle on public.chat_sessions(vehicle_id) where vehicle_id is not null;
create index chat_sessions_category on public.chat_sessions(category_id) where category_id is not null;
create table public.chat_messages (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.chat_sessions(id) on delete cascade,
    role text not null check (role in ('user', 'assistant')),
    content text not null,
    created_at timestamptz not null default now()
);
create index chat_messages_session on public.chat_messages(session_id, created_at, id);
create table public.chat_settings (
    id text primary key check (id = 'default'),
    starter_questions text[] not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
-- Configurable presets only; no demo vehicles, accounts or safety content.
insert into public.chat_settings(id, starter_questions) values ('default', array[
    'How do I check tyre pressure?',
    'What should I check before a long drive?',
    'How do I check my engine oil?'
]);

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
create trigger chat_scope_immutable before update on public.chat_sessions
    for each row execute function public.chat_scope_immutable();

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
create function public.publish_manufacturer_schedule(schedule_id uuid) returns public.manufacturer_schedules
language plpgsql set search_path = '' as $$
declare candidate public.manufacturer_schedules;
begin
    select * into candidate from public.manufacturer_schedules where id = schedule_id;
    if not found then raise exception 'Schedule missing'; end if;
    -- Lock the vehicle first to serialize competing revisions.
    perform 1 from public.knowledge_vehicles where id = candidate.vehicle_id for update;
    select * into candidate from public.manufacturer_schedules where id = schedule_id for update;
    if not found then raise exception 'Schedule missing'; end if;
    if candidate.status = 'superseded' then raise exception 'Schedule superseded'; end if;
    update public.manufacturer_schedules set status = 'superseded'
        where vehicle_id = candidate.vehicle_id and status = 'published' and id <> schedule_id;
    update public.manufacturer_schedules set status = 'published', verified_at = now()
        where id = schedule_id returning * into candidate;
    return candidate;
end;
$$;

-- Direct API roles get no table access. FastAPI checks accounts, ownership,
-- admin privileges and public-content visibility before using service_role.
-- The explicit application list avoids touching Supabase-managed objects.
grant usage on schema public to service_role;
do $$
declare application_table text;
begin
    foreach application_table in array array[
        'app_users', 'app_sessions', 'vehicle_manufacturers', 'vehicle_models',
        'knowledge_vehicles', 'maintenance_items', 'documents', 'guide_categories',
        'guides', 'guide_images', 'document_vehicles', 'document_categories',
        'manufacturer_schedules', 'maintenance_assistance', 'admin_review_questions', 'knowledge_videos', 'youtube_channels', 'emergency_playbooks',
        'emergency_contacts', 'user_vehicles', 'user_tasks', 'service_records',
        'learning_progress', 'incident_records', 'chat_sessions', 'chat_messages', 'chat_settings'
    ] loop
        execute format('alter table public.%I enable row level security', application_table);
        execute format('revoke all on public.%I from public, anon, authenticated, service_role', application_table);
        execute format('grant select, insert, update, delete on public.%I to service_role', application_table);
        if exists (select 1 from information_schema.columns
                   where table_schema = 'public' and table_name = application_table and column_name = 'updated_at') then
            execute format('create trigger content_updated_at before update on public.%I for each row execute function public.content_updated_at()', application_table);
        end if;
    end loop;
end;
$$;
revoke all on function public.content_updated_at(), public.chat_scope_immutable(),
    public.publish_document(uuid), public.publish_manufacturer_schedule(uuid) from public, anon, authenticated;
grant execute on function public.content_updated_at(), public.chat_scope_immutable(),
    public.publish_document(uuid), public.publish_manufacturer_schedule(uuid) to service_role;

-- Storage is Supabase-managed. No client upload/list/delete policies are needed.
-- Images are intentionally public by URL, including uploaded draft-guide assets.
-- Originals/extractions stay private; the backend authorizes downloads/signatures.
-- Change these IDs before running if the backend uses custom bucket names.
insert into storage.buckets(id, name, public) values
    ('documents', 'documents', false), ('content-images', 'content-images', true)
on conflict (id) do nothing;
commit;
