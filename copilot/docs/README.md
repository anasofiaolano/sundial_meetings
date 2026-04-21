# Sundial Co-pilot

Live call assistant for sales reps. Listens to a call via microphone, detects
client questions in real time, and surfaces answers from the knowledge base.

---

## Quick start

```bash
cd sundial_meetings

# Install dependencies (first time)
pip install fastapi uvicorn python-dotenv anthropic vosk

# Run the server
uvicorn backend.server:app --port 3003 --reload
```

Open `http://localhost:3003/copilot` in Chrome or Firefox.

> **Mic access note:** Browsers block mic on plain HTTP. For localhost this
> usually works anyway. For any other host, you need HTTPS.

---

## What you need

| Requirement | Notes |
|---|---|
| `ANTHROPIC_API_KEY` | In a `.env` file at the repo root |
| Python 3.10+ | Tested on 3.11 |
| Vosk model | Auto-downloads (~50MB) on first mic click |
| Knowledge base | `.md` files in `dummy_data/notes/` |

---

## URLs

| URL | What it does |
|---|---|
| `GET /copilot` | The co-pilot UI |
| `POST /api/copilot/analyze` | Analyze a transcript segment, returns `{questions: [...]}` |
| `GET /api/copilot/knowledge` | List of KB files currently loaded |
| `WS /ws/stt` | WebSocket: send 16kHz PCM audio, receive transcript events |

---

## How it works

1. Rep clicks the mic button — browser captures audio via `getUserMedia`
2. Audio is streamed over WebSocket to the server's Vosk STT engine
3. On each Vosk "final" utterance (~every 3–8 seconds), the frontend sends the
   transcript to `/api/copilot/analyze`
4. The server calls Claude Haiku with tool use, forcing a structured response
5. Detected questions + KB answers are rendered as cards on the right panel

Multiple analysis requests can be in flight at once. The frontend deduplicates
by normalized question text so the same question never appears twice.

---

## Files

```
copilot/
  engine.py       KB loader + Claude analysis (tool use, non-streaming)
  routes.py       FastAPI router — HTTP endpoints + WebSocket handler
  stt.py          Vosk WebSocket handler (16kHz PCM → transcript events)
  docs/
    README.md     This file
    architecture.md  Design decisions and production considerations
    changes.md    Dev log — what was built and what's planned
frontend/copilot/
  copilot.html    Standalone UI (dark/light mode, mic, Q&A feed)
dummy_data/notes/
  *.md            Knowledge base — edit these to update what the co-pilot knows
```

---

## Updating the knowledge base

Add, edit, or delete `.md` files in `dummy_data/notes/`. The server reloads
them at startup — restart uvicorn after any changes.

---

## Known limitations

- **Vosk cold start:** First mic click downloads the model (~50MB). Takes
  30–60 seconds and the server hangs during download. See `architecture.md`
  for the Deepgram migration plan.
- **macOS SSL:** Python 3.11 on macOS may fail to download the Vosk model due
  to missing certs. Fix: run
  `/Applications/Python\ 3.11/Install\ Certificates.command`
- **No speaker diarization:** Transcript is a single stream — no rep vs.
  client labeling.
