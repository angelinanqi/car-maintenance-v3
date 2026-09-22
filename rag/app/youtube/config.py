from pathlib import Path

CHANNEL_FILE = Path("youtube_channel.txt")
OUTPUT_DIR = Path("output/youtube")
COLLECTION_NAME = "youtube_chunks"
# overlap always consist of whole snippets
CHUNK_TOKENS = 400
OVERLAP_TOKENS = 60
