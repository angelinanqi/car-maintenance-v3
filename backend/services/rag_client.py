"""Provider-independent HTTP boundary for the existing private RAG service."""
import logging

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend import settings
from backend.models import SourceAttachmentReference

logger = logging.getLogger(__name__)


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


async def query(message, history, scope):
    if not settings.RAG_SERVICE_URL or not settings.RAG_SERVICE_TOKEN:
        raise HTTPException(503, "The RAG service connection is not configured. Set RAG_SERVICE_URL and RAG_SERVICE_TOKEN on the backend to use the existing pipeline.")
    try:
        async with httpx.AsyncClient(timeout=settings.RAG_SERVICE_TIMEOUT, follow_redirects=False) as client:
            response = await client.post(settings.RAG_SERVICE_URL + "/v1/chat",
                headers={"Authorization": "Bearer " + settings.RAG_SERVICE_TOKEN},
                json={"message": message, "history": history, "scope": scope})
            response.raise_for_status()
            answer = ChatAnswer.model_validate(response.json()).model_dump(mode='json')
            metadata = scope.get('document_metadata', {})
            by_id = {str(v.get('document_id', key)): v for key, v in metadata.items()}
            by_id.update(metadata)
            for source in answer['sources'] + answer['attachments']:
                document = by_id.get(str(source.get('document_id')))
                if document is None:
                    raise ValueError('The RAG service returned a source outside the resolved scope')
                if document.get('document_title'):
                    source.setdefault('document_title', document['document_title'])
            return answer
    except (httpx.HTTPError, ValidationError, ValueError) as error:
        logger.warning("RAG service request failed (%s)", type(error).__name__)
        raise HTTPException(503, "The chatbot service is unavailable or returned an invalid response. Please retry.") from None
