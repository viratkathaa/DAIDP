"""
API Routes: Exposes the generation pipeline as REST endpoints.
"""

import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from app.schemas import (
    CampaignBrief, CampaignCreateRequest, CampaignInput, PipelineState, RefinementRequest, SelectionRequest,
    TargetMarketExpansionRequest, IdeaRequest
)
from app.generation_engine import (
    generate_brief_suggestions, generate_personas, generate_angles,
    generate_scripts, generate_storyboards, generate_related_target_markets,
    extract_idea_fields
)
from app.constraint_layer import validate_all
from app.refinement_module import refine_asset
from app.evaluation_layer import evaluate_campaign
from app.video_pipeline import (
    build_video_prompt_exports,
    create_contact_sheets,
    download_video,
    evaluate_video_output,
    generate_video_from_prompt,
    resolve_local_video_url,
    save_uploaded_video,
    validate_video_file,
)
from app.example_cache import ensure_min_delay, get_example_key, load_stage, save_stage

router = APIRouter(prefix="/api")

# In-memory campaign store (prototype)
campaigns: dict[str, PipelineState] = {}


def _load_cached_stage(state: PipelineState, stage: str) -> Optional[dict]:
    if not state.brief:
        return None
    example_key = get_example_key(state.brief)
    if not example_key:
        return None
    return load_stage(example_key, stage)


def _save_cached_stage(state: PipelineState, stage: str, payload: dict) -> None:
    if not state.brief:
        return
    example_key = get_example_key(state.brief)
    if not example_key:
        return
    save_stage(example_key, stage, payload)


def _normalized_selection(items: list, selection: Optional[SelectionRequest]) -> list[int]:
    if not selection or not selection.selected_indices:
        return list(range(len(items)))
    indices: list[int] = []
    for index in selection.selected_indices:
        if index < 0 or index >= len(items):
            raise HTTPException(status_code=400, detail="Selection index out of range")
        if index not in indices:
            indices.append(index)
    return indices


def _ensure_prompt_exports(state: PipelineState) -> None:
    if state.prompt_exports:
        return
    if not state.storyboards or not state.scripts or not state.brief:
        raise HTTPException(status_code=400, detail="Generate storyboards first")
    state.selected_storyboard_indices = list(range(len(state.storyboards)))
    state.prompt_exports = build_video_prompt_exports(state.brief, state.storyboards, state.scripts)


def _storyboard_for_prompt(state: PipelineState, prompt_index: int):
    source_index = state.selected_storyboard_indices[prompt_index] if (
        state.selected_storyboard_indices and prompt_index < len(state.selected_storyboard_indices)
    ) else prompt_index
    if source_index < 0 or source_index >= len(state.storyboards):
        raise HTTPException(status_code=400, detail="Storyboard selection out of range")
    return state.storyboards[source_index]


def _evaluate_local_video(
    campaign_id: str,
    state: PipelineState,
    prompt_index: int,
    local_video_path: Path,
    public_video_url: str,
) -> dict:
    prompt_export = state.prompt_exports[prompt_index]
    storyboard = _storyboard_for_prompt(state, prompt_index)
    contact_sheets, duration = create_contact_sheets(campaign_id, local_video_path)
    contact_sheet_paths = [Path(sheet.image_url.lstrip("/")) for sheet in contact_sheets]
    report = evaluate_video_output(
        state.brief,
        prompt_export,
        local_video_path,
        contact_sheet_paths,
        duration,
    )
    return {
        "video_url": public_video_url,
        "prompt_title": prompt_export.title,
        "prompt_text": prompt_export.prompt,
        "storyboard_name": storyboard.script_name,
        "storyboard_sheets": [sheet.model_dump() for sheet in contact_sheets],
        "duration_seconds": duration,
        "evaluation": report.model_dump(),
    }


@router.post("/extract-idea")
def extract_idea(request: IdeaRequest):
    """Extract brand info from a raw idea string."""
    extraction = extract_idea_fields(request.raw_idea)
    return extraction.model_dump()


@router.post("/campaign")
def create_campaign(request: CampaignCreateRequest):
    """Initialize a campaign from either a raw-idea input or a finalized brief."""
    campaign_id = str(uuid.uuid4())[:8]
    campaign_input = request.to_campaign_input()
    brief = request.to_campaign_brief()
    state = PipelineState(
        campaign_id=campaign_id,
        campaign_input=campaign_input,
        brief=brief,
        current_stage="brief_confirmed" if brief else "brief"
    )
    campaigns[campaign_id] = state
    return {
        "campaign_id": campaign_id,
        "status": "created",
        "brief_ready": brief is not None,
    }


