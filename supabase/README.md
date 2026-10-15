# Supabase setup

Supabase stores application data and uploaded files. Accounts use the backend's
`app_users` and `app_sessions` tables rather than Supabase Auth.

1. Create a **fresh** Supabase project.
2. Run all of [`initial_schema.sql`](initial_schema.sql) once in the SQL Editor,
   including `begin;` and `commit;`.
3. Confirm the application tables exist and Storage contains a private
   `documents` bucket and public `content-images` bucket.
4. Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and a random `JWT_SECRET`
   of at least 32 bytes in the root `.env`. Keep the service-role key server-side.

The script creates the schema and buckets without accounts or sample content.
Follow the [root setup](../README.md) to register and promote an administrator.

Do not rerun the initial schema on an existing database. Put future changes in
new `supabase/migrations/` SQL files and apply each once in order. This repository
currently uses the SQL Editor; Supabase CLI migration tracking is not configured.
