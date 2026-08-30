ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS idempotency_key varchar(200);
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS request_fingerprint varchar(64);
UPDATE campaigns
SET idempotency_key = COALESCE(idempotency_key, 'legacy:' || id::text),
    request_fingerprint = COALESCE(request_fingerprint, repeat('0', 64));
ALTER TABLE campaigns ALTER COLUMN idempotency_key SET NOT NULL;
ALTER TABLE campaigns ALTER COLUMN request_fingerprint SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_campaign_idempotency ON campaigns(tenant_id, idempotency_key);

ALTER TABLE campaign_approvals ADD COLUMN IF NOT EXISTS tenant_id varchar(64);
UPDATE campaign_approvals approval
SET tenant_id = campaign.tenant_id
FROM campaigns campaign
WHERE approval.campaign_id = campaign.id AND approval.tenant_id IS NULL;
ALTER TABLE campaign_approvals ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE campaign_approvals ADD COLUMN IF NOT EXISTS decided_at timestamptz;
CREATE INDEX IF NOT EXISTS ix_campaign_approvals_tenant_campaign
  ON campaign_approvals(tenant_id, campaign_id);

ALTER TABLE audiences ADD COLUMN IF NOT EXISTS idempotency_key varchar(200);
ALTER TABLE audiences ADD COLUMN IF NOT EXISTS request_fingerprint varchar(64);
UPDATE audiences
SET idempotency_key = COALESCE(idempotency_key, 'legacy:' || id::text),
    request_fingerprint = COALESCE(request_fingerprint, repeat('0', 64));
ALTER TABLE audiences ALTER COLUMN idempotency_key SET NOT NULL;
ALTER TABLE audiences ALTER COLUMN request_fingerprint SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_audience_idempotency ON audiences(tenant_id, idempotency_key);

ALTER TABLE creatives ADD COLUMN IF NOT EXISTS idempotency_key varchar(200);
ALTER TABLE creatives ADD COLUMN IF NOT EXISTS request_fingerprint varchar(64);
UPDATE creatives
SET idempotency_key = COALESCE(idempotency_key, 'legacy:' || id::text),
    request_fingerprint = COALESCE(request_fingerprint, repeat('0', 64));
ALTER TABLE creatives ALTER COLUMN idempotency_key SET NOT NULL;
ALTER TABLE creatives ALTER COLUMN request_fingerprint SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_creative_idempotency ON creatives(tenant_id, idempotency_key);
