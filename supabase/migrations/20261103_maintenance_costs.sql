begin;

-- NULL retains unknown attribution on historical records; costs are not backfilled.
alter table public.service_records
    add column performed_by text check (performed_by in ('self', 'mechanic'));

notify pgrst, 'reload schema';
commit;
