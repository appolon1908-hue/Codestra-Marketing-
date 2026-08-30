DROP INDEX IF EXISTS uq_creative_idempotency;
ALTER TABLE creatives DROP COLUMN IF EXISTS request_fingerprint;
ALTER TABLE creatives DROP COLUMN IF EXISTS idempotency_key;

DROP INDEX IF EXISTS uq_audience_idempotency;
ALTER TABLE audiences DROP COLUMN IF EXISTS request_fingerprint;
ALTER TABLE audiences DROP COLUMN IF EXISTS idempotency_key;

DROP INDEX IF EXISTS ix_campaign_approvals_tenant_campaign;
ALTER TABLE campaign_approvals DROP COLUMN IF EXISTS decided_at;
ALTER TABLE campaign_approvals DROP COLUMN IF EXISTS tenant_id;

DROP INDEX IF EXISTS uq_campaign_idempotency;
ALTER TABLE campaigns DROP COLUMN IF EXISTS request_fingerprint;
ALTER TABLE campaigns DROP COLUMN IF EXISTS idempotency_key;
