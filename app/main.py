"""
Main FastAPI application entry point.
Serves the API and static frontend files.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.routes import router
from app import config

app = FastAPI(
    title="AI Ad Generator",
    description="Multimodal orchestration platform for AI-generated advertising creatives",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_frontend():
    return FileResponse("static/index.html")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "demo_mode": config.DEMO_MODE,
        "ai_provider": config.AI_PROVIDER,
    }
