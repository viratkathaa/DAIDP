"""
Constraint Layer: Enforces brand safety, policy compliance,
and platform-specific formatting rules on all generated content.
"""

import re
import json
from app.schemas import (
    CampaignBrief, ConstraintResult, ConstraintViolation,
    Persona, CampaignAngle, AdScript, Storyboard, AdPlatform
)

# Prohibited claim patterns
HEALTH_CLAIMS = [
    r"\bcures?\b", r"\btreat(?:s|ment)?\b", r"\bprevents?\b",
    r"\bguaranteed\s+(?:weight|health|cure)\b", r"\bmiracl(?:e|ous)\b",
    r"\bclinically\s+proven\b", r"\bdoctor\s+recommended\b",
    r"\bFDA\s+approved\b",
]

FINANCIAL_CLAIMS = [
    r"\bguaranteed\s+(?:returns?|income|profit)\b",
    r"\brisk[- ]free\b", r"\bget\s+rich\b",
    r"\bmake\s+money\s+fast\b", r"\bfinancial\s+freedom\b",
    r"\b\d+%\s+(?:returns?|ROI)\b",
]

SUPERLATIVE_CLAIMS = [
    r"\b(?:best|#1|number\s+one|world'?s?\s+(?:best|leading|top))\b",
    r"\bguaranteed\s+(?:best|results)\b",
    r"\bunbeatable\b", r"\bnothing\s+(?:better|compares)\b",
]

OFFENSIVE_PATTERNS = [
    r"\bstupid\b", r"\bidiot\b", r"\bhate\b",
    r"\bdiscriminat(?:e|ion|ory)\b",
]

PLATFORM_CONSTRAINTS = {
    AdPlatform.INSTAGRAM: {"max_duration": 60, "aspect": "9:16", "max_text_ratio": 0.20},
    AdPlatform.YOUTUBE: {"max_duration": 90, "aspect": "16:9", "max_text_ratio": 0.30},
    AdPlatform.FACEBOOK: {"max_duration": 60, "aspect": "1:1", "max_text_ratio": 0.20},
    AdPlatform.TIKTOK: {"max_duration": 60, "aspect": "9:16", "max_text_ratio": 0.20},
    AdPlatform.WEBSITE: {"max_duration": 120, "aspect": "16:9", "max_text_ratio": 0.40},
    AdPlatform.MOBILE_APP: {"max_duration": 30, "aspect": "9:16", "max_text_ratio": 0.25},
}


def _check_patterns(text: str, patterns: list[str], rule_name: str, severity: str, location: str) -> list[ConstraintViolation]:
    violations = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            violations.append(ConstraintViolation(
                rule=rule_name,
                severity=severity,
                message=f"Detected prohibited pattern: '{matches[0]}'",
                location=location
            ))
    return violations


def _check_competitor_mentions(text: str, competitors: str) -> list[ConstraintViolation]:
    if not competitors:
        return []
    violations = []
    for comp in [c.strip() for c in competitors.split(",") if c.strip()]:
        if re.search(r'\b' + re.escape(comp) + r'\b', text, re.IGNORECASE):
            violations.append(ConstraintViolation(
                rule="competitor_mention",
                severity="error",
                message=f"Competitor '{comp}' is mentioned in the content",
                location="content"
            ))
    return violations


def _check_custom_prohibited(text: str, prohibited: str) -> list[ConstraintViolation]:
    if not prohibited:
        return []
    violations = []
    for claim in [c.strip() for c in prohibited.split(",") if c.strip()]:
        if re.search(re.escape(claim), text, re.IGNORECASE):
            violations.append(ConstraintViolation(
                rule="custom_prohibited_claim",
                severity="error",
                message=f"Prohibited claim detected: '{claim}'",
                location="content"
            ))
    return violations


def validate_personas(personas: list[Persona], brief: CampaignBrief) -> ConstraintResult:
    violations = []
    rules_checked = 0

    for i, persona in enumerate(personas):
        loc = f"persona[{i}] ({persona.name})"
        full_text = f"{persona.persona_summary} {persona.buying_motivation} {' '.join(persona.interests)}"

        rules_checked += 3
        violations.extend(_check_patterns(full_text, OFFENSIVE_PATTERNS, "offensive_content", "error", loc))
        violations.extend(_check_competitor_mentions(full_text, brief.competitors))
        violations.extend(_check_custom_prohibited(full_text, brief.prohibited_claims))

    return ConstraintResult(
        passed=not any(v.severity == "error" for v in violations),
        violations=violations,
        checked_rules=rules_checked,
        passed_rules=rules_checked - len(violations)
    )


