"""Preview catalogue usage and remove only unreferenced entries in one transaction."""
from typing import Literal
from uuid import UUID
from fastapi import HTTPException
from pydantic import Field
from postgrest.exceptions import APIError
from backend import db
from backend.locks import content_lock
from shared.models import InputModel

CatalogueKind = Literal['manufacturers', 'models', 'vehicles']
TABLES = {'manufacturers': 'vehicle_manufacturers', 'models': 'vehicle_models', 'vehicles': 'knowledge_vehicles'}


class RemovalInput(InputModel):
    fingerprint: str = Field(pattern=r'^[a-f0-9]{32}$')


def rpc(name, values):
    try:
        return db.client().rpc(name, values).execute().data
    except APIError as error:
        if error.code in {'PT404', 'PT409', 'PT422'}:
            raise HTTPException(int(error.code[2:]), error.message) from None
        if error.code in {'23503', '23001'}:
            raise HTTPException(409, 'A linked record now uses this entry. Refresh the deletion details or deactivate it.') from None
        if error.code in {'PGRST202', 'PGRST204', 'PGRST205', '42703', '42P01', '42883'}:
            raise HTTPException(503, 'Safe catalogue deletion needs a database update. Apply supabase/migrations/20261103_catalogue_deletion.sql and retry.') from None
        raise


def removal_impact(kind: CatalogueKind, record_id: UUID):
    result = rpc('catalogue_removal_impact', {'p_kind': kind, 'p_record_id': str(record_id)})
    identity = str(record_id)
    groups = {
        'models': ('Models', f'/admin/vehicles?section=models&manufacturer={identity}'),
        'vehicles': ('Vehicle variants', f'/admin/vehicles?section=vehicles&model={identity}'),
        'documents': ('Document assignments', f'/admin/vehicles/{identity}#vehicle-documents'),
        'schedules': ('Service schedules (all versions)', f'/admin/schedules?vehicle={identity}'),
        'videos': ('Video assignments', None),
        'user_vehicles': ('User vehicles and their saved records', None),
        'review_questions': ('Clarification questions', '/admin/review-questions'),
        'chats': ('Saved chat sessions', None),
        'test_questions': ('Saved document test questions', '/admin/kb'),
        'test_runs': ('Document test history', '/admin/kb'),
    }
    result['blockers'] = [dict(key=key, label=groups[key][0], count=count, href=groups[key][1])
                          for key, count in result['references'].items() if count]
    related = result.get('related', {})
    for blocker in result['blockers']:
        key = blocker['key']
        if key == 'videos':
            blocker['items'] = [dict(name=row['video_id'], href=f'https://www.youtube.com/watch?v={row["video_id"]}')
                                for row in related.get('videos', [])]
        else:
            documents = related.get('test_documents' if key in {'test_questions', 'test_runs'} else key, [])
            blocker['items'] = [dict(name=row['name'], href=f'/admin/kb/{row["id"]}') for row in documents]
    return result


def remove(kind: CatalogueKind, record_id: UUID, request: RemovalInput):
    with content_lock(record_id):
        rpc('remove_catalogue_entry', {'p_kind': kind, 'p_record_id': str(record_id),
                                     'p_expected_impact': request.fingerprint})


def deactivate(kind: CatalogueKind, record_id: UUID):
    with content_lock(record_id):
        # Patch only availability; preserve identity, publication and other edits.
        return db.update(TABLES[kind], record_id, {'active': False})
