# Maintenance assistance API

All routes use `/admin/maintenance-assistance` and require an administrator session.
Cookie-authenticated writes also require the existing Origin and X-CSRF-Token
checks. Bearer sessions follow the application's existing authentication rules.

Apply `supabase/migrations/20261018_maintenance_assistance.sql` once for an existing
database. Fresh databases include it in `initial_schema.sql`. The backend uses
only its normal dependencies and the dependency-free RAG assistance module; no
running RAG service, shared worker filesystem, Chroma, Gemini or OCR is required.

## Endpoints

| Method | Relative path | Purpose |
| --- | --- | --- |
| GET | `/documents` | Paginated document discovery with revision and extraction availability |
| GET | `/documents/{id}?source_revision=…` | Complete inventory, confirmations, suggestions, bookmarks and review version |
| GET | `/documents/{id}/tables?source_revision=…` | Ranked tables; supports `q`, `classification`, `offset`, `limit` |
| GET | `/documents/{id}/original?source_revision=…` | Authorized original PDF or plain-text Markdown for exactly the current revision |
| PUT | `/documents/{id}/confirmation` | Replace the confirmed table/column selection for this revision |
| POST | `/documents/{id}/suggestions` | Generate suggestions from the persisted confirmed selection |
| GET | `/documents/{id}/suggestions?source_revision=…` | Read suggestions; supports `status`, `offset`, `limit` |
| PATCH | `/documents/{id}/suggestions/{suggestion_id}` | Accept, correct, reject or revise a mapping; original evidence is immutable |
| GET | `/matches?name=…` | Suggested text matches against active standard items |
| POST | `/documents/{id}/bookmarks` | Add a manual PDF page or Markdown section bookmark |
| POST | `/documents/{id}/manual-items` | Add a manually entered item under a confirmed table or manual bookmark |

Writes carry `source_revision` and the latest returned `version`. A stale document
revision, superseded source (except historical original viewing), concurrent editor version or busy document returns
409. Unknown document/item/suggestion IDs return 404. Invalid choices return 422.

GET inventory caches extraction-derived data in the private application database.
The original extraction package is downloaded only on the first load, on an
assistance-version change, or when extraction becomes available after manual-only
review. This supports separate backend and RAG machines. Missing extraction
produces an empty inventory with `extraction_available: false`; manual bookmarks
and items can still be saved. Malformed extraction is reported without changing
document status or starting OCR/indexing. Unknown page metadata stays unknown.

## Workflow

1. Discover a document and its `source_revision`.
2. Load its inventory. Read the returned review `version`.
3. Confirm selected tables/columns (zero-based indices):

```json
{
  "source_revision": "<document revision UUID>",
  "version": 1,
  "tables": [
    {"table_id": "table-00000", "confirmed": true, "columns": [0], "excluded_rows": [0, 8]}
  ]
}
```

4. POST suggestions using the new version:

```json
{"source_revision": "<document revision UUID>", "version": 2}
```

5. Review an individual suggestion, URL-encoding its identifier if needed:

```json
{
  "source_revision": "<document revision UUID>",
  "version": 3,
  "status": "accepted",
  "edited_name": "Engine oil filter",
  "mapped_item_id": "<standard maintenance item UUID>"
}
```

`mapped_item_id` may be null. Accepting an unmapped suggestion does not publish a
schedule. Use the existing `/admin/maintenance-items` endpoints to create standard
items, then explicitly confirm the mapping. The review response's `reviewed_by`
and `reviewed_at` identify its last writer; this is not an immutable audit log.

Regeneration retains review edits/mappings when the source text and columns are
unchanged. Changing confirmations discards affected unaccepted generated
suggestions; accepted ones must first be marked suggested/rejected. A rejected
suggestion remains in review storage. No frequency is generated or copied.

Manual bookmarks use `title`, `page`, `section`, `notes`, plus revision/version.
PDFs require a positive page; Markdown requires a section and forbids a PDF page.
Manual items use `table_id`, `name`, optional `mapped_item_id`, and revision/version.
They carry `manual: true` and `original_text: null` to distinguish admin entry from
extracted evidence. Review them with the same suggestion PATCH endpoint.

## Source rendering and scope

For PDF navigation append `#page=N` to `original_url`. The endpoint verifies the
revision before serving bytes. Tables contain native MinerU bounding boxes when
available; highlighting/coordinate conversion belongs to the future viewer.
Markdown is served as plain text; use table IDs/section paths/source offsets for
navigation. Raw `source.original_html`, original cells and original Markdown are
untrusted evidence: display as text, or render only the existing sanitized `html`
field using appropriate client safeguards.

The API does not publish schedules, alter document publication, change source
packages or write embeddings. Existing frequency/schedule endpoints remain in
charge of verified rules. Imported schedule rules retain `sourceRevision`,
`sourceTableId` and `sourceSuggestionId`. Validation verifies the current document
revision, table confirmation/bookmark and accepted item mapping. Markdown rules
use reviewed table/bookmark references without a PDF page; PDF rules still require
a page before publication. Existing PDF/page-only schedules remain supported.

The database review/cache is separate from disposable local RAG artifacts.
Reprocessing yields a new revision and new review state; previous rows are retained
until the parent document is deleted and never silently applied to the new source.
Document APIs continue to control source replacement and deletion. This feature
uses the same supported single-backend-process locking model as existing editors.

## Admin schedule editor

Open **Service schedules**, select a vehicle and an associated PDF or Markdown
source. The source stays alongside the review/editor. Browse all tables or filter
by relevance; confirm the tables and description columns, exclude unwanted rows,
then save confirmation and extract suggestions. Review names and mappings; create
standard items in place when necessary. Save decisions and import accepted mapped
items into the draft. Duplicate standard items already in the draft are skipped.
Use manual bookmarks/items when extraction misses a table or item.

Enter frequencies individually or select multiple items and apply a recurring
interval. Previous interval values are offered only from this vehicle's schedules
and require explicit selection. Review groups by frequency, save the draft,
validate, check the source verification box, then publish. No frequencies are
inferred and publication never happens from extraction review alone.

The editor marks unsaved review changes and retains edits in other suggestion
rows when one row is saved. Conflicts appear as errors and require reloading the
current review. The SQL migration described above remains required in a live
Supabase project.

After deployment, verify this workflow against a configured database and an
admin-reviewed source document, including source viewing, draft validation and
explicit publication.
