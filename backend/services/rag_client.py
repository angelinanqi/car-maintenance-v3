"""Provider-independent HTTP boundary for the existing private RAG service."""
import logging
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend import settings
from shared.models import SourceAttachmentReference
from shared.models import MechanicQuestionDraft
from shared.mechanic_questions import general_questions

logger = logging.getLogger(__name__)


async def test_document(request):
    from shared.document_testing import DocumentTestReply
    if not settings.RAG_SERVICE_URL or not settings.RAG_SERVICE_TOKEN:
        raise HTTPException(503, "Configure the private RAG service before testing this document.")
    try:
        async with httpx.AsyncClient(timeout=settings.RAG_SERVICE_TIMEOUT, follow_redirects=False) as client:
            response = await client.post(settings.RAG_SERVICE_URL + "/v1/document-test",
                headers={"Authorization": "Bearer " + settings.RAG_SERVICE_TOKEN}, json=request.model_dump(mode="json"))
            response.raise_for_status()
            return DocumentTestReply.model_validate(response.json())
    except (httpx.HTTPError, ValidationError, ValueError) as error:
        logger.warning("Document test unavailable (%s)", type(error).__name__)
        raise HTTPException(503, "The document test service could not complete the request. Check indexing and service availability, then retry.") from None


async def draft_schedule(request):
    from shared.schedule_drafting import ScheduleDraftResponse
    if not settings.RAG_SERVICE_URL or not settings.RAG_SERVICE_TOKEN:
        raise HTTPException(503, "Configure the private RAG service before drafting a schedule with AI.")
    try:
        async with httpx.AsyncClient(timeout=settings.RAG_SERVICE_TIMEOUT, follow_redirects=False) as client:
            response = await client.post(settings.RAG_SERVICE_URL + "/v1/schedule-draft",
                headers={"Authorization": "Bearer " + settings.RAG_SERVICE_TOKEN},
                json=request.model_dump(mode="json"))
            response.raise_for_status()
            return ScheduleDraftResponse.model_validate(response.json())
    except (httpx.HTTPError, ValidationError, ValueError) as error:
        logger.warning("Schedule drafting unavailable (%s)", type(error).__name__)
        raise HTTPException(503, "AI drafting failed or returned an invalid response. Your saved review is unchanged; retry or enter the schedule manually.") from None


async def mechanic_questions(question, user_questions, vehicle_profile):
    if settings.RAG_SERVICE_URL and settings.RAG_SERVICE_TOKEN:
        try:
            # A general checklist remains available if tailored preparation is slow.
            async with httpx.AsyncClient(timeout=min(settings.RAG_SERVICE_TIMEOUT, 45), follow_redirects=False) as client:
                response = await client.post(settings.RAG_SERVICE_URL + '/v1/mechanic-questions',
                    headers={'Authorization': 'Bearer ' + settings.RAG_SERVICE_TOKEN},
                    json={'question': question, 'user_questions': user_questions, 'vehicle_profile': vehicle_profile})
                response.raise_for_status()
                data = response.json()
                draft = MechanicQuestionDraft.model_validate(data['draft'])
                if not isinstance(data.get('tailored'), bool):
                    raise ValueError('Invalid preparation result')
                return draft, data['tailored']
        except (httpx.HTTPError, ValidationError, ValueError, KeyError, TypeError) as error:
            logger.warning('Question preparation unavailable (%s)', type(error).__name__)
    return general_questions(question), False


class ChatAnswer(BaseModel):
    # Explicit public fields prevent internal prompts/diagnostics leaking to clients.
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    answer: str = Field(min_length=1)
    route: str = "rag"
    videos: list[dict] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    attachments: list[SourceAttachmentReference] = Field(default_factory=list, max_length=5)
    external_warning: bool = False
    manual_relevant: bool = False
    response_type: str = "manual_only"
    suggested_activity: Literal['service_plan'] | None = None
    recommended_guides: list[dict] = Field(default_factory=list, max_length=2)


async def query(message, history, scope, *, vehicle_profile=None, maintenance_context=None,
                activity_context=None, assistance=None):
    if not settings.RAG_SERVICE_URL or not settings.RAG_SERVICE_TOKEN:
        raise HTTPException(503, "The RAG service connection is not configured. Set RAG_SERVICE_URL and RAG_SERVICE_TOKEN on the backend to use the existing pipeline.")
    try:
        async with httpx.AsyncClient(timeout=settings.RAG_SERVICE_TIMEOUT, follow_redirects=False) as client:
            response = await client.post(settings.RAG_SERVICE_URL + "/v1/chat",
                headers={"Authorization": "Bearer " + settings.RAG_SERVICE_TOKEN},
                json={"message": message, "history": history, "scope": scope,
                      "vehicle_profile": vehicle_profile, "maintenance_context": maintenance_context,
                      "activity_context": activity_context, "assistance": assistance})
            response.raise_for_status()
            answer = ChatAnswer.model_validate(response.json()).model_dump(mode='json')
            metadata = scope.get('document_metadata', {})
            by_id = {str(v.get('document_id', key)): v for key, v in metadata.items()}
            by_id.update(metadata)
            content = {(s['source_type'], s['source_id']): s for s in scope.get('content_sources', [])}
            from backend.services.content_sources import resolve_guide_recommendations
            answer['recommended_guides'] = resolve_guide_recommendations(
                answer['recommended_guides'], scope.get('content_sources', []), strict=True)
            for source in answer['sources']:
                kind = source.get('source_type', 'manual')
                if kind == 'manual':
                    document = by_id.get(str(source.get('document_id')))
                    if document is None:
                        raise ValueError('The RAG service returned a source outside the resolved scope')
                    source['document_title'] = document['document_title']
                elif kind in {'personal_vehicle_profile', 'personal_maintenance'}:
                    personal = kind == 'personal_maintenance'
                    label = 'P2' if personal else 'P1'
                    if (not vehicle_profile or source.get('label') != label
                            or source.get('vehicle_id') != vehicle_profile['vehicle_id']):
                        raise ValueError('The RAG service returned another vehicle\'s personal source')
                    if personal and (not maintenance_context
                            or source.get('as_of') != maintenance_context['as_of']
                            or maintenance_context['vehicle_id'] != vehicle_profile['vehicle_id']):
                        raise ValueError('The RAG service returned stale maintenance evidence')
                    source.clear()
                    source.update(label=label, source_type=kind, vehicle_id=vehicle_profile['vehicle_id'],
                                  title='Saved maintenance records' if personal else 'Saved vehicle profile')
                    if personal:
                        source['as_of'] = maintenance_context['as_of']
                else:
                    current = content.get((kind, source.get('source_id')))
                    if current is None or source.get('revision') != current['revision']:
                        raise ValueError('The RAG service returned unpublished or stale content')
                    label = source.get('label')
                    source.clear()
                    source.update(label=label, source_type=kind, source_id=current['source_id'],
                                  revision=current['revision'], title=current['title'],
                                  source_reference=current.get('source_reference', ''), reviewed_at=current.get('reviewed_at'))
            for source in answer['attachments']:
                document = by_id.get(str(source.get('document_id')))
                if document is None:
                    raise ValueError('The RAG service returned a source outside the resolved scope')
                if document.get('document_title'):
                    source.setdefault('document_title', document['document_title'])
            return answer
    except (httpx.HTTPError, ValidationError, ValueError) as error:
        logger.warning("RAG service request failed (%s)", type(error).__name__)
        raise HTTPException(503, "The chatbot service is unavailable or returned an invalid response. Please retry.") from None
