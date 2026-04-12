"""
Refinement Module: Supports natural language asset modification.
Users can request changes to any generated asset using plain English.
"""

import json
from app.schemas import (
    CampaignBrief, Persona, CampaignAngle, AdScript, Storyboard,
    RefinementRequest
)
from app.generation_engine import refine_content, _parse_json
from app import config


def _apply_demo_refinement(stage: str, content: dict | list, instruction: str) -> dict | list:
    """In demo mode, apply simple keyword-based refinements."""
    text = json.dumps(content)
    instruction_lower = instruction.lower()

    # Tone changes
    if "formal" in instruction_lower or "professional" in instruction_lower:
        text = text.replace("!", ".")
    if "casual" in instruction_lower or "friendly" in instruction_lower:
        text = text.replace(".", "! ").replace("!  ", "! ")

    # Simple find/replace instructions like "change X to Y"
    if "change" in instruction_lower and "to" in instruction_lower:
        parts = instruction_lower.split("change", 1)[1]
        if " to " in parts:
            old, new = parts.split(" to ", 1)
            old = old.strip().strip('"\'')
            new = new.strip().strip('"\'')
            if old and new:
                text = text.replace(old, new)

    return json.loads(text)


def refine_asset(brief: CampaignBrief, request: RefinementRequest) -> str:
    """Refine a generated asset based on natural language instruction.

    Returns the refined content as a JSON string.
    """
    if config.DEMO_MODE:
        content = json.loads(request.current_content)
        refined = _apply_demo_refinement(request.stage, content, request.instruction)
        return json.dumps(refined, indent=2)

    return refine_content(
        brief=brief,
        stage=request.stage,
        content=request.current_content,
        instruction=request.instruction
    )
