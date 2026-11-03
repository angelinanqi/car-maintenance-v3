# Supabase database

[`init.sql`](init.sql) is the single complete fresh-install database definition.
The existing `supabase/` directory is reused instead of adding `database/`.
Run the entire file once in a fresh Supabase project's SQL Editor. It creates
34 application tables, constraints, indexes, functions, triggers, permissions,
Storage bucket definitions and initial presets in one transaction.

This is a manual fresh-install script, not an upgrade or reset. It does not run
during application startup. Existing objects cause an error and transaction
rollback; never run it over an existing installation. Supabase-managed Auth,
Storage, schemas and roles must already exist. The retained column-specific
`ON DELETE SET NULL` syntax requires PostgreSQL 15 or later; UUID generation is
built in, so no application extensions need to be installed.

## Historical scripts and existing installations

For maintenance cost tracking, apply
[`migrations/20261103_maintenance_costs.sql`](migrations/20261103_maintenance_costs.sql)
before deploying the updated backend, mobile app and admin web client. It adds nullable
`service_records.performed_by` (`self` or `mechanic`). Historical attribution and
missing costs remain unknown; no costs are backfilled. New records must specify
who performed the work, and mechanic records require a non-negative RM cost
(including zero) on create and edit. Fresh installations include the column in
`init.sql`. The migration has no automatic startup runner.

For persistent website-to-PDF imports, apply
[`migrations/20261103_website_pdf_imports.sql`](migrations/20261103_website_pdf_imports.sql)
once in the SQL Editor **before starting the updated app**. It adds the server-only
`website_import_jobs` queue, document `source_metadata`, fenced job claims and
transactional document finalization. Existing documents are preserved. The script
reloads the PostgREST schema cache; `init.sql` includes the same definitions for
fresh installations. Do not run `init.sql` on an existing database.

Before using deferred correction indexing on an existing installation, run
[`migrations/20261103_deferred_correction_indexing.sql`](migrations/20261103_deferred_correction_indexing.sql)
in the Supabase SQL Editor. It extends the document status constraint with
`awaiting_confirmation` without changing document records. Fresh installs already
include it in `init.sql`.

For category archiving and safe removal, also run
[`migrations/20261103_category_removal.sql`](migrations/20261103_category_removal.sql).
It adds the archive flag and server-only functions for removal previews and
transactional guide reassignment/deletion. It does not archive, move or delete
existing content. Fresh installs include the same definitions in `init.sql`.

The 12 additive migrations, original `initial_schema.sql` and previous
`fresh_schema.sql` are archived unchanged under
`dumpster/database-migrations/supabase/`, preserving their original relative paths.
The archive is excluded from Git by the root `/dumpster/` rule and is local only:
retain a separate copy if an existing deployment still needs an upgrade. Fresh
clones receive only `init.sql`. No Supabase CLI migration ledger, automatic migration
runner or startup reference to these files was found in the repository.

For existing databases, use only the missing additive upgrades from that archive
after checking the deployed schema; do not substitute `init.sql`. In particular,
`supabase_auth.sql`, `mobile_learning.sql`, `mobile_maintenance.sql` and
`admin_maintenance.sql` remain relevant to installations that have not deployed
those features. Moving the files does not apply any upgrade to those installations.

Historical replay order used for validation:

1. `initial_schema.sql`. This already incorporates `admin_review_workflow.sql`,
   `maintenance_assistance.sql` and `youtube_channels.sql`; their non-idempotent
   DDL must not be applied again. It also includes the initial document review,
   document testing and companion structures.
2. `migrations/automatic_chat_context.sql`
3. `migrations/learning_companion.sql`
4. `migrations/document_testing.sql`
5. `migrations/document_test_follow_up.sql`
6. `migrations/document_review_progress.sql`
7. `migrations/supabase_auth.sql`
8. `migrations/mobile_learning.sql`
9. `migrations/mobile_maintenance.sql`
10. `migrations/admin_maintenance.sql`

This is a dependency order, not a deployment ledger: historical filenames have no
numeric ordering. The archived automatic-chat migration conditionally replaces
only the original starter presets, preserving administrator edits. A fresh install
seeds the final presets directly. Existing learning completion dates are deliberately
not backfilled by the mobile-learning migration. Auth identity linking remains an
explicit administrative operation; no accounts or live records are seeded.

## Initialise the database

1. Create a fresh Supabase project with no application tables. Preserve
   Supabase-managed schemas, roles, extensions and Storage infrastructure.
