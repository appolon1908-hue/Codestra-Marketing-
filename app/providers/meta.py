from dataclasses import dataclass

@dataclass(frozen=True)
class MetaCampaignDraft:
    campaign_id: str
    objective: str
    daily_budget_minor: int
    currency: str

class MetaAdsConnector:
    """Provider boundary for Facebook/Instagram advertising.

    Production writes are intentionally unavailable in this foundation.
    """

    provider = "meta"
    live_writes_enabled = False

    def validate(self, draft: MetaCampaignDraft) -> list[str]:
        errors: list[str] = []
        if draft.daily_budget_minor < 0:
            errors.append("daily_budget_minor_must_be_non_negative")
        if len(draft.currency) != 3:
            errors.append("currency_must_be_iso_4217")
        return errors

    def publish(self, draft: MetaCampaignDraft) -> None:
        raise RuntimeError("meta_live_writes_disabled")
