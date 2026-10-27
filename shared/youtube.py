"""YouTube channel URL validation shared by admin and ingestion."""
import re
from urllib.parse import quote, unquote, urlsplit


def parse_channel_url(value):
    url = urlsplit(value.strip())
    if url.scheme not in {"http", "https"} or url.netloc.lower() not in {
        "youtube.com", "www.youtube.com", "m.youtube.com",
    }:
        raise ValueError("Enter a YouTube channel URL, such as https://www.youtube.com/@handle.")
    parts = unquote(url.path).strip("/").split("/")
    if parts[0].startswith("@") and len(parts[0]) > 1:
        field, identifier, rest = "forHandle", parts[0], parts[1:]
        path = identifier
    elif len(parts) >= 2 and parts[0] == "channel" and re.fullmatch(r"UC[A-Za-z0-9_-]{22}", parts[1]):
        field, identifier, rest = "id", parts[1], parts[2:]
        path = "channel/" + identifier
    elif len(parts) >= 2 and parts[0] == "user" and parts[1]:
        field, identifier, rest = "forUsername", parts[1], parts[2:]
        path = "user/" + identifier
    else:
        raise ValueError("Use a /@handle, /channel/UC..., or /user/... channel URL.")
    if any(character.isspace() or ord(character) < 32 for character in identifier) or "/" in identifier:
        raise ValueError("Invalid YouTube channel name.")
    if rest and rest not in (["videos"], ["shorts"], ["streams"], ["featured"], ["about"]):
        raise ValueError("Invalid channel URL path.")
    return "https://www.youtube.com/" + quote(path, safe="/@_-"), {field: identifier}
