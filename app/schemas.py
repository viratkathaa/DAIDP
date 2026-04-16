from pydantic import BaseModel, Field, model_validator
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


class CampaignInput(BaseModel):
    brand_name: str = Field(..., description="Name of the brand")
    product_name: str = Field(..., description="Product or service name")
    raw_idea: str = Field(..., description="User's raw product idea in their own words")
    platform: AdPlatform = Field(default=AdPlatform.INSTAGRAM, description="Ad platform")
    budget_tier: str = Field(default="mid", description="Budget tier: low, mid, high")
    brand_guidelines: str = Field(default="", description="Brand colors, tone, voice, logo rules")
    prohibited_claims: str = Field(default="", description="Claims that must NOT be made")
    competitors: str = Field(default="", description="Known competitor names to avoid mentioning")


class CampaignCreateRequest(BaseModel):
    brand_name: str = Field(..., description="Name of the brand")
    product_name: str = Field(..., description="Product or service name")
    product_description: str = Field(default="", description="Detailed description of the product/service")
    target_market: str = Field(default="", description="Target market description")
    marketing_objectives: str = Field(default="", description="Campaign goals and KPIs")
    raw_idea: str = Field(default="", description="User's raw product idea in their own words")
    platform: AdPlatform = Field(default=AdPlatform.INSTAGRAM, description="Ad platform")
    budget_tier: str = Field(default="mid", description="Budget tier: low, mid, high")
    brand_guidelines: str = Field(default="", description="Brand colors, tone, voice, logo rules")
    prohibited_claims: str = Field(default="", description="Claims that must NOT be made")
    competitors: str = Field(default="", description="Known competitor names to avoid mentioning")

    @model_validator(mode="after")
    def validate_payload(self):
        has_brief_fields = bool(
            self.product_description.strip()
            and self.target_market.strip()
            and self.marketing_objectives.strip()
        )
        has_raw_idea = bool(self.raw_idea.strip())
        if not has_brief_fields and not has_raw_idea:
            raise ValueError(
                "Provide either raw_idea or the finalized brief fields: "
                "product_description, target_market, and marketing_objectives"
            )
        return self

    def to_campaign_input(self) -> CampaignInput:
        synthesized_raw_idea = self.raw_idea.strip() or " ".join(
            part.strip()
            for part in [
                self.product_description,
                self.target_market,
                self.marketing_objectives,
            ]
            if part.strip()
        )
        return CampaignInput(
            brand_name=self.brand_name,
            product_name=self.product_name,
            raw_idea=synthesized_raw_idea,
            platform=self.platform,
            budget_tier=self.budget_tier,
            brand_guidelines=self.brand_guidelines,
            prohibited_claims=self.prohibited_claims,
            competitors=self.competitors,
        )

    def to_campaign_brief(self) -> Optional["CampaignBrief"]:
        if not (
            self.product_description.strip()
            and self.target_market.strip()
            and self.marketing_objectives.strip()
        ):
            return None
        return CampaignBrief(
            brand_name=self.brand_name,
            product_name=self.product_name,
            product_description=self.product_description,
            target_market=self.target_market,
            brand_guidelines=self.brand_guidelines,
            marketing_objectives=self.marketing_objectives,
            platform=self.platform,
            budget_tier=self.budget_tier,
            prohibited_claims=self.prohibited_claims,
            competitors=self.competitors,
        )


class IdeaExtraction(BaseModel):
    brand_name: str
    product_name: str
    refined_idea: str


class IdeaRequest(BaseModel):
    raw_idea: str


class BriefSuggestions(BaseModel):
    product_description: str
    target_markets: list[str]
    marketing_objectives: list[str]


class TargetMarketExpansionRequest(BaseModel):
    seed_tag: str
    existing_tags: list[str] = Field(default_factory=list)


class SelectionRequest(BaseModel):
    selected_indices: list[int] = Field(default_factory=list)


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


class VideoPromptExport(BaseModel):
    title: str
    storyboard_name: str
    prompt: str
    shot_plan: list[str]


class VideoEvaluationSegment(BaseModel):
    start_seconds: float
    end_seconds: float
    color: str
    label: str
    detail: str


class VideoEvaluationReport(BaseModel):
    brand_alignment: float = Field(..., ge=0, le=10)
    message_clarity: float = Field(..., ge=0, le=10)
    visual_quality: float = Field(..., ge=0, le=10)
    prompt_alignment: float = Field(..., ge=0, le=10)
    overall_score: float = Field(..., ge=0, le=10)
    summary: str
    segments: list[VideoEvaluationSegment]


class VideoStoryboardSheet(BaseModel):
    image_url: str
    timestamps: list[float]


class RefinementRequest(BaseModel):
    stage: str  # "personas", "angles", "scripts", "storyboards"
    item_index: int
    instruction: str  # natural language edit instruction
    current_content: str


class PipelineState(BaseModel):
    campaign_id: str
    campaign_input: Optional[CampaignInput] = None
    brief: Optional[CampaignBrief] = None
    brief_suggestions: Optional[BriefSuggestions] = None
    selected_angle_indices: list[int] = Field(default_factory=list)
    selected_script_indices: list[int] = Field(default_factory=list)
    selected_storyboard_indices: list[int] = Field(default_factory=list)
    prompt_exports: list[VideoPromptExport] = Field(default_factory=list)
    personas: list[Persona] = Field(default_factory=list)
    angles: list[CampaignAngle] = Field(default_factory=list)
    scripts: list[AdScript] = Field(default_factory=list)
    storyboards: list[Storyboard] = Field(default_factory=list)
    constraint_results: dict[str, ConstraintResult] = Field(default_factory=dict)
    evaluation: Optional[EvaluationScore] = None
    current_stage: str = "brief"
    metrics: dict = Field(default_factory=dict)
