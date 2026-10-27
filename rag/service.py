"""HTTP transport for the existing pipeline. No retrieval or model changes.

Start with: python -m rag.service (requires the root RAG dependencies).
Only FastAPI's server-resolved scope and history should reach this private API.
"""
import logging
from contextlib import asynccontextmanager
import os
import secrets
import asyncio
import json
from typing import Literal
from uuid import UUID

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, UploadFile, File
from fastapi.exceptions import RequestValidationError
from shared.http_errors import http_error, validation_error
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, ConfigDict, Field
from rag.config import settings
from shared.models import PersonalVehicleProfile, PersonalMaintenanceContext, SourceAttachmentReference, MechanicQuestionDraft

@asynccontextmanager
async def lifespan(app):
    # Pay the local encoder's cold-start cost before advertising API readiness.
    # An unavailable encoder leaves the scoped lexical fallback operational.
    if (settings.CHROMA_PATH / "chroma.sqlite3").is_file():
        try:
            from rag.app.embedding.embedder import embed_query
            await asyncio.to_thread(embed_query, "vehicle manual")
        except Exception as error:
            logging.getLogger(__name__).warning("Embedding warmup unavailable (%s)", type(error).__name__)
        if settings.RAG_RERANK:
            try:
                from rag.app.retrieval.hybrid import reranker
                await asyncio.to_thread(reranker)
            except Exception as error:
                logging.getLogger(__name__).warning("Reranker warmup unavailable (%s)", type(error).__name__)
    yield


app = FastAPI(lifespan=lifespan)
app.add_exception_handler(RequestValidationError, validation_error)
app.add_exception_handler(StarletteHTTPException, http_error)
logger = logging.getLogger(__name__)


class Message(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    role: Literal['user', 'assistant']
    # Server-loaded assistant replies can exceed the user-message limit.
    content: str = Field(min_length=1)


class Request(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=settings.CHAT_MAX_MESSAGE_LENGTH)
    history: list[Message] = Field(default_factory=list, max_length=settings.CHAT_HISTORY_LIMIT)
    scope: dict
    vehicle_profile: PersonalVehicleProfile | None = None
    maintenance_context: PersonalMaintenanceContext | None = None


class Answer(BaseModel):
    answer: str = Field(min_length=1)
    route: str = 'rag'
    videos: list[dict] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    attachments: list[SourceAttachmentReference] = Field(default_factory=list, max_length=5)
    external_warning: bool = False
    manual_relevant: bool = False
    response_type: str = 'manual_only'


class MechanicQuestionsRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=4000)
    user_questions: list[str] = Field(default_factory=list, max_length=settings.CHAT_HISTORY_LIMIT)
    vehicle_profile: PersonalVehicleProfile | None = None


class MechanicQuestionsAnswer(BaseModel):
    draft: MechanicQuestionDraft
    tailored: bool


class YouTubeSyncRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sync_id: UUID


def verify_service_credentials(authorization):
    token = os.getenv('RAG_SERVICE_TOKEN', '')
    if len(token.encode()) < 32:
        raise HTTPException(503, 'Configure RAG_SERVICE_TOKEN with at least 32 bytes.')
    scheme, _, supplied = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not secrets.compare_digest(supplied.encode(), token.encode()):
        raise HTTPException(401, 'Invalid service credentials.')


@app.post('/v1/visual-description')
def visual_description(original: UploadFile = File(), source_page: UploadFile = File(),
                       authorization: str = Header(default='')):
    verify_service_credentials(authorization)
    from pathlib import Path
    import tempfile
    from rag.app.generation.descriptions import describe_asset
    limit = 10 * 1024 * 1024
    with tempfile.TemporaryDirectory() as directory:
        paths = []
        for name, upload in [('original.png', original), ('page.png', source_page)]:
            data = upload.file.read(limit + 1)
            if not data or len(data) > limit:
                raise HTTPException(413, 'Source image is empty or exceeds 10 MB.')
            path = Path(directory) / name
            path.write_bytes(data)
            paths.append(path)
        result, reused = describe_asset(paths[0], settings.OUTPUT_DIR / 'visual-descriptions',
                                        page_image=paths[1])
    return {**result, 'cache_reused': reused}


