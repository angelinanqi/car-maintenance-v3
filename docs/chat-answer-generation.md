# Chat answer generation

The answer-writing instructions live in `rag/app/generation/answer_prompt.py`.
Gemini chooses the wording, Markdown structure, explanation length and relevant
attachments. JSON blocks carry citations and provenance; they are not a fixed
user-facing template. Table and saved-record instructions are added only when
those sources are present.

The writer receives the user's actual text and conversation history. Search
rewrites are used for retrieval, not passed back as a competing user request.
An answer may include a focused follow-up question without being discarded by
the response validator.

Applicable sources remain authoritative for vehicle-specific facts. General
knowledge can explain concepts and routine, low-risk owner tasks when excerpts
are incomplete. Exact vehicle specifications, locations, service intervals and
hazardous procedures must not be filled from memory. General guidance is marked
in response metadata and distinguished naturally in the answer, without a forced
disclaimer on each paragraph.

The chatbot accepts text input only. Asking for a description of labels or symptoms
is supported; asking for uploaded photos, videos or files is not. The app can still
display existing source images and videos.

The renderer validates source/reference IDs, numeric provenance and original-page
support for table claims. It no longer automatically adds every table sharing a
cited page: attachment selection belongs to the model. Citation validation and
attachment selection remain separate.

An unsupported numeric claim is withheld with a brief explanation, while other
independently valid blocks survive. This prevents a rejected specification from
erasing an otherwise useful general answer.

This change does not rebuild the index or alter retrieval settings. Emergency fast
paths still use the existing application responses; improving their content or
media requires separate work. The mobile answer/attachment layout is unchanged.

Run the focused checks:

```sh
.venv/bin/python -m unittest rag.app.generation.test_grounded
```

The running RAG service must restart to load Python changes. With the normal
launcher, stop the existing app terminal and start `./start-app.command` again;
do not start a second stack alongside the first one. No re-ingestion, migration or
mobile rebuild is required.
