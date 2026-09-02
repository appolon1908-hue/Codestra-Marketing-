from __future__ import annotations

import hashlib
import json
import os
import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .auth import Principal, authenticate
from .models import ApprovalModel, AudienceModel, CampaignModel, CreativeModel
from .providers.meta_read import MetaReadClient

app = FastAPI(title="Codestra Marketing API", version="0.3.0")
router = APIRouter(prefix="/v1/marketing", dependencies=[Depends(authenticate)])

LIVE_ADVERTISING_ENABLED = os.getenv("LIVE_ADVERTISING_ENABLED", "false").lower() == "true"
META_READ_SYNC_ENABLED = os.getenv("META_READ_SYNC_ENABLED", "false").lower() == "true"
META_ALLOWED_AD_ACCOUNT_IDS = {
    value.strip()
    for value in os.getenv("META_ALLOWED_AD_ACCOUNT_IDS", "").split(",")
    if value.strip()
}
SERVICE = "codestra-marketing"


@app.middleware("http")
async def operational_headers(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
    request.state.correlation_id = correlation_id
    try:
        response = await call_next(request)
    except Exception:
        response = JSONResponse(status_code=500, content={"detail": "internal_error", "correlation_id": correlation_id})
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Correlation-ID"] = correlation_id
    return response

TenantHeader = Annotated[str, Header(alias="X-Tenant-ID", min_length=1, max_length=64)]
IdempotencyHeader = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]


