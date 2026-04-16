"""
Context Engine: Formats campaign inputs into structured prompt chains
for optimal model generation across each pipeline stage.
"""

from app.schemas import CampaignBrief, CampaignInput, AdPlatform


PLATFORM_SPECS = {
    AdPlatform.INSTAGRAM: {"aspect": "9:16", "max_duration": 60, "format": "Reels/Stories vertical"},
    AdPlatform.YOUTUBE: {"aspect": "16:9", "max_duration": 90, "format": "Pre-roll/In-feed horizontal"},
    AdPlatform.FACEBOOK: {"aspect": "1:1", "max_duration": 60, "format": "Feed square or vertical"},
    AdPlatform.TIKTOK: {"aspect": "9:16", "max_duration": 60, "format": "Vertical short-form"},
    AdPlatform.WEBSITE: {"aspect": "16:9", "max_duration": 120, "format": "Hero banner / embedded"},
    AdPlatform.MOBILE_APP: {"aspect": "9:16", "max_duration": 30, "format": "Interstitial / rewarded"},
}


def build_brand_context(brief: CampaignBrief) -> str:
    """Format the campaign brief into a structured brand context block."""
    platform = PLATFORM_SPECS.get(brief.platform, PLATFORM_SPECS[AdPlatform.INSTAGRAM])
    return f"""=== BRAND CONTEXT ===
Brand: {brief.brand_name}
Product: {brief.product_name}
Description: {brief.product_description}
Target Market: {brief.target_market}
Brand Guidelines: {brief.brand_guidelines or 'No specific guidelines provided'}
Marketing Objectives: {brief.marketing_objectives}
Platform: {brief.platform.value} ({platform['format']})
Aspect Ratio: {platform['aspect']}
Max Duration: {platform['max_duration']}s
Budget Tier: {brief.budget_tier}
Prohibited Claims: {brief.prohibited_claims or 'None specified'}
Competitors to Avoid: {brief.competitors or 'None specified'}
=== END CONTEXT ==="""


def build_persona_prompt(brief: CampaignBrief) -> str:
    context = build_brand_context(brief)
    return f"""{context}

You are a senior marketing strategist. Based on the brand context above, generate exactly 3 distinct target audience personas for this advertising campaign.

For each persona, provide:
- name: A representative first name
- age_range: e.g. "25-34"
- occupation: Their job/role
- interests: List of 4-5 interests relevant to the product
- pain_points: List of 3-4 problems the product solves for them
- media_habits: List of 3-4 media consumption habits
- buying_motivation: What drives their purchase decision
- persona_summary: 2-3 sentence summary of this persona

Return ONLY valid JSON as an array of 3 persona objects. No markdown, no explanation."""


def build_brief_assist_prompt(campaign_input: CampaignInput) -> str:
    platform = PLATFORM_SPECS.get(campaign_input.platform, PLATFORM_SPECS[AdPlatform.INSTAGRAM])
    return f"""You are helping a marketer turn a rough product idea into a clean campaign brief.

Brand: {campaign_input.brand_name}
Product: {campaign_input.product_name}
Raw Idea: {campaign_input.raw_idea}
Platform: {campaign_input.platform.value} ({platform['format']})
Budget Tier: {campaign_input.budget_tier}
Brand Guidelines: {campaign_input.brand_guidelines or 'Not provided yet'}
Prohibited Claims: {campaign_input.prohibited_claims or 'Not provided yet'}
Competitors to Avoid: {campaign_input.competitors or 'Not provided yet'}

Generate:
- product_description: one concise, clear paragraph
- target_markets: exactly 5 short audience options the user can choose from
- marketing_objectives: exactly 6 short marketing objective options the user can choose from

Requirements:
- Keep the writing practical and easy to review
- Make target markets specific and user-facing, not vague categories
- Keep each target market tag short, ideally 2 to 5 words
- Make marketing objectives action-oriented
- Do not mention prohibited claims or competitors unless the user already provided them

Return ONLY valid JSON in this shape:
{{
  "product_description": "string",
  "target_markets": ["string"],
  "marketing_objectives": ["string"]
}}
No markdown, no explanation."""


def build_target_market_expansion_prompt(
    campaign_input: CampaignInput,
    seed_tag: str,
    existing_tags: list[str],
) -> str:
    platform = PLATFORM_SPECS.get(campaign_input.platform, PLATFORM_SPECS[AdPlatform.INSTAGRAM])
    existing = ", ".join(existing_tags) if existing_tags else "None yet"
    return f"""You are expanding target-audience ideas for a campaign brief.

Brand: {campaign_input.brand_name}
Product: {campaign_input.product_name}
Raw Idea: {campaign_input.raw_idea}
Platform: {campaign_input.platform.value} ({platform['format']})
Current selected audience tag: {seed_tag}
Existing audience tags already shown: {existing}

Generate exactly 6 additional target audience tags that are closely related to the selected tag.

Requirements:
- Keep each tag short, specific, and user-facing
- Keep each tag ideally 2 to 5 words
- Make the tags meaningfully similar to "{seed_tag}", not generic
- Do not repeat the selected tag
- Do not repeat any existing tags
- Avoid vague labels like "general users" or "professionals"

Return ONLY valid JSON in this shape:
{{
  "target_markets": ["string"]
}}
No markdown, no explanation."""


