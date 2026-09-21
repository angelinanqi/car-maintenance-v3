import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, unquote
from urllib.request import Request, urlopen
from .config import CHANNEL_FILE


def read_channel(path=CHANNEL_FILE):
    try:
        value = path.read_text(encoding="utf-8-sig").strip()
    except FileNotFoundError:
        raise ValueError(
            f"Create {path} and paste your public YouTube channel URL."
        ) from None
    url = urlparse(value)
    parts = unquote(url.path).strip("/").split("/")
    if url.scheme not in ("https", "http") or url.netloc not in (
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
    ):
        raise ValueError(
            f"{path} must contain one YouTube channel URL (for example https://www.youtube.com/@handle)."
        )
    # Channel subpages such as /videos are harmless.
    if parts[0].startswith("@") and len(parts[0]) > 1:
        field, identifier, rest = "forHandle", parts[0], parts[1:]
    elif (
        len(parts) >= 2
        and parts[0] == "channel"
        and re.fullmatch(r"UC[\w-]{22}", parts[1], re.ASCII)
    ):
        field, identifier, rest = "id", parts[1], parts[2:]
    elif len(parts) >= 2 and parts[0] == "user" and parts[1]:
        field, identifier, rest = "forUsername", parts[1], parts[2:]
    else:
        raise ValueError(
            "Use a /@handle, /channel/UC..., or /user/... URL; legacy /c/ URLs need the channel's handle instead."
        )
    if rest and rest not in (
        ["videos"],
        ["shorts"],
        ["streams"],
        ["featured"],
        ["about"],
    ):
        raise ValueError("Invalid channel URL path.")
    return {field: identifier}


def api_get(resource, api_key, **parameters):
    url = (
        "https://www.googleapis.com/youtube/v3/"
        + resource
        + "?"
        + urlencode(parameters)
    )
    # Keep the key out of URLs and exception messages.
    request = Request(url, headers={"X-Goog-Api-Key": api_key})
    try:
        with urlopen(request, timeout=30) as response:
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
        raise ValueError("YouTube channel not found. Check youtube_channel.txt.")
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
            maxResults=50,
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
                "title": snippet.get("title", video_id),
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
