"""
Evaluation Layer: Multi-point quality assessment of generated assets.
Scores outputs on brand alignment, message clarity, visual coherence,
CTA effectiveness, and overall quality.
"""

import re
from app.schemas import (
    CampaignBrief, EvaluationScore, Persona, CampaignAngle,
    AdScript, Storyboard
)


def _score_brand_alignment(brief: CampaignBrief, scripts: list[AdScript], storyboards: list[Storyboard]) -> tuple[float, list[str]]:
    """Score how well content aligns with brand guidelines."""
    score = 8.0
    feedback = []

    # Check brand name presence in scripts
    brand_mentions = 0
    for script in scripts:
        for scene in script.scenes:
            full_text = f"{scene.narration} {scene.on_screen_text}"
            brand_mentions += full_text.lower().count(brief.brand_name.lower())

    if brand_mentions == 0:
        score -= 3.0
        feedback.append("Brand name not mentioned in any script narration or on-screen text")
    elif brand_mentions < len(scripts):
        score -= 1.0
        feedback.append("Brand name could be more prominent across scripts")
    else:
        feedback.append("Brand name consistently referenced across scripts")

    # Check if brand guidelines keywords appear
    if brief.brand_guidelines:
        guideline_words = [w.strip().lower() for w in brief.brand_guidelines.split(",") if len(w.strip()) > 3]
        if guideline_words:
            all_text = " ".join(
                f"{s.narration} {s.on_screen_text}" for script in scripts for s in script.scenes
            ).lower()
            matched = sum(1 for w in guideline_words if w in all_text)
            ratio = matched / len(guideline_words) if guideline_words else 1
            if ratio < 0.3:
                score -= 2.0
                feedback.append("Few brand guideline keywords reflected in content")
            elif ratio > 0.6:
                score += 1.0
                feedback.append("Brand guidelines well-reflected in generated content")

    # Check color palette in storyboards
    for sb in storyboards:
        if len(sb.color_palette) >= 3:
            score += 0.5
            feedback.append(f"Storyboard '{sb.script_name}' has a comprehensive color palette")
            break

    return min(max(score, 0), 10), feedback


def _score_message_clarity(scripts: list[AdScript]) -> tuple[float, list[str]]:
    """Score clarity and readability of the ad message."""
    score = 7.5
    feedback = []

    for script in scripts:
        # CTA check
        if script.cta_text and len(script.cta_text) > 5:
            score += 0.5
            feedback.append(f"'{script.concept_name}' has a clear CTA: '{script.cta_text}'")
        else:
            score -= 1.5
            feedback.append(f"'{script.concept_name}' lacks a strong call-to-action")

        # Check narration clarity (short sentences are clearer)
        total_words = 0
        long_sentences = 0
        for scene in script.scenes:
            words = scene.narration.split()
            total_words += len(words)
            sentences = re.split(r'[.!?]', scene.narration)
            for sent in sentences:
                if len(sent.split()) > 20:
                    long_sentences += 1

        if long_sentences > 0:
            score -= 0.5 * long_sentences
            feedback.append(f"'{script.concept_name}' has {long_sentences} overly long sentence(s) in narration")

        # On-screen text readability
        for scene in script.scenes:
            if scene.on_screen_text and len(scene.on_screen_text) > 50:
                score -= 0.5
                feedback.append(f"Scene {scene.scene_number} on-screen text may be too long for quick reading")

    return min(max(score, 0), 10), feedback


def _score_visual_coherence(storyboards: list[Storyboard]) -> tuple[float, list[str]]:
    """Score visual consistency across storyboard scenes."""
    score = 8.0
    feedback = []

    for sb in storyboards:
        # Check typography consistency
        if sb.typography_style:
            score += 0.5
            feedback.append(f"'{sb.script_name}' specifies typography style for consistency")

        # Check music mood
        if sb.music_mood:
            score += 0.3
            feedback.append(f"'{sb.script_name}' includes music direction")

        # Check scene transition smoothness (all scenes should have camera direction)
        scenes_with_direction = sum(1 for s in sb.scenes if s.camera_direction)
        if scenes_with_direction == len(sb.scenes):
            score += 0.5
            feedback.append(f"'{sb.script_name}' has complete camera direction coverage")
        else:
            score -= 0.5
            feedback.append(f"'{sb.script_name}' is missing camera direction in some scenes")

        # Check image prompt quality
        prompts_with_detail = sum(1 for s in sb.scenes if len(s.image_prompt) > 30)
        if prompts_with_detail == len(sb.scenes):
            score += 0.5
            feedback.append(f"'{sb.script_name}' has detailed image prompts for all scenes")

    return min(max(score, 0), 10), feedback


def _score_cta_effectiveness(scripts: list[AdScript], angles: list[CampaignAngle]) -> tuple[float, list[str]]:
    """Score the effectiveness of calls-to-action."""
    score = 7.0
    feedback = []

    action_words = ["try", "start", "get", "join", "discover", "launch", "create", "download", "shop", "buy", "learn", "sign up", "subscribe"]

    for script in scripts:
        cta = script.cta_text.lower()
        has_action = any(word in cta for word in action_words)
        if has_action:
            score += 1.0
            feedback.append(f"'{script.concept_name}' CTA uses strong action verb")
        else:
            score -= 0.5
            feedback.append(f"'{script.concept_name}' CTA could use a stronger action verb")

        # Check urgency
        urgency_words = ["today", "now", "free", "limited", "exclusive", "instant"]
        has_urgency = any(word in cta for word in urgency_words)
        if has_urgency:
            score += 0.5
            feedback.append(f"'{script.concept_name}' CTA creates urgency")

    for angle in angles:
        if angle.cta and len(angle.cta) > 3:
            score += 0.3

    return min(max(score, 0), 10), feedback


def evaluate_campaign(
    brief: CampaignBrief,
    personas: list[Persona],
    angles: list[CampaignAngle],
    scripts: list[AdScript],
    storyboards: list[Storyboard]
) -> EvaluationScore:
    """Run full evaluation across all quality dimensions."""

    brand_score, brand_feedback = _score_brand_alignment(brief, scripts, storyboards)
    clarity_score, clarity_feedback = _score_message_clarity(scripts)
    visual_score, visual_feedback = _score_visual_coherence(storyboards)
    cta_score, cta_feedback = _score_cta_effectiveness(scripts, angles)

    # Weighted overall score
    overall = (
        brand_score * 0.30 +
        clarity_score * 0.25 +
        visual_score * 0.25 +
        cta_score * 0.20
    )

    all_feedback = brand_feedback + clarity_feedback + visual_feedback + cta_feedback

    return EvaluationScore(
        brand_alignment=round(brand_score, 1),
        message_clarity=round(clarity_score, 1),
        visual_coherence=round(visual_score, 1),
        cta_effectiveness=round(cta_score, 1),
        overall_score=round(overall, 1),
        feedback=all_feedback
    )
