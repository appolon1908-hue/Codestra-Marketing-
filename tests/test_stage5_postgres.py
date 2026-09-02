from __future__ import annotations

import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request

from app.auth import Principal
from app.main import (
    ApprovalAction,
    CampaignCreate,
    CampaignUpdate,
    activate_campaign,
    approve_campaign,
    create_campaign,
    get_campaign,
    pause_campaign,
    resume_campaign,
    submit_for_approval,
    update_campaign,
)
from app.models import AuditEventModel, CampaignModel, OperationModel, OutboxModel

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_idempotency_and_cross_tenant_reads_fail_closed():
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    tenant_a = f"tenant-a-{uuid.uuid4()}"
    tenant_b = f"tenant-b-{uuid.uuid4()}"
    key = f"campaign-{uuid.uuid4()}"
    body = CampaignCreate(name="Stage 5 campaign", objective="leads", daily_budget_minor=0)

    async with sessions() as session:
        first = await create_campaign(body, tenant_a, key, session)
        first_id = first.id
    async with sessions() as session:
        duplicate = await create_campaign(body, tenant_a, key, session)
        assert duplicate.id == first_id
    async with sessions() as session:
        with pytest.raises(HTTPException) as conflict:
            await create_campaign(
                CampaignCreate(name="Different campaign", objective="leads", daily_budget_minor=0),
                tenant_a,
                key,
                session,
            )
        assert conflict.value.status_code == 409
    async with sessions() as session:
        with pytest.raises(HTTPException) as denied:
            await get_campaign(first_id, tenant_b, session)
        assert denied.value.status_code == 404

    await engine.dispose()


def _request(tenant_id: str, subject: str, scopes: set[str]) -> Request:
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
    request.state.correlation_id = f"corr-{uuid.uuid4()}"
    request.state.principal = Principal(subject, tenant_id, frozenset(scopes), "codestra-console")
    return request


@pytest.mark.asyncio
async def test_campaign_lifecycle_is_versioned_audited_and_idempotent():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    tenant_id = f"tenant-lifecycle-{uuid.uuid4()}"
    writer = _request(tenant_id, "writer-1", {"marketing.write"})
    approver = _request(tenant_id, "approver-1", {"marketing.approve"})
    async with sessions() as session:
        created = await create_campaign(
            CampaignCreate(name="Lifecycle", objective="leads", daily_budget_minor=100),
            tenant_id,
            f"create-{uuid.uuid4()}",
            session,
        )
        campaign_id = created.id
        version = created.resource_version
    async with sessions() as session:
        updated = await update_campaign(
            campaign_id,
            CampaignUpdate(expected_version=version, daily_budget_minor=200),
            writer,
            tenant_id,
            "update-key",
            session,
        )
    async with sessions() as session:
        submitted = await submit_for_approval(
            campaign_id,
            ApprovalAction(actor_id="writer-1", expected_version=updated.resource_version),
            writer,
            tenant_id,
            "submit-key",
            session,
        )
    async with sessions() as session:
        approved = await approve_campaign(
            campaign_id,
            ApprovalAction(actor_id="approver-1", expected_version=submitted.resource_version),
            approver,
            tenant_id,
            "approve-key",
            session,
        )
    async with sessions() as session:
        paused = await pause_campaign(
            campaign_id,
            ApprovalAction(actor_id="writer-1", expected_version=approved.resource_version),
            writer,
            tenant_id,
            "pause-key",
            session,
        )
    async with sessions() as session:
        resumed = await resume_campaign(
            campaign_id,
            ApprovalAction(actor_id="writer-1", expected_version=paused.resource_version),
            writer,
            tenant_id,
            "resume-key",
            session,
        )
        assert resumed.state == "approved"
    async with sessions() as session:
        replay = await resume_campaign(
            campaign_id,
            ApprovalAction(actor_id="writer-1", expected_version=paused.resource_version),
            writer,
            tenant_id,
            "resume-key",
            session,
        )
        assert replay.resource_version == resumed.resource_version
        assert await session.scalar(
            select(func.count()).select_from(AuditEventModel).where(
                AuditEventModel.tenant_id == tenant_id,
                AuditEventModel.aggregate_id == campaign_id,
            )
        ) == 5

    await engine.dispose()


@pytest.mark.asyncio
async def test_disabled_activation_is_durable_idempotent_and_has_no_outbox():
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    tenant_id = f"tenant-activation-{uuid.uuid4()}"
    key = f"activate-{uuid.uuid4()}"

    async with sessions() as session:
        campaign = await create_campaign(
            CampaignCreate(name="Denied activation", objective="leads", daily_budget_minor=0),
            tenant_id,
            f"create-{uuid.uuid4()}",
            session,
        )
        campaign.state = "approved"
        await session.commit()
        campaign_id = campaign.id

    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
    request.state.correlation_id = f"corr-{uuid.uuid4()}"
    request.state.principal = Principal(
        subject="marketing-operator",
        tenant_id=tenant_id,
        scopes=frozenset({"marketing.provider.write"}),
        client_id="codestra-console",
    )
    async with sessions() as session:
        first = await activate_campaign(campaign_id, request, tenant_id, key, session)
        assert first.status_code == 423
    async with sessions() as session:
        duplicate = await activate_campaign(campaign_id, request, tenant_id, key, session)
        assert duplicate.status_code == 423
    async with sessions() as session:
        operation = (
            await session.execute(
                select(OperationModel).where(
                    OperationModel.tenant_id == tenant_id,
                    OperationModel.idempotency_key == key,
                )
            )
        ).scalar_one()
        assert operation.state == "denied"
        assert operation.error_code == "live_advertising_disabled"
        assert await session.scalar(
            select(func.count()).select_from(OutboxModel).where(OutboxModel.operation_id == operation.id)
        ) == 0
        assert await session.scalar(
            select(func.count()).select_from(AuditEventModel).where(AuditEventModel.operation_id == operation.id)
        ) == 1
        assert await session.scalar(
            select(func.count()).select_from(CampaignModel).where(CampaignModel.id == campaign_id)
        ) == 1

    await engine.dispose()
