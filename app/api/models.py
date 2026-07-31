"""Models endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.security import require_bearer_token

router = APIRouter()


@router.get("/v1/models", dependencies=[Depends(require_bearer_token)])
async def list_models() -> dict[str, object]:
    return {
        "object": "list",
        "data": [
            {
                "id": "coursepilot-probe",
                "object": "model",
                "owned_by": "coursepilot",
            }
        ],
    }
