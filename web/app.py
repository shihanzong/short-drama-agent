"""Short Drama Agent - Web API Server (async tasks).

FastAPI backend with async task queue for long-running operations.
"""

import os
import sys
import json
import time
import shutil
import asyncio
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

app = FastAPI(title="Short Drama Agent", version="1.0.0")
STATIC_DIR = Path(__file__).parent / "static"
OUTPUT_BASE = PROJECT_ROOT / "output"
OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

# ─── Async Task Queue ────────────────────────────────────

tasks: Dict[str, Dict[str, Any]] = {}
executor = ThreadPoolExecutor(max_workers=2)


class TaskResult(BaseModel):
    status: str  # pending, running, completed, failed
    progress: float  # 0-100
    message: str
    data: Optional[Dict] = None


class GenerateRequest(BaseModel):
    genres: List[str]
    episodes: int = 3
    style: str = "cinematic_realistic"


class TTSGenRequest(BaseModel):
    script_path: str
    genre: str = ""
    episode: int = 1


def get_genres() -> dict:
    from agents.creative_planner import CreativePlannerAgent
    return CreativePlannerAgent.GENRE_TEMPLATES


def get_styles() -> List[str]:
    styles = ["cinematic_realistic", "anime", "noir", "webtoon", "dark_fantasy", "modern_minimal"]
    kb_dir = PROJECT_ROOT / "knowledge_base" / "style_presets"
    if kb_dir.exists():
        for f in kb_dir.glob("*.json"):
            name = f.stem
            if name not in styles:
                styles.append(name)
    return sorted(styles)


def do_batch_generate(req: GenerateRequest, task_id: str):
    """Background task for batch generation."""
    from workflow import ShortDramaWorkflow

    results = []
    analytics = {"series": [], "total_episodes": 0, "total_time": 0}
    start = time.time()
    genres = req.genres
    total = len(genres)

    for idx, genre in enumerate(genres):
        # Update progress
        pct = max(5, ((idx) / max(total, 1)) * 90 + 5)  # 5-95%
        tasks[task_id]["status"] = "running"
        tasks[task_id]["progress"] = round(pct, 0)
        tasks[task_id]["message"] = f"正在生成: {genre} ({idx+1}/{total})"

        try:
            workflow = ShortDramaWorkflow()
            result = workflow.run_series(
                genre=genre, episode_count=req.episodes,
                style=req.style, output_base=OUTPUT_BASE,
                quick_mode=True,
            )
            results.append(result)
            eps = result.get("episodes_produced", 0)
            analytics["series"].append({
                "genre": genre, "episodes_produced": eps,
                "output_directory": result.get("output_directory", ""),
            })
            analytics["total_episodes"] += eps
        except Exception as e:
            results.append({"genre": genre, "episodes_produced": 0, "error": str(e)})
            analytics["series"].append({"genre": genre, "episodes_produced": 0, "error": str(e)})

    analytics["total_time"] = round(time.time() - start, 1)
    analytics["avg_per_episode"] = round(analytics["total_time"] / max(analytics["total_episodes"], 1), 1)

    tasks[task_id]["status"] = "completed"
    tasks[task_id]["progress"] = 100
    tasks[task_id]["message"] = f"完成！共 {analytics['total_episodes']} 集"
    tasks[task_id]["data"] = {"results": results, "analytics": analytics}


