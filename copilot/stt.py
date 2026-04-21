"""Vosk-based real-time speech-to-text module for live call co-pilot.

Provides a WebSocket handler that accepts raw 16 kHz PCM audio,
feeds it through a Vosk KaldiRecognizer, and streams back partial
and final transcript JSON messages.
"""

from __future__ import annotations

import json
import zipfile
import urllib.request
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect
from vosk import Model, KaldiRecognizer

# ---------------------------------------------------------------------------
# Model management
# ---------------------------------------------------------------------------

MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
MODEL_DIR = Path(__file__).parent / "vosk-model"

_model: Model | None = None


def get_model() -> Model:
    """Return a cached Vosk ``Model`` instance.

    On first call the model directory is checked.  If it does not exist the
    small English model is downloaded from *alphacephei.com*, extracted, and
    renamed to ``vosk-model/`` next to this file.  Subsequent calls return the
    already-loaded model without any I/O.
    """
    global _model
    if _model is not None:
        return _model

    if not MODEL_DIR.exists():
        print("Downloading Vosk model...")
        zip_path = MODEL_DIR.parent / "vosk-model.zip"
        urllib.request.urlretrieve(MODEL_URL, str(zip_path))
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(MODEL_DIR.parent)
        # The archive extracts into vosk-model-small-en-us-0.15/; rename it.
        extracted = MODEL_DIR.parent / "vosk-model-small-en-us-0.15"
        if extracted.exists():
            extracted.rename(MODEL_DIR)
        zip_path.unlink()
        print("Vosk model ready.")

    _model = Model(str(MODEL_DIR))
    return _model


# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------

SAMPLE_RATE = 16_000


async def stt_websocket(websocket: WebSocket) -> None:
    """Accept a WebSocket connection and stream speech-to-text results.

    The client should send raw **16 kHz, 16-bit mono PCM** audio frames as
    binary WebSocket messages.  The server replies with JSON objects:

    * ``{"type": "partial", "text": "..."}`` -- interim hypothesis while the
      speaker is still talking.
    * ``{"type": "final",   "text": "..."}`` -- stable result after an
      utterance boundary is detected.
    """
    await websocket.accept()

    model = get_model()
    recognizer = KaldiRecognizer(model, SAMPLE_RATE)

    try:
        while True:
            data: bytes = await websocket.receive_bytes()

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "")
                if text:
                    await websocket.send_json({"type": "final", "text": text})
            else:
                partial = json.loads(recognizer.PartialResult())
                text = partial.get("partial", "")
                if text:
                    await websocket.send_json({"type": "partial", "text": text})

    except WebSocketDisconnect:
        # Client disconnected -- flush any remaining audio.
        final = json.loads(recognizer.FinalResult())
        text = final.get("text", "")
        if text:
            try:
                await websocket.send_json({"type": "final", "text": text})
            except Exception:
                pass  # Connection already closed; nothing to do.
