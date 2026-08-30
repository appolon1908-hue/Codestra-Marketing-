from enum import StrEnum
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI(title="Codestra Marketing API", version="0.1.0")

LIVE_ADVERTISING_ENABLED = False

class CampaignState(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PAUSED = "paused"

class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    objective: str = Field(min_length=1, max_length=80)
    daily_budget_minor: int = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)

class Campaign(BaseModel):
    id: UUID
    name: str
    objective: str
    daily_budget_minor: int
    currency: str
    state: CampaignState

_campaigns: dict[UUID, Campaign] = {}

@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "live_advertising_enabled": LIVE_ADVERTISING_ENABLED}

@app.get("/v1/capabilities")
def capabilities() -> dict[str, object]:
    return {
        "campaigns": True,
        "audiences": True,
        "creatives": True,
        "approvals": True,
        "attribution": True,
        "provider_writes": LIVE_ADVERTISING_ENABLED,
    }

@app.post("/v1/campaigns", response_model=Campaign, status_code=status.HTTP_201_CREATED)
def create_campaign(body: CampaignCreate) -> Campaign:
    campaign = Campaign(id=uuid4(), state=CampaignState.DRAFT, **body.model_dump())
    _campaigns[campaign.id] = campaign
    return campaign

@app.post("/v1/campaigns/{campaign_id}/request-approval", response_model=Campaign)
def request_approval(campaign_id: UUID) -> Campaign:
    campaign = _campaigns.get(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    campaign.state = CampaignState.PENDING_APPROVAL
    return campaign

@app.post("/v1/campaigns/{campaign_id}/activate")
def activate_campaign(campaign_id: UUID) -> dict[str, str]:
    if not LIVE_ADVERTISING_ENABLED:
        raise HTTPException(status_code=423, detail="live_advertising_disabled")
    raise HTTPException(status_code=501, detail="provider_activation_not_implemented")