def do_tts_generate(req: TTSGenRequest, task_id: str):
    """Background task for TTS generation."""
    from modules.tts_engine import TTSEngine
    from modules.llm_client import LLMClient
    from agents.audio_maker import AudioMakerAgent

    tasks[task_id]["status"] = "running"
    tasks[task_id]["progress"] = 10
    tasks[task_id]["message"] = "正在解析剧本..."

    script_path = PROJECT_ROOT / req.script_path
    if not script_path.exists():
        script_path = OUTPUT_BASE / req.script_path
    if not script_path.exists():
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["message"] = f"Script not found: {req.script_path}"
        return

    char_cards = []
    planning_path = PROJECT_ROOT / "output" / req.genre / "planning.json"
    if planning_path.exists():
        with open(planning_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            char_cards = data.get("character_cards", [])

    tts_output = PROJECT_ROOT / "output" / "web_tts" / req.genre / f"ep{req.episode:03d}"
    tts_output.mkdir(parents=True, exist_ok=True)

    tasks[task_id]["message"] = "正在生成语音..."

    tts = TTSEngine({
        "voice_female": "zh-CN-XiaoxiaoNeural",
        "voice_male": "zh-CN-YunxiNeural",
        "output_dir": str(tts_output),
    })
    llm = LLMClient()
    agent = AudioMakerAgent(llm_client=llm, tts_engine=tts)

    with open(script_path, "r", encoding="utf-8") as f:
        script = f.read()

    result = agent.run(script, char_cards, episode_number=req.episode)
    audio_files = result.get("dialogue_audio", [])

    files_info = []
    for af in audio_files:
        if os.path.exists(af):
            size = os.path.getsize(af)
            rel = os.path.relpath(af, PROJECT_ROOT / "output")
            files_info.append({"path": rel, "size": size})

    tasks[task_id]["status"] = "completed"
    tasks[task_id]["progress"] = 100
    tasks[task_id]["message"] = f"完成！{len(files_info)} 个音频文件"
    tasks[task_id]["data"] = {
        "dialogue_lines": len(result.get("dialogue_lines", [])),
        "audio_files": files_info,
        "total_size": sum(f["size"] for f in files_info),
    }


def list_drama_outputs() -> dict:
    genres = []
    if OUTPUT_BASE.exists():
        for d in sorted(OUTPUT_BASE.iterdir()):
            if d.is_dir() and d.name not in ("analytics", "audio", "web_tts", "tts_output", "__pycache__"):
                planning = d / "planning.json"
                if planning.exists():
                    with open(planning, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    eps = data.get("episode_outlines", [])
                    chars = data.get("character_cards", [])
                    ep_dirs = []
                    for i in range(1, len(eps) + 1):
                        ep_dir = PROJECT_ROOT / "output" / f"ep{i:03d}"
                        script = ep_dir / "script.md"
                        audio_dir = ep_dir / "audio"
                        tts_dir = PROJECT_ROOT / "output" / "web_tts" / d.name
                        has_tts = (tts_dir / f"ep{i:03d}").exists() if tts_dir.exists() else False
                        ep_dirs.append({
                            "episode": i,
                            "script_size": os.path.getsize(script) if script.exists() else 0,
                            "audio_files": len(list(audio_dir.glob("*.mp3"))) if audio_dir.exists() else 0,
                            "has_tts": has_tts,
                        })
                    genres.append({
                        "genre": d.name, "episodes": len(eps),
                        "characters": len(chars), "episode_details": ep_dirs,
                    })
    return {"genres": genres}


# ─── API Routes ───────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        return HTMLResponse(content=idx.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Short Drama Agent</h1>")


@app.get("/api/genres")
def api_genres():
    genres = get_genres()
    result = {}
    for name, info in genres.items():
        result[name] = {
            "description": info.get("description", ""),
            "key_elements": info.get("key_elements", []),
            "target_audience": info.get("target_audience", ""),
        }
    return JSONResponse(content=result)


@app.get("/api/styles")
def api_styles():
    return JSONResponse(content={"styles": get_styles()})


@app.get("/api/outputs")
def api_outputs():
    return JSONResponse(content=list_drama_outputs())


@app.post("/api/generate")
def api_generate(req: GenerateRequest):
    """Start async generation task."""
    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "message": "排队中...",
        "data": None,
        "created_at": time.time(),
    }
    executor.submit(do_batch_generate, req, task_id)
    return JSONResponse(content={"task_id": task_id, "message": "生成任务已启动"})


@app.post("/api/tts")
def api_tts(req: TTSGenRequest):
    """Start async TTS task."""
    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "message": "排队中...",
        "data": None,
        "created_at": time.time(),
    }
    executor.submit(do_tts_generate, req, task_id)
    return JSONResponse(content={"task_id": task_id, "message": "TTS任务已启动"})


@app.get("/api/task/{task_id}")
def api_task_status(task_id: str):
    """Get async task status."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return JSONResponse(content=tasks[task_id])


@app.get("/api/tts/{rel_path:path}")
def api_tts_download(rel_path: str):
    audio_path = PROJECT_ROOT / "output" / rel_path
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(audio_path), filename=os.path.basename(audio_path), media_type="audio/mpeg")


@app.get("/api/script/{rel_path:path}")
def api_script_download(rel_path: str):
    script_path = PROJECT_ROOT / "output" / rel_path
    if not script_path.exists():
        raise HTTPException(status_code=404, detail="Script not found")
    return FileResponse(str(script_path), filename=os.path.basename(script_path), media_type="text/markdown")


@app.get("/api/script/{rel_path:path}/text")
def api_script_text(rel_path: str):
    script_path = PROJECT_ROOT / "output" / rel_path
    if not script_path.exists():
        raise HTTPException(status_code=404, detail="Script not found")
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()
    return JSONResponse(content={"content": content})


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()

    print(f"Short Drama Agent Web Server (async)")
    print(f"  URL: http://{args.host}:{args.port}")
    print()

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)
