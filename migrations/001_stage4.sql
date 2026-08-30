CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS campaigns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id varchar(64) NOT NULL,
  name varchar(160) NOT NULL,
  objective varchar(80) NOT NULL,
  daily_budget_minor bigint NOT NULL CHECK (daily_budget_minor >= 0),
  currency varchar(3) NOT NULL DEFAULT 'USD',
  state varchar(32) NOT NULL DEFAULT 'draft',
  provider varchar(32),
  provider_campaign_id varchar(128),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, provider, provider_campaign_id)
);
CREATE INDEX IF NOT EXISTS ix_campaigns_tenant_state ON campaigns(tenant_id, state);

CREATE TABLE IF NOT EXISTS campaign_approvals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id uuid NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  requested_by varchar(128) NOT NULL,
  decided_by varchar(128),
  state varchar(24) NOT NULL DEFAULT 'pending',
  reason text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_campaign_approvals_campaign ON campaign_approvals(campaign_id);

CREATE TABLE IF NOT EXISTS audiences (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id varchar(64) NOT NULL,
  name varchar(160) NOT NULL,
  definition_json text NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audiences_tenant ON audiences(tenant_id);

CREATE TABLE IF NOT EXISTS creatives (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id varchar(64) NOT NULL,
  name varchar(160) NOT NULL,
  content_json text NOT NULL,
  approval_state varchar(24) NOT NULL DEFAULT 'draft'
);
CREATE INDEX IF NOT EXISTS ix_creatives_tenant_approval ON creatives(tenant_id, approval_state);
