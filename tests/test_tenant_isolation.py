from app.models import ApprovalModel, AudienceModel, CampaignModel, CreativeModel


def test_every_marketing_aggregate_has_a_required_tenant_boundary():
    for model in (CampaignModel, ApprovalModel, AudienceModel, CreativeModel):
        column = model.__table__.columns["tenant_id"]
        assert column.nullable is False
