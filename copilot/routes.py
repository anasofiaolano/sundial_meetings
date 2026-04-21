"""FastAPI router for the live call co-pilot with Vosk real-time STT."""

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, WebSocket
from fastapi.responses import FileResponse
from pydantic import BaseModel

ROUTES_DIR = Path(__file__).parent
ROOT_DIR = ROUTES_DIR.parent

if str(ROUTES_DIR) not in sys.path:
    sys.path.insert(0, str(ROUTES_DIR))

from engine import load_knowledge_base, format_knowledge_base, copilot_analyze  # noqa: E402
from stt import stt_websocket  # noqa: E402

log = logging.getLogger("copilot.routes")

COPILOT_HTML = ROOT_DIR / "frontend" / "copilot" / "copilot.html"

# Pre-load and cache KB at import time
_kb_cache = load_knowledge_base()
_kb_formatted = format_knowledge_base(_kb_cache)

copilot_router = APIRouter()


class CopilotRequest(BaseModel):
    transcript: str


@copilot_router.get("/copilot")
async def serve_copilot():
    return FileResponse(COPILOT_HTML)


@copilot_router.get("/api/copilot/knowledge")
async def get_knowledge():
    return {"files": list(_kb_cache.keys()), "count": len(_kb_cache)}


@copilot_router.post("/api/copilot/analyze")
async def analyze_transcript(request: CopilotRequest):
    try:
        result = copilot_analyze(request.transcript, _kb_formatted)
        return result
    except Exception as exc:
        log.exception("Analysis endpoint error: %s", exc)
        return {"questions": [], "error": str(exc)}


@copilot_router.websocket("/ws/stt")
async def websocket_stt(websocket: WebSocket):
    await stt_websocket(websocket)
