import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

class CampaignModel(Base):
    __tablename__ = "campaigns"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(160))
    objective: Mapped[str] = mapped_column(String(80))
    daily_budget_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    state: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_campaign_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    approvals: Mapped[list["ApprovalModel"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("tenant_id", "provider", "provider_campaign_id", name="uq_campaign_provider_id"),)

class ApprovalModel(Base):
    __tablename__ = "campaign_approvals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    requested_by: Mapped[str] = mapped_column(String(128))
    decided_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str] = mapped_column(String(24), default="pending")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    campaign: Mapped[CampaignModel] = relationship(back_populates="approvals")

class AudienceModel(Base):
    __tablename__ = "audiences"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(160))
    definition_json: Mapped[str] = mapped_column(Text)

class CreativeModel(Base):
    __tablename__ = "creatives"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(160))
    content_json: Mapped[str] = mapped_column(Text)
    approval_state: Mapped[str] = mapped_column(String(24), default="draft")
