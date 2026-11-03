from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import Field

from backend import auth, db
from backend.services import website_imports as service
from shared.models import InputModel

router = APIRouter(prefix='/website-imports', tags=['Website imports'], dependencies=[Depends(auth.require_admin)])


class WebsiteImport(InputModel):
    url: str = Field(min_length=1, max_length=2048)
    idempotency_key: UUID
    media: Literal['screen', 'print'] = 'screen'


@router.post('', status_code=202)
def submit(request: WebsiteImport, identity=Depends(auth.require_admin)):
    return service.public_job(service.submit(identity['user']['id'], request.idempotency_key, request.url, request.media))


@router.get('')
def list_jobs(offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100)):
    jobs = db.read_rows(db.client().table(service.TABLE).select('*')
        .order('created_at', desc=True).order('id', desc=True).range(offset, offset + limit - 1))
    return [service.public_job(job) for job in jobs]


@router.post('/manual')
def manual(url: str = Form(..., max_length=2048), idempotency_key: UUID = Form(...),
           file: UploadFile = File(...), identity=Depends(auth.require_admin)):
    job = service.submit(identity['user']['id'], idempotency_key, url, manual=True)
    if job['status'] == 'completed':
        return service.public_job(job)
    return service.public_job(service.attach_manual(job['id'], file))


@router.get('/{job_id}')
def get_job(job_id: UUID):
    return service.public_job(db.get(service.TABLE, job_id))


@router.post('/{job_id}/retry', status_code=202)
def retry(job_id: UUID):
    service.enabled()
    return service.public_job(service.rpc('control_website_import', p_id=str(job_id), p_action='retry'))


@router.post('/{job_id}/cancel')
def cancel(job_id: UUID):
    return service.public_job(service.rpc('control_website_import', p_id=str(job_id), p_action='cancel'))


@router.post('/{job_id}/manual-pdf')
def attach_pdf(job_id: UUID, file: UploadFile = File(...)):
    return service.public_job(service.attach_manual(job_id, file))
