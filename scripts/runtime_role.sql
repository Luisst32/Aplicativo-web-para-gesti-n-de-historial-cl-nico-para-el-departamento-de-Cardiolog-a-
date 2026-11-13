-- Run with psql as migration owner. No credentials are stored in this file.
-- This creates a new role; an existing role is deliberately not modified.
SET password_encryption = 'scram-sha-256';
CREATE ROLE cardio_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
\password cardio_runtime
GRANT CONNECT ON DATABASE :"DBNAME" TO cardio_runtime;
DO $$
DECLARE schema_name text;
BEGIN
  FOR schema_name IN SELECT nspname FROM pg_namespace WHERE nspname IN
    ('public','clinical','catalog','security','audit','ai') LOOP
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO cardio_runtime',schema_name);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO cardio_runtime',schema_name);
    EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO cardio_runtime',schema_name);
    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cardio_runtime',schema_name);
    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT USAGE, SELECT ON SEQUENCES TO cardio_runtime',schema_name);
  END LOOP;
END $$;