@app.post('/v1/youtube-channels/{channel_id}/sync', status_code=202)
def sync_youtube_channel(channel_id: UUID, request: YouTubeSyncRequest,
                         background: BackgroundTasks, authorization: str = Header(default='')):
    verify_service_credentials(authorization)
    from rag.app.youtube.worker import sync_channel
    background.add_task(sync_channel, str(channel_id), str(request.sync_id))
    return {'status': 'queued'}


def verify_revisions(scope):
    """Never hand an incomplete or stale managed index to RAG."""
    document_ids = scope.get('document_ids', [])
    if not document_ids:
        return
    expected = {name: metadata['index_revision'] for name, metadata in scope.get('document_metadata', {}).items()
                if metadata.get('index_revision')}
    if any(name not in expected for name in document_ids):
        raise ValueError('Missing managed document revision')
    from rag.app.embedding.vector_store import VectorStore
    store = VectorStore(create=False)
    for name in document_ids:
        source_path = settings.OUTPUT_DIR / 'sources' / f'{name}.json'
        if source_path.parent.resolve() != (settings.OUTPUT_DIR / 'sources').resolve():
            raise ValueError('Invalid managed source name')
        source_manifest = json.loads(source_path.read_text(encoding='utf-8'))
        document_id = scope['document_metadata'][name]['document_id']
        if (source_manifest.get('format_version') != 2
                or source_manifest.get('document_id') != document_id
                or source_manifest.get('source_revision') != expected[name]):
            raise ValueError('Source manifest requires reprocessing')
        records = store.collection.get(where={'document_name': name}, include=['metadatas'])
        expected_count = scope['document_metadata'][name].get('indexed_chunk_count')
        if (not records['ids'] or (expected_count is not None and len(records['ids']) != expected_count)
                or any(m.get('document_id') != document_id or m.get('index_revision') != expected[name]
                       or m.get('format_version') != 2 for m in records['metadatas'])):
            raise ValueError('The authorised document revision is not completely indexed')


@app.post('/v1/chat', response_model=Answer)
async def chat(request: Request, authorization: str = Header(default='')):
    verify_service_credentials(authorization)
    if (request.scope.get('scope_type') not in {'auto', 'vehicle', 'category'}
            or not request.scope.get('scope_id')):
        raise HTTPException(422, 'A resolved knowledge scope is required.')
    try:
        await asyncio.to_thread(verify_revisions, request.scope)
        from rag.app.query import handle_query
        return Answer.model_validate(await handle_query(request.message,
            history=[message.model_dump() for message in request.history], scope=request.scope,
            vehicle_profile=request.vehicle_profile.model_dump(mode='json') if request.vehicle_profile else None,
            maintenance_context=request.maintenance_context.model_dump(mode='json') if request.maintenance_context else None))
    except Exception:
        logger.exception('Existing RAG pipeline request failed')
        raise HTTPException(503, 'The AI service is temporarily unavailable.') from None


@app.post('/v1/mechanic-questions', response_model=MechanicQuestionsAnswer)
async def mechanic_questions(request: MechanicQuestionsRequest, authorization: str = Header(default='')):
    verify_service_credentials(authorization)
    try:
        from rag.app.generation.mechanic_questions import prepare_questions
        result = await asyncio.to_thread(prepare_questions, request.question, request.user_questions,
            request.vehicle_profile.model_dump(mode='json') if request.vehicle_profile else None)
        return MechanicQuestionsAnswer.model_validate(result)
    except Exception:
        logger.exception('Mechanic question preparation failed')
        raise HTTPException(503, 'The AI service is temporarily unavailable.') from None


if __name__ == '__main__':
    rag_logger = logging.getLogger('rag')
    rag_logger.setLevel(logging.INFO)
    rag_logger.addHandler(logging.StreamHandler())
    rag_logger.propagate = False
    import uvicorn
    uvicorn.run(app, host=os.getenv('RAG_HTTP_HOST', '127.0.0.1'),
                port=int(os.getenv('RAG_HTTP_PORT', '8001')))
