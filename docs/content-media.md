# Learning guides and emergency media

Apply `supabase/migrations/20261103_content_media.sql` and
`supabase/migrations/20261103_guide_indexing.sql`, then
`supabase/migrations/20261103_emergency_media_indexing.sql` to an existing database before
deploying the backend and RAG service together. New databases include these schemas
in `supabase/init.sql`. Keep the existing private RAG credentials, indexing worker,
Gemini configuration and persistent Chroma volume configured.

## Learning guides

Write and publish the guide using the existing editor. Insert images and YouTube
embeds directly into its content or exploration examples. There is no separate
media registration or review step. Publication controls chat eligibility.
Existing manually entered image descriptions and video transcript segments are
retained and indexed; saving in the simplified editor does not overwrite them.

The existing RAG index worker polls guide handoffs alongside document handoffs.
This also backfills existing published guides. A small HTML adapter supplies
section context, image assets, structured tables and source metadata, then uses
the same HTML parser, normalization, section chunking, embedding model, Chroma
collection and hybrid retrieval as documents. Guide content is no longer sent to
chat as a whole-guide text snapshot or embedded during a chat request.

Images are detected automatically, resolved from uploaded storage assets or
bounded public HTTP(S) downloads, and described through the existing private
visual-description endpoint. The existing vision implementation caches results
by asset hash, model and prompt. Generated identification remains labelled as
generated and retains uncertainty. It is not a substitute for explicit vehicle
compatibility or authoritative specifications. Guide images are not sent as
pixels on every chat query; retrieved descriptions link to their original URLs
through the existing chat media response. HTML tables retain their original
cells, headers, spans and notes through the existing source-element handling and
can be returned through the existing protected attachment endpoints.

Embedded YouTube URLs and ordinary YouTube links enter the existing YouTube
ingestor. Channel-indexed videos and videos shared by multiple guides are reused.
Available captions are cached, chunked and indexed with timestamps. Captions are
not audio transcription or visual frame analysis. Videos retain the existing
supplementary recommendation behavior rather than becoming ordinary answer
evidence. Without captions, metadata fallback and the original guide link remain
available; a preparation warning allows an explicit retry. Guide-only videos are
excluded from global recommendations unless an eligible published guide in the
current scope includes them. Previously channel-indexed videos keep their normal
independent eligibility.

`guide_indexes` stores content hashes, extraction revisions, processed media,
warnings and indexing status independently of the guide's publication status.
The guide editor shows preparation status and a retry action. Image or video
failures do not prevent the ordinary guide reader from displaying the guide;
available guide text and assets can still be indexed. A retry creates a new
index revision and refetches assets, including images changed behind the same URL.
Previously generated vision descriptions are reused when the bytes are unchanged.

Every chat request resolves the current published guide and matching processed
index revision. Edits, unpublishing, hidden categories and deletion immediately
exclude stale records through the existing scope checks; the worker reconciles
and removes its obsolete vectors and local assets on subsequent polls. Late
indexing acknowledgements cannot activate a superseded revision. Restarting the
service reuses complete indexes; missing local guide indexes can be rebuilt from
their stored extraction archives. Shared YouTube records are retained because
other guides or independently indexed channels may still use them.

## Emergency media

Emergency media belongs to an individual written step. Save the playbook and step,
then upload files using the same shared Chakra `FileUploadField` as document
uploads. The editor displays file names, sizes, previews, validation errors and
indeterminate upload/description progress. Emergency media URLs cannot be entered.
Legacy external links must be removed or replaced with owned uploads before the
playbook can be saved or republished.

Images: PNG, JPEG, WebP and GIF, within configured `IMAGE_MAX_BYTES` (10 MiB by
default), up to 8192 pixels per side, 16 million pixels total and 100 frames. Bytes
and extensions are checked with Pillow. The existing private visual-description
endpoint generates a draft using its existing hash cache. Admins edit and review
the description before publishing. A vision failure leaves the uploaded image
available and displays an actionable warning; a manual description/review is then
required.

