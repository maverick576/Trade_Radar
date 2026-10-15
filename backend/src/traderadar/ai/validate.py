"""Validation logic for AI outputs to prevent hallucination and fabricated numbers."""

import math
from typing import Any

from traderadar.ai.schemas import (
    AIComment,
    AIInputPayload,
    MarketBriefNarrative,
    MarketBriefPayload,
)


def extract_numbers_from_dict(obj: Any) -> list[float]:
    """Recursively extract all numeric float values from nested dict/list structures."""
    nums: list[float] = []
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if not math.isnan(obj) and not math.isinf(obj):
            nums.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            nums.extend(extract_numbers_from_dict(v))
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            nums.extend(extract_numbers_from_dict(item))
    return nums


def is_number_in_collection(
    target: float, collection: list[float], rel_tol: float = 0.008, abs_tol: float = 0.5
) -> bool:
    """Check if target number matches any number in collection within tolerance."""
    for val in collection:
        if math.isclose(target, val, rel_tol=rel_tol, abs_tol=abs_tol):
            return True
    return False


def validate_ai_comment(
    comment: AIComment,
    payload: AIInputPayload,
) -> tuple[bool, str | None]:
    """Validate AI comment against input payload.

    Returns:
        (is_valid, failure_reason)
    """
    # 1. Check ringkasan word count (spec: <= 120 kata, allow 150 max buffer)
    words = comment.ringkasan.strip().split()
    if len(words) > 160:
        return False, f"Ringkasan melebihi batas kata: {len(words)} kata (> 160 kata)"

    # 2. Extract all numbers from input payload
    payload_dict = payload.model_dump(mode="json")
    valid_numbers = extract_numbers_from_dict(payload_dict)

    if not valid_numbers:
        return True, None

    # 3. Verify every level in level_penting is present in input data
    if comment.level_penting:
        for lvl in comment.level_penting:
            # Check if this price level is grounded in input numbers
            if not is_number_in_collection(lvl, valid_numbers):
                return (
                    False,
                    f"Level {lvl} tidak ada dalam input data (terindikasi halusinasi)",
                )

    return True, None


def validate_brief_narrative(
    narrative: MarketBriefNarrative,
    payload: MarketBriefPayload,
) -> tuple[bool, str | None]:
    """Validate market brief narrative against input snapshot data."""
    payload_dict = payload.model_dump(mode="json")
    valid_numbers = extract_numbers_from_dict(payload_dict)

    for sym_key, sym_nar in narrative.symbols.items():
        if sym_nar.level_kunci and valid_numbers:
            for lvl in sym_nar.level_kunci:
                if not is_number_in_collection(lvl, valid_numbers):
                    return (
                        False,
                        f"Level kunci {lvl} ({sym_key}) tidak ada dalam snapshot pasar",
                    )

    return True, None
