# Python Migration Plan

## Why FastAPI (not Flask)

- The Anthropic Python SDK's async client requires `asyncio`. FastAPI runs every route handler in asyncio natively — `await client.messages.create(...)` just works. Flask's async support is a bolt-on with subtle gotchas.
- Pydantic request models replace the ad-hoc `if (!field?.trim())` validation guards scattered across the Node routes.
- `uvicorn server:app --port 3001` is a direct replacement for `node server.js`.

---

## Files to Create (old files untouched)

```
requirements.txt                      # new — anthropic, fastapi, uvicorn[standard], regex
scripts/phase-2/apply_edits.py        # port of scripts/phase-2/apply-edits.js
server.py                             # port of server.js
```

`app/index.html` does not change — it's static HTML/JS calling the same API.

---

## Steps

### Step 1 — `requirements.txt`
Establish the environment before writing any code.

```
anthropic>=0.39.0
fastapi>=0.115.0
uvicorn[standard]>=0.29.0
regex>=2024.0.0        # needed for \p{L} Unicode property escapes in preserve_quote_style
```

### Step 2 — `scripts/phase-2/apply_edits.py`
Port of `apply-edits.js`. Internal order matches the dependency graph:

| JS function | Python | Notes |
|---|---|---|
| `readFileState` Map | `read_file_state: dict[str, dict]` | Module-level dict — safe with single uvicorn worker |
| `trackRead` | `track_read(abs_path) -> str` | `Path.stat().st_mtime` (float seconds) instead of `mtimeMs` |
| `loadProjectFiles` | `load_project_files(project_dir)` | `Path.rglob("*.md")` |
| `normalizeQuotes` | `normalize_quotes(s)` | Direct port |
| `findActualString` | `find_actual_string(...)` | `str.find()` returns -1 on miss |
| `preserveQuoteStyle` | `preserve_quote_style(...)` | `re.sub` with callable; needs `regex` package for `\p{L}` |
| `clarifyOldValue` | `clarify_old_value(...)` | `async`, `await client.messages.create(...)` |
| `applyEditToContent` | `apply_edit_to_content(...)` | `str.replace(old, new, 1)` — the `count=1` is critical (JS `.replace(literal)` only replaces first match) |
| `applySingleEdit` | `apply_single_edit(...)` | `async`, recursive retry pattern identical |
| `applyBatch` | `apply_batch(...)` | `async`; git via `subprocess.run([...], capture_output=True, check=True)` |

**Key gotchas:**
- `str.replace(old, new, 1)` not `str.replace(old, new)` — JS `String.replace(literal)` only replaces the first occurrence; Python's default replaces all.
- `\p{L}` Unicode property escape requires the PyPI `regex` package — stdlib `re` doesn't support it.
- Staleness check: `Path(abs_path).stat().st_mtime > state["mtime"]` (float seconds).
- Write phase must not contain any `await` — preserve the atomicity guarantee from the JS version.
- `subprocess.run` with a list (not a string + `shell=True`) avoids shell injection.

### Step 3 — `server.py`
FastAPI port of `server.js`. One route at a time, in order:

| Route | Async? | Notes |
|---|---|---|
| `GET /api/files` | No | Sync I/O |
| `GET /api/calls` | No | Sync I/O |
| `POST /api/extract` | Yes | `await client.messages.countTokens(...)` + `await client.messages.create(...)` |
| `POST /api/apply` | Yes | `await apply_batch(...)`, subprocess for git snapshot |
| `POST /api/new-file` | No | Slug regex: `re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')` |
| `POST /api/save-file` | No | Disk write only |
| `POST /api/commit-checkpoint` | No | Disk write + subprocess git |
| `GET /api/history` | No | subprocess git log |
| `POST /api/protect-version` | No | JSON file update |

**Critical: mount static files last.** `app.mount("/", StaticFiles(...))` must come after all `@app.get`/`@app.post` decorators, or it shadows the API routes.

Path traversal check: `Path(absolute_path).resolve().is_relative_to(PROJECT_DIR.resolve())` — not string `.startswith()`.

### Step 4 — Update deployment

- Replace `pm2 start server.js --name sundial` with `pm2 start "uvicorn server:app --port 3001" --name sundial`
- Or use a `Procfile` / shell script: `uvicorn server:app --port 3001`
- Update `docs/deployment.md`

---

## Python Gotchas Summary

| Issue | JS | Python |
|---|---|---|
| Replace first match only | `str.replace(literal, fn)` | `str.replace(old, new, 1)` |
| Unicode `\p{L}` in regex | Built-in | `import regex as re` (PyPI package) |
| Git subprocess | `execSync(cmd, { stdio: 'pipe' })` | `subprocess.run([...], capture_output=True, check=True)` |
| File mtime | `fs.statSync().mtimeMs` (ms) | `Path.stat().st_mtime` (seconds, float) |
| Path traversal check | `str.startsWith(projectDir)` | `Path.resolve().is_relative_to(base.resolve())` |
| Module-level state | Safe (single-threaded) | Safe with `--workers 1` (uvicorn default); breaks with `--workers N` |

---

## Status

- [x] Step 1 — `requirements.txt`
- [x] Step 2 — `scripts/phase-2/apply_edits.py`
- [x] Step 3 — `server.py`
- [x] Step 4 — deployment update
