"""HTTP transport for the existing pipeline. No retrieval or model changes.

Start with: python -m rag.service (requires the root RAG dependencies).
Only FastAPI's server-resolved scope and history should reach this private API.
"""
import logging
from time import perf_counter
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
from shared.schedule_drafting import ScheduleDraftRequest, ScheduleDraftResponse
from shared.document_testing import DocumentTestRequest, DocumentTestReply

from shared.observability import configure, ready, shutdown, request_monitor

configure("rag")


@asynccontextmanager
async def lifespan(app):
    # Model imports and cached weights can take several minutes on a cold start.
    # Report each stage while the launcher waits for application readiness.
    startup_logger = logging.getLogger("uvicorn.error")
    # An unavailable encoder leaves the scoped lexical fallback operational.
    if (settings.CHROMA_PATH / "chroma.sqlite3").is_file():
        started = perf_counter()
        startup_logger.info("RAG startup: loading embedding model %s and running warmup", settings.EMBEDDING_MODEL)
        try:
            from rag.app.embedding.embedder import embed_query
            await asyncio.to_thread(embed_query, "vehicle manual")
            startup_logger.info("RAG startup: embedding model ready in %.1fs", perf_counter() - started)
        except Exception as error:
            logging.getLogger(__name__).warning("Embedding warmup unavailable (%s)", type(error).__name__)
        if settings.RAG_RERANK:
            started = perf_counter()
            startup_logger.info("RAG startup: loading reranker %s", settings.RERANK_MODEL)
            try:
                from rag.app.retrieval.hybrid import reranker
                await asyncio.to_thread(reranker)
                startup_logger.info("RAG startup: reranker ready in %.1fs", perf_counter() - started)
            except Exception as error:
                logging.getLogger(__name__).warning("Reranker warmup unavailable (%s)", type(error).__name__)
    startup_logger.info("RAG startup: model warmup finished; starting HTTP service")
    worker = None
    if os.getenv('RAG_INDEX_WORKER_MODE', 'external') == 'embedded':
        from rag.index_worker import start_embedded
        worker = start_embedded()
    ready()
    try:
        yield
    finally:
        if worker:
            stop, thread = worker
            stop.set()
            startup_logger.info('Waiting for the current indexing pass to finish before shutdown')
            await asyncio.to_thread(thread.join)
        shutdown()


app = FastAPI(lifespan=lifespan)
app.middleware("http")(request_monitor)
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
    activity_context: dict | None = None
    assistance: Literal['explain', 'simplify'] | None = None


class Answer(BaseModel):
    answer: str = Field(min_length=1)
    answer_sections: list[dict] = Field(default_factory=list, max_length=16)
    route: str = 'rag'
    videos: list[dict] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    attachments: list[SourceAttachmentReference] = Field(default_factory=list, max_length=5)
    external_warning: bool = False
    manual_relevant: bool = False
    response_type: str = 'manual_only'
    suggested_activity: Literal['service_plan'] | None = None
    recommended_guides: list[dict] = Field(default_factory=list, max_length=2)


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
def visual_description(original: UploadFile = File(), source_page: UploadFile | None = File(default=None),
                       authorization: str = Header(default='')):
    verify_service_credentials(authorization)
    from pathlib import Path
    import tempfile
    from rag.app.generation.descriptions import describe_asset
    limit = 10 * 1024 * 1024
    with tempfile.TemporaryDirectory() as directory:
        paths = []
        for name, upload in [('original.png', original), ('page.png', source_page)]:
            if upload is None:
                continue
            data = upload.file.read(limit + 1)
            if not data or len(data) > limit:
                raise HTTPException(413, 'Source image is empty or exceeds 10 MB.')
            path = Path(directory) / name
            path.write_bytes(data)
            paths.append(path)
        result, reused = describe_asset(paths[0], settings.OUTPUT_DIR / 'visual-descriptions',
                                        page_image=paths[1] if len(paths) > 1 else None)
    return {**result, 'cache_reused': reused}


@app.post('/v1/youtube-channels/{channel_id}/sync', status_code=202)
def sync_youtube_channel(channel_id: UUID, request: YouTubeSyncRequest,
                         background: BackgroundTasks, authorization: str = Header(default='')):
    verify_service_credentials(authorization)
    from rag.app.youtube.worker import sync_channel
    background.add_task(sync_channel, str(channel_id), str(request.sync_id))
    return {'status': 'queued'}


