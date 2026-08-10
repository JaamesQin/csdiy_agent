"""Models endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.security import SecurityPrincipal, require_principal

router = APIRouter()


@router.get("/v1/models")
async def list_models(
    _principal: SecurityPrincipal = Depends(require_principal),
) -> dict[str, object]:
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
