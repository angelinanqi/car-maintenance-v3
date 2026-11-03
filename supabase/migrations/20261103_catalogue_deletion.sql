-- Safe removal of unused catalogue entries. Existing records are preserved.
begin;

-- Coverage and video assignments must never disappear through a vehicle cascade.
alter table public.document_vehicles drop constraint document_vehicles_vehicle_id_fkey;
alter table public.document_vehicles add constraint document_vehicles_vehicle_id_fkey
    foreign key (vehicle_id) references public.knowledge_vehicles(id) on delete restrict;
alter table public.knowledge_videos drop constraint knowledge_videos_vehicle_id_fkey;
alter table public.knowledge_videos add constraint knowledge_videos_vehicle_id_fkey
    foreign key (vehicle_id) references public.knowledge_vehicles(id) on delete restrict;

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

notify pgrst, 'reload schema';
commit;
