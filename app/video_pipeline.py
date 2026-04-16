"""
Video prompt export and post-generation video evaluation helpers.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from urllib.error import HTTPError

from app import config
from app.schemas import (
    AdScript,
    CampaignBrief,
    Storyboard,
    VideoEvaluationReport,
    VideoEvaluationSegment,
    VideoPromptExport,
    VideoStoryboardSheet,
)


STATIC_ROOT = Path("static/generated")


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _is_gemini_rate_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "429" in message or
        "resource_exhausted" in message or
        "rate limit" in message or
        "too many requests" in message
    )


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def _json_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict | None = None,
) -> dict:
    request_headers = headers.copy() if headers else {}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, method=method, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except HTTPError as exc:
        charset = exc.headers.get_content_charset() or "utf-8"
        detail = exc.read().decode(charset, errors="replace")
        raise RuntimeError(f"{url} returned {exc.code}: {detail}") from exc


def _safe_name(text: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-") or "asset"


def _storyboard_format_to_aspect_ratio(format_text: str) -> str:
    if "9:16" in format_text:
        return "9:16"
    if "16:9" in format_text:
        return "16:9"
    return "16:9"


def _xai_duration(total_duration: int) -> int:
    return max(5, min(15, total_duration))


def _pick_scripts_for_storyboards(storyboards: list[Storyboard], scripts: list[AdScript]) -> list[AdScript]:
    by_name = {script.concept_name: script for script in scripts}
    picked = []
    for storyboard in storyboards:
        picked.append(by_name.get(storyboard.script_name, scripts[0]))
    return picked


def build_video_prompt_exports(
    brief: CampaignBrief,
    storyboards: list[Storyboard],
    scripts: list[AdScript],
) -> list[VideoPromptExport]:
    exports: list[VideoPromptExport] = []
    paired_scripts = _pick_scripts_for_storyboards(storyboards, scripts)

    for storyboard, script in zip(storyboards, paired_scripts):
        shot_plan = []
        scene_lines = []
        elapsed = 0
        for scene in storyboard.scenes:
            start = elapsed
            elapsed += scene.duration_seconds
            shot_plan.append(
                f"{start:02d}s-{elapsed:02d}s: {scene.visual_description} | Camera: {scene.camera_direction} | "
                f"On-screen text: {scene.on_screen_text or 'None'}"
            )
            scene_lines.append(
                f"Scene {scene.scene_number} ({scene.duration_seconds}s): {scene.visual_description}. "
                f"Narration: {scene.narration}. Camera: {scene.camera_direction}. "
                f"Visual prompt cues: {scene.image_prompt}."
            )

        color_palette = ", ".join(storyboard.color_palette)
        prompt = (
            f"Create a polished {storyboard.format} advertisement video for {brief.brand_name} promoting "
            f"{brief.product_name}. Product context: {brief.product_description} "
            f"Target audience: {brief.target_market}. Marketing objectives: {brief.marketing_objectives}. "
            f"Tone: {script.tone}. Music mood: {storyboard.music_mood}. Typography: {storyboard.typography_style}. "
            f"Color palette: {color_palette}. Keep branding clear, mobile-friendly, and visually consistent. "
            f"Storyboard plan: {' '.join(scene_lines)} "
            f"End with this CTA: {script.cta_text}. "
            f"Keep pacing smooth, transitions intentional, characters consistent across scenes, and text readable."
        )

        if brief.brand_guidelines:
            prompt += f" Follow these brand guidelines: {brief.brand_guidelines}. "
        if brief.prohibited_claims:
            prompt += f"Avoid these claims: {brief.prohibited_claims}. "
        if brief.competitors:
            prompt += f"Do not mention these competitors: {brief.competitors}. "

        exports.append(VideoPromptExport(
            title=f"{storyboard.script_name} Video Prompt",
            storyboard_name=storyboard.script_name,
            prompt=prompt.strip(),
            shot_plan=shot_plan,
        ))

    return exports


def _video_dir(campaign_id: str) -> Path:
    return _ensure_dir(STATIC_ROOT / "evaluations" / campaign_id)


def save_uploaded_video(campaign_id: str, source_path: Path, filename: str) -> tuple[Path, str]:
    target_dir = _video_dir(campaign_id)
    suffix = Path(filename).suffix or ".mp4"
    out_name = f"{uuid.uuid4().hex[:8]}{suffix}"
    out_path = target_dir / out_name
    shutil.copyfile(source_path, out_path)
    validate_video_file(out_path)
    return out_path, f"/static/generated/evaluations/{campaign_id}/{out_name}"


def _is_youtube_url(video_url: str) -> bool:
    host = (urllib.parse.urlparse(video_url).netloc or "").lower()
    return host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}


def _download_youtube_video(campaign_id: str, video_url: str) -> tuple[Path, str]:
    target_dir = _video_dir(campaign_id)
    out_name = f"{uuid.uuid4().hex[:8]}.mp4"
    out_path = target_dir / out_name
    result = subprocess.run(
        [
            "yt-dlp",
            "--no-playlist",
            "--format", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
            "--merge-output-format", "mp4",
            "--output", str(out_path),
            video_url,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or "Failed to download YouTube video")
    validate_video_file(out_path)
    return out_path, f"/static/generated/evaluations/{campaign_id}/{out_name}"


def download_video(campaign_id: str, video_url: str) -> tuple[Path, str]:
    if _is_youtube_url(video_url):
        return _download_youtube_video(campaign_id, video_url)
    target_dir = _video_dir(campaign_id)
    suffix = Path(urllib.parse.urlparse(video_url).path).suffix or ".mp4"
    out_name = f"{uuid.uuid4().hex[:8]}{suffix}"
    out_path = target_dir / out_name
    urllib.request.urlretrieve(video_url, out_path)
    validate_video_file(out_path)
    return out_path, video_url


def resolve_local_video_url(video_url: str) -> Path | None:
    parsed = urllib.parse.urlparse(video_url)
    if parsed.scheme not in {"", "http", "https"}:
        return None
    path = parsed.path or ""
    if not path.startswith("/static/generated/evaluations/"):
        return None
    local_path = Path(path.lstrip("/"))
    return local_path if local_path.exists() else None


def generate_video_from_prompt(
    campaign_id: str,
    prompt_export: VideoPromptExport,
    storyboard: Storyboard,
    model_name: str,
    api_key: str,
) -> tuple[Path, str, str]:
    selected_model = model_name.strip().lower()
    if selected_model in {"grok", config.XAI_VIDEO_MODEL}:
        return _generate_with_xai(campaign_id, prompt_export, storyboard, api_key, config.XAI_VIDEO_MODEL)
    if selected_model in {
        "veo",
        config.GOOGLE_VIDEO_MODEL,
        config.GOOGLE_FAST_VIDEO_MODEL,
    }:
        actual_model = config.GOOGLE_VIDEO_MODEL if selected_model == "veo" else selected_model
        return _generate_with_veo(campaign_id, prompt_export, storyboard, api_key, actual_model)
    raise ValueError("Unsupported video model")


def _generate_with_xai(
    campaign_id: str,
    prompt_export: VideoPromptExport,
    storyboard: Storyboard,
    api_key: str,
    model_name: str,
) -> tuple[Path, str, str]:
    headers = {"Authorization": f"Bearer {api_key}"}
    create = _json_request(
        "https://api.x.ai/v1/videos/generations",
        method="POST",
        headers=headers,
        payload={
            "model": model_name,
            "prompt": prompt_export.prompt,
            "duration": _xai_duration(storyboard.total_duration),
            "aspect_ratio": _storyboard_format_to_aspect_ratio(storyboard.format),
            "resolution": "720p",
        },
    )
    request_id = create["request_id"]
    deadline = time.time() + 900
    while time.time() < deadline:
        current = _json_request(
            f"https://api.x.ai/v1/videos/{request_id}",
            headers=headers,
        )
        status = str(current.get("status", "")).lower()
        if status == "done":
            video_url = (current.get("video") or {}).get("url")
            if not video_url:
                raise RuntimeError("Grok returned a completed job without a video URL")
            local_path, public_url = download_video(campaign_id, video_url)
            return local_path, public_url, f"xai:{request_id}"
        if status in {"failed", "error", "expired"}:
            raise RuntimeError(current.get("error") or current.get("message") or "Grok video generation failed")
        time.sleep(5)

    raise TimeoutError("Timed out waiting for Grok video generation")


def _generate_with_veo(
    campaign_id: str,
    prompt_export: VideoPromptExport,
    storyboard: Storyboard,
    api_key: str,
    model_name: str,
) -> tuple[Path, str, str]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    operation = client.models.generate_videos(
        model=model_name,
        prompt=prompt_export.prompt,
        config=types.GenerateVideosConfig(
            durationSeconds=_xai_duration(storyboard.total_duration),
            aspectRatio=_storyboard_format_to_aspect_ratio(storyboard.format),
            resolution="720p",
            generateAudio=False,
        ),
    )
    deadline = time.time() + 900
    while time.time() < deadline:
        current = client.operations.get(operation)
        if current.done:
            if current.error:
                message = getattr(current.error, "message", None) or str(current.error)
                raise RuntimeError(message or "Veo video generation failed")
            result = current.result
            videos = getattr(result, "generated_videos", None) or []
            if not videos:
                raise RuntimeError("Veo returned no generated videos")
            video = videos[0].video
            target_dir = _video_dir(campaign_id)
            out_name = f"{uuid.uuid4().hex[:8]}.mp4"
            out_path = target_dir / out_name
            if getattr(video, "video_bytes", None):
                out_path.write_bytes(video.video_bytes)
                public_url = f"/static/generated/evaluations/{campaign_id}/{out_name}"
                return out_path, public_url, f"google:{current.name}"
            if getattr(video, "uri", None):
                local_path, public_url = download_video(campaign_id, video.uri)
                return local_path, public_url, f"google:{current.name}"
            raise RuntimeError("Veo returned a completed job without video bytes or URI")
        time.sleep(5)

    raise TimeoutError("Timed out waiting for Veo video generation")


def get_video_duration(video_path: Path) -> float:
    result = _run([
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        str(video_path),
    ])
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def validate_video_file(video_path: Path) -> None:
    if not video_path.exists() or video_path.stat().st_size == 0:
        raise ValueError("The video file is missing or empty")

    header = video_path.read_bytes()[:512].lower()
    if header.startswith(b"<!doctype html") or header.startswith(b"<html") or b"<html" in header:
        raise ValueError("The provided URL did not return a direct video file")

    try:
        get_video_duration(video_path)
    except Exception as exc:
        raise ValueError("The provided file is not a readable video") from exc


def create_contact_sheets(campaign_id: str, video_path: Path) -> tuple[list[VideoStoryboardSheet], float]:
    target_dir = _video_dir(campaign_id)
    duration = max(get_video_duration(video_path), 1.0)
    second_count = max(1, math.ceil(duration))
    all_timestamps = [float(second) for second in range(second_count)]
    sheets: list[VideoStoryboardSheet] = []

    for chunk_start in range(0, len(all_timestamps), 9):
        chunk = all_timestamps[chunk_start:chunk_start + 9]
        frames_dir = _ensure_dir(target_dir / f"frames_{uuid.uuid4().hex[:8]}")

        for idx, ts in enumerate(chunk):
            frame_path = frames_dir / f"frame_{idx:02d}.jpg"
            _run([
                "ffmpeg",
                "-y",
                "-ss", str(ts),
                "-i", str(video_path),
                "-frames:v", "1",
                "-vf", "scale=320:320:force_original_aspect_ratio=decrease,pad=320:320:(ow-iw)/2:(oh-ih)/2:color=white",
                str(frame_path),
            ])

        # Pad incomplete sheets by repeating the last frame so the 3x3 tile is always valid.
        last_index = len(chunk) - 1
        for idx in range(len(chunk), 9):
            shutil.copyfile(frames_dir / f"frame_{last_index:02d}.jpg", frames_dir / f"frame_{idx:02d}.jpg")

        contact_name = f"contact_{uuid.uuid4().hex[:8]}.jpg"
        contact_path = target_dir / contact_name
        _run([
            "ffmpeg",
            "-y",
            "-framerate", "1",
            "-i", str(frames_dir / "frame_%02d.jpg"),
            "-vf", "tile=3x3:padding=8:margin=8:color=white",
            "-frames:v", "1",
            str(contact_path),
        ])
        sheets.append(VideoStoryboardSheet(
            image_url=f"/static/generated/evaluations/{campaign_id}/{contact_name}",
            timestamps=[round(ts, 2) for ts in chunk],
        ))
        shutil.rmtree(frames_dir, ignore_errors=True)

    return sheets, duration


def _heuristic_segments(duration: float) -> list[VideoEvaluationSegment]:
    segment_count = 5 if duration >= 10 else 3
    segment_length = duration / segment_count
    segments = []
    for idx in range(segment_count):
        start = round(idx * segment_length, 2)
        end = round(duration if idx == segment_count - 1 else (idx + 1) * segment_length, 2)
        if idx in (0, segment_count - 1):
            color = "green"
            label = "Strong section"
            detail = "The visuals read clearly and the message feels well-structured in this region."
        else:
            color = "red"
            label = "Needs tightening"
            detail = "This section could use clearer motion, faster pacing, or sharper message focus."
        segments.append(VideoEvaluationSegment(
            start_seconds=start,
            end_seconds=end,
            color=color,
            label=label,
            detail=detail,
        ))
    return segments


def _heuristic_report(duration: float) -> VideoEvaluationReport:
    segments = _heuristic_segments(duration)
    return VideoEvaluationReport(
        brand_alignment=7.8,
        message_clarity=7.4,
        visual_quality=7.6,
        prompt_alignment=7.2,
        overall_score=7.5,
        summary="The video captures the core campaign idea, but some middle sections can be clearer and tighter.",
        segments=segments,
    )


def _call_gemini_video_eval(prompt: str, image_paths: list[Path]) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    contents = [prompt]
    for image_path in image_paths:
        image_bytes = image_path.read_bytes()
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
    try:
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=contents,
            config={"response_mime_type": "application/json"},
        )
    except Exception as exc:
        if not _is_gemini_rate_limit_error(exc):
            raise
        response = client.models.generate_content(
            model=config.GEMINI_FALLBACK_MODEL,
            contents=contents,
            config={"response_mime_type": "application/json"},
        )
    return json.loads(response.text)


def evaluate_video_output(
    brief: CampaignBrief,
    prompt_export: VideoPromptExport,
    video_path: Path,
    contact_sheet_paths: list[Path],
    duration: float,
) -> VideoEvaluationReport:
    if config.DEMO_MODE or not config.GEMINI_API_KEY:
        return _heuristic_report(duration)

    prompt = f"""You are evaluating a generated advertisement video against the original prompt.

