# Supabase database

[`fresh_schema.sql`](fresh_schema.sql) is the complete fresh-install database
definition, incorporating the initial schema and all eight current migrations.
Run the entire file once in a fresh Supabase project's SQL Editor. It creates all
32 application tables, constraints, indexes, functions, triggers, permissions,
Storage bucket definitions and initial presets in one transaction.

The original [`initial_schema.sql`](initial_schema.sql) and every file in
[`migrations/`](migrations/) remain unchanged in their existing locations. A fresh
installation using `fresh_schema.sql` does not need to run them separately.
Existing installations should continue applying only the migrations they need.
Include new migration changes in `fresh_schema.sql` when extending the schema.

For an existing Car guide installation, apply [`migrations/learning_companion.sql`](migrations/learning_companion.sql)
after `automatic_chat_context.sql`, then deploy the backend/private RAG service,
admin dashboard and mobile client. It adds optional companion content, activity
progress, structured chat replies, saved items and service plans. Existing guide
content and completion remain intact.

## Initialise the database

1. Create a Supabase project, or confirm that its existing application tables and
   functions have already been removed through an approved reset. Preserve
   Supabase-managed schemas, roles, extensions and Storage infrastructure.
2. If using custom bucket names, edit the two bucket IDs in the Storage section
   of `fresh_schema.sql` to match the backend configuration below.
3. Paste the entire file into the project's SQL Editor and execute it, including
   `begin;` and `commit;`. Tables, relationships, constraints, indexes, triggers,
   permissions, publication functions and initial presets are created together.
4. Confirm that the application tables exist and that Storage contains these
   buckets:

   | Bucket | Visibility | Contents |
   | --- | --- | --- |
   | `documents` | Private | Original PDF/Markdown documents and extraction bundles |
   | `content-images` | Public | Images uploaded for learning guides |

   Existing bucket IDs are left unchanged by the script. If reusing buckets,
   verify their visibility explicitly.
5. Configure the root `.env` for the backend:

   ```dotenv
   SUPABASE_URL=https://YOUR_PROJECT.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVER_ONLY_SERVICE_ROLE_KEY
   JWT_SECRET=YOUR_RANDOM_SECRET_OF_AT_LEAST_32_BYTES
   SUPABASE_DOCUMENT_BUCKET=documents
   SUPABASE_CONTENT_BUCKET=content-images
   ```

   The bucket settings are optional when using the defaults shown. Keep the
   service-role key and signing secret on the server. See the
   [project README](../README.md) for the remaining application configuration.
6. Start the application and register an account. Promote its exact normalized
   email in the SQL Editor:

   ```sql
   update public.app_users
   set role = 'admin'
   where email = 'your-email@example.com';
   ```

7. Sign in to the admin dashboard and add the actual catalogue and application
   content. The schema creates no accounts, demo vehicles, schedules, guides,
   emergency protocols or contacts. It seeds only the singleton `chat_settings`
   row with three editable starter questions.

## Schema overview

For saved document questions and private RAG previews, apply
[`migrations/document_testing.sql`](migrations/document_testing.sql) before
deploying the updated backend, private RAG service and dashboard. It adds
admin-only question/run records with revision-bound results and explicit reviews.
Fresh installations include these tables in `fresh_schema.sql`. This migration
does not publish documents or change driver access.

For document test follow-up on the home dashboard and reference library, apply
[`migrations/document_test_follow_up.sql`](migrations/document_test_follow_up.sql)
after `document_testing.sql`. It adds an index for each question's latest run;
fresh installations include it in `fresh_schema.sql`. No test history or
publication state is changed. Deploy the updated backend and dashboard together.

For saved admin document review, apply
[`migrations/document_review_progress.sql`](migrations/document_review_progress.sql)
before deploying the updated backend and dashboard. It adds revision-bound,
per-admin checklists and source positions without changing existing publications.

For automatic mobile conversations, apply
[`migrations/automatic_chat_context.sql`](migrations/automatic_chat_context.sql)
before deploying the updated backend and mobile app. This adds automatic
conversation identity, allows general chats without a registered vehicle, and
preserves existing vehicle/category sessions. Only the original untouched starter
question presets are upgraded; administrator customisations are preserved.
Fresh installations include these changes in `fresh_schema.sql`.

For admin-managed YouTube channels, apply
[`migrations/youtube_channels.sql`](migrations/youtube_channels.sql) once to an
existing database. It stores channel URLs, queued ingestion requests and sync
results. New installations include this table in `fresh_schema.sql`.

