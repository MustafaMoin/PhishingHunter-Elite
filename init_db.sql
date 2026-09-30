-- init_db.sql
-- -----------
-- PostgreSQL database initialization script
-- Automatically run by docker-entrypoint-initdb.d

-- This file is executed only on first container creation
-- For schema updates, use database_postgres.py init_db() function

-- Note: Schema is created by database_postgres.py
-- This file is just a placeholder for any custom initialization

-- Set timezone
SET timezone = 'UTC';

-- Enable extensions if needed
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For fuzzy string matching
-- CREATE EXTENSION IF NOT EXISTS btree_gin;  -- For better indexing

-- Custom initialization can go here
-- Example: Create read-only user
-- CREATE USER readonly WITH PASSWORD 'readonly_password';
-- GRANT CONNECT ON DATABASE phishinghunter TO readonly;
-- GRANT USAGE ON SCHEMA public TO readonly;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'PhishingHunter database initialized successfully';
END $$;