2. If using custom bucket names, edit the two bucket IDs in the Storage section
   of `init.sql` to match the backend configuration below.
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
   SUPABASE_DOCUMENT_BUCKET=documents
   SUPABASE_CONTENT_BUCKET=content-images
   ```

   The bucket settings are optional when using the defaults shown. Keep the
   service-role key on the server. See the
   [project README](../README.md) for the remaining application configuration.
6. Register through the interface, confirm your email and sign in once so FastAPI
   creates your application profile. In Supabase's Table Editor, open
   `public.app_users`, find your account by email and change `role` from `user`
   to `admin`. Admin permissions are managed in this table, not Auth user metadata.

7. Sign in through Supabase and complete mandatory TOTP setup before admin access.
   Existing admin profiles must be linked to a confirmed Supabase identity; the
   custom admin login is retired. Promotion does not create a legacy password.
   See the project README for exact callback
   allowlists and explicit linking of an existing admin. The schema creates
   no accounts, demo vehicles, schedules, guides,
   emergency protocols or contacts. It seeds only the singleton `chat_settings`
   row with three editable starter questions.

## Schema overview

| Area | Tables |
| --- | --- |
| Application profiles | `app_users` (linked to `auth.users`) |
| Retained legacy sessions (unused) | `app_sessions` |
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
| Personal progress and incidents | `learning_progress`, `learning_recaps`, `incident_records` |
| Chat and configurable examples | `chat_sessions`, `chat_messages`, `chat_settings` |

The schema also creates shared update-timestamp handling, an immutable chat-scope
trigger, and the `publish_document` and `publish_manufacturer_schedule` functions
for atomic publication changes.

## Authentication and access

For an existing Auth-enabled installation, run
[`migrations/20261103_link_auth_profiles.sql`](migrations/20261103_link_auth_profiles.sql)
in Supabase SQL Editor to backfill application profiles for confirmed Auth users.
It preserves `app_users.id` and all dependent foreign keys, assigns only `user`
to newly created profiles, and can be rerun without changing linked profiles.
It relies on the existing unique `auth_user_id` foreign key from `init.sql` or
the historical Auth upgrade. Email collisions stop the transaction for explicit
operator linking; existing admins can use `scripts/link_supabase_admin.py`.
Future profiles continue to be created by FastAPI on first verified sign-in;
this migration adds no Auth signup trigger. It does not promote administrators
or migrate legacy passwords.

Supabase Auth owns credentials and sessions. FastAPI verifies Supabase access
tokens and loads server-managed roles from `app_users` through `auth_user_id`.
Email confirmation is required; admins require TOTP verification. Multiple admin
profiles are supported. Application ownership and attribution continue to reference
the original `app_users.id`.

The schema still defines legacy `app_sessions` and
`app_users.password_hash` for compatibility. Active code neither reads nor writes
them. No tables, columns, hashes or records were deleted during the auth cleanup.
Any cleanup requires a separately approved database migration. Do not rerun
fresh-schema SQL on an existing database.

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

`init.sql` is for a fresh installation; it does not migrate existing data
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

## Consolidation validation

Validated on disposable local PostgreSQL 18 databases on 2 November 2026, comparing
the historical replay above with `init.sql`. Catalogue comparisons matched all
33 tables, 319 columns (types, defaults, nullability and comments), constraints,
85 indexes (including constraint indexes), 27 triggers, four functions (bodies,
signatures, security settings, search paths and execute grants), RLS settings,
table grants, public schema permissions, types, two buckets and starter presets.
There are no application enums, standalone custom types, views, procedures or
direct-client RLS/Storage policies. Function body comparison ignores formatting
and comments; column order and creation timestamps are not compared.

Database smoke checks passed for service-role writes, unique Auth identity links,
composite ownership foreign keys, retained service history, learning progress,
immutable chat ownership, stale schedule rejection and publication history,
document indexing/publication checks, timestamp triggers, and denied anonymous
and authenticated table/RPC access. Test writes were rolled back.
Repeated initialization was rejected without changing seed values or timestamps.
A forced mid-script index conflict rolled back all newly created application
tables and preserved pre-existing sentinel data.

The local test supplied minimal stand-ins for `auth.users`, `storage.buckets` and
Supabase roles. This verifies PostgreSQL schema equivalence in that environment,
not live Supabase Auth, Storage, PostgREST, backend HTTP workflows or hosted default
privileges. Those integrations still require a disposable Supabase project and the
operational checks above. The live project was not accessed or modified.
