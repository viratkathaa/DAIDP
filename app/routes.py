"""
API Routes: Exposes the generation pipeline as REST endpoints.
"""

import time
import json
import uuid
from fastapi import APIRouter, HTTPException
from app.schemas import (
    CampaignBrief, PipelineState, RefinementRequest, EvaluationScore
)
from app.generation_engine import (
    generate_personas, generate_angles, generate_scripts, generate_storyboards
)
from app.constraint_layer import validate_all
from app.refinement_module import refine_asset
from app.evaluation_layer import evaluate_campaign

router = APIRouter(prefix="/api")

# In-memory campaign store (prototype)
campaigns: dict[str, PipelineState] = {}


@router.post("/campaign")
def create_campaign(brief: CampaignBrief):
    """Initialize a new campaign with the provided brief."""
    campaign_id = str(uuid.uuid4())[:8]
    state = PipelineState(campaign_id=campaign_id, brief=brief, current_stage="brief")
    campaigns[campaign_id] = state
    return {"campaign_id": campaign_id, "status": "created"}


@router.get("/campaign/{campaign_id}")
def get_campaign(campaign_id: str):
    """Get the current state of a campaign."""
    state = campaigns.get(campaign_id)
    if not state:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return state.model_dump()


@router.post("/generate/{campaign_id}/personas")
def gen_personas(campaign_id: str):
    """Generate audience personas for the campaign."""
    state = campaigns.get(campaign_id)
    if not state or not state.brief:
        raise HTTPException(status_code=404, detail="Campaign not found")

    start = time.time()
    state.personas = generate_personas(state.brief)

    # Validate
    results = validate_all(state.brief, personas=state.personas)
    state.constraint_results.update({k: v.model_dump() for k, v in results.items()})

    state.current_stage = "personas"
    state.metrics["personas_time"] = round(time.time() - start, 2)

    return {
        "personas": [p.model_dump() for p in state.personas],
        "constraints": {k: v.model_dump() for k, v in results.items()},
        "time_taken": state.metrics["personas_time"]
    }


@router.post("/generate/{campaign_id}/angles")
def gen_angles(campaign_id: str):
    """Generate campaign angles and hooks."""
    state = campaigns.get(campaign_id)
    if not state or not state.personas:
        raise HTTPException(status_code=400, detail="Generate personas first")

    start = time.time()
    state.angles = generate_angles(state.brief, state.personas)

    results = validate_all(state.brief, angles=state.angles)
    state.constraint_results.update({k: v.model_dump() for k, v in results.items()})

    state.current_stage = "angles"
    state.metrics["angles_time"] = round(time.time() - start, 2)

    return {
        "angles": [a.model_dump() for a in state.angles],
        "constraints": {k: v.model_dump() for k, v in results.items()},
        "time_taken": state.metrics["angles_time"]
    }


@router.post("/generate/{campaign_id}/scripts")
def gen_scripts(campaign_id: str):
    """Generate ad scripts with scene breakdowns."""
    state = campaigns.get(campaign_id)
    if not state or not state.angles:
        raise HTTPException(status_code=400, detail="Generate angles first")

    start = time.time()
    state.scripts = generate_scripts(state.brief, state.angles, state.personas)

    results = validate_all(state.brief, scripts=state.scripts)
    state.constraint_results.update({k: v.model_dump() for k, v in results.items()})

    state.current_stage = "scripts"
    state.metrics["scripts_time"] = round(time.time() - start, 2)

    return {
        "scripts": [s.model_dump() for s in state.scripts],
        "constraints": {k: v.model_dump() for k, v in results.items()},
        "time_taken": state.metrics["scripts_time"]
    }


@router.post("/generate/{campaign_id}/storyboards")
def gen_storyboards(campaign_id: str):
    """Generate storyboards from scripts."""
    state = campaigns.get(campaign_id)
    if not state or not state.scripts:
        raise HTTPException(status_code=400, detail="Generate scripts first")

    start = time.time()
    state.storyboards = generate_storyboards(state.brief, state.scripts)

    results = validate_all(state.brief, storyboards=state.storyboards)
    state.constraint_results.update({k: v.model_dump() for k, v in results.items()})

    state.current_stage = "storyboards"
    state.metrics["storyboards_time"] = round(time.time() - start, 2)

    return {
        "storyboards": [sb.model_dump() for sb in state.storyboards],
        "constraints": {k: v.model_dump() for k, v in results.items()},
        "time_taken": state.metrics["storyboards_time"]
    }


@router.post("/generate/{campaign_id}/evaluate")
def run_evaluation(campaign_id: str):
    """Run the evaluation layer on all generated assets."""
    state = campaigns.get(campaign_id)
    if not state or not state.storyboards:
        raise HTTPException(status_code=400, detail="Generate storyboards first")

    start = time.time()
    state.evaluation = evaluate_campaign(
        state.brief, state.personas, state.angles, state.scripts, state.storyboards
    )

    # Full constraint validation
    all_results = validate_all(
        state.brief,
        personas=state.personas,
        angles=state.angles,
        scripts=state.scripts,
        storyboards=state.storyboards
    )
    state.constraint_results = {k: v.model_dump() for k, v in all_results.items()}

    state.current_stage = "evaluation"
    state.metrics["evaluation_time"] = round(time.time() - start, 2)
    state.metrics["total_time"] = round(
        sum(v for k, v in state.metrics.items() if k.endswith("_time")), 2
    )

    return {
        "evaluation": state.evaluation.model_dump(),
        "constraints": state.constraint_results,
        "metrics": state.metrics,
        "time_taken": state.metrics["evaluation_time"]
    }


@router.post("/refine/{campaign_id}")
def refine(campaign_id: str, request: RefinementRequest):
    """Refine a generated asset using natural language instruction."""
    state = campaigns.get(campaign_id)
    if not state:
        raise HTTPException(status_code=404, detail="Campaign not found")

    refined = refine_asset(state.brief, request)
    return {"refined_content": refined, "stage": request.stage}


@router.post("/adversarial-test/{campaign_id}")
def adversarial_test(campaign_id: str, test_prompt: dict):
    """A/B Policy Compliance test: feed prohibited content and verify blocking."""
    state = campaigns.get(campaign_id)
    if not state:
        raise HTTPException(status_code=404, detail="Campaign not found")

    from app.schemas import CampaignAngle
    from app.constraint_layer import validate_angles

    # Create a test angle with the adversarial content
    test_angle = CampaignAngle(
        angle_name="Adversarial Test",
        hook=test_prompt.get("hook", ""),
        emotional_trigger="test",
        value_proposition=test_prompt.get("value_proposition", ""),
        target_persona="Test",
        cta=test_prompt.get("cta", "")
    )

    result = validate_angles([test_angle], state.brief)

    return {
        "blocked": not result.passed,
        "violations": [v.model_dump() for v in result.violations],
        "test_input": test_prompt,
        "verdict": "BLOCKED - Policy violation detected" if not result.passed else "PASSED - No violations found"
    }
