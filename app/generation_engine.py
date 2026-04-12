"""
Generation Engine: Routes generation tasks to optimal AI models
and handles response parsing. Supports Gemini, OpenAI, and demo mode.
"""

import json
import time
from app import config
from app.schemas import (
    CampaignBrief, Persona, CampaignAngle, AdScript, Storyboard, SceneDescription
)
from app.context_engine import (
    build_persona_prompt, build_angles_prompt,
    build_script_prompt, build_storyboard_prompt, build_refinement_prompt
)


def _call_gemini(prompt: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.GEMINI_MODEL)
    response = model.generate_content(prompt)
    return response.text


def _call_openai(prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
    )
    return response.choices[0].message.content


def _call_model(prompt: str) -> str:
    if config.AI_PROVIDER == "openai":
        return _call_openai(prompt)
    return _call_gemini(prompt)


def _parse_json(text: str) -> dict | list:
    """Extract JSON from model response, handling markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        end = len(lines) - 1
        if lines[0].startswith("```json"):
            start = 1
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        text = "\n".join(lines[start:end])
    return json.loads(text)


# ─── Demo data for offline demonstrations ─────────────────────────

def _demo_personas(brief: CampaignBrief) -> list[Persona]:
    return [
        Persona(
            name="Priya", age_range="25-32", occupation="Digital Marketing Manager",
            interests=["social media trends", "productivity tools", "online courses", "fitness"],
            pain_points=["limited ad budget", "time-consuming creative process", "inconsistent brand output", "low engagement rates"],
            media_habits=["Instagram daily", "YouTube tutorials", "LinkedIn networking", "marketing podcasts"],
            buying_motivation="Wants to scale content output without hiring a full creative team",
            persona_summary=f"Priya is a growth-focused marketer at a mid-stage startup. She needs to produce high volumes of ad creatives for {brief.brand_name} but is constrained by budget and team size. She values tools that automate repetitive creative tasks."
        ),
        Persona(
            name="Arjun", age_range="30-40", occupation="Startup Founder / CEO",
            interests=["business strategy", "technology", "venture capital", "public speaking"],
            pain_points=["expensive agency retainers", "slow turnaround on ad iterations", "difficulty communicating vision to designers"],
            media_habits=["Twitter/X for news", "YouTube for product demos", "TechCrunch reader", "podcast listener"],
            buying_motivation="Needs professional-grade ads quickly to test product-market fit across channels",
            persona_summary=f"Arjun runs an early-stage startup and needs to rapidly experiment with different ad formats for {brief.product_name}. He doesn't have a design team and wants an AI-powered solution to go from idea to ad in minutes."
        ),
        Persona(
            name="Sneha", age_range="20-26", occupation="Freelance Content Creator",
            interests=["video editing", "graphic design", "trending content", "brand collaborations"],
            pain_points=["client revisions take too long", "maintaining consistency across campaigns", "limited access to premium tools"],
            media_habits=["TikTok power user", "Instagram Reels creator", "design tool daily user", "YouTube Shorts"],
            buying_motivation="Wants to deliver faster turnaround to clients with polished, professional results",
            persona_summary=f"Sneha creates social media content for multiple clients. She would use {brief.brand_name}'s platform to rapidly prototype ad concepts and deliver storyboards to clients for approval."
        ),
    ]


def _demo_angles(brief: CampaignBrief) -> list[CampaignAngle]:
    return [
        CampaignAngle(
            angle_name="The Efficiency Play",
            hook=f"What if your next ad campaign took 5 minutes instead of 5 days?",
            emotional_trigger="Relief / Time-saving",
            value_proposition=f"{brief.brand_name} automates your entire ad creation pipeline — from strategy to finished video.",
            target_persona="Priya",
            cta=f"Try {brief.brand_name} Free Today"
        ),
        CampaignAngle(
            angle_name="The Founder's Edge",
            hook="Stop paying agencies $10K for ads you can make yourself.",
            emotional_trigger="Empowerment / Cost-saving",
            value_proposition=f"{brief.brand_name} gives founders agency-quality creatives at a fraction of the cost.",
            target_persona="Arjun",
            cta="Launch Your First Campaign"
        ),
        CampaignAngle(
            angle_name="The Creator Accelerator",
            hook="Your clients want 10 ad variants by tomorrow. Here's how.",
            emotional_trigger="FOMO / Professional growth",
            value_proposition=f"With {brief.brand_name}, create multiple ad variants in minutes and impress every client.",
            target_persona="Sneha",
            cta="Create Ads 10x Faster"
        ),
    ]


def _demo_scripts(brief: CampaignBrief) -> list[AdScript]:
    return [
        AdScript(
            concept_name="Speed to Market",
            target_persona="Priya",
            angle="The Efficiency Play",
            tone="Energetic and professional",
            duration_seconds=30,
            scenes=[
                SceneDescription(scene_number=1, duration_seconds=5,
                    visual_description="Close-up of a marketer's frustrated face staring at a blank design canvas, clock ticking in background",
                    narration="Creating ads shouldn't take forever.",
                    on_screen_text="We've all been here.", camera_direction="Slow zoom into screen",
                    image_prompt="Photorealistic close-up of a young professional woman looking frustrated at a computer screen showing a blank design canvas, modern office, warm lighting"),
                SceneDescription(scene_number=2, duration_seconds=8,
                    visual_description=f"Screen recording style: user types a brief into {brief.brand_name}'s clean UI, AI generates personas and hooks instantly",
                    narration=f"With {brief.brand_name}, just describe your product and watch the magic happen.",
                    on_screen_text="AI-Powered Campaign Generation", camera_direction="Screen capture with subtle zoom",
                    image_prompt=f"Modern web application interface showing AI generating marketing content, clean UI with cards appearing, purple and blue color scheme, product name {brief.brand_name}"),
                SceneDescription(scene_number=3, duration_seconds=10,
                    visual_description="Split screen showing 3 different ad variants being generated simultaneously, progress bars filling up",
                    narration="Personas, hooks, scripts, and storyboards — all generated in seconds.",
                    on_screen_text="3 Complete Ad Variants", camera_direction="Dynamic split screen with animations",
                    image_prompt="Split screen showing three different advertisement variants being created simultaneously, modern flat design, vibrant colors"),
                SceneDescription(scene_number=4, duration_seconds=7,
                    visual_description=f"Happy marketer presenting results on a big screen to impressed colleagues, {brief.brand_name} logo visible",
                    narration=f"From brief to campaign-ready in under 5 minutes. That's {brief.brand_name}.",
                    on_screen_text=f"Try {brief.brand_name} Free Today", camera_direction="Wide shot pulling back to reveal team, end on logo",
                    image_prompt=f"Professional team in modern office looking impressed at a large screen showing advertisement results, {brief.brand_name} logo on screen, celebratory atmosphere"),
            ],
            cta_text=f"Try {brief.brand_name} Free Today — No credit card required",
            disclaimer="AI-generated content may require review before publication."
        ),
        AdScript(
            concept_name="Founder's Toolkit",
            target_persona="Arjun",
            angle="The Founder's Edge",
            tone="Bold and inspiring",
            duration_seconds=30,
            scenes=[
                SceneDescription(scene_number=1, duration_seconds=5,
                    visual_description="Startup founder working late, surrounded by sticky notes and rejected ad mockups",
                    narration="Building a startup is hard enough. Making ads shouldn't be.",
                    on_screen_text="$10,000+ for an agency?", camera_direction="Handheld, intimate close-up",
                    image_prompt="Young entrepreneur working late at night in a startup office, surrounded by sticky notes and printed ad mockups, laptop glowing, moody lighting"),
                SceneDescription(scene_number=2, duration_seconds=8,
                    visual_description=f"Founder opens {brief.brand_name}, types product description, AI generates complete campaign strategy",
                    narration=f"{brief.brand_name} turns your product vision into a complete ad campaign — powered by AI.",
                    on_screen_text="AI Does The Heavy Lifting", camera_direction="Over-the-shoulder screen capture",
                    image_prompt=f"Over-the-shoulder view of a founder using {brief.brand_name} platform on laptop, AI generating campaign content on screen, modern minimalist workspace"),
                SceneDescription(scene_number=3, duration_seconds=10,
                    visual_description="Montage of generated ads appearing across different platforms — Instagram, YouTube, Facebook",
                    narration="Professional ads for every platform. Multiple variants. Zero design skills needed.",
                    on_screen_text="Every Platform. Every Format.", camera_direction="Quick cuts between platforms",
                    image_prompt="Montage showing advertisements displayed across Instagram phone mockup, YouTube player, and Facebook feed, professional quality, diverse ad formats"),
                SceneDescription(scene_number=4, duration_seconds=7,
                    visual_description=f"Confident founder at a pitch meeting, showing ad campaign results, {brief.brand_name} logo reveal",
                    narration=f"Launch faster. Spend smarter. Win bigger. {brief.brand_name}.",
                    on_screen_text="Launch Your First Campaign", camera_direction="Cinematic wide shot, logo fade-in",
                    image_prompt=f"Confident startup founder presenting impressive ad campaign metrics at a board meeting, modern glass conference room, {brief.brand_name} logo on presentation screen"),
            ],
            cta_text="Launch Your First Campaign — Start Free",
            disclaimer="Results may vary. AI-generated content should be reviewed before publication."
        ),
    ]


def _demo_storyboards(brief: CampaignBrief, scripts: list[AdScript]) -> list[Storyboard]:
    brand_colors = ["#6366f1", "#8b5cf6", "#06b6d4", "#f59e0b", "#1e293b"]
    storyboards = []
    for script in scripts:
        storyboards.append(Storyboard(
            script_name=script.concept_name,
            format="9:16 vertical (Instagram Reels)",
            total_duration=script.duration_seconds,
            scenes=script.scenes,
            music_mood="Upbeat electronic with building energy, subtle bass drops at transitions",
            color_palette=brand_colors,
            typography_style="Modern sans-serif (Inter/Poppins), bold headlines, light body text"
        ))
    return storyboards


# ─── Public generation functions ──────────────────────────────────

def generate_personas(brief: CampaignBrief) -> list[Persona]:
    if config.DEMO_MODE:
        return _demo_personas(brief)

    prompt = build_persona_prompt(brief)
    raw = _call_model(prompt)
    data = _parse_json(raw)
    return [Persona(**p) for p in data]


def generate_angles(brief: CampaignBrief, personas: list[Persona]) -> list[CampaignAngle]:
    if config.DEMO_MODE:
        return _demo_angles(brief)

    personas_text = json.dumps([p.model_dump() for p in personas], indent=2)
    prompt = build_angles_prompt(brief, personas_text)
    raw = _call_model(prompt)
    data = _parse_json(raw)
    return [CampaignAngle(**a) for a in data]


def generate_scripts(brief: CampaignBrief, angles: list[CampaignAngle], personas: list[Persona]) -> list[AdScript]:
    if config.DEMO_MODE:
        return _demo_scripts(brief)

    scripts = []
    for angle in angles[:2]:  # Generate 2 scripts
        persona = next((p for p in personas if p.name == angle.target_persona), personas[0])
        prompt = build_script_prompt(
            brief,
            json.dumps(angle.model_dump(), indent=2),
            json.dumps(persona.model_dump(), indent=2)
        )
        raw = _call_model(prompt)
        data = _parse_json(raw)
        scripts.append(AdScript(**data))
    return scripts


def generate_storyboards(brief: CampaignBrief, scripts: list[AdScript]) -> list[Storyboard]:
    if config.DEMO_MODE:
        return _demo_storyboards(brief, scripts)

    storyboards = []
    for script in scripts:
        prompt = build_storyboard_prompt(brief, json.dumps(script.model_dump(), indent=2))
        raw = _call_model(prompt)
        data = _parse_json(raw)
        storyboards.append(Storyboard(**data))
    return storyboards


def refine_content(brief: CampaignBrief, stage: str, content: str, instruction: str) -> str:
    if config.DEMO_MODE:
        return content  # In demo mode, return as-is

    prompt = build_refinement_prompt(stage, content, instruction, brief)
    return _call_model(prompt)
