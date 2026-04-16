import os
import time
from dotenv import load_dotenv

load_dotenv()

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
ASSET_VERSION = (
    os.getenv("APP_ASSET_VERSION")
    or os.getenv("RENDER_GIT_COMMIT")
    or str(int(time.time()))
)

GEMINI_MODEL = "gemini-3-flash-preview"
GEMINI_FALLBACK_MODEL = "gemini-2.5-flash"
OPENAI_MODEL = "gpt-5.4"
GROQ_SMALL_MODEL = "openai/gpt-oss-20b"
XAI_VIDEO_MODEL = "grok-imagine-video"
GOOGLE_VIDEO_MODEL = "veo-3.1-generate-preview"
GOOGLE_FAST_VIDEO_MODEL = "veo-3.1-fast-generate-preview"
