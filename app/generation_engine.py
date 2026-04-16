"""
Generation Engine: Routes generation tasks to optimal AI models
and handles response parsing. Supports Gemini, OpenAI, Groq small-task helpers, and demo mode.
"""

import json
import time
import re
from app import config
from app.schemas import (
    CampaignBrief, CampaignInput, BriefSuggestions, Persona,
    CampaignAngle, AdScript, Storyboard, SceneDescription, IdeaExtraction
)
from app.context_engine import (
    build_brief_assist_prompt, build_persona_prompt, build_angles_prompt,
    build_script_prompt, build_storyboard_prompt, build_refinement_prompt,
    build_target_market_expansion_prompt, build_idea_extraction_prompt
)


def _is_gemini_rate_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "429" in message or
        "resource_exhausted" in message or
        "rate limit" in message or
        "too many requests" in message
    )


def _call_gemini(prompt: str) -> str:
    from google import genai
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
        )
        return response.text
    except Exception as exc:
        if not _is_gemini_rate_limit_error(exc):
            raise
        response = client.models.generate_content(
            model=config.GEMINI_FALLBACK_MODEL,
            contents=prompt,
        )
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


def _call_groq(prompt: str) -> str:
    from groq import Groq
    client = Groq(api_key=config.GROQ_API_KEY)
    response = client.chat.completions.create(
        model=config.GROQ_SMALL_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
    )
    return response.choices[0].message.content


def _call_model(prompt: str) -> str:
    if config.AI_PROVIDER == "openai":
        return _call_openai(prompt)
    return _call_gemini(prompt)


def _call_small_model(prompt: str) -> str:
    if config.GROQ_API_KEY:
        return _call_groq(prompt)
    return _call_model(prompt)


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


