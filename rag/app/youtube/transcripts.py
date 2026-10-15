from rag.config.settings import YOUTUBE_TRANSCRIPT_LANGUAGES
import json
from youtube_transcript_api import YouTubeTranscriptApi

def save_json(path, data):
    # replace a cache only after the entire JSON file has been written
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def fetch_transcript(video_id):

    available = list(YouTubeTranscriptApi().list(video_id))
    for language in YOUTUBE_TRANSCRIPT_LANGUAGES:
        for generated in (False, True):
            for transcript in available:
                if (
                    transcript.language_code == language
                    and transcript.is_generated == generated
                ):
                    fetched = transcript.fetch()
                    return {
                        "video_id": video_id,
                        "language": language,
                        "is_generated": generated,
                        "snippets": fetched.to_raw_data(),
                    }
    raise ValueError("No transcript in YOUTUBE_TRANSCRIPT_LANGUAGES available (translation disabled).")
