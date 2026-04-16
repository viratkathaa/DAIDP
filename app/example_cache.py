"""
Persistent cache for a few built-in example briefs so repeat demo runs avoid model calls.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any

from app.schemas import CampaignBrief


CACHE_ROOT = Path(".cache/example_stage_outputs")
CACHE_DELAY_MIN_SECONDS = 2.0
CACHE_DELAY_MAX_SECONDS = 10.0

EXAMPLE_BRIEFS: dict[str, dict[str, Any]] = {
    "nike": {
        "brand_name": "Nike",
        "product_name": "Pegasus Turbo Next",
        "product_description": (
            "A high-performance running shoe designed for urban runners who want speed, "
            "responsive cushioning, and street-ready style."
        ),
        "target_market": "Young urban runners and style-conscious fitness consumers",
        "marketing_objectives": "Drive launch awareness, boost product consideration, and increase online purchases",
        "platform": "instagram",
        "budget_tier": "high",
        "brand_guidelines": "Bold, kinetic, premium, aspirational, black-white-orange palette",
        "prohibited_claims": "",
        "competitors": "Adidas, New Balance",
    },
    "coffee": {
        "brand_name": "Volt Brew",
        "product_name": "Cold Charge RTD",
        "product_description": (
            "A ready-to-drink caffeinated coffee beverage that blends energy-drink intensity "
            "with premium iced coffee taste for busy professionals and creators."
        ),
        "target_market": "Busy professionals, creators, and on-the-go consumers needing clean energy",
        "marketing_objectives": "Drive trial, build brand awareness, and increase repeat purchase intent",
        "platform": "instagram",
        "budget_tier": "mid",
        "brand_guidelines": "Modern, sharp, fast-paced, premium convenience, silver and espresso tones",
        "prohibited_claims": "Guaranteed productivity boosts",
        "competitors": "Red Bull, Monster, Starbucks",
    },
    "beauty": {
        "brand_name": "Luma Skin",
        "product_name": "Radiant Ritual Collection",
        "product_description": (
            "A premium skincare and makeup line centered on radiant skin, confidence, and "
            "elevated daily beauty rituals."
        ),
        "target_market": "Beauty-conscious consumers seeking premium daily skincare and makeup rituals",
        "marketing_objectives": "Increase brand desirability, drive collection sales, and improve social engagement",
        "platform": "instagram",
        "budget_tier": "high",
        "brand_guidelines": "Polished, luxurious, emotionally resonant, soft neutrals and gold accents",
        "prohibited_claims": "Guaranteed skin transformation",
        "competitors": "Rare Beauty, Charlotte Tilbury, Fenty Beauty",
    },
}


def _normalize_value(value: Any) -> str:
    return str(value or "").strip().lower()


def get_example_key(brief: CampaignBrief) -> str | None:
    normalized = {
        "brand_name": _normalize_value(brief.brand_name),
        "product_name": _normalize_value(brief.product_name),
        "product_description": _normalize_value(brief.product_description),
        "target_market": _normalize_value(brief.target_market),
        "marketing_objectives": _normalize_value(brief.marketing_objectives),
        "platform": _normalize_value(getattr(brief.platform, "value", brief.platform)),
        "budget_tier": _normalize_value(brief.budget_tier),
        "brand_guidelines": _normalize_value(brief.brand_guidelines),
        "prohibited_claims": _normalize_value(brief.prohibited_claims),
        "competitors": _normalize_value(brief.competitors),
    }
    for key, example in EXAMPLE_BRIEFS.items():
        example_normalized = {field: _normalize_value(value) for field, value in example.items()}
        if normalized == example_normalized:
            return key
    return None


def load_stage(example_key: str, stage: str) -> dict[str, Any] | None:
    cache_path = CACHE_ROOT / example_key / f"{stage}.json"
    if not cache_path.exists():
        return None
    return json.loads(cache_path.read_text())


def save_stage(example_key: str, stage: str, payload: dict[str, Any]) -> None:
    cache_path = CACHE_ROOT / example_key / f"{stage}.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, indent=2))


def ensure_min_delay(
    start_time: float,
    seconds: float | None = None,
    min_seconds: float = CACHE_DELAY_MIN_SECONDS,
    max_seconds: float = CACHE_DELAY_MAX_SECONDS,
) -> float:
    target_seconds = seconds if seconds is not None else random.uniform(min_seconds, max_seconds)
    elapsed = time.time() - start_time
    if elapsed < target_seconds:
        time.sleep(target_seconds - elapsed)
    return round(target_seconds, 2)
