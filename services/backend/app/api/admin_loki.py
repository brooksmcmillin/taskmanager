"""Loki log ingestion summary API for admin users."""

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings
from app.dependencies import AdminUser

router = APIRouter(prefix="/api/admin/loki", tags=["admin-loki"])

LOKI_TIMEOUT = 10.0
KEY_LABELS = ["container", "logstream"]


class LokiSummary(BaseModel):
    """Response schema for Loki ingestion summary."""

    connected: bool
    labels: list[str]
    label_values: dict[str, list[str]]
    series_count: int
    error: str | None = None


@router.get("/summary", response_model=LokiSummary)
async def get_loki_summary(_admin: AdminUser) -> LokiSummary:
    """Get a summary of what Loki is ingesting.

    Returns label names, values for key labels, and active series count.
    Requires admin privileges.
    """
    base_url = settings.loki_url

    try:
        async with httpx.AsyncClient(timeout=LOKI_TIMEOUT) as client:
            # Fetch all label names
            labels_resp = await client.get(f"{base_url}/loki/api/v1/labels")
            labels_resp.raise_for_status()
            labels: list[str] = labels_resp.json().get("data", [])

            # Fetch values for key labels
            label_values: dict[str, list[str]] = {}
            for label in KEY_LABELS:
                if label in labels:
                    values_resp = await client.get(
                        f"{base_url}/loki/api/v1/label/{label}/values"
                    )
                    values_resp.raise_for_status()
                    label_values[label] = values_resp.json().get("data", [])

            # Fetch active series count
            series_resp = await client.get(
                f"{base_url}/loki/api/v1/series",
                params={"match[]": '{__name__=~".+"}'},
            )
            series_resp.raise_for_status()
            series: list[object] = series_resp.json().get("data", [])

            return LokiSummary(
                connected=True,
                labels=labels,
                label_values=label_values,
                series_count=len(series),
            )

    except Exception as exc:
        return LokiSummary(
            connected=False,
            labels=[],
            label_values={},
            series_count=0,
            error=str(exc),
        )