For an existing installation, apply
[`migrations/admin_review_workflow.sql`](migrations/admin_review_workflow.sql)
once before running the updated admin. It adds private clarification questions,
draft return notes and the saved reference page. It preserves existing data.
Fresh installations already include these changes in `fresh_schema.sql`.

| Area | Tables |
| --- | --- |
| Accounts and sessions | `app_users`, `app_sessions` |
| Shared vehicle catalogue | `vehicle_manufacturers`, `vehicle_models`, `knowledge_vehicles` |
| Maintenance catalogue and rules | `maintenance_items`, `manufacturer_schedules`, `maintenance_assistance` |
| Private admin clarification | `admin_review_questions` |
| Documents and applicability | `documents`, `document_vehicles`, `document_categories`, `document_review_progress` |
| Private document previews | `document_test_questions`, `document_test_runs` |
| Learning content | `guide_categories`, `guides`, `guide_images` |
| Supplementary videos and channel ingestion | `knowledge_videos`, `youtube_channels` |
| Emergency content | `emergency_playbooks`, `emergency_contacts` |
| Personal vehicles and maintenance | `user_vehicles`, `user_tasks`, `service_records` |
| Personal saved resources and plans | `saved_items`, `service_plans` |
| Personal progress and incidents | `learning_progress`, `incident_records` |
| Chat and configurable examples | `chat_sessions`, `chat_messages`, `chat_settings` |

The schema also creates shared update-timestamp handling, an immutable chat-scope
trigger, and the `publish_document` and `publish_manufacturer_schedule` functions
for atomic publication changes.

## Authentication and access

Application accounts belong to `app_users`; sessions store token hashes in
`app_sessions`. The application uses backend authentication rather than
Supabase Auth accounts.

Both clients access data through FastAPI. Every application table enables Row
Level Security, with no direct client policies. `PUBLIC`, `anon` and
`authenticated` have no application-table privileges; `service_role` receives
select, insert, update and delete permissions. Publication functions use invoker
permissions and are executable only by the service role. The backend must enforce
account ownership, administrator permissions and public-content visibility.

Document originals and extraction bundles stay private. Guide images are readable
by their public URLs, including images uploaded for draft guides. Uploads and
other Storage operations go through the backend; the schema adds no direct client
Storage policies. Review any pre-existing bucket policies when reusing a project.

## Content and data rules

- Document-to-vehicle assignments control both chat applicability and the mobile
  manual catalogue. Use `vehicle_independent` only for genuinely shared references.
- Documents require confirmed indexing before publication. Assign their scopes,
  process, wait for the private index worker, review and publish. Chat scope
  publication is configured separately.
- Manufacturer schedules use reviewed revisions, with at most one published
  revision per vehicle. Emergency publication requires ordered steps, a scenario
  key, source reference and review timestamp.
- Standard personal tasks derive their text and action from maintenance items;
  custom tasks store their own values. Service history retains its original title
  and calendar date. Ownership is enforced through composite foreign keys.
- Small related-content lists and nested rules remain arrays/JSON. Their embedded
  references and detailed shapes are validated by the backend. Use the admin/API
  workflows for edits and keep the supported single-backend-process deployment.

## Existing projects and resets

`fresh_schema.sql` is for a fresh installation; it does not migrate existing data
or support repeated execution over an installed schema. Stop application writes and indexing
before an approved rebuild, retain any desired backups, and review application
dependencies before manually removing objects. Do not drop entire managed schemas
or use a project-wide reset merely to replace application tables.

Removing table metadata does not remove uploaded Storage files or the separate
RAG index. Handle unwanted files through the Storage dashboard/API, and reconcile
the document index through the application's indexing workflow. After rebuilding,
recreate accounts/content and clear obsolete mobile local records whose server
IDs no longer exist. Deploy the matching database, backend and clients together.

After setup, check account login, admin content edits, vehicle registration,
maintenance records, incident synchronization, manual downloads, scoped chat and
source access. A successful backend health check establishes process liveness;
it does not verify those integrations.

## Maintenance assistance upgrade

For an existing installation, apply [`migrations/maintenance_assistance.sql`](migrations/maintenance_assistance.sql) once in the Supabase SQL Editor before using the admin assistance endpoints. Fresh installations already include this table in `fresh_schema.sql`; do not also run the migration. The migration adds only the private review/cache table, its permissions and timestamp trigger. It does not modify schedules, documents or Chroma.
