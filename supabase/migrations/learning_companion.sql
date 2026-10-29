-- Apply after automatic_chat_context.sql. Existing articles and chats remain readable.
begin;
alter table public.guides
    add column if not exists beginner_friendly boolean not null default false,
    add column if not exists featured_in_companion boolean not null default false,
    add column if not exists learning_outcomes text[] not null default '{}',
    add column if not exists exploration jsonb;
alter table public.learning_progress
    add column if not exists current_step_id text,
    add column if not exists guide_revision text;
alter table public.chat_sessions add column if not exists activity jsonb;
alter table public.chat_messages add column if not exists reply jsonb;
alter table public.chat_settings
    add column if not exists mechanic_template jsonb,
    add column if not exists mechanic_details text[] not null default '{}';

create table if not exists public.service_plans (
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
create index if not exists service_plans_owner on public.service_plans(user_id, vehicle_id, created_at);
create table if not exists public.saved_items (
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
create index if not exists saved_items_owner on public.saved_items(user_id, created_at);
alter table public.service_plans enable row level security;
alter table public.saved_items enable row level security;
-- Personal APIs use the server service role after account/ownership validation.
revoke all on public.service_plans, public.saved_items from anon, authenticated;
grant all on public.service_plans, public.saved_items to service_role;
drop trigger if exists service_plans_updated on public.service_plans;
create trigger service_plans_updated before update on public.service_plans
    for each row execute function public.content_updated_at();
drop trigger if exists saved_items_updated on public.saved_items;
create trigger saved_items_updated before update on public.saved_items
    for each row execute function public.content_updated_at();
commit;