@router.post("/generate/{campaign_id}/brief-assist")
def generate_brief_assist(campaign_id: str):
    """Generate a cleaned-up product description and selectable brief options."""
    state = campaigns.get(campaign_id)
    if not state or not state.campaign_input:
        raise HTTPException(status_code=404, detail="Campaign not found")

    start = time.time()
    state.brief_suggestions = generate_brief_suggestions(state.campaign_input)
    state.current_stage = "brief_assist"
    state.metrics["brief_assist_time"] = round(time.time() - start, 2)

    return {
        "suggestions": state.brief_suggestions.model_dump(),
        "time_taken": state.metrics["brief_assist_time"]
    }


@router.post("/generate/{campaign_id}/target-market-tags")
def generate_target_market_tags(campaign_id: str, request: TargetMarketExpansionRequest):
    """Generate more target market tags related to a selected audience tag."""
    state = campaigns.get(campaign_id)
    if not state or not state.campaign_input:
        raise HTTPException(status_code=404, detail="Campaign not found")

    tags = generate_related_target_markets(
        state.campaign_input,
        request.seed_tag,
        request.existing_tags,
    )
    return {"target_markets": tags}


@router.post("/campaign/{campaign_id}/brief")
def finalize_brief(campaign_id: str, brief: CampaignBrief):
    """Finalize the campaign brief after user review."""
    state = campaigns.get(campaign_id)
    if not state:
        raise HTTPException(status_code=404, detail="Campaign not found")

    state.brief = brief
    state.current_stage = "brief_confirmed"
    return {"status": "ready", "brief": state.brief.model_dump()}


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
    cached = _load_cached_stage(state, "personas")
    if cached:
        from app.schemas import Persona
        simulated_time = ensure_min_delay(start)
        state.personas = [Persona(**p) for p in cached["personas"]]
        state.constraint_results.update(cached.get("constraints", {}))
        state.current_stage = "personas"
        state.metrics["personas_time"] = simulated_time
        payload = dict(cached)
        payload["time_taken"] = simulated_time
        return payload

    state.personas = generate_personas(state.brief)

    # Validate
    results = validate_all(state.brief, personas=state.personas)
    state.constraint_results.update({k: v.model_dump() for k, v in results.items()})

    state.current_stage = "personas"
    state.metrics["personas_time"] = round(time.time() - start, 2)

    payload = {
        "personas": [p.model_dump() for p in state.personas],
        "constraints": {k: v.model_dump() for k, v in results.items()},
        "time_taken": state.metrics["personas_time"]
    }
    _save_cached_stage(state, "personas", payload)
    return payload


@router.post("/generate/{campaign_id}/angles")
def gen_angles(campaign_id: str):
    """Generate campaign angles and hooks."""
    state = campaigns.get(campaign_id)
    if not state or not state.personas:
        raise HTTPException(status_code=400, detail="Generate personas first")

    start = time.time()
    cached = _load_cached_stage(state, "angles")
    if cached:
        from app.schemas import CampaignAngle
        simulated_time = ensure_min_delay(start)
        state.angles = [CampaignAngle(**a) for a in cached["angles"]]
        state.constraint_results.update(cached.get("constraints", {}))
        state.current_stage = "angles"
        state.metrics["angles_time"] = simulated_time
        payload = dict(cached)
        payload["time_taken"] = simulated_time
        return payload

    state.angles = generate_angles(state.brief, state.personas)

    results = validate_all(state.brief, angles=state.angles)
    state.constraint_results.update({k: v.model_dump() for k, v in results.items()})

    state.current_stage = "angles"
    state.metrics["angles_time"] = round(time.time() - start, 2)

    payload = {
        "angles": [a.model_dump() for a in state.angles],
        "constraints": {k: v.model_dump() for k, v in results.items()},
        "time_taken": state.metrics["angles_time"]
    }
    _save_cached_stage(state, "angles", payload)
    return payload


