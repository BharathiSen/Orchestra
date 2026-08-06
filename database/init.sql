-- Orchestra database bootstrap.
--
-- Runs once, on an empty Postgres data directory, via the official image's
-- docker-entrypoint-initdb.d hook. Only extensions are created here: tables are
-- created by SQLAlchemy at backend startup, so keeping DDL in one place avoids
-- the two definitions drifting apart.
--
-- pgcrypto provides gen_random_uuid(); vector is required by pgvector for the
-- document_chunks.embedding column.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS vector;
