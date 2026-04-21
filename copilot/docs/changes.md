# Co-pilot Changes Log

## Implemented

### Initial build (swarm)
- Created copilot/engine.py, copilot/stt.py, copilot/routes.py
- Created frontend/copilot/copilot.html (mic-only, dark UI, Vosk WebSocket)
- Wired copilot router into backend/server.py
- Installed vosk, downloaded vosk-model-small-en-us-0.15

### Bug fixes
- Skipped macOS ._ resource fork files in KB loader (UTF-8 decode errors)
- Added HTTPS (self-signed cert) so browser allows mic access
- Added favicon.ico 204 route to suppress 404
- Added .env file + python-dotenv for ANTHROPIC_API_KEY
- Fixed SSE token parsing (frontend was concatenating raw payloads instead
  of extracting token field)

### Architecture improvements
- Added context-aware analysis: PRIOR CONTEXT / NEW SECTION markers so
  Claude only detects questions from new transcript text
- Added frontend deduplication via seenQuestions Set
- Cached KB at startup in routes.py (was reloading 14 files from disk per
  request)
- Switched to tool use for structured output (no more regex JSON extraction)
- Reduced debounce from 3s to 1.5s
- Removed char-by-char answer animation (instant display)

### Prompt improvements
- Made prompt tolerant of garbled STT output (interpret generously)
- Broadened question detection to any speaker (not just "client")
- Added instruction to say so directly if topic not in KB


## Not yet implemented

### 1. Non-streaming API call (engine.py)
**What**: Replace `client.messages.stream()` with `call_with_retry()` (non-
streaming). Since tool use requires the full response anyway, streaming gives
us nothing.
**Where**: copilot/engine.py — rename `copilot_stream()` to
`copilot_analyze()`, return parsed dict directly instead of yielding SSE
strings.

### 2. Plain JSON response (routes.py)
**What**: Replace `StreamingResponse` with a plain JSON return from the
`/api/copilot/analyze` endpoint.
**Where**: copilot/routes.py — change `analyze_transcript()` to return the
dict from `copilot_analyze()` directly.

### 3. Simplified frontend fetch (copilot.html)
**What**: Replace the SSE reader / token buffer / JSON assembly with a simple
`await response.json()` call.
**Where**: frontend/copilot/copilot.html — rewrite `analyzeTranscript()`.

### 4. Remove debounce, fire on every Vosk final (copilot.html)
**What**: Instead of debouncing, fire an analysis request immediately on
every Vosk "final" utterance. Multiple requests can be in flight concurrently.
**Why**: On a live call there is no reliable pause. Questions come rapid-fire
and the rep fills silence with filler words. Debounce either never fires or
fires too late.
**Where**: frontend/copilot/copilot.html — remove `scheduleAnalyze()` /
`analyzeTimer`, call `analyzeTranscript()` directly from the "final" handler.

### 5. Concurrent in-flight analysis (copilot.html)
**What**: Allow multiple `fetch()` calls to `/api/copilot/analyze` to be in
flight simultaneously. Don't block new analyses while waiting for previous
ones. Each tracks its own `lastAnalyzedUpTo` snapshot.
**Where**: frontend/copilot/copilot.html — remove the single-request guard,
use per-request state.

### 6. Loading state between fire and response (copilot.html)
**What**: When an analysis request fires, show "Analyzing transcript..." with
a spinner in the status area. If multiple in flight, show count. When
response arrives, clear it.
**Why**: Gives the rep confidence the system heard them. Honest — doesn't
claim to know what question is being answered until Claude responds.
**Where**: frontend/copilot/copilot.html — update `setStatus()`.

### 7. Retry visibility (copilot.html + engine.py)
**What**: If the Claude API call fails and retries, surface that to the
frontend. Show "Retrying... (attempt 2/4)" in the loading state.
**Where**: engine.py — catch retryable errors and include attempt info in
response. copilot.html — display retry state.


## Future considerations

### Better STT: NVIDIA Parakeet TDT
Vosk small model has ~15-20% WER. Parakeet TDT 0.6B has ~6% WER and is
3386x real-time. Requires NVIDIA GPU (CUDA). Target machines have GPUs;
current dev (MacBook M1) does not. Vosk is fine for dev/testing, swap to
Parakeet for production.

### Prompt caching
Anthropic supports caching the system prompt. Since the KB is the same
across all requests in a session, caching it would eliminate re-processing
~14 files of tokens on every call. Significant latency and cost reduction.

### KB summarization
Currently sending full text of all 14 .md files as system prompt. Could
pre-summarize or only send files relevant to the current conversation topic.
Fewer tokens = faster Claude response.