@router.post("/generate/{campaign_id}/scripts")
def gen_scripts(campaign_id: str, selection: Optional[SelectionRequest] = None):
    """Generate ad scripts with scene breakdowns."""
    state = campaigns.get(campaign_id)
    if not state or not state.angles:
        raise HTTPException(status_code=400, detail="Generate angles first")

    start = time.time()
    cached = _load_cached_stage(state, "scripts")
    if cached and not selection:
        from app.schemas import AdScript
        simulated_time = ensure_min_delay(start)
        state.selected_angle_indices = cached.get("selected_angle_indices", list(range(len(state.angles))))
        state.scripts = [AdScript(**s) for s in cached["scripts"]]
        state.constraint_results.update(cached.get("constraints", {}))
        state.current_stage = "scripts"
        state.metrics["scripts_time"] = simulated_time
        payload = dict(cached)
        payload["time_taken"] = simulated_time
        return payload

    state.selected_angle_indices = _normalized_selection(state.angles, selection)
    selected_angles = [state.angles[index] for index in state.selected_angle_indices]
    state.scripts = generate_scripts(state.brief, selected_angles, state.personas)

    results = validate_all(state.brief, scripts=state.scripts)
    state.constraint_results.update({k: v.model_dump() for k, v in results.items()})

    state.current_stage = "scripts"
    state.metrics["scripts_time"] = round(time.time() - start, 2)

    payload = {
        "scripts": [s.model_dump() for s in state.scripts],
        "selected_angle_indices": state.selected_angle_indices,
        "constraints": {k: v.model_dump() for k, v in results.items()},
        "time_taken": state.metrics["scripts_time"]
    }
    if not selection:
        _save_cached_stage(state, "scripts", payload)
    return payload


@router.post("/generate/{campaign_id}/storyboards")
def gen_storyboards(campaign_id: str, selection: Optional[SelectionRequest] = None):
    """Generate storyboards from scripts."""
    state = campaigns.get(campaign_id)
    if not state or not state.scripts:
        raise HTTPException(status_code=400, detail="Generate scripts first")

    start = time.time()
    cached = _load_cached_stage(state, "storyboards")
    if cached and not selection:
        from app.schemas import Storyboard
        simulated_time = ensure_min_delay(start)
        state.selected_script_indices = cached.get("selected_script_indices", list(range(len(state.scripts))))
        state.storyboards = [Storyboard(**sb) for sb in cached["storyboards"]]
        state.constraint_results.update(cached.get("constraints", {}))
        state.current_stage = "storyboards"
        state.metrics["storyboards_time"] = simulated_time
        payload = dict(cached)
        payload["time_taken"] = simulated_time
        return payload

    state.selected_script_indices = _normalized_selection(state.scripts, selection)
    selected_scripts = [state.scripts[index] for index in state.selected_script_indices]
    state.storyboards = generate_storyboards(state.brief, selected_scripts)

    results = validate_all(state.brief, storyboards=state.storyboards)
    state.constraint_results.update({k: v.model_dump() for k, v in results.items()})

    state.current_stage = "storyboards"
    state.metrics["storyboards_time"] = round(time.time() - start, 2)

    payload = {
        "storyboards": [sb.model_dump() for sb in state.storyboards],
        "selected_script_indices": state.selected_script_indices,
        "constraints": {k: v.model_dump() for k, v in results.items()},
        "time_taken": state.metrics["storyboards_time"]
    }
    if not selection:
        _save_cached_stage(state, "storyboards", payload)
    return payload


@router.post("/generate/{campaign_id}/video-prompts")
def gen_video_prompts(campaign_id: str, selection: Optional[SelectionRequest] = None):
    """Generate copy-ready video prompts from chosen storyboards."""
    state = campaigns.get(campaign_id)
    if not state or not state.storyboards:
        raise HTTPException(status_code=400, detail="Generate storyboards first")

    start = time.time()
    cached = _load_cached_stage(state, "video_prompts")
    if cached and not selection:
        from app.schemas import VideoPromptExport
        simulated_time = ensure_min_delay(start)
        state.selected_storyboard_indices = cached.get("selected_storyboard_indices", list(range(len(state.storyboards))))
        state.prompt_exports = [VideoPromptExport(**prompt) for prompt in cached["prompts"]]
        state.current_stage = "video_prompts"
        payload = dict(cached)
        payload["time_taken"] = simulated_time
        return payload

    state.selected_storyboard_indices = _normalized_selection(state.storyboards, selection)
    selected_storyboards = [state.storyboards[index] for index in state.selected_storyboard_indices]
    state.prompt_exports = build_video_prompt_exports(state.brief, selected_storyboards, state.scripts)
    state.current_stage = "video_prompts"

    payload = {
        "prompts": [prompt.model_dump() for prompt in state.prompt_exports],
        "selected_storyboard_indices": state.selected_storyboard_indices,
    }
    if not selection:
        _save_cached_stage(state, "video_prompts", payload)
    return payload


