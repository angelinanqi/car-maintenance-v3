-- Admin-managed YouTube ingestion. Apply once to an existing installation.
begin;

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
create trigger content_updated_at before update on public.youtube_channels
    for each row execute function public.content_updated_at();
alter table public.youtube_channels enable row level security;
revoke all on public.youtube_channels from public, anon, authenticated, service_role;
grant select, insert, update, delete on public.youtube_channels to service_role;

commit;
