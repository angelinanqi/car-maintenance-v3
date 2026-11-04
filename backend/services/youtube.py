"""Dispatch explicit admin sync requests to the private RAG service."""
import logging
import re
from urllib.parse import urlsplit, parse_qs

import httpx

from backend import db, settings
from backend.locks import content_lock

logger = logging.getLogger(__name__)


def restore_recommendations(videos, scope, channel_ids):
    """Keep saved public links only while their channel or scoped guide is allowed."""
    allowed = scope.get('video_ids', [])
    guides = set(scope.get('guide_video_ids', []))
    result = []
    seen = set()
    for video in videos:
        if not isinstance(video, dict) or not isinstance(video.get('url'), str):
            continue
        try:
            url = urlsplit(video['url'])
        except ValueError:
            continue
        identity = parse_qs(url.query).get('v', [''])[0]
        if (url.scheme != 'https' or url.netloc != 'www.youtube.com' or url.path != '/watch'
                or not re.fullmatch(r'[A-Za-z0-9_-]{11}', identity) or identity in seen):
            continue
        if allowed is not None:
            if identity not in allowed:
                continue
        elif identity not in guides and video.get('channel_id') not in channel_ids:
            continue
        seen.add(identity)
        result.append({**video, 'content_verified': False,
                       'notice': ('Generic demonstration. ' if video.get('vehicle_match') == 'generic' else 'External video. ')
                                 + 'Content and vehicle compatibility have not been verified.'})
        if len(result) == 2:
            break
    return result


def dispatch_sync(row):
    try:
        if not settings.RAG_SERVICE_URL or not settings.RAG_SERVICE_TOKEN:
            raise ValueError("The RAG service connection is not configured.")
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            response = client.post(
                settings.RAG_SERVICE_URL + f"/v1/youtube-channels/{row['id']}/sync",
                headers={"Authorization": "Bearer " + settings.RAG_SERVICE_TOKEN},
                json={"sync_id": row["sync_id"]},
            )
            response.raise_for_status()
    except (httpx.HTTPError, ValueError):
        logger.exception("Could not dispatch YouTube channel sync %s", row["id"])
        with content_lock(row["id"]):
            current = db.get("youtube_channels", row["id"])
            # Do not overwrite a newer request or a job that already started.
            if current["sync_id"] == row["sync_id"] and current["status"] == "queued":
                return db.update("youtube_channels", row["id"], {
                    "status": "failed",
                    "error": "Could not start syncing. Check the RAG service, then click Retry sync.",
                })
            return current
    return row


def recover_interrupted():
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        for row in db.all_rows("youtube_channels", status=["queued", "syncing"]):
            db.update("youtube_channels", row["id"], {
                "status": "failed",
                "error": "Syncing was interrupted by a backend restart. Click Retry sync to resume.",
            })