def validate_angles(angles: list[CampaignAngle], brief: CampaignBrief) -> ConstraintResult:
    violations = []
    rules_checked = 0

    for i, angle in enumerate(angles):
        loc = f"angle[{i}] ({angle.angle_name})"
        full_text = f"{angle.hook} {angle.value_proposition} {angle.cta}"

        rules_checked += 5
        violations.extend(_check_patterns(full_text, HEALTH_CLAIMS, "health_claim", "error", loc))
        violations.extend(_check_patterns(full_text, FINANCIAL_CLAIMS, "financial_claim", "error", loc))
        violations.extend(_check_patterns(full_text, SUPERLATIVE_CLAIMS, "superlative_claim", "warning", loc))
        violations.extend(_check_competitor_mentions(full_text, brief.competitors))
        violations.extend(_check_custom_prohibited(full_text, brief.prohibited_claims))

    return ConstraintResult(
        passed=not any(v.severity == "error" for v in violations),
        violations=violations,
        checked_rules=rules_checked,
        passed_rules=rules_checked - len(violations)
    )


def validate_scripts(scripts: list[AdScript], brief: CampaignBrief) -> ConstraintResult:
    violations = []
    rules_checked = 0
    platform_spec = PLATFORM_CONSTRAINTS.get(brief.platform, PLATFORM_CONSTRAINTS[AdPlatform.INSTAGRAM])

    for i, script in enumerate(scripts):
        loc = f"script[{i}] ({script.concept_name})"

        # Duration check
        rules_checked += 1
        if script.duration_seconds > platform_spec["max_duration"]:
            violations.append(ConstraintViolation(
                rule="duration_limit",
                severity="error",
                message=f"Script duration ({script.duration_seconds}s) exceeds platform max ({platform_spec['max_duration']}s)",
                location=loc
            ))

        # CTA presence check
        rules_checked += 1
        if not script.cta_text:
            violations.append(ConstraintViolation(
                rule="missing_cta",
                severity="warning",
                message="No call-to-action text found",
                location=loc
            ))

        # Check all scene content
        for j, scene in enumerate(script.scenes):
            scene_loc = f"{loc} > scene[{j}]"
            scene_text = f"{scene.narration} {scene.on_screen_text} {scene.visual_description}"

            rules_checked += 5
            violations.extend(_check_patterns(scene_text, HEALTH_CLAIMS, "health_claim", "error", scene_loc))
            violations.extend(_check_patterns(scene_text, FINANCIAL_CLAIMS, "financial_claim", "error", scene_loc))
            violations.extend(_check_patterns(scene_text, SUPERLATIVE_CLAIMS, "superlative_claim", "warning", scene_loc))
            violations.extend(_check_competitor_mentions(scene_text, brief.competitors))
            violations.extend(_check_custom_prohibited(scene_text, brief.prohibited_claims))

        # Scene duration consistency
        rules_checked += 1
        total_scene_dur = sum(s.duration_seconds for s in script.scenes)
        if abs(total_scene_dur - script.duration_seconds) > 5:
            violations.append(ConstraintViolation(
                rule="duration_mismatch",
                severity="warning",
                message=f"Sum of scene durations ({total_scene_dur}s) doesn't match total ({script.duration_seconds}s)",
                location=loc
            ))

    return ConstraintResult(
        passed=not any(v.severity == "error" for v in violations),
        violations=violations,
        checked_rules=rules_checked,
        passed_rules=rules_checked - len(violations)
    )


def validate_storyboards(storyboards: list[Storyboard], brief: CampaignBrief) -> ConstraintResult:
    violations = []
    rules_checked = 0

    for i, sb in enumerate(storyboards):
        loc = f"storyboard[{i}] ({sb.script_name})"

        # Color palette check
        rules_checked += 1
        if len(sb.color_palette) < 3:
            violations.append(ConstraintViolation(
                rule="insufficient_palette",
                severity="warning",
                message="Color palette has fewer than 3 colors",
                location=loc
            ))

        # Scene completeness
        rules_checked += 1
        for j, scene in enumerate(sb.scenes):
            if not scene.image_prompt:
                violations.append(ConstraintViolation(
                    rule="missing_image_prompt",
                    severity="warning",
                    message=f"Scene {j+1} is missing an image generation prompt",
                    location=f"{loc} > scene[{j}]"
                ))

    return ConstraintResult(
        passed=not any(v.severity == "error" for v in violations),
        violations=violations,
        checked_rules=rules_checked,
        passed_rules=rules_checked - len(violations)
    )


def validate_all(brief: CampaignBrief, personas=None, angles=None, scripts=None, storyboards=None) -> dict[str, ConstraintResult]:
    results = {}
    if personas:
        results["personas"] = validate_personas(personas, brief)
    if angles:
        results["angles"] = validate_angles(angles, brief)
    if scripts:
        results["scripts"] = validate_scripts(scripts, brief)
    if storyboards:
        results["storyboards"] = validate_storyboards(storyboards, brief)
    return results
