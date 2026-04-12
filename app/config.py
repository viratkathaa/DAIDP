import os
from dotenv import load_dotenv

load_dotenv()

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

GEMINI_MODEL = "gemini-2.0-flash"
OPENAI_MODEL = "gpt-4o-mini"
