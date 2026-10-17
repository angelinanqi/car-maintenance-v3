# Supabase database

[`initial_schema.sql`](initial_schema.sql) is the complete application database
definition. Run it once against a fresh Supabase project or after an explicitly
approved removal of the existing application structures. There are no migration,
reset or audit scripts in this directory.

## Initialise the database

1. Create a Supabase project, or confirm that its existing application tables and
   functions have already been removed through an approved reset. Preserve
   Supabase-managed schemas, roles, extensions and Storage infrastructure.
2. If using custom bucket names, edit the two bucket IDs at the end of
   `initial_schema.sql` to match the backend configuration below.
3. Paste the entire file into the project's SQL Editor and execute it, including
   `begin;` and `commit;`. Tables, relationships, constraints, indexes, triggers,
   permissions, publication functions and initial presets are created together.
4. Confirm that the 24 application tables exist and that Storage contains these
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

| Area | Tables |
| --- | --- |
| Accounts and sessions | `app_users`, `app_sessions` |
| Shared vehicle catalogue | `vehicle_manufacturers`, `vehicle_models`, `knowledge_vehicles` |
| Maintenance catalogue and rules | `maintenance_items`, `manufacturer_schedules` |
| Documents and applicability | `documents`, `document_vehicles`, `document_categories` |
| Learning content | `guide_categories`, `guides`, `guide_images` |
| Supplementary videos | `knowledge_videos` |
| Emergency content | `emergency_playbooks`, `emergency_contacts` |
| Personal vehicles and maintenance | `user_vehicles`, `user_tasks`, `service_records` |
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

`initial_schema.sql` does not drop existing objects, migrate data or support
repeated execution over an installed schema. Stop application writes and indexing
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