def _compact_target_market_tag(tag: str) -> str:
    cleaned = re.sub(r"[.,]", "", str(tag)).strip()
    cleaned = re.sub(
        r"\b(preparing for|planning for|focused on|aiming for|targeting|mastering|navigating|supporting|balancing|using|earning|making|creating|studying for|revising from|learning from)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\bclass notes and lecture slides\b", "lecture notes", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bstandardized exams\b", "test prep", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bcollege entrance exams\b", "entrance prep", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bprofessional certifications\b", "certifications", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bmixed materials\b", "mixed sources", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")

    lower = cleaned.lower()
    replacements = [
        ("high-school seniors", "High-school seniors"),
        ("high-school students", "High-school students"),
        ("college students", "College students"),
        ("undergraduate students", "Undergrads"),
        ("graduate students", "Grad students"),
        ("students", "Students"),
        ("test-takers", "Test takers"),
        ("adult learners", "Adult learners"),
        ("language learners", "Language learners"),
        ("mooc learners", "MOOC learners"),
        ("mooc participants", "MOOC learners"),
        ("online course enthusiasts", "Online learners"),
        ("digital learners", "Online learners"),
        ("virtual classroom users", "Online learners"),
        ("self-paced course students", "Self-paced learners"),
        ("working professionals", "Working professionals"),
        ("parents", "Parents"),
        ("international students", "International students"),
    ]
    for needle, replacement in replacements:
        if lower.startswith(needle):
            suffix = cleaned[len(needle):].strip()
            return f"{replacement} {suffix}".strip()

    return cleaned


def _normalize_target_market_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for tag in tags:
        compact = _compact_target_market_tag(tag)
        compact = re.sub(r"\s+", " ", compact).strip()
        if not compact:
            continue

        words = compact.split()
        if len(words) > 5:
            compact = " ".join(words[:5])

        key = compact.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(compact)

    return normalized


# ─── Demo data for offline demonstrations ─────────────────────────

def _demo_brief_suggestions(campaign_input: CampaignInput) -> BriefSuggestions:
    raw = campaign_input.raw_idea.lower()
    if any(term in raw for term in ["student", "study", "exam", "quiz", "flashcard", "pdf", "lecture"]):
        description = (
            f"{campaign_input.product_name} helps students turn study materials like PDFs, slides, "
            "and recorded lessons into faster revision tools such as notes, quizzes, flashcards, "
            "and summaries in one workspace."
        )
        target_markets = [
            "High-school students preparing for major exams",
            "College students revising from class notes and lecture slides",
            "Competitive-exam learners studying across mixed materials",
            "Students who learn from YouTube lessons and recorded classes",
            "Coaching-center students who need faster revision workflows",
        ]
        objectives = [
            "Drive new student signups",
            "Increase daily study sessions",
            "Improve repeat usage during exam periods",
            "Boost feature adoption for quizzes and flashcards",
            "Position the product as a faster way to revise",
            "Increase retention after the first study session",
        ]
    else:
        description = (
            f"{campaign_input.product_name} gives users a simpler way to act on {campaign_input.raw_idea.strip()} "
            "with a clear workflow, practical outcomes, and less manual effort."
        )
        target_markets = [
            "Busy professionals looking for faster workflows",
            "Small teams replacing manual processes",
            "First-time users who want a simple starting point",
            "Digital-first customers comparing modern tools",
            "Budget-conscious buyers seeking practical value",
        ]
        objectives = [
            "Drive qualified signups",
            "Increase product activation",
            "Improve weekly active usage",
            "Position the product around speed and simplicity",
            "Increase repeat usage",
            "Improve conversion from interest to trial",
        ]

    return BriefSuggestions(
        product_description=description,
        target_markets=_normalize_target_market_tags(target_markets),
        marketing_objectives=objectives,
    )


def _demo_related_target_markets(seed_tag: str, existing_tags: list[str]) -> list[str]:
    seed = seed_tag.lower()
    if "high-school" in seed or "school" in seed:
        candidates = [
            "Students preparing for board exams",
            "Class 11-12 students revising science subjects",
            "High-school students learning from school PDFs",
            "Students balancing tuition homework and exams",
            "Teens using short revision sessions after class",
            "Students who prefer quiz-based revision",
        ]
    elif "college" in seed:
        candidates = [
            "Undergraduates revising before internal exams",
            "Students organizing lecture slides into notes",
            "College learners studying from recorded lectures",
            "Semester-end revision focused students",
            "Students preparing quick summaries before tests",
            "Campus learners juggling multiple subjects",
        ]
    elif "competitive" in seed or "exam" in seed:
        candidates = [
            "Aspirants revising large syllabi in short bursts",
            "Learners using mock tests and flashcards daily",
            "Students combining coaching notes with YouTube lessons",
            "Exam takers studying from mixed digital materials",
            "Learners preparing for aptitude-heavy exams",
            "Students who need rapid recall before practice tests",
        ]
    else:
        candidates = [
            f"{seed_tag} who study from mixed materials",
            f"{seed_tag} looking for faster revision",
            f"{seed_tag} using notes quizzes and flashcards",
            f"{seed_tag} who learn from video lessons",
            f"{seed_tag} preparing for timed exams",
            f"{seed_tag} who want simpler study workflows",
        ]

    existing = {tag.strip().lower() for tag in existing_tags}
    existing.add(seed.strip())
    filtered = [candidate for candidate in candidates if candidate.strip().lower() not in existing][:6]
    return _normalize_target_market_tags(filtered)

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

    try:
        prompt = build_persona_prompt(brief)
        raw = _call_model(prompt)
        data = _parse_json(raw)
        return [Persona(**p) for p in data]
    except Exception as e:
        print(f"[WARN] AI call failed, falling back to demo data: {e}")
        return _demo_personas(brief)


def generate_brief_suggestions(campaign_input: CampaignInput) -> BriefSuggestions:
    if config.DEMO_MODE:
        return _demo_brief_suggestions(campaign_input)

    try:
        prompt = build_brief_assist_prompt(campaign_input)
        raw = _call_small_model(prompt)
        data = _parse_json(raw)
        data["target_markets"] = _normalize_target_market_tags(data.get("target_markets", []))
        return BriefSuggestions(**data)
    except Exception as e:
        print(f"[WARN] AI call failed, falling back to demo data: {e}")
        return _demo_brief_suggestions(campaign_input)


def generate_related_target_markets(
    campaign_input: CampaignInput,
    seed_tag: str,
    existing_tags: list[str],
) -> list[str]:
    if config.DEMO_MODE:
        return _demo_related_target_markets(seed_tag, existing_tags)

    try:
        prompt = build_target_market_expansion_prompt(campaign_input, seed_tag, existing_tags)
        raw = _call_small_model(prompt)
        data = _parse_json(raw)
        return _normalize_target_market_tags([
            item.strip() for item in data.get("target_markets", [])
            if isinstance(item, str) and item.strip()
        ])[:6]
    except Exception as e:
        print(f"[WARN] AI call failed, falling back to demo data: {e}")
        return _demo_related_target_markets(seed_tag, existing_tags)


def generate_angles(brief: CampaignBrief, personas: list[Persona]) -> list[CampaignAngle]:
    if config.DEMO_MODE:
        return _demo_angles(brief)

    try:
        personas_text = json.dumps([p.model_dump() for p in personas], indent=2)
        prompt = build_angles_prompt(brief, personas_text)
        raw = _call_model(prompt)
        data = _parse_json(raw)
        return [CampaignAngle(**a) for a in data]
    except Exception as e:
        print(f"[WARN] AI call failed, falling back to demo data: {e}")
        return _demo_angles(brief)


def generate_scripts(brief: CampaignBrief, angles: list[CampaignAngle], personas: list[Persona]) -> list[AdScript]:
    if config.DEMO_MODE:
        return _demo_scripts(brief)

    try:
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
    except Exception as e:
        print(f"[WARN] AI call failed, falling back to demo data: {e}")
        return _demo_scripts(brief)


def generate_storyboards(brief: CampaignBrief, scripts: list[AdScript]) -> list[Storyboard]:
    if config.DEMO_MODE:
        return _demo_storyboards(brief, scripts)

    try:
        storyboards = []
        for script in scripts:
            prompt = build_storyboard_prompt(brief, json.dumps(script.model_dump(), indent=2))
            raw = _call_model(prompt)
            data = _parse_json(raw)
            storyboards.append(Storyboard(**data))
        return storyboards
    except Exception as e:
        print(f"[WARN] AI call failed, falling back to demo data: {e}")
        return _demo_storyboards(brief, scripts)


def refine_content(brief: CampaignBrief, stage: str, content: str, instruction: str) -> str:
    if config.DEMO_MODE:
        return content  # In demo mode, return as-is

    prompt = build_refinement_prompt(stage, content, instruction, brief)
    return _call_model(prompt)


def extract_idea_fields(raw_idea: str) -> IdeaExtraction:
    if config.DEMO_MODE:
        return IdeaExtraction(
            brand_name="AdForge AI",
            product_name="AI Ad Platform",
            refined_idea=f"A platform for generating AI ads based on {raw_idea}"
        )

    try:
        prompt = build_idea_extraction_prompt(raw_idea)
        raw = _call_small_model(prompt)
        data = _parse_json(raw)
        return IdeaExtraction(**data)
    except Exception as e:
        print(f"[WARN] AI call failed during idea extraction: {e}")
        return IdeaExtraction(
            brand_name="New Brand",
            product_name="New Service",
            refined_idea=raw_idea
        )