def build_angles_prompt(brief: CampaignBrief, personas_text: str) -> str:
    context = build_brand_context(brief)
    return f"""{context}

=== GENERATED PERSONAS ===
{personas_text}
=== END PERSONAS ===

You are a creative director at a top advertising agency. Based on the brand context and target personas above, generate exactly 3 unique campaign angles/hooks.

Each angle should target a different persona and use a distinct emotional strategy.

For each angle, provide:
- angle_name: A catchy internal name for this campaign direction
- hook: The opening hook line (first 3 seconds of the ad)
- emotional_trigger: The core emotion being leveraged (e.g. "FOMO", "aspiration", "relief")
- value_proposition: The key benefit being communicated
- target_persona: Which persona this angle targets (use their name)
- cta: Call-to-action text

Return ONLY valid JSON as an array of 3 angle objects. No markdown, no explanation."""


def build_script_prompt(brief: CampaignBrief, angle_text: str, persona_text: str) -> str:
    context = build_brand_context(brief)
    platform = PLATFORM_SPECS.get(brief.platform, PLATFORM_SPECS[AdPlatform.INSTAGRAM])
    max_dur = platform["max_duration"]
    return f"""{context}

=== CAMPAIGN ANGLE ===
{angle_text}
=== END ANGLE ===

=== TARGET PERSONA ===
{persona_text}
=== END PERSONA ===

You are an advertisement scriptwriter. Write a detailed ad script for the campaign angle above, targeting the specified persona.

The script should be for a {platform['format']} ad, maximum {max_dur} seconds.

Structure the script with 4-6 scenes. For each scene provide:
- scene_number: Sequential number
- duration_seconds: How long this scene lasts
- visual_description: What the viewer sees (detailed)
- narration: Voiceover or dialogue text
- on_screen_text: Any text overlays
- camera_direction: Camera movement/framing instructions
- image_prompt: A detailed prompt that could be used to generate this scene's visual with an AI image model

Also provide:
- concept_name: Name for this ad concept
- target_persona: Persona name
- angle: The campaign angle name
- tone: Overall tone (e.g. "energetic", "warm", "professional")
- duration_seconds: Total ad duration
- cta_text: Final call-to-action
- disclaimer: Any required legal disclaimers

Return ONLY valid JSON as a single script object. No markdown, no explanation."""


def build_storyboard_prompt(brief: CampaignBrief, script_text: str) -> str:
    context = build_brand_context(brief)
    platform = PLATFORM_SPECS.get(brief.platform, PLATFORM_SPECS[AdPlatform.INSTAGRAM])
    return f"""{context}

=== AD SCRIPT ===
{script_text}
=== END SCRIPT ===

You are a storyboard artist and art director. Convert the ad script above into a detailed production storyboard.

Provide:
- script_name: The concept name from the script
- format: "{platform['aspect']} {platform['format']}"
- total_duration: Total duration in seconds
- music_mood: Description of background music style
- color_palette: Array of 4-5 hex color codes that match the brand
- typography_style: Font style recommendation
- scenes: Enhanced scene descriptions with production-ready detail

For each scene, expand the visual_description and image_prompt with specific:
- Composition details (rule of thirds, center-frame, etc.)
- Lighting direction (warm, cool, natural, dramatic)
- Color grading notes
- Transition to next scene (cut, fade, swipe, zoom)

Return ONLY valid JSON as a single storyboard object. No markdown, no explanation."""


def build_refinement_prompt(stage: str, current_content: str, instruction: str, brief: CampaignBrief) -> str:
    context = build_brand_context(brief)
    return f"""{context}

=== CURRENT CONTENT ({stage.upper()}) ===
{current_content}
=== END CURRENT CONTENT ===

User refinement request: "{instruction}"

Modify the content above according to the user's request. Maintain the same JSON structure and format.
Ensure changes are consistent with the brand context.
Return ONLY the modified JSON. No markdown, no explanation."""


def build_idea_extraction_prompt(raw_idea: str) -> str:
    return f"""You are a senior brand consultant. A user has provided a rough idea for a new product or service.
Your task is to extract and refine the brand name, product/service name, and a concise version of the idea.

USER'S ROUGH IDEA:
"{raw_idea}"

Instructions:
1. brand_name: If the user mentioned a specific brand name, extract it. If not, suggest a punchy, professional name based on the idea.
2. product_name: Extract or suggest a clear 2-4 word name for the product/service.
3. refined_idea: Rewrite the user's idea into a clear, professional 1-2 sentence description that captures the core value proposition.

Return ONLY valid JSON in this shape:
{{
  "brand_name": "string",
  "product_name": "string",
  "refined_idea": "string"
}}
No markdown, no explanation."""
