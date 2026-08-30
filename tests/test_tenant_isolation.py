from app.db import Base
from app.models import Campaign


def test_campaign_has_tenant_boundary():
    assert "tenant_id" in Campaign.__table__.columns.keys()
    assert Campaign.__table__.columns["tenant_id"].nullable is False
