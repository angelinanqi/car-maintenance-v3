from rag.config.settings import YOUTUBE_API_TIMEOUT, YOUTUBE_PAGE_SIZE
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from rag.config.settings import YOUTUBE_API_URL, YOUTUBE_CHANNEL_URL
from shared.youtube import parse_channel_url


def read_channel(channel_url=None):
    value = channel_url if channel_url is not None else YOUTUBE_CHANNEL_URL
    if not value:
        raise ValueError("Provide --channel-url, or add a channel in the admin dashboard.")
    return parse_channel_url(value)[1]


def api_get(resource, api_key, **parameters):
    url = (
        YOUTUBE_API_URL.rstrip("/") + "/"
        + resource
        + "?"
        + urlencode(parameters)
    )
    # Keep the key out of URLs and exception messages.
    request = Request(url, headers={"X-Goog-Api-Key": api_key})
    try:
        with urlopen(request, timeout=YOUTUBE_API_TIMEOUT) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(
            f"YouTube Data API {resource}: HTTP {error.code}; check API key, API enablement and quota."
        ) from None
    except URLError:
        raise RuntimeError(f"YouTube Data API {resource}: connection failed.") from None


def discover_videos(channel_filter, api_key):
    if not api_key.strip():
        raise ValueError(
            "Set YOUTUBE_API_KEY in the root .env file or environment; enable YouTube Data API v3."
        )
    channels = api_get(
        "channels", api_key, part="snippet,contentDetails", **channel_filter
    ).get("items", [])
    if not channels:
        raise ValueError("YouTube channel not found. Check the channel URL.")
    channel = channels[0]
    playlist = channel["contentDetails"]["relatedPlaylists"]["uploads"]
    videos = {}
    page = ""
    while True:
        response = api_get(
            "playlistItems",
            api_key,
            part="snippet,contentDetails",
            playlistId=playlist,
            maxResults=YOUTUBE_PAGE_SIZE,
            pageToken=page,
        )
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            details = item.get("contentDetails", {})
            video_id = details.get("videoId", "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
                print("Skipping playlist item without a valid video ID.")
                continue
            thumbnails = snippet.get("thumbnails", {})
            videos[video_id] = {
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "published_at": details.get("videoPublishedAt", ""),
                "thumbnail_url": thumbnails.get(
                    "high", thumbnails.get("default", {})
                ).get("url", ""),
                "channel_id": channel["id"],
                "channel_title": channel["snippet"]["title"],
            }
        page = response.get("nextPageToken")
        if not page:
            return {
                "channel_id": channel["id"],
                "channel_title": channel["snippet"]["title"],
                "videos": list(videos.values()),
            }
