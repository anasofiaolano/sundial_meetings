# Co-pilot Architecture

---

## ⚠️ OPEN DECISION: Speech-to-Text Provider

**Status: Must decide before enterprise launch**

Current implementation uses **Vosk** (self-hosted, runs locally). This works in development but has production problems:

- Model (~50MB) downloads at runtime on first mic click — causes a 30–60s hang that looks like a broken product
- Download uses a blocking call (`urlretrieve`) inside an async handler — freezes the entire server while downloading
- Model lives on disk next to the code — gets wiped on pod/container restarts (Fly, Kubernetes, etc.)
- No download progress shown to the user
- Accuracy is lower than cloud STT APIs

**Recommended alternative: Deepgram**

Replace the Vosk WebSocket handler with Deepgram's streaming API:
- $0.0043/minute — negligible cost for sales calls
- Sub-300ms latency, enterprise SLAs
- No model to manage, no cold starts, no disk storage
- Works identically in dev, staging, and production
- One API key, nothing to install

Architecture stays the same (`Browser → WebSocket → server → STT API → transcript`), only the STT backend changes. Estimated change: ~30 lines in `stt.py`.

**Action required:** Decide on Vosk vs Deepgram before deploying to any enterprise customer. Do not ship the current Vosk implementation to production.

---

## Overview

The Sundial Co-pilot is a live call assistant for sales reps. It listens to a
call in real-time via speech-to-text, detects questions being asked, and
surfaces answers from a knowledge base of project notes.

## Pipeline

```
Browser mic
  → AudioContext (16kHz mono PCM)
  → WebSocket /ws/stt
  → Vosk KaldiRecognizer (server-side)
  → partial/final transcript events
  → WebSocket back to browser
  → transcript displayed in left panel

On every Vosk "final" utterance:
  → POST /api/copilot/analyze  (fire immediately, no debounce)
  → Server: Claude Haiku tool use call (non-streaming)
  → Server: extract structured questions from tool result
  → Server: return plain JSON response
  → Frontend: render Q&A cards, deduplicate against seen questions
```

## Key Design Decisions

### 1. Tool use for structured output (not free-text JSON)

Claude is called with a `report_questions` tool definition that forces it to
return a validated JSON object matching our schema. The Anthropic SDK enforces
the schema — no markdown fences, no trailing commentary, no parsing hacks.

Tool schema returns:
```json
{
  "questions": [
    {
      "question": "string — the detected question",
      "answer": "string — 2-3 sentence answer from KB only",
      "confidence": "high | medium | low",
      "source": "filename.md"
    }
  ]
}
```

### 2. Non-streaming API call (not streaming)

Since tool use requires the full response before we get valid structured data,
streaming tokens to the frontend gives us nothing — we can't render a
half-built card. So we use a regular (non-streaming) API call, wait for the
complete response (~2-3s with Haiku), and return plain JSON.

### 3. Continuous rolling analysis (not debounced)

On a live call there is no reliable "pause" to trigger analysis. People talk
continuously. Instead of debouncing, we fire an analysis request on every Vosk
"final" utterance (natural sentence boundaries, ~every 3-8 seconds).

Multiple analysis requests can be in flight concurrently. Each sends the full
transcript for context but marks only the new section for question detection.
The frontend deduplicates by normalized question text.

### 4. Server-side parsing, plain JSON response (not SSE)

The server calls Claude, parses the tool result, and returns a plain JSON
response. The frontend does a simple `fetch()` → `response.json()` → render
cards. No SSE, no token assembly, no client-side JSON parsing from fragments.

### 5. Context-aware analysis (prior + new sections)

Each analysis request includes the full transcript but splits it into:
- `[PRIOR CONTEXT]` — already analyzed, used for understanding only
- `[NEW SECTION]` — the new text, where questions are detected

This gives Claude full conversational context without re-detecting old
questions.

### 6. Frontend deduplication

A `seenQuestions` Set stores normalized question strings (lowercased,
alphanumeric only). Even if concurrent requests detect the same question,
only the first one renders a card.

## Components

### copilot/engine.py
- `load_knowledge_base()` — reads all .md files from dummy_data/notes/
- `format_knowledge_base(kb)` — formats KB dict into system prompt string
- `copilot_analyze(transcript, kb_context)` — calls Claude Haiku with tool
  use, returns parsed `{"questions": [...]}` dict

### copilot/stt.py
- `get_model()` — lazy-loads Vosk model (auto-downloads on first run)
- `stt_websocket(websocket)` — WebSocket handler, accepts 16kHz PCM audio,
  returns `{"type": "partial"|"final", "text": "..."}`

### copilot/routes.py
- `GET /copilot` — serves the HTML page
- `GET /api/copilot/knowledge` — returns list of KB files
- `POST /api/copilot/analyze` — accepts `{"transcript": "..."}`, returns
  `{"questions": [...]}`
- `WebSocket /ws/stt` — real-time speech-to-text

### frontend/copilot/copilot.html
Standalone HTML page. Two-panel dark UI:
- Left: live transcript display + mic controls
- Right: Q&A card feed

### backend/server.py
Includes the copilot router. Loads `.env` for API key via python-dotenv.

## Infrastructure

- **STT**: Vosk (vosk-model-small-en-us-0.15), runs on CPU
- **LLM**: Claude Haiku (claude-haiku-4-5-20251001) via Anthropic API
- **KB**: .md files in dummy_data/notes/ (14 files, Golden Eagle Log Homes)
- **Server**: FastAPI + Uvicorn, HTTPS (self-signed cert for mic access)
- **API key**: loaded from .env via python-dotenv

## Cost estimate

Haiku at ~$0.0002/call. A 30-minute call with utterances every 5 seconds =
~360 calls = ~$0.07 per call session.
