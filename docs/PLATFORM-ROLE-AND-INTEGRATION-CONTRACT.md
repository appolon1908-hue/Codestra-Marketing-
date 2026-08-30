# Codestra Marketing Platform — Role and Integration Contract

## Mission
Codestra Marketing is the campaign and paid-acquisition control plane. It owns campaign strategy, campaign lifecycle, audiences, creatives, budgets, approvals, attribution, experiments, optimization recommendations, and marketing performance.

## Owns
- Campaigns, objectives, ad sets/ad groups, audiences, creatives and offers
- Budget policy, pacing policy, spend limits and approval state
- Paid-channel connectors and normalized campaign/ad performance
- Lead-source attribution and campaign-to-lead linkage
- CPL, CPA, conversion rate, ROAS and funnel performance
- Experiment definitions and optimization recommendations
- Campaign audit trail and deterministic state transitions

## Does Not Own
- Identity or SSO: Keycloak
- Edge routing/auth enforcement: Kong
- Cross-system provider delivery, durable webhooks, outbox/inbox: Middleware
- CRM/customer master: Odoo
- Email/SMS/WhatsApp delivery: Codestra Communication
- Organic social publishing runtime: Codestra Social + social.codestra.co
- General AI provider access: Codestra AI
- Workflow orchestration: n8n

## Mandatory Request Path
Caller -> Codestra SDK -> Kong -> Codestra Marketing -> approved downstream service/adapter.
No direct database coupling across repositories.

## Paid Media Safety
AI may draft, analyze, recommend and prepare campaigns, but may not bypass policy to activate spend. New campaigns, material budget increases, new ad-account connections, material targeting changes and spend above configured thresholds require explicit approval gates.

## Core Domains
Campaign, ChannelAccount, Audience, Creative, Offer, BudgetPolicy, Approval, Experiment, Attribution, LeadSource, ConversionGoal, PerformanceSnapshot, OptimizationRecommendation, ProviderSyncState.

## Required APIs
- /v1/marketing/campaigns
- /v1/marketing/audiences
- /v1/marketing/creatives
- /v1/marketing/budgets
- /v1/marketing/approvals
- /v1/marketing/attribution
- /v1/marketing/performance
- /v1/marketing/recommendations
- /v1/marketing/connectors

## Required Events
marketing.campaign.created, marketing.campaign.approved, marketing.campaign.activated, marketing.campaign.paused, marketing.budget.changed, marketing.lead.attributed, marketing.performance.updated, marketing.recommendation.created.

## Implementation Order
1. Domain models and state machines
2. Authorization and tenancy
3. Approval/budget policy
4. Provider-neutral API
5. Durable event publication
6. Meta Ads adapter
7. Google Ads adapter
8. Attribution and Odoo sync
9. AI recommendations
10. Additional paid-channel adapters

Production spend remains disabled until approval, audit, idempotency, reconciliation, observability and rollback gates are proven.