"""Run one admin-requested channel sync in the private RAG service."""
import logging
import os
from threading import Lock

import httpx
from filelock import Timeout

from rag.config import settings

logger = logging.getLogger(__name__)
sync_lock = Lock()


def sync_channel(channel_id, sync_id):
    # Serialize admin requests without blocking document indexing or the API.
    with sync_lock:
        url = os.getenv('RAG_BACKEND_URL', 'http://127.0.0.1:8000').rstrip('/')
        token = os.getenv('RAG_SERVICE_TOKEN', '')
        with httpx.Client(base_url=url, headers={'Authorization': 'Bearer ' + token},
                          timeout=settings.SUPABASE_TIMEOUT, follow_redirects=False) as client:
            path = f"/internal/youtube-channels/{channel_id}"
            try:
                response = client.post(path + "/start", json={"sync_id": sync_id})
                response.raise_for_status()
                channel = response.json()
            except httpx.HTTPError:
                logger.exception("Could not start YouTube channel sync %s", channel_id)
                return
            try:
                from rag.app.youtube.pipeline import run_youtube_ingestion
                # Pin resolved identities so a handle change cannot switch channels.
                channel_url = ("https://www.youtube.com/channel/" + channel["channel_id"]
                               if channel.get("channel_id") else channel["url"])
                result = run_youtube_ingestion(channel_url=channel_url)
                failed = result["summary"]["videos_failed"]
                result.update(status="failed" if failed else "ready",
                              error=f"{failed} videos failed to index. Retry syncing to resume." if failed else None)
            except Timeout:
                result = {"status": "failed", "error": "YouTube ingestion is busy. Click Retry sync after it finishes."}
            except Exception as error:
                logger.exception("YouTube channel sync failed for %s", channel_id)
                message = str(error) if isinstance(error, (ValueError, RuntimeError)) else "YouTube ingestion failed. Check the RAG service logs and retry."
                result = {"status": "failed", "error": message[:2000]}
            result["sync_id"] = sync_id
            try:
                response = client.post(path + "/result", json=result)
                response.raise_for_status()
            except httpx.HTTPError:
                logger.exception("Could not report YouTube sync result for %s", channel_id)
