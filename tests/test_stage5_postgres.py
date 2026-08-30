from __future__ import annotations

import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import CampaignCreate, create_campaign, get_campaign

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