def verify_revisions(scope, *, allow_partial=False):
    """Never hand an incomplete or stale managed index to RAG."""
    document_ids = scope.get('document_ids', [])
    if not document_ids:
        return scope
    from rag.app.embedding.vector_store import VectorStore
    try:
        store = VectorStore(create=False)
    except Exception as error:
        if not allow_partial:
            raise
        logger.warning('Manual index unavailable (%s)', type(error).__name__)
        return {**scope, 'document_ids': [], 'document_metadata': {},
                'unavailable_documents': list(document_ids)}
    valid, unavailable = [], []
    for name in document_ids:
        try:
            metadata = scope.get('document_metadata', {}).get(name, {})
            revision = metadata.get('index_revision')
            if not revision:
                raise ValueError('Missing managed document revision')
            source_path = settings.OUTPUT_DIR / 'sources' / f'{name}.json'
            if source_path.parent.resolve() != (settings.OUTPUT_DIR / 'sources').resolve():
                raise ValueError('Invalid managed source name')
            source_manifest = json.loads(source_path.read_text(encoding='utf-8'))
            document_id = metadata['document_id']
            if (source_manifest.get('format_version') != 2
                    or source_manifest.get('document_id') != document_id
                    or source_manifest.get('source_revision') != revision):
                raise ValueError('Source manifest requires reprocessing')
            records = store.collection.get(where={'document_name': name}, include=['metadatas'])
            expected_count = metadata.get('indexed_chunk_count')
            if (not records['ids'] or (expected_count is not None and len(records['ids']) != expected_count)
                    or any(m.get('document_id') != document_id or m.get('index_revision') != revision
                           or m.get('format_version') != 2 for m in records['metadatas'])):
                raise ValueError('The authorised document revision is not completely indexed')
        except Exception as error:
            if not allow_partial:
                raise
            logger.warning('Excluded unavailable manual revision (%s)', type(error).__name__)
            unavailable.append(name)
        else:
            valid.append(name)
    return {**scope, 'document_ids': valid,
            'document_metadata': {name: scope['document_metadata'][name] for name in valid},
            'unavailable_documents': unavailable}


@app.post('/v1/chat', response_model=Answer)
async def chat(request: Request, authorization: str = Header(default='')):
    verify_service_credentials(authorization)
    if (request.scope.get('scope_type') not in {'auto', 'vehicle', 'category'}
            or not request.scope.get('scope_id')):
        raise HTTPException(422, 'A resolved knowledge scope is required.')
    try:
        from shared.safety import immediate_emergency
        scope = request.scope
        if not immediate_emergency(request.message):
            scope = await asyncio.to_thread(verify_revisions, request.scope, allow_partial=True)
        from rag.app.query import handle_query
        return Answer.model_validate(await handle_query(request.message,
            history=[message.model_dump() for message in request.history], scope=scope,
            vehicle_profile=request.vehicle_profile.model_dump(mode='json') if request.vehicle_profile else None,
            maintenance_context=request.maintenance_context.model_dump(mode='json') if request.maintenance_context else None,
            activity_context=request.activity_context, assistance=request.assistance))
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


@app.post('/v1/document-test', response_model=DocumentTestReply)
async def document_test(request: DocumentTestRequest, authorization: str = Header(default='')):
    verify_service_credentials(authorization)
    scope = request.scope
    names = scope.get('document_ids', [])
    if (scope.get('scope_type') not in {'vehicle', 'category'} or not scope.get('scope_id')
            or len(names) != 1 or set(scope.get('document_metadata', {})) != set(names)
            or scope.get('content_sources') or scope.get('video_ids', []) != []):
        raise HTTPException(422, 'Document previews require exactly one resolved document and context.')
    try:
        await asyncio.to_thread(verify_revisions, scope)
        from rag.app.query import handle_query
        trace = {}
        answer = await handle_query(request.message, scope=scope, admin_trace=trace)
        return DocumentTestReply.model_validate({key: answer[key] for key in
            ('answer', 'response_type', 'route', 'sources', 'attachments')} | trace)
    except Exception:
        logger.exception('Document preview failed')
        raise HTTPException(503, 'The document test could not complete. Check indexing and service availability, then retry.') from None


@app.post('/v1/schedule-draft', response_model=ScheduleDraftResponse)
async def schedule_draft(request: ScheduleDraftRequest, authorization: str = Header(default='')):
    verify_service_credentials(authorization)
    if len(request.model_dump_json()) > 100000:
        raise HTTPException(413, 'This table is too large to draft in one request. Use manual schedule entry.')
    try:
        from rag.app.generation.schedule_drafting import draft_schedule
        return await asyncio.to_thread(draft_schedule, request)
    except Exception:
        logger.exception('Schedule drafting failed')
        raise HTTPException(503, 'The AI service could not draft this table. Retry or use manual entry.') from None


if __name__ == '__main__':
    rag_logger = logging.getLogger('rag')
    rag_logger.setLevel(logging.INFO)
    rag_logger.addHandler(logging.StreamHandler())
    rag_logger.propagate = False
    import uvicorn
    uvicorn.run(app, host=os.getenv('RAG_HTTP_HOST', '127.0.0.1'),
                port=int(os.getenv('RAG_HTTP_PORT', '8001')))