class CampaignState(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PAUSED = "paused"


class CampaignCreate(BaseModel):
    tenant_id: str | None = Field(default=None, min_length=1, max_length=64)
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


class ApprovalAction(BaseModel):
    actor_id: str = Field(min_length=1, max_length=128)
    reason: str | None = Field(default=None, max_length=2000)


class AudienceCreate(BaseModel):
    tenant_id: str | None = Field(default=None, min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    definition: dict[str, Any]


class Audience(BaseModel):
    id: UUID
    tenant_id: str
    name: str
    definition: dict[str, Any]


class CreativeCreate(BaseModel):
    tenant_id: str | None = Field(default=None, min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    content: dict[str, Any]


class Creative(BaseModel):
    id: UUID
    tenant_id: str
    name: str
    content: dict[str, Any]
    approval_state: str


def _tenant(header_tenant: str, body_tenant: str | None = None) -> str:
    if body_tenant is not None and body_tenant != header_tenant:
        raise HTTPException(status_code=403, detail="tenant_mismatch")
    return header_tenant


def _principal(request: Request) -> Principal:
    value = getattr(request.state, "principal", None)
    if not isinstance(value, Principal):
        raise HTTPException(status_code=401, detail="authenticated_principal_required")
    return value


def _request_scope(request: Request | None, scope: str) -> Principal | None:
    # Direct service-function tests may omit Request; every HTTP route receives it
    # from FastAPI and is additionally guarded by the router authentication dependency.
    if request is None:
        return None
    principal = _principal(request)
    principal.require(scope)
    return principal


def _bind_actor(principal: Principal, claimed_actor: str) -> None:
    if claimed_actor != principal.subject:
        raise HTTPException(status_code=403, detail="actor_identity_mismatch")


def _fingerprint(kind: str, tenant_id: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        {"kind": kind, "tenant_id": tenant_id, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def _campaign_for_tenant(session: AsyncSession, campaign_id: UUID, tenant_id: str) -> CampaignModel:
    result = await session.execute(
        select(CampaignModel).where(
            CampaignModel.id == campaign_id,
            CampaignModel.tenant_id == tenant_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    return row


@app.get("/health")
def health(request: Request = None) -> dict[str, object]:
    correlation_id = getattr(getattr(request, "state", None), "correlation_id", str(uuid4()))
    return {
        "status": "ok",
        "service": SERVICE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
    }


@app.get("/ready")
async def ready(request: Request, session: AsyncSession = Depends(get_session)):
    try:
        await asyncio.wait_for(session.execute(select(1)), timeout=2.0)
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready", "service": SERVICE, "dependencies": {"database": "unavailable"}, "correlation_id": request.state.correlation_id})
    return {"status": "ready", "service": SERVICE, "dependencies": {"database": "ready", "configuration": "ready"}, "correlation_id": request.state.correlation_id}


@app.get("/version")
def version(request: Request = None) -> dict[str, object]:
    correlation_id = getattr(getattr(request, "state", None), "correlation_id", str(uuid4()))
    return {"service": SERVICE, "application_version": app.version, "api_versions": ["v1"], "git_sha": os.getenv("CODESTRA_GIT_SHA", "unknown"), "image_digest": os.getenv("CODESTRA_IMAGE_DIGEST", "unknown"), "build_timestamp": os.getenv("CODESTRA_BUILD_TIMESTAMP", "unknown"), "migration_revision": os.getenv("CODESTRA_MIGRATION_REVISION", "unknown"), "environment": os.getenv("CODESTRA_ENVIRONMENT", "unknown"), "correlation_id": correlation_id}


@app.get("/capabilities")
@router.get("/capabilities")
def capabilities(request: Request = None) -> dict[str, object]:
    correlation_id = getattr(getattr(request, "state", None), "correlation_id", str(uuid4()))
    return {
        "service": SERVICE,
        "maintenance_mode": os.getenv("MAINTENANCE_MODE", "false").lower() == "true",
        "degraded_mode": False,
        "business_writes_enabled": False,
        "external_delivery_enabled": LIVE_ADVERTISING_ENABLED,
        "live_advertising_enabled": LIVE_ADVERTISING_ENABLED,
        "read_only_mode": not LIVE_ADVERTISING_ENABLED,
        "simulation_enabled": not LIVE_ADVERTISING_ENABLED,
        "supported_api_versions": ["v1"],
        "campaigns": True,
        "audiences": True,
        "creatives": True,
        "approvals": True,
        "attribution": False,
        "meta_read_sync": META_READ_SYNC_ENABLED,
        "provider_writes": LIVE_ADVERTISING_ENABLED,
        "correlation_id": correlation_id,
    }


@router.post("/campaigns", response_model=Campaign, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    body: CampaignCreate,
    x_tenant_id: TenantHeader,
    idempotency_key: IdempotencyHeader,
    session: AsyncSession = Depends(get_session),
    request: Request = None,
) -> CampaignModel:
    _request_scope(request, "marketing.write")
    tenant_id = _tenant(x_tenant_id, body.tenant_id)
    data = body.model_dump(mode="json", exclude={"tenant_id"})
    fingerprint = _fingerprint("campaign.create", tenant_id, data)
    existing = await session.execute(
        select(CampaignModel).where(
            CampaignModel.tenant_id == tenant_id,
            CampaignModel.idempotency_key == idempotency_key,
        )
    )
    row = existing.scalar_one_or_none()
    if row is not None:
        if row.request_fingerprint != fingerprint:
            raise HTTPException(status_code=409, detail="idempotency_conflict")
        return row

    row = CampaignModel(
        **data,
        tenant_id=tenant_id,
        state=CampaignState.DRAFT.value,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.execute(
            select(CampaignModel).where(
                CampaignModel.tenant_id == tenant_id,
                CampaignModel.idempotency_key == idempotency_key,
            )
        )
        row = existing.scalar_one_or_none()
        if row is None or row.request_fingerprint != fingerprint:
            raise HTTPException(status_code=409, detail="idempotency_conflict")
        return row
    await session.refresh(row)
    return row


@router.get("/campaigns/{campaign_id}", response_model=Campaign)
async def get_campaign(
    campaign_id: UUID,
    x_tenant_id: TenantHeader,
    session: AsyncSession = Depends(get_session),
    request: Request = None,
) -> CampaignModel:
    _request_scope(request, "marketing.read")
    return await _campaign_for_tenant(session, campaign_id, x_tenant_id)


@router.get("/campaigns", response_model=list[Campaign])
async def list_campaigns(
    x_tenant_id: TenantHeader,
    session: AsyncSession = Depends(get_session),
    request: Request = None,
) -> list[CampaignModel]:
    _request_scope(request, "marketing.read")
    result = await session.execute(
        select(CampaignModel)
        .where(CampaignModel.tenant_id == x_tenant_id)
        .order_by(CampaignModel.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/campaigns/{campaign_id}/submit-for-approval", response_model=Campaign)
async def submit_for_approval(
    campaign_id: UUID,
    body: ApprovalAction,
    request: Request,
    x_tenant_id: TenantHeader,
    session: AsyncSession = Depends(get_session),
) -> CampaignModel:
    principal = _principal(request)
    principal.require("marketing.write")
    _bind_actor(principal, body.actor_id)
    row = await _campaign_for_tenant(session, campaign_id, x_tenant_id)
    if row.state != CampaignState.DRAFT.value:
        raise HTTPException(status_code=409, detail="invalid_campaign_state")
    row.state = CampaignState.PENDING_APPROVAL.value
    session.add(
        ApprovalModel(
            tenant_id=x_tenant_id,
            campaign_id=row.id,
            requested_by=principal.subject,
            state="pending",
            reason=body.reason,
        )
    )
    await session.commit()
    await session.refresh(row)
    return row


@router.post("/campaigns/{campaign_id}/approve", response_model=Campaign)
async def approve_campaign(
    campaign_id: UUID,
    body: ApprovalAction,
    request: Request,
    x_tenant_id: TenantHeader,
    session: AsyncSession = Depends(get_session),
) -> CampaignModel:
    principal = _principal(request)
    principal.require("marketing.approve")
    _bind_actor(principal, body.actor_id)
    row = await _campaign_for_tenant(session, campaign_id, x_tenant_id)
    if row.state != CampaignState.PENDING_APPROVAL.value:
        raise HTTPException(status_code=409, detail="invalid_campaign_state")
    approval_result = await session.execute(
        select(ApprovalModel)
        .where(
            ApprovalModel.tenant_id == x_tenant_id,
            ApprovalModel.campaign_id == campaign_id,
            ApprovalModel.state == "pending",
        )
        .order_by(ApprovalModel.created_at.desc())
    )
    approval = approval_result.scalars().first()
    if approval is None:
        raise HTTPException(status_code=409, detail="pending_approval_missing")
    if approval.requested_by == principal.subject:
        raise HTTPException(status_code=409, detail="approval_separation_of_duties_required")
    approval.state = "approved"
    approval.decided_by = principal.subject
    approval.reason = body.reason
    approval.decided_at = datetime.now(timezone.utc)
    row.state = CampaignState.APPROVED.value
    await session.commit()
    await session.refresh(row)
    return row


@router.post("/campaigns/{campaign_id}/activate")
async def activate_campaign(
    campaign_id: UUID,
    request: Request,
    x_tenant_id: TenantHeader,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    _principal(request).require("marketing.provider.write")
    row = await _campaign_for_tenant(session, campaign_id, x_tenant_id)
    if row.state != CampaignState.APPROVED.value:
        raise HTTPException(status_code=409, detail="campaign_not_approved")
    if not LIVE_ADVERTISING_ENABLED:
        raise HTTPException(status_code=423, detail="live_advertising_disabled")
    raise HTTPException(status_code=501, detail="provider_activation_not_implemented")


@router.post("/audiences", response_model=Audience, status_code=status.HTTP_201_CREATED)
async def create_audience(
    body: AudienceCreate,
    x_tenant_id: TenantHeader,
    idempotency_key: IdempotencyHeader,
    session: AsyncSession = Depends(get_session),
    request: Request = None,
) -> Audience:
    _request_scope(request, "marketing.write")
    tenant_id = _tenant(x_tenant_id, body.tenant_id)
    definition_json = json.dumps(body.definition, sort_keys=True, separators=(",", ":"))
    fingerprint = _fingerprint("audience.create", tenant_id, {"name": body.name, "definition": body.definition})
    result = await session.execute(
        select(AudienceModel).where(
            AudienceModel.tenant_id == tenant_id,
            AudienceModel.idempotency_key == idempotency_key,
        )
    )
    row = result.scalar_one_or_none()
    if row is not None:
        if row.request_fingerprint != fingerprint:
            raise HTTPException(status_code=409, detail="idempotency_conflict")
    else:
        row = AudienceModel(
            tenant_id=tenant_id,
            name=body.name,
            definition_json=definition_json,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return Audience(id=row.id, tenant_id=row.tenant_id, name=row.name, definition=json.loads(row.definition_json))


@router.post("/creatives", response_model=Creative, status_code=status.HTTP_201_CREATED)
async def create_creative(
    body: CreativeCreate,
    x_tenant_id: TenantHeader,
    idempotency_key: IdempotencyHeader,
    session: AsyncSession = Depends(get_session),
    request: Request = None,
) -> Creative:
    _request_scope(request, "marketing.write")
    tenant_id = _tenant(x_tenant_id, body.tenant_id)
    content_json = json.dumps(body.content, sort_keys=True, separators=(",", ":"))
    fingerprint = _fingerprint("creative.create", tenant_id, {"name": body.name, "content": body.content})
    result = await session.execute(
        select(CreativeModel).where(
            CreativeModel.tenant_id == tenant_id,
            CreativeModel.idempotency_key == idempotency_key,
        )
    )
    row = result.scalar_one_or_none()
    if row is not None:
        if row.request_fingerprint != fingerprint:
            raise HTTPException(status_code=409, detail="idempotency_conflict")
    else:
        row = CreativeModel(
            tenant_id=tenant_id,
            name=body.name,
            content_json=content_json,
            approval_state="draft",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return Creative(
        id=row.id,
        tenant_id=row.tenant_id,
        name=row.name,
        content=json.loads(row.content_json),
        approval_state=row.approval_state,
    )


@router.get("/providers/meta/accounts/{ad_account_id}/campaigns")
async def meta_campaign_snapshots(
    ad_account_id: str,
    request: Request,
    x_tenant_id: TenantHeader,
) -> list[dict[str, object]]:
    _principal(request).require("marketing.provider.read")
    del x_tenant_id  # tenant is mandatory even though provider credentials remain centrally scoped.
    if not META_READ_SYNC_ENABLED:
        raise HTTPException(status_code=423, detail="meta_read_sync_disabled")
    if ad_account_id not in META_ALLOWED_AD_ACCOUNT_IDS:
        raise HTTPException(status_code=403, detail="meta_ad_account_not_allowlisted")
    snapshots = await MetaReadClient().list_campaigns(ad_account_id)
    return [
        {
            "provider_campaign_id": item.provider_campaign_id,
            "name": item.name,
            "status": item.status,
            "objective": item.objective,
            "daily_budget_minor": item.daily_budget_minor,
        }
        for item in snapshots
    ]


app.include_router(router)
