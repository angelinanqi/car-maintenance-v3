"""Admin-managed channels and the private ingestion worker handoff."""
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, field_validator, model_validator

from backend import auth, db, settings
from backend.locks import content_lock
from backend.routes.indexing import require_rag_service
from backend.services.documents import now
from backend.services.youtube import dispatch_sync
from shared.models import InputModel
from shared.youtube import parse_channel_url

router = APIRouter(prefix="/admin/youtube-channels", tags=["YouTube channels"],
                   dependencies=[Depends(auth.require_admin)])
internal_router = APIRouter(prefix="/internal/youtube-channels", tags=["RAG integration"],
                            dependencies=[Depends(require_rag_service)])


class ChannelInput(InputModel):
    url: str = Field(min_length=1, max_length=500)

    @field_validator("url")
    @classmethod
    def channel_url(cls, value):
        return parse_channel_url(value)[0]


class SyncRequest(InputModel):
    sync_id: UUID


class SyncResult(SyncRequest):
    status: Literal["ready", "failed"]
    channel_id: str | None = Field(default=None, pattern=r"^UC[A-Za-z0-9_-]{22}$")
    channel_title: str = Field(default="", max_length=500)
    summary: dict[str, int] = Field(default_factory=dict)
    error: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def valid_result(self):
        if self.status == "ready" and (not self.channel_id or self.error or self.summary.get("videos_failed", 0)):
            raise ValueError("A successful sync requires a channel ID and no failures.")
        if self.status == "failed" and not self.error:
            raise ValueError("A failed sync requires an error message.")
        if any(value < 0 for value in self.summary.values()):
            raise ValueError("Sync counts cannot be negative.")
        return self


@router.get("")
def list_channels(offset: int = Query(0, ge=0), limit: int = Query(settings.API_PAGE_SIZE, ge=1, le=1000)):
    return db.list_rows("youtube_channels", offset=offset, limit=limit)


@router.post("", status_code=201)
def add_channel(request: ChannelInput):
    with content_lock("youtube-channels"):
        if db.all_rows("youtube_channels", url=request.url):
            raise HTTPException(409, "This YouTube channel has already been added.")
        row = db.insert("youtube_channels", {"url": request.url, "sync_id": str(uuid4()), "status": "queued"})
    return dispatch_sync(row)


@router.post("/{channel_id}/sync", status_code=202)
def queue_sync(channel_id: UUID):
    with content_lock(channel_id):
        row = db.get("youtube_channels", channel_id)
        if row["status"] in {"queued", "syncing"}:
            raise HTTPException(409, "This channel is already queued or syncing.")
        row = db.update("youtube_channels", channel_id, {
            "status": "queued", "sync_id": str(uuid4()), "error": None,
        })
    return dispatch_sync(row)


def current_sync(channel_id, sync_id):
    row = db.get("youtube_channels", channel_id)
    if row["sync_id"] != str(sync_id):
        raise HTTPException(409, "This channel sync is out of date.")
    return row


@internal_router.post("/{channel_id}/start")
def start_sync(channel_id: UUID, request: SyncRequest):
    with content_lock(channel_id):
        row = current_sync(channel_id, request.sync_id)
        if row["status"] != "queued":
            raise HTTPException(409, "This channel sync has already started or finished.")
        return db.update("youtube_channels", channel_id, {"status": "syncing", "error": None})


@internal_router.post("/{channel_id}/result")
def finish_sync(channel_id: UUID, result: SyncResult):
    with content_lock(channel_id):
        row = current_sync(channel_id, result.sync_id)
        # A retry after a lost HTTP response cannot undo a completed sync.
        if row["status"] in {"ready", "failed"}:
            if row["status"] != result.status:
                raise HTTPException(409, "This channel sync has already finished.")
            return row
        if row["status"] != "syncing":
            raise HTTPException(409, "Start this sync before reporting its result.")
        values = result.model_dump(mode="json", exclude={"sync_id"})
        if not result.channel_id:
            values.pop("channel_id")
            values.pop("channel_title")
        if result.status == "ready":
            values["last_synced_at"] = now()
        return db.update("youtube_channels", channel_id, values)
