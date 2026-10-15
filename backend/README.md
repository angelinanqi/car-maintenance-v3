# Backend API

FastAPI handles accounts, permissions, admin content, personal maintenance data,
Supabase storage, document processing, and requests to the private AI service.

## Run

Complete the [root setup](../README.md) for `.env` and Supabase first. From the
repository root, using Python 3.12:

```powershell
py -3.12 -m venv .venv-api
.\.venv-api\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv-api\Scripts\python.exe -m backend
```

- API documentation: http://127.0.0.1:8000/docs.
- Health check: http://127.0.0.1:8000/health (process liveness only).
- Run one backend process; processing locks and recovery depend on this.
- PDF extraction needs a separate MinerU installation and `MINERU_EXECUTABLE`.
- AI chat and document indexing need the separate [RAG processes](../rag/README.md).
- Browser access uses session cookies and CSRF; mobile uses bearer tokens.

Set `NEXT_PUBLIC_API_URL` and `CORS_ORIGINS` for the admin's browser connection.
For a physical phone on the LAN, bind `BACKEND_HOST=0.0.0.0` and use the server's
reachable address. Keep the Supabase service-role key and other secrets on the server.

## Personal vehicle context in chat

Every authenticated mobile `/chat` request loads the account's current
`active_vehicle_id` from `app_users`, reads its owned `user_vehicles` row, and joins
`knowledge_vehicles`, `vehicle_models`, and `vehicle_manufacturers`. The private
RAG request carries a separate `vehicle_profile` with the saved name, plate,
odometer in kilometres, catalogue identity, make, model, year, engine, variant,
powertrain, and last profile update time. It is refreshed for every turn, including
restored conversations. The mobile client does not supply or override this data.

The profile is personal context, not a shared Chroma document. It can support
profile facts under the `[P1]` citation; manufacturer procedures and specifications
still require eligible document evidence. Service records and maintenance tasks
are not part of the personal profile.

Existing scope publication requirements still apply. Category
chats include the active profile when one is selected; accounts without an active
vehicle have no personal context, and admin knowledge previews remain impersonal.
Changing vehicles requires the matching separate conversation. If the profile
changes while an answer is being prepared, the request returns 409 for retry.

This uses the existing schema in `supabase/initial_schema.sql`; no migration or
sample-data import is required. Configure the database, account authentication,
and private RAG connection as described in the root setup. Production code has no
sample-folder fallback. Verify these flows manually with your configured services.

## Published guides and reviewed emergency protocols

The chatbot loads current published content from Supabase on every request.
Publishing a learning guide makes its text retrievable immediately; it does not
require a Chroma indexing job. Draft guides and guides in unpublished categories
are excluded. Vehicle scopes include all visible guides because the current
schema has no guide-to-vehicle applicability relation. Category scopes include
their own guides plus uncategorized guides. These are educational sources, not
manufacturer evidence for a particular vehicle's specifications or intervals.

Emergency protocols must be published, have a review date, source reference,
scenario key, and ordered steps. The existing admin **Review and publish** action
provides this state; editing instructions returns them to draft and clears review.
Protocols are shared across scopes. The source snapshot retains warnings and
all ordered steps. It contains text only: image-only and video-only guides are
not used as factual evidence.

The private RAG service ranks this live text with the existing BM25 retriever and
combines relevant sources with the separately retrieved manual passages. Answers
identify source types, titles, IDs and revisions; protocol citations also include
the review date and source reference. Both clients display these distinctions.
Immediate emergency queries retain the fixed safety response and append the
matching reviewed protocol verbatim, without model inference. No matching
reviewed protocol leaves the existing safety response in place.

A published knowledge scope is usable with a published guide or reviewed protocol
even when it has no manual. Specifications still require applicable manufacturer
evidence. Unpublishing, deletion, category hiding and edits affect the next query;
if eligibility or content changes during a reply, that reply is rejected for retry.
The backend rejects citations to unknown or stale content. No migration or sample
data is needed for this flow.
