import os
from dataclasses import dataclass
from typing import Any
import httpx

META_GRAPH_BASE_URL = os.getenv("META_GRAPH_BASE_URL", "https://graph.facebook.com/v25.0")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
META_READ_SYNC_ENABLED = os.getenv("META_READ_SYNC_ENABLED", "false").lower() == "true"

@dataclass(frozen=True)
class MetaCampaignSnapshot:
    provider_campaign_id: str
    name: str
    status: str
    objective: str | None
    daily_budget_minor: int | None

class MetaReadClient:
    """Read-only adapter. No POST/PUT/PATCH/DELETE methods are exposed."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=15.0)

    async def list_campaigns(self, ad_account_id: str) -> list[MetaCampaignSnapshot]:
        if not META_READ_SYNC_ENABLED:
            return []
        if not META_ACCESS_TOKEN:
            raise RuntimeError("meta_access_token_missing")
        response = await self._client.get(
            f"{META_GRAPH_BASE_URL}/act_{ad_account_id}/campaigns",
            params={"fields": "id,name,status,objective,daily_budget", "access_token": META_ACCESS_TOKEN},
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        return [MetaCampaignSnapshot(provider_campaign_id=item["id"], name=item.get("name", ""), status=item.get("status", "UNKNOWN"), objective=item.get("objective"), daily_budget_minor=int(item["daily_budget"]) if item.get("daily_budget") else None) for item in payload.get("data", [])]
