-- Existing installations: run once in the Supabase SQL Editor before deploying.
-- This only extends the allowed status values; it does not change saved documents.
begin;
alter table public.documents drop constraint documents_status_check;
alter table public.documents add constraint documents_status_check
    check (status in ('uploaded', 'processing', 'awaiting_confirmation', 'awaiting_index', 'processed', 'failed'));
commit;
