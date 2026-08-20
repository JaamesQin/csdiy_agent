"""Small deterministic helpers for learner-facing Chinese number references."""

from __future__ import annotations


_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_UNITS = {"十": 10, "百": 100, "千": 1000}


def parse_positive_int(value: str) -> int | None:
    cleaned = value.strip()
    if cleaned.isdigit():
        parsed = int(cleaned)
        return parsed if parsed > 0 else None
    if not cleaned or any(char not in _DIGITS and char not in _UNITS for char in cleaned):
        return None
    if not any(char in _UNITS for char in cleaned):
        parsed = int("".join(str(_DIGITS[char]) for char in cleaned))
        return parsed if parsed > 0 else None
    total = 0
    current = 0
    for char in cleaned:
        if char in _DIGITS:
            current = _DIGITS[char]
            continue
        unit = _UNITS[char]
        total += (current or 1) * unit
        current = 0
    parsed = total + current
    return parsed if parsed > 0 else None
