-- Existing installations: run in the Supabase SQL Editor before deploying.
begin;

alter table public.guide_categories add column if not exists archived boolean not null default false;
alter table public.guide_categories add constraint archived_categories_hidden
    check (not archived or (not published and not knowledge_published));

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

notify pgrst, 'reload schema';
commit;