Videos: MP4 files within the existing `DOCUMENT_MAX_BYTES` (50 MiB by default),
containing one H.264 video stream (up to 3840 pixels per side), with optional AAC
audio. **Install FFmpeg and put `ffprobe` on the backend PATH.** Uploads fail closed
with a clear availability error if validation is unavailable. ffprobe inspects
and counts decodable frames with a bounded execution time and file-only protocol
access. Unsupported codecs, damaged streams, empty files and oversized files are
rejected. No size limit was increased. Supabase's content bucket must accept
`video/mp4` and the configured maximum file size, alongside its existing image
formats. Provision bucket settings in deployment; the migration does not change
storage service configuration.

Every video requires a description of the demonstrated actions (at least six
words, five distinct words and 30 characters) on upload and save/publish. This
catches empty and generic labels; the admin remains responsible for the actual
content. Emergency videos are never transcribed and never enter the YouTube
pipeline. All emergency descriptions must be reviewed before publishing. Editing
description fields clears their checkbox; changing a playbook returns it to draft.
The backend independently verifies the asset belongs to that exact playbook and
step and replaces submitted size/hash/type metadata with trusted storage records.

`emergency_media_assets` stores immutable application-owned file references,
SHA-256 digests, MIME types and sizes. The files use the existing content bucket.
`emergency_indexes` uses the same durable handoff schema and shared preparation
service as learning guides. The existing index worker accepts emergency HTML
alongside guide HTML and document Markdown, then uses the same parser, chunker,
embedding model, persistent Chroma collection, hybrid retrieval and reranker.
Reviewed image/video descriptions are paragraph records with scenario, step ID,
step order and media ID; the original media URL is resolved by the backend from
the current published source, never generated by the model. No media bytes are
embedded. Revisions prevent duplicate work, exclude stale vectors immediately
from scopes, and let the worker clean obsolete records after edits, unpublishing
or deletion. Missing local indexes restore from their cached extraction archives.

The urgent safety route continues to return complete reviewed written protocols
without waiting for indexing, embeddings, vision, media downloads or playback.
Its optional protocol read does not query the index-status table. Ordinary chat
retrieves emergency chunks through the shared persistent index; it does not
re-embed whole emergency snapshots on each question. The existing emergency and
vehicle safety restrictions still apply.

Flutter uses the existing `ContentRepository`, `ApiClient` and `LocalStore`
synchronisation. Actual image and video bytes are downloaded, size/hash checked,
then written to staged files and atomically renamed before the guide manifest is
committed. Hash-identical media is reused across revisions; cleanup respects
references from other steps/guides. Interrupted or invalid downloads retain the
previous committed revision and files. On a first download failure, complete
written instructions are still saved, with a missing-media warning and retry on
later synchronisation. Missing files never hide instructions or safety warnings.
Old image caches remain readable.

Uploaded emergency MP4s use Flutter's official `video_player` (2.11.1, compatible
with this project's Dart 3.11 SDK), with local files preferred, play/pause and seek
controls, bounded responsive sizing and explicit errors. Playback starts only
when requested. Run `flutter pub get` before building the mobile app. The same
media cards render chat attachments; matching downloaded emergency assets are
resolved from the local manifest before display. Other learning video links retain
their existing behavior. Failed chat requests offer the existing emergency screen
so downloaded written guides remain reachable without the AI backend. AI-generated
chat itself still requires the existing online service; no local model or second
emergency reasoning engine is added. Offline videos target Android/iOS; device codec support
and airplane-mode operation must be checked on the release devices.

## Verification

Restore the test trees from the evaluation archive before running regression tests.
Run `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` and
`node --test tests/*.test.mjs`, `npm run build` in `web`, and
`flutter test` in `mobile`. Guide tests exercise HTML adaptation, structured tables,
image source resolution, publication/revision checks, worker reuse and cleanup,
and the real shared parsing/chunking/persistent Chroma path using fixed embeddings
instead of provider calls. Live Gemini, Supabase and YouTube integration requires
the configured services and the database migration.
