DROP TABLE IF EXISTS marketing_audit_events;
DROP TABLE IF EXISTS marketing_outbox;
DROP TABLE IF EXISTS marketing_operations;
ALTER TABLE campaigns DROP COLUMN IF EXISTS resource_version;
