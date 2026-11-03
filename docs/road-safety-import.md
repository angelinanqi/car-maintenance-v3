# Malaysian HTML content import

Source: `malaysian_car_maintenance_road_safety.html`. This is a standalone import,
not application runtime code. It uses the configured backend Supabase credentials,
content bucket, existing models, guide validation, emergency media validation and
emergency publication handler. No database migration or runtime change is required.

Run from the repository root:

```sh
.venv/bin/python -m pip install resvg-py==0.5.0
.venv/bin/python scripts/import_road_safety.py
.venv/bin/python scripts/import_road_safety.py --apply
.venv/bin/python -m unittest tests.test_road_safety_import
```

Without `--apply`, the importer parses and rasterises every diagram without network
access or database writes. The JSON report defaults to `output/road-safety-import.json`.

The six source learning categories retain their titles and article order. All 29
articles become learning guides. Two supporting guides, “Car Maintenance & Road
Safety” and “Recommended Video, Diagrams & Official Resources”, retain the overview,
image provenance note, shared resources and footer under Maintenance Essentials.
Navigation labels and the browser print button are interface controls, not imported
content. Original HTML remains the authoritative source.

The six emergency articles become playbooks with their original scenario IDs as
scenario keys. The common Malaysia emergency notice is each playbook's description;
immediate warnings populate safety warnings. The 41 procedure steps retain their
headings, paragraphs, captions and sequence. Fourteen closing paragraphs/source
references become additional ordered steps (55 stored steps total). The existing
mobile adapter additionally prepends Situation and Safety warnings. Emergency text
uses paragraph breaks and explicit original URLs because its reader is plain text.

All 70 embedded SVG diagrams are mechanically rendered to 640 × 340 PNGs, using the
existing content bucket and guide_images/emergency_media_assets relationships.
Emergency assets include canonical hashes, byte lengths and MIME types for existing
offline synchronisation. Their descriptions are copied from the supplied captions,
including the warning that these are illustrative icons. They are marked reviewed
for the explicitly requested publication; no generated descriptions, new diagrams,
video downloads or invented vehicle instructions are introduced. Generic diagrams
do not become vehicle-specific specifications. Both occurrences of the one original
YouTube URL stay in their original learning/resource placements. The suggestions
for additional videos remain text, without invented links.

Figure captions become paragraphs, `<b>` becomes `<strong>`, and fourth-level
headings become third-level headings to fit the current admin editor and Flutter
reader. Text, list items and links are compared in source-fidelity tests. There are
no source tables. The script fails on unexpected image formats rather than dropping
them. An import-only SVG renderer is sufficient; CairoSVG is not required.

IDs and storage paths are deterministic. Existing matching category names are
reused only when visible. Existing imported published records must match exactly;
changed records produce an error rather than being overwritten. Unrelated records
are neither updated nor deleted. Partial imports retain their own drafts and can
resume; writes are not one transaction, so inspect failures before rerunning. Keep
the source unchanged when rerunning. An edited source requires a deliberate migration.

Verification limits: database readback, publication validation, public endpoint
responses and downloaded asset bytes can be checked without a device. Actual Flutter
layout, admin browser editing, YouTube playback, indexing worker completion and
release-device airplane-mode operation require their respective running clients or
services. Do not infer those results from successful persistence.

## Execution results — 3 November 2026

Persisted and published to the configured Supabase database: six learning categories,
31 learning guides (29 articles plus two supporting guides), six emergency playbooks,
55 stored steps (41 procedures plus 14 closing/source steps), and 70 PNG diagrams.
The single YouTube video is retained at both original link placements.

Four import tests passed. Persisted content matched the constructed source payloads.
FastAPI TestClient exercised the real public route handlers against the configured
database: all 31 guides, six categories and six playbooks were returned. This was an
in-process API check, not a deployed server HTTP test. All 70 public PNG URLs returned
PNG bytes; all 41 emergency assets matched their stored hash and byte length.
YouTube oEmbed returned HTTP 200 and the title “How to check your tires in 5 mins |
THE WORKSHOP”. No missing media were found. One converted diagram was visually
inspected. The source's remaining suggested videos are still suggestions.

The first pass exposed a nullable model default for emergency status. The standalone
importer now explicitly inserts `draft`, then calls the existing publication handler;
no production model or database change was needed. Learning records created before
that failure were verified and preserved on resume.

Flutter SDK is unavailable in this environment, so Flutter tests and actual device
offline operation were not run. Browser layout/admin editing and RAG worker indexing
completion were not tested. Existing runtime/offline implementation was unchanged.
The machine-readable reports `road-safety-import.json`, `road-safety-verification.json`
and `road-safety-rerun.json` are preserved in the evaluation archive’s `output/` directory.

A full second `--apply` run completed successfully: existing published records and
assets matched, with no duplicate creation or content updates.
