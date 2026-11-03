-- Persistent browser capture queue. Apply once to an existing installation.
begin;

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
commit;
