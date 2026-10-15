-- Complete fresh-project schema. Run this entire file once; see supabase/README.md.
begin;
-- Run in the Supabase SQL editor. No demo content or invented contacts.

create table public.documents (
 id uuid primary key default gen_random_uuid(),
 name text not null check (length(trim(name)) > 0),
 car_model text not null default 'general' check (car_model in ('general','myvi','axia','bezza')),
 tags text[] not null default '{}',
 original_filename text not null,
 source_type text not null check (source_type in ('pdf','md')),
 storage_path text not null unique,
 size_bytes bigint not null check (size_bytes > 0),
 status text not null default 'uploaded' check (status in ('uploaded','processing','processed','failed')),
 error text,
 chunk_count integer not null default 0,
 processing_started_at timestamptz,
 processed_at timestamptz,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create table public.guide_categories (
 id uuid primary key default gen_random_uuid(),
 name text not null check (length(trim(name)) > 0),
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create unique index guide_categories_name_unique on public.guide_categories(lower(name));
create table public.guides (
 id uuid primary key default gen_random_uuid(),
 title text not null check (length(trim(title)) > 0),
 category_id uuid references public.guide_categories(id) on delete restrict,
 content text not null default '<p></p>',
 status text not null default 'draft' check (status in ('draft','published')),
 published_at timestamptz,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create index guides_category_id on public.guides(category_id);
create table public.guide_images (
 id uuid primary key default gen_random_uuid(),
 guide_id uuid not null references public.guides(id) on delete cascade,
 storage_path text not null unique,
 url text not null,
 created_at timestamptz not null default now()
);
create index guide_images_guide_id on public.guide_images(guide_id);
create table public.emergency_playbooks (
 id uuid primary key default gen_random_uuid(),
 title text not null check (length(trim(title)) > 0),
 -- Array order is the checklist order; the entire edit saves atomically.
 steps jsonb not null default '[]' check (jsonb_typeof(steps) = 'array'),
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create table public.emergency_contacts (
 id uuid primary key default gen_random_uuid(),
 name text not null check (length(trim(name)) > 0),
 phone text not null,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create function public.content_updated_at() returns trigger language plpgsql as $$
begin
 new.updated_at = now();
 return new;
end;
$$;
do $$
declare table_name text;
begin
 foreach table_name in array array['documents','guide_categories','guides','emergency_playbooks','emergency_contacts'] loop
  execute format('create trigger content_updated_at before update on public.%I for each row execute function public.content_updated_at()', table_name);
 end loop;
 foreach table_name in array array['documents','guide_categories','guides','guide_images','emergency_playbooks','emergency_contacts'] loop
  execute format('alter table public.%I enable row level security', table_name);
  execute format('revoke all on public.%I from anon, authenticated', table_name);
  execute format('grant all on public.%I to service_role', table_name);
 end loop;
end;
$$;
-- Backend service-role access only. No browser database/storage write policies.
-- If using different bucket names, change these names before running the SQL.
insert into storage.buckets (id,name,public) values
 ('documents','documents',false), ('content-images','content-images',true)
on conflict (id) do nothing;

-- Application accounts, accessible only through the backend service role.

create table public.app_users (
 id uuid primary key default gen_random_uuid(),
 email text not null,
 display_name text not null check (length(trim(display_name)) > 0),
 password_hash text not null,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 constraint app_users_email_normalized check (email = lower(trim(email)))
);
create unique index app_users_email_unique on public.app_users (email);
create trigger app_users_updated_at before update on public.app_users
 for each row execute function public.content_updated_at();
alter table public.app_users enable row level security;
revoke all on public.app_users from anon, authenticated;
grant all on public.app_users to service_role;

alter table public.app_users add column role text not null default 'user'
 check (role in ('user', 'admin'));
-- The primary key is a SHA-256 session-token hash; raw tokens are never stored.
create table public.app_sessions (
 id text primary key check (length(id) = 64),
 user_id uuid not null references public.app_users(id) on delete cascade,
 created_at timestamptz not null default now(),
 expires_at timestamptz not null,
 csrf_token text not null,
 check (expires_at > created_at)
);
create index app_sessions_user on public.app_sessions(user_id);
create index app_sessions_expiry on public.app_sessions(expires_at);
alter table public.app_sessions enable row level security;
revoke all on public.app_sessions from anon, authenticated;
grant all on public.app_sessions to service_role;

alter table public.emergency_playbooks
 add column status text not null default 'draft' check (status in ('draft','published')),
 add column scenario_key text unique check (scenario_key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
 add column source text not null default '',
 add column reviewed_at timestamptz,
 add constraint emergency_publication_complete check (
   status <> 'published' or
   (scenario_key is not null and length(trim(source)) > 0 and reviewed_at is not null and jsonb_array_length(steps) > 0)
 );
create index emergency_playbooks_status on public.emergency_playbooks(status);

-- Existing and newly uploaded documents remain private until an admin publishes them.
alter table public.documents
  add column if not exists mobile_visible boolean not null default false;

create index if not exists documents_mobile_scope_idx
  on public.documents (car_model) where mobile_visible = true;

-- Knowledge scopes and chat.

create table public.knowledge_vehicles (
 id uuid primary key default gen_random_uuid(),
 code text not null unique check (code ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
 name text not null check (length(trim(name)) > 0),
 year text not null default '', engine text not null default '', variant text not null default '',
 published boolean not null default false,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
alter table public.guide_categories add column knowledge_published boolean not null default false;
alter table public.documents add column index_document_name text unique;
alter table public.documents add column source_fidelity_verified boolean not null default false;
alter table public.documents add column vehicle_independent boolean not null default false;
alter table public.documents add column year text not null default '';
alter table public.documents add column engine text not null default '';
alter table public.documents add column variant text not null default '';
create table public.document_vehicles (
 id uuid primary key default gen_random_uuid(),
 document_id uuid not null references public.documents(id) on delete cascade,
 vehicle_id uuid not null references public.knowledge_vehicles(id) on delete cascade,
 created_at timestamptz not null default now(), unique(document_id, vehicle_id)
);
create table public.document_categories (
 id uuid primary key default gen_random_uuid(),
 document_id uuid not null references public.documents(id) on delete cascade,
 category_id uuid not null references public.guide_categories(id) on delete cascade,
 created_at timestamptz not null default now(), unique(document_id, category_id)
);
create table public.knowledge_videos (
 id uuid primary key default gen_random_uuid(),
 video_id text not null check (video_id ~ '^[A-Za-z0-9_-]{11}$'),
 vehicle_id uuid references public.knowledge_vehicles(id) on delete cascade,
 category_id uuid references public.guide_categories(id) on delete cascade,
 created_at timestamptz not null default now(),
 check (num_nonnulls(vehicle_id, category_id) = 1)
);
create unique index knowledge_vehicle_video on public.knowledge_videos(vehicle_id,video_id) where vehicle_id is not null;
create unique index knowledge_category_video on public.knowledge_videos(category_id,video_id) where category_id is not null;
create table public.chat_sessions (
 id uuid primary key default gen_random_uuid(),
 token_hash text not null check (length(token_hash) = 64),
 vehicle_id uuid references public.knowledge_vehicles(id) on delete restrict,
 category_id uuid references public.guide_categories(id) on delete restrict,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 check (num_nonnulls(vehicle_id, category_id) = 1)
);
create table public.chat_messages (
 id uuid primary key default gen_random_uuid(),
 session_id uuid not null references public.chat_sessions(id) on delete cascade,
 role text not null check (role in ('user','assistant')),
 content text not null,
 created_at timestamptz not null default now()
);
create index chat_messages_session on public.chat_messages(session_id,created_at,id);
-- Migrate only existing explicit vehicle associations. No general document is added automatically.
insert into public.knowledge_vehicles(code,name)
 select distinct car_model, initcap(car_model) from public.documents where car_model <> 'general';
insert into public.document_vehicles(document_id,vehicle_id)
 select d.id,v.id from public.documents d join public.knowledge_vehicles v on v.code=d.car_model;
do $$
declare t text;
begin
 foreach t in array array['knowledge_vehicles','document_vehicles','document_categories','knowledge_videos','chat_sessions','chat_messages'] loop
  execute format('alter table public.%I enable row level security',t);
  execute format('revoke all on public.%I from anon, authenticated',t);
  execute format('grant all on public.%I to service_role',t);
 end loop;
 foreach t in array array['knowledge_vehicles','chat_sessions'] loop
  execute format('create trigger content_updated_at before update on public.%I for each row execute function public.content_updated_at()',t);
 end loop;
end $$;
-- A chat scope is immutable even for direct service-role updates.
create function public.chat_scope_immutable() returns trigger language plpgsql as $$
begin
 if new.vehicle_id is distinct from old.vehicle_id or new.category_id is distinct from old.category_id then
  raise exception 'Start a new chat to change knowledge scope';
 end if;
 return new;
end $$;
create trigger chat_scope_immutable before update on public.chat_sessions for each row execute function public.chat_scope_immutable();

-- Document extraction and indexing.

alter table public.documents drop constraint documents_status_check;
alter table public.documents add constraint documents_status_check
 check (status in ('uploaded','processing','awaiting_index','processed','failed'));
alter table public.documents
 add column source_revision uuid not null default gen_random_uuid(),
 add column extraction_storage_path text,
 add column extraction_completed_at timestamptz,
 add column indexed_revision uuid,
 add column indexed_at timestamptz,
 add constraint documents_index_confirmation check (
   indexed_revision is null or
   (indexed_revision = source_revision and indexed_at is not null and chunk_count > 0 and status = 'processed')
 );
-- Legacy processed rows stay intact, but are ineligible for remote chat until reprocessed
-- and confirmed by the MacBook service. No legacy local index is presumed to exist there.
create index documents_awaiting_index on public.documents(created_at, id) where status = 'awaiting_index';
comment on column public.documents.source_revision is 'Rotated on replacement or a new OCR attempt; rejects stale RAG results.';
comment on column public.documents.indexed_revision is 'Set only by an authenticated RAG success acknowledgement.';
-- Existing RLS/service-role-only grants remain in force. No new public policies.

-- Shared vehicle catalogue, maintenance schedules, and content publication.

create table public.vehicle_manufacturers (
 id uuid primary key default gen_random_uuid(), name text not null check (length(trim(name)) > 0),
 active boolean not null default true, created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create unique index manufacturer_name_unique on public.vehicle_manufacturers(lower(trim(name)));
create table public.vehicle_models (
 id uuid primary key default gen_random_uuid(), manufacturer_id uuid not null references public.vehicle_manufacturers(id) on delete restrict,
 name text not null check (length(trim(name)) > 0), active boolean not null default true,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create unique index model_identity_unique on public.vehicle_models(manufacturer_id,lower(trim(name)));
alter table public.knowledge_vehicles add column model_id uuid references public.vehicle_models(id) on delete restrict;
alter table public.knowledge_vehicles add column powertrain text not null default 'petrol' check (powertrain in ('petrol','diesel'));
alter table public.knowledge_vehicles add column active boolean not null default true;
create unique index vehicle_identity_unique on public.knowledge_vehicles(model_id,year,lower(trim(engine)),lower(trim(variant)),powertrain) where model_id is not null;
create table public.maintenance_items (
 id uuid primary key default gen_random_uuid(), title text not null check (length(trim(title)) > 0),
 category text not null default '', description text not null default '', action text not null check (action in ('inspect','replace','service')),
 active boolean not null default true, created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create unique index maintenance_item_identity_unique on public.maintenance_items(lower(trim(title)),action);
create table public.manufacturer_schedules (
 id uuid primary key default gen_random_uuid(), vehicle_id uuid not null references public.knowledge_vehicles(id) on delete restrict,
 revision integer not null default 1 check (revision > 0), status text not null default 'draft' check (status in ('draft','published','superseded')),
 entries jsonb not null default '[]' check (jsonb_typeof(entries) = 'array'),
 verified_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(vehicle_id,revision), check (status <> 'published' or verified_at is not null)
);
create unique index one_published_vehicle_schedule on public.manufacturer_schedules(vehicle_id) where status='published';
alter table public.documents add column document_type text not null default 'other_reference' check (document_type in ('owners_manual','maintenance_booklet','service_manual','other_reference'));
alter table public.documents add column published boolean not null default false;
-- Preserve eligibility of existing confirmed material; new uploads start as drafts.
update public.documents set published=true where status='processed' and indexed_revision=source_revision and chunk_count>0;
alter table public.documents add column replacement_for_id uuid references public.documents(id) on delete restrict;
alter table public.documents add column superseded_by_id uuid references public.documents(id) on delete set null;
alter table public.documents add constraint replacement_not_self check (replacement_for_id is distinct from id);
alter table public.documents add constraint publication_requires_index check (not published or (status='processed' and indexed_revision is not null and indexed_revision=source_revision and chunk_count>0));
-- Replace the old fixed manual labels with backend-managed stable vehicle codes.
alter table public.documents drop constraint documents_car_model_check;
alter table public.guide_categories add column description text not null default '';
alter table public.guide_categories add column display_order integer not null default 0 check (display_order>=0);
alter table public.guide_categories add column published boolean not null default true;
alter table public.guides add column description text not null default '';
alter table public.guides add column reading_minutes integer check (reading_minutes>0);
alter table public.guides add column related_lesson_ids uuid[] not null default '{}';
alter table public.guides add column maintenance_item_ids uuid[] not null default '{}';
alter table public.emergency_playbooks add column category text not null default '';
alter table public.emergency_playbooks add column description text not null default '';
alter table public.emergency_playbooks add column safety_warnings text not null default '';
do $$ declare t text; begin
 foreach t in array array['vehicle_manufacturers','vehicle_models','maintenance_items','manufacturer_schedules'] loop
  execute format('alter table public.%I enable row level security',t);
  execute format('revoke all on public.%I from anon, authenticated',t);
  execute format('grant all on public.%I to service_role',t);
  execute format('create trigger content_updated_at before update on public.%I for each row execute function public.content_updated_at()',t);
 end loop;
end $$;
-- Atomic publication switches. Service-role only, after FastAPI validation/review.
create function public.publish_document(document_id uuid) returns public.documents language plpgsql as $$
declare candidate public.documents; previous public.documents;
begin
 select * into candidate from public.documents where id=document_id for update;
 if not found then raise exception 'Document missing'; end if;
 if candidate.superseded_by_id is not null then raise exception 'Document superseded'; end if;
 if candidate.status<>'processed' or candidate.indexed_revision is distinct from candidate.source_revision or candidate.chunk_count<1 then raise exception 'Indexing not confirmed'; end if;
 if candidate.replacement_for_id is not null then
  select * into previous from public.documents where id=candidate.replacement_for_id for update;
  if not found then raise exception 'Replacement source missing'; end if;
  if previous.superseded_by_id is not null and previous.superseded_by_id<>candidate.id then raise exception 'Replacement source already superseded'; end if;
  update public.documents set published=false,mobile_visible=false,superseded_by_id=candidate.id where id=previous.id;
 end if;
 update public.documents set published=true,mobile_visible=true where id=document_id returning * into candidate;
 return candidate;
end $$;
create function public.publish_manufacturer_schedule(schedule_id uuid) returns public.manufacturer_schedules language plpgsql as $$
declare candidate public.manufacturer_schedules;
begin
 select * into candidate from public.manufacturer_schedules where id=schedule_id;
 if not found then raise exception 'Schedule missing'; end if;
 -- Lock the vehicle to serialize competing revisions.
 perform 1 from public.knowledge_vehicles where id=candidate.vehicle_id for update;
 select * into candidate from public.manufacturer_schedules where id=schedule_id for update;
 if candidate.status='superseded' then raise exception 'Schedule superseded'; end if;
 update public.manufacturer_schedules set status='superseded' where vehicle_id=candidate.vehicle_id and status='published' and id<>schedule_id;
 update public.manufacturer_schedules set status='published',verified_at=now() where id=schedule_id returning * into candidate;
 return candidate;
end $$;
revoke all on function public.publish_document(uuid), public.publish_manufacturer_schedule(uuid) from public,anon,authenticated;
grant execute on function public.publish_document(uuid), public.publish_manufacturer_schedule(uuid) to service_role;

-- Personal vehicles, maintenance records, and authenticated chat ownership.

create table public.user_vehicles (
 user_id uuid not null references public.app_users(id) on delete cascade,
 id text not null check (length(id) between 1 and 200),
 catalogue_id uuid not null references public.knowledge_vehicles(id) on delete restrict,
 name text not null default '', plate_number text not null default '',
 mileage integer not null check (mileage>=0),
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 primary key(user_id,id)
);
alter table public.app_users add column active_vehicle_id text;
alter table public.app_users add constraint user_active_vehicle_fk
 foreign key(id,active_vehicle_id) references public.user_vehicles(user_id,id)
 on delete set null(active_vehicle_id);
create table public.user_tasks (
 user_id uuid not null, id text not null check (length(id) between 1 and 200), vehicle_id text not null,
 item_id uuid references public.maintenance_items(id) on delete restrict,
 title text not null check (length(trim(title))>0), category text not null default '',
 action text not null check (action in ('inspect','replace','service')),
 schedule_source text not null check (schedule_source in ('none','custom','manufacturer')),
 custom_rule jsonb check (custom_rule is null or jsonb_typeof(custom_rule)='object'),
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 primary key(user_id,id), unique(user_id,vehicle_id,id),
 foreign key(user_id,vehicle_id) references public.user_vehicles(user_id,id) on delete cascade,
 check (schedule_source<>'custom' or custom_rule is not null)
);
create unique index user_standard_item_unique on public.user_tasks(user_id,vehicle_id,item_id) where item_id is not null;
create table public.service_records (
 user_id uuid not null, id text not null check (length(id) between 1 and 200), vehicle_id text not null, task_id text,
 title text not null, category text not null default '', mileage integer not null check (mileage>=0),
 performed_at timestamp not null, notes text not null default '', cost numeric check (cost>=0),
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 primary key(user_id,id),
 foreign key(user_id,vehicle_id) references public.user_vehicles(user_id,id) on delete cascade,
 foreign key(user_id,vehicle_id,task_id) references public.user_tasks(user_id,vehicle_id,id) on delete set null(task_id)
);
create index service_vehicle_history on public.service_records(user_id,vehicle_id,performed_at desc);
create table public.learning_progress (
 user_id uuid not null references public.app_users(id) on delete cascade,
 id uuid not null references public.guides(id) on delete cascade,
 completed boolean not null default false,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(), primary key(user_id,id)
);
create table public.incident_records (
 user_id uuid not null references public.app_users(id) on delete cascade,
 id text not null check (length(id) between 1 and 200),
 payload jsonb not null check (jsonb_typeof(payload)='object'), revision integer not null check (revision>0),
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(), primary key(user_id,id)
);
alter table public.chat_sessions add column user_id uuid references public.app_users(id) on delete cascade;
alter table public.chat_sessions add column user_vehicle_id text;
-- Anonymous legacy sessions remain stored but are rejected by the authenticated API.
create index chat_sessions_owner on public.chat_sessions(user_id);
create or replace function public.chat_scope_immutable() returns trigger language plpgsql as $$
begin
 if new.vehicle_id is distinct from old.vehicle_id or new.category_id is distinct from old.category_id
    or new.user_id is distinct from old.user_id or new.user_vehicle_id is distinct from old.user_vehicle_id then
  raise exception 'Start a new chat to change owner or knowledge scope';
 end if;
 return new;
end $$;
do $$ declare t text; begin
 foreach t in array array['user_vehicles','user_tasks','service_records','learning_progress','incident_records'] loop
  execute format('alter table public.%I enable row level security',t);
  execute format('revoke all on public.%I from anon, authenticated',t);
  execute format('grant all on public.%I to service_role',t);
  execute format('create trigger content_updated_at before update on public.%I for each row execute function public.content_updated_at()',t);
 end loop;
end $$;

commit;

