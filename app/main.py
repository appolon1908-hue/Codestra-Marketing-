import os
from enum import StrEnum
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import ApprovalModel, CampaignModel

app = FastAPI(title="Codestra Marketing API", version="0.2.0")
LIVE_ADVERTISING_ENABLED = os.getenv("LIVE_ADVERTISING_ENABLED", "false").lower() == "true"
META_READ_SYNC_ENABLED = os.getenv("META_READ_SYNC_ENABLED", "false").lower() == "true"

class CampaignState(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PAUSED = "paused"

class CampaignCreate(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    objective: str = Field(min_length=1, max_length=80)
    daily_budget_minor: int = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)

class Campaign(BaseModel):
    id: UUID
    tenant_id: str
    name: str
    objective: str
    daily_budget_minor: int
    currency: str
    state: str
    model_config = {"from_attributes": True}

@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "live_advertising_enabled": LIVE_ADVERTISING_ENABLED, "meta_read_sync_enabled": META_READ_SYNC_ENABLED}

@app.get("/v1/capabilities")
def capabilities() -> dict[str, object]:
    return {"campaigns": True, "audiences": True, "creatives": True, "approvals": True, "attribution": True, "meta_read_sync": META_READ_SYNC_ENABLED, "provider_writes": LIVE_ADVERTISING_ENABLED}

@app.post("/v1/campaigns", response_model=Campaign, status_code=status.HTTP_201_CREATED)
async def create_campaign(body: CampaignCreate, session: AsyncSession = Depends(get_session)) -> CampaignModel:
    row = CampaignModel(**body.model_dump(), state=CampaignState.DRAFT.value)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row

@app.get("/v1/campaigns/{campaign_id}", response_model=Campaign)
async def get_campaign(campaign_id: UUID, session: AsyncSession = Depends(get_session)) -> CampaignModel:
    row = await session.get(CampaignModel, campaign_id)
    if row is None:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    return row

@app.post("/v1/campaigns/{campaign_id}/request-approval", response_model=Campaign)
async def request_approval(campaign_id: UUID, requested_by: str, session: AsyncSession = Depends(get_session)) -> CampaignModel:
    row = await session.get(CampaignModel, campaign_id)
    if row is None:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    if row.state != CampaignState.DRAFT.value:
        raise HTTPException(status_code=409, detail="invalid_campaign_state")
    row.state = CampaignState.PENDING_APPROVAL.value
    session.add(ApprovalModel(campaign_id=row.id, requested_by=requested_by, state="pending"))
    await session.commit()
    await session.refresh(row)
    return row

@app.post("/v1/campaigns/{campaign_id}/activate")
async def activate_campaign(campaign_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    row = await session.get(CampaignModel, campaign_id)
    if row is None:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    if row.state != CampaignState.APPROVED.value:
        raise HTTPException(status_code=409, detail="campaign_not_approved")
    if not LIVE_ADVERTISING_ENABLED:
        raise HTTPException(status_code=423, detail="live_advertising_disabled")
    raise HTTPException(status_code=501, detail="provider_activation_not_implemented")

@app.get("/v1/campaigns")
async def list_campaigns(tenant_id: str, session: AsyncSession = Depends(get_session)) -> list[Campaign]:
    result = await session.execute(select(CampaignModel).where(CampaignModel.tenant_id == tenant_id).order_by(CampaignModel.created_at.desc()))
    return [Campaign.model_validate(row) for row in result.scalars().all()]
