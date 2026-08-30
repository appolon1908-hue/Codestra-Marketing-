# Codestra Marketing Architecture

## Role
Codestra Marketing is the campaign and acquisition control plane. It owns business intent and provider-neutral marketing objects; it does not become the transport layer, CRM system of record, identity provider, or workflow engine.

## Owns
- campaigns and objectives
- audiences and segments
- ad accounts as external references
- creative concepts and variants
- campaign/ad-set/ad-group abstractions
- budgets, caps, pacing policy, approval state
- experiments and variant lineage
- attribution and lead-source mapping
- conversion goals
- CPL/CPA/ROAS and funnel metrics
- optimization recommendations
- advertising-provider connector contracts
- campaign audit history

## Does not own
- customer master records or opportunity stage authority: Odoo
- authentication/authorization: Keycloak
- ingress/API policies: Kong
- provider transport/retry/webhook durability: Middleware
- cross-service workflow orchestration: n8n
- message delivery: Codestra Communication CC
- social publishing engine: Codestra Social/existing social platform
- model vendor credentials or AI routing: Codestra AI

## Initial APIs
- POST /v1/marketing/campaigns
- GET /v1/marketing/campaigns
- GET /v1/marketing/campaigns/{id}
- PATCH /v1/marketing/campaigns/{id}
- POST /v1/marketing/campaigns/{id}/submit-for-approval
- POST /v1/marketing/campaigns/{id}/approve
- POST /v1/marketing/campaigns/{id}/activate
- POST /v1/marketing/campaigns/{id}/pause
- POST /v1/marketing/campaigns/{id}/budget-change-requests
- POST /v1/marketing/audiences
- POST /v1/marketing/creatives
- POST /v1/marketing/experiments
- GET /v1/marketing/metrics
- GET /v1/marketing/attribution
- POST /v1/marketing/provider-events

Activation endpoints remain policy-gated and incapable of live spend until provider connectors and approval controls are explicitly certified.

## Core entities
Campaign, Objective, Audience, Segment, Creative, CreativeVariant, ProviderAccountRef, ProviderCampaignRef, BudgetPolicy, Approval, Experiment, ConversionGoal, LeadAttribution, Recommendation, SpendSnapshot, CampaignMetricSnapshot.

## State model
Draft -> ReadyForReview -> Approved -> Scheduled -> Active -> Paused -> Completed/Cancelled.

Provider synchronization is a separate state: NotSynced, Pending, Synced, Degraded, Failed. Business state must not be inferred solely from provider HTTP success.

## Spend safety
- default live_spend_enabled=false
- immutable audit record for approval and budget changes
- absolute campaign cap and daily cap
- per-business-unit policy
- no AI model may bypass approval policy
- idempotent activation and budget mutations
- provider account allowlist

## Events
marketing.campaign.created
marketing.campaign.approval_requested
marketing.campaign.approved
marketing.campaign.activation_requested
marketing.campaign.activated
marketing.campaign.paused
marketing.budget.change_requested
marketing.budget.changed
marketing.lead.attributed
marketing.conversion.recorded
marketing.provider.sync_failed
marketing.recommendation.created

All events carry event_id, occurred_at, tenant_id, business_unit_id, correlation_id, causation_id, actor, aggregate_id, aggregate_version, and schema_version.
