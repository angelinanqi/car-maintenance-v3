# Maintenance assistance — pipeline layer

This module consumes the **existing version-2 `elements.json`** produced for PDFs
by MinerU or directly from uploaded Markdown. It never runs OCR, changes source
records, calls an LLM, generates frequencies, or writes embeddings.

After successful ingestion, `rag.pipeline` writes a disposable table inventory to
`OUTPUT_DIR/maintenance/<document_id>_<source_revision>.json`. The indexing worker
also backfills/retries inventories for processed documents with locally saved
source manifests. It does not download old packages or rerun indexing to backfill.
Failures are logged independently and do not change indexing acknowledgements.
Worker reconciliation removes its obsolete inventories and generated suggestions.

Every table remains available, ordered by explainable keyword scores. Scores are
not probabilities. Original table records (including cell markup, legends,
context, provenance and continuation parts) are preserved. PDF page/box metadata
is conditional; Markdown uses element IDs, section paths and source offsets.
Treat raw markup as evidence, not trusted HTML. Use the existing sanitized `html`
field for display. No HTML is rendered by this module.

Cache identity includes the document revision, manifest digest and assistance
version. Writes are atomic. Unchanged inputs reuse the inventory. Admin decisions
are stored separately by the backend, never inside these disposable artifacts. Original source content remains authoritative in the extraction ZIP.

## Run without OCR or model dependencies

```sh
python3 -m rag.app.maintenance /path/to/elements.json --output-dir output
```

A saved `output/sources/<document_id>_<revision>.json` works as the input too.

Item extraction requires explicit confirmation and selected **zero-based** item
columns. Exclude header/category/legend rows where needed. For example:

```json
{
  "document_id": "00000000-0000-4000-8000-000000000001",
  "source_revision": "00000000-0000-4000-8000-000000000002",
  "tables": [
    {
      "table_id": "table-00000",
      "confirmed": true,
      "columns": [0],
      "excluded_rows": [0, 8]
    }
  ]
}
```

```sh
python3 -m rag.app.maintenance /path/to/elements.json --output-dir output \
  --selection /path/to/selection.json --catalogue /path/to/items.json
```

The optional catalogue is a JSON list with `id`, `title`, `action`, `category`,
and optionally `active`. Results include suggested text matches but never assign
an item automatically. Duplicate names are flagged, not merged. Selected cell
text is preserved verbatim alongside whitespace-normalized names. Merged cells,
possible header/note rows and incomplete labels remain available with uncertainty
flags. Rows marked as headers by extraction are excluded automatically. Merged
labels are not propagated to other rows. The admin must verify column choices,
row boundaries and action compatibility. Multiple tables can be selected.

Generated suggestions are written to `<document_id>_<revision>.suggestions.json`.
These contain no frequency rules and are never read by chat retrieval.

Python callers can use `build_catalogue(manifest)`, `prepare(manifest, output_dir)`
and `extract_items(catalogue, selection, standard_items)`. API inputs require
authorization and validation at the backend boundary. Confirmation
here is an explicit processing prerequisite, not proof of an authenticated review.

## Scope of this first stage

Admin APIs and the Service schedules editor consume these functions through the
backend review/cache table. See `backend/docs/maintenance-assistance.md` for the
workflow and database setup. Gemini cleanup is deferred;
this stage is deterministic. Schedule publication remains admin-verified through the application backend.
The pipeline adds no dependencies. Backend review state requires the database
setup described in the linked API documentation.
