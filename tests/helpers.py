from __future__ import annotations

import json
from typing import Any


def parse_sse(body: str) -> list[dict[str, Any] | str]:
    events: list[dict[str, Any] | str] = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        assert block.startswith("data: ")
        data = block.removeprefix("data: ")
        events.append(data if data == "[DONE]" else json.loads(data))
    return events
