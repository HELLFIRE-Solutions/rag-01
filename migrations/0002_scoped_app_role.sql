-- Least-privilege application role for the `rag` schema, mirroring
-- internal-db's crm_app/marketing_app pattern
-- (internal-db/migrations/0007_scoped_app_roles.sql). That migration
-- deliberately left rag_app for whoever owns the `rag` schema to add --
-- see its own comment: "Any future app role (e.g. a rag_app, left to
-- whoever owns the rag schema to add) needs its own explicit CONNECT
-- grant added when it's created." This is that migration.
--
-- Runs against the same shared Postgres instance/database as internal-db
-- (see 0001_rag_schema.sql's own note that it targets that same instance,
-- not a new one) -- CONNECT to the database was already revoked from
-- PUBLIC by internal-db's 0007; this only adds rag_app to the allowlist,
-- it does not touch crm_app/marketing_app's existing grants.
--
-- Role is created with LOGIN but no password -- a role with no password
-- set cannot authenticate, so this file is safe to commit to git.
-- Password is set separately, outside version control, via
-- scripts/set-rag-app-password.sh (reads RAG_APP_PASSWORD from the
-- deploy-time .env, which is gitignored and never written to a tracked
-- file).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rag_app') THEN
    CREATE ROLE rag_app LOGIN;
  END IF;
END
$$;

DO $$
BEGIN
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO rag_app', current_database());
END
$$;

-- rag_app: read/write on rag's tables only. No DDL, no access to
-- crm or marketing (schema-scoped GRANT/USAGE never mentions them).
GRANT USAGE ON SCHEMA rag TO rag_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA rag TO rag_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA rag TO rag_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA rag
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rag_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA rag
  GRANT USAGE, SELECT ON SEQUENCES TO rag_app;