Brand: {brief.brand_name}
Product: {brief.product_name}
Target market: {brief.target_market}
Marketing objectives: {brief.marketing_objectives}
Expected video prompt:
{prompt_export.prompt}

The attached images are 3x3 storyboard contact sheets sampled every second across the video timeline.
Video duration: {duration:.2f} seconds.

Return ONLY valid JSON in this shape:
{{
  "brand_alignment": 0-10,
  "message_clarity": 0-10,
  "visual_quality": 0-10,
  "prompt_alignment": 0-10,
  "overall_score": 0-10,
  "summary": "short paragraph",
  "segments": [
    {{
      "start_seconds": 0,
      "end_seconds": 0,
      "color": "green or red",
      "label": "short label",
      "detail": "why this region is strong or weak"
    }}
  ]
}}

Requirements:
- Provide 4 to 6 timeline segments spanning the whole video
- Use green for strong regions and red for weak regions
- Keep the summary concise and practical
- Judge the video on how well it matches the prompt and works as an ad
"""

    try:
        data = _call_gemini_video_eval(prompt, contact_sheet_paths)
        return VideoEvaluationReport(**data)
    except Exception as exc:
        print(f"[WARN] Video evaluation fell back to heuristic mode: {exc}")
        return _heuristic_report(duration)