@router.post("/generate-video/{campaign_id}")
def generate_video(
    campaign_id: str,
    prompt_index: int = Form(0),
    model: str = Form(...),
    api_key: str = Form(...),
):
    """Generate a video from the selected prompt using a BYOK model."""
    state = campaigns.get(campaign_id)
    if not state or not state.storyboards or not state.brief:
        raise HTTPException(status_code=400, detail="Generate storyboards first")

    _ensure_prompt_exports(state)
    if prompt_index < 0 or prompt_index >= len(state.prompt_exports):
        raise HTTPException(status_code=400, detail="Prompt selection out of range")
    if not api_key.strip():
        raise HTTPException(status_code=400, detail="Enter an API key for the selected model")

    start = time.time()
    storyboard = _storyboard_for_prompt(state, prompt_index)
    prompt_export = state.prompt_exports[prompt_index]
    try:
        local_video_path, public_video_url, provider_job_id = generate_video_from_prompt(
            campaign_id,
            prompt_export,
            storyboard,
            model,
            api_key.strip(),
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "video_url": public_video_url,
        "prompt_title": prompt_export.title,
        "prompt_text": prompt_export.prompt,
        "storyboard_name": storyboard.script_name,
        "model": model.strip().lower(),
        "provider_job_id": provider_job_id,
        "time_taken": round(time.time() - start, 2),
    }


@router.post("/generate/{campaign_id}/evaluate")
def run_evaluation(campaign_id: str):
    """Run the evaluation layer on all generated assets."""
    state = campaigns.get(campaign_id)
    if not state or not state.storyboards:
        raise HTTPException(status_code=400, detail="Generate storyboards first")

    start = time.time()
    cached = _load_cached_stage(state, "evaluation")
    if cached:
        from app.schemas import EvaluationScore
        simulated_time = ensure_min_delay(start)
        state.evaluation = EvaluationScore(**cached["evaluation"])
        state.constraint_results = cached.get("constraints", {})
        state.current_stage = "evaluation"
        state.metrics.update(cached.get("metrics", {}))
        state.metrics["evaluation_time"] = simulated_time
        if "total_time" in state.metrics:
            stage_time_total = sum(v for k, v in state.metrics.items() if k.endswith("_time"))
            state.metrics["total_time"] = round(stage_time_total, 2)
        payload = dict(cached)
        payload["metrics"] = dict(state.metrics)
        payload["time_taken"] = simulated_time
        return payload

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

    payload = {
        "evaluation": state.evaluation.model_dump(),
        "constraints": state.constraint_results,
        "metrics": state.metrics,
        "time_taken": state.metrics["evaluation_time"]
    }
    _save_cached_stage(state, "evaluation", payload)
    return payload


@router.post("/evaluate-video/{campaign_id}")
async def evaluate_video(
    campaign_id: str,
    prompt_index: int = Form(0),
    video_url: str = Form(""),
    video_file: Optional[UploadFile] = File(default=None),
):
    """Evaluate a generated video against the selected exported prompt."""
    state = campaigns.get(campaign_id)
    if not state or not state.storyboards or not state.brief:
        raise HTTPException(status_code=400, detail="Generate storyboards first")
    _ensure_prompt_exports(state)
    if prompt_index < 0 or prompt_index >= len(state.prompt_exports):
        raise HTTPException(status_code=400, detail="Prompt selection out of range")
    if not video_file and not video_url.strip():
        raise HTTPException(status_code=400, detail="Upload a video file or provide a direct video URL")

    start = time.time()
    if video_file:
        suffix = Path(video_file.filename or "video.mp4").suffix or ".mp4"
        temp_path = Path(f"/tmp/{uuid.uuid4().hex}{suffix}")
        temp_path.write_bytes(await video_file.read())
        try:
            saved_path, public_video_url = save_uploaded_video(campaign_id, temp_path, video_file.filename or "video.mp4")
            local_video_path = saved_path
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            temp_path.unlink(missing_ok=True)
    else:
        resolved_local_path = resolve_local_video_url(video_url.strip())
        if resolved_local_path:
            try:
                validate_video_file(resolved_local_path)
                local_video_path = resolved_local_path
                public_video_url = video_url.strip()
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        else:
            try:
                local_video_path, public_video_url = download_video(campaign_id, video_url.strip())
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        payload = _evaluate_local_video(
            campaign_id,
            state,
            prompt_index,
            local_video_path,
            public_video_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    elapsed = round(time.time() - start, 2)
    payload["time_taken"] = elapsed
    return payload


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
