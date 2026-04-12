from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class AdPlatform(str, Enum):
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    WEBSITE = "website"
    MOBILE_APP = "mobile_app"


class CampaignBrief(BaseModel):
    brand_name: str = Field(..., description="Name of the brand")
    product_name: str = Field(..., description="Product or service name")
    product_description: str = Field(..., description="Detailed description of the product/service")
    target_market: str = Field(..., description="Target market description")
    brand_guidelines: str = Field(default="", description="Brand colors, tone, voice, logo rules")
    marketing_objectives: str = Field(..., description="Campaign goals and KPIs")
    platform: AdPlatform = Field(default=AdPlatform.INSTAGRAM, description="Ad platform")
    budget_tier: str = Field(default="mid", description="Budget tier: low, mid, high")
    prohibited_claims: str = Field(default="", description="Claims that must NOT be made")
    competitors: str = Field(default="", description="Known competitor names to avoid mentioning")


class Persona(BaseModel):
    name: str
    age_range: str
    occupation: str
    interests: list[str]
    pain_points: list[str]
    media_habits: list[str]
    buying_motivation: str
    persona_summary: str


class CampaignAngle(BaseModel):
    angle_name: str
    hook: str
    emotional_trigger: str
    value_proposition: str
    target_persona: str
    cta: str


class SceneDescription(BaseModel):
    scene_number: int
    duration_seconds: int
    visual_description: str
    narration: str
    on_screen_text: str
    camera_direction: str
    image_prompt: str


class AdScript(BaseModel):
    concept_name: str
    target_persona: str
    angle: str
    tone: str
    duration_seconds: int
    scenes: list[SceneDescription]
    cta_text: str
    disclaimer: str


class Storyboard(BaseModel):
    script_name: str
    format: str  # e.g. "9:16 vertical", "16:9 horizontal"
    total_duration: int
    scenes: list[SceneDescription]
    music_mood: str
    color_palette: list[str]
    typography_style: str


class ConstraintViolation(BaseModel):
    rule: str
    severity: str  # "error", "warning"
    message: str
    location: str  # which field/section


class ConstraintResult(BaseModel):
    passed: bool
    violations: list[ConstraintViolation]
    checked_rules: int
    passed_rules: int


class EvaluationScore(BaseModel):
    brand_alignment: float = Field(..., ge=0, le=10)
    message_clarity: float = Field(..., ge=0, le=10)
    visual_coherence: float = Field(..., ge=0, le=10)
    cta_effectiveness: float = Field(..., ge=0, le=10)
    overall_score: float = Field(..., ge=0, le=10)
    feedback: list[str]


class RefinementRequest(BaseModel):
    stage: str  # "personas", "angles", "scripts", "storyboards"
    item_index: int
    instruction: str  # natural language edit instruction
    current_content: str


class PipelineState(BaseModel):
    campaign_id: str
    brief: Optional[CampaignBrief] = None
    personas: list[Persona] = []
    angles: list[CampaignAngle] = []
    scripts: list[AdScript] = []
    storyboards: list[Storyboard] = []
    constraint_results: dict[str, ConstraintResult] = {}
    evaluation: Optional[EvaluationScore] = None
    current_stage: str = "brief"
    metrics: dict = {}
