# Evaluation 1 — Best Practices + Backend System Design

**Status:** 📋 Draft — Pending Critique
**Created:** 2026-03-31
**Builds on:** epoch-1-happy-path.md

---

## 🚨 Items Flagged for Critique

Before reading the rest of this document, these are the decisions I most want challenged:

1. **better-sqlite3 synchronous blocking** — I'm recommending the synchronous SQLite library. In a multi-user future, this will need to change. Is it acceptable now?
2. **Git as version storage with child_process.spawn** — This is the highest-risk operation in the system. Every git call is a subprocess with a non-zero failure rate. See section 4.
3. **Full-file saves for direct edits (stale content problem)** — Blind spot review flagged this. The fix I propose is a "re-fetch before save" pattern. Is there a better approach?
4. **No queue for Claude API calls** — If the rep processes multiple calls at once, Claude requests run concurrently. Rate limits will bite. Is a simple in-memory serialization queue enough, or do we need something durable?

---

## 1. Express vs React — What You're Actually Choosing

Since you've never used Express, let's be clear about what these things even are, because "Express vs React" is actually not the right framing — they live at different layers and don't compete.

### What Express is

Express is a **backend web framework for Node.js**. It sits on a port on your machine (e.g., port 3000), listens for HTTP requests, routes them to handler functions, and sends back responses. That's it. It's the mailroom: receives a request, routes it to the right handler, sends a response.

```
Browser fetches GET /api/files/floor-plan.md
         ↓
Express receives the request
         ↓
app.get('/api/files/:filename', (req, res) => {
  const content = fs.readFileSync(path)
  res.json({ content })
})
         ↓
Browser gets the response, renders it in the HTML
```

Express does nothing about UI. It doesn't generate HTML pages (usually). It just handles requests and returns data. Our frontend HTML file calls it with `fetch()` and renders the results itself.

**Why Express specifically (not something else)?**

| | Express | Fastify | Koa | Raw Node.js http |
|---|---|---|---|---|
| Learning curve | Low — just `app.get`, `app.post`, done | Very low but less familiar | Similar to Express | High — you write all routing logic yourself |
| Ecosystem | Huge — every Node.js tutorial uses it | Good but smaller | Good | N/A — you build your own ecosystem |
| Error handling | Needs disciplined setup (covered below) | Similar | Similar | Fully manual |
| When to choose | Default Node.js server framework | If you need maximum throughput (we don't) | If you want a lighter-weight Express | Never — write Express instead |

**Decision:** Express. It's the de facto standard, every tutorial shows it, and its ecosystem (middleware, logging, etc.) is battle-tested.

### What React is (and why we're not using it)

React is a **frontend UI library**. It runs in the browser and is an alternative to writing plain HTML + vanilla JS. Instead of `document.getElementById`, you write declarative components.

**The real choice we already made:** Keep the existing mockup HTML (vanilla JS) and wire it to an Express backend with `fetch()` calls. The alternative was "throw away the mockup, rewrite everything in React + Next.js."

We made the right call. The mockup is the product. It already implements everything — version history panels, proposed edits module, diff rendering. Rebuilding it in React would mean:
- 3–5 days of porting work
- Risk of regressions in UI state
- Adding React state management complexity around things we already solved
- A build step that breaks the "just open the HTML file" simplicity

The only reason to move to React/Next.js in the future: if we need real-time state sync across multiple browser tabs or multiple users, and the vanilla JS event model becomes unmanageable. That's a Phase 4+ concern.

---

## 2. Backend Architecture — System Design for Critique

This is the core of the evaluation. I've designed each layer with the engineering principles in mind. Read the callouts — they're where I'm least confident.

### 2.1 Project Directory Layout (File System)

```
/projects/
  golden-eagle/               ← project directory; also a git repo
    .git/                     ← managed by git; never touch directly
    floor-plan.md
    project-overview.md
    people/
      lauren-thompson.md
      sarah-chen.md
    calls/
      2026-03-10/
        transcript.txt
        consolidated.txt
        proposed-edits.json   ← exists while edits pending; deleted when all resolved
        screenshots/
          frame-001.jpg
          frame-002.jpg
      2026-03-25/
        ...
```

**Key rule (from Blind Spot Finding 1):** The project directory path is always stored as an **absolute path** in SQLite. The Express server never uses `process.cwd()` to locate project files. Every file operation resolves from the stored absolute path.

### 2.2 SQLite Schema

The schema is designed to enforce invariants at the database layer (Principle 2: Enforce Impossible States at the Database Level).

```sql
-- Projects: one row per CRM project
CREATE TABLE projects (
  id          TEXT PRIMARY KEY,           -- "golden-eagle"
  name        TEXT NOT NULL,              -- "Golden Eagle"
  dir_path    TEXT NOT NULL UNIQUE,       -- "/Users/ana/projects/golden-eagle" — ABSOLUTE
  git_init    INTEGER NOT NULL DEFAULT 0, -- 1 once git repo initialized
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Calls: one row per call recording
CREATE TABLE calls (
  id          TEXT PRIMARY KEY,           -- "2026-03-25-001"
  project_id  TEXT NOT NULL REFERENCES projects(id),
  label       TEXT NOT NULL,              -- "Mar 25 call" — used in git commit messages
  call_date   TEXT NOT NULL,              -- "2026-03-25"
  dir_path    TEXT NOT NULL,              -- ABSOLUTE path to calls/{date}/ directory
  status      TEXT NOT NULL DEFAULT 'uploaded'
                CHECK (status IN ('uploaded','processing','extraction_ready','extraction_failed')),
  error_msg   TEXT,                       -- non-null only when status = 'extraction_failed'
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Proposed edits: one row per file-level proposed change
CREATE TABLE proposed_edits (
  id            TEXT PRIMARY KEY,
  call_id       TEXT NOT NULL REFERENCES calls(id),
  file_path     TEXT NOT NULL,             -- RELATIVE to project dir: "floor-plan.md"
  field_label   TEXT NOT NULL,             -- "Flooring material"
  old_value     TEXT NOT NULL,
  new_value     TEXT NOT NULL,
  confidence    TEXT NOT NULL CHECK (confidence IN ('high','medium','low')),
  source_quote  TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','accepted','skipped')),
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  resolved_at   TEXT                       -- non-null once accepted or skipped
);

-- Events: append-only audit log
CREATE TABLE events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id  TEXT NOT NULL REFERENCES projects(id),
  event_type  TEXT NOT NULL,               -- "git_commit_failed", "edit_accepted", "extraction_failed"
  entity_type TEXT,                        -- "call", "proposed_edit", "file"
  entity_id   TEXT,
  message     TEXT NOT NULL,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Constraints
-- A proposed edit can't have resolved_at set while still pending
CREATE TRIGGER enforce_resolved_at
BEFORE UPDATE ON proposed_edits
WHEN NEW.status = 'pending' AND NEW.resolved_at IS NOT NULL
BEGIN
  SELECT RAISE(ABORT, 'resolved_at must be null for pending edits');
END;

-- A call can't be extraction_ready without error_msg being null
CREATE TRIGGER enforce_no_error_on_ready
BEFORE UPDATE ON calls
WHEN NEW.status = 'extraction_ready' AND NEW.error_msg IS NOT NULL
BEGIN
  SELECT RAISE(ABORT, 'extraction_ready calls cannot have error_msg');
END;
```

🚨 **HUMAN EVALUATE:** SQLite in WAL mode with `better-sqlite3` is synchronous (blocking). For a single-user local tool, this is fine — there's no concurrency issue. If this becomes a shared server with multiple users, we need to switch to an async SQLite driver or Postgres. I'm accepting this now and flagging it as the first thing to revisit at the start of Phase 2.

### 2.3 Error Handling Architecture

This is where "rock solid" comes from. The architecture has four layers:

**Layer 1 — Typed error class**

```javascript
// errors.js
class AppError extends Error {
  constructor(message, statusCode = 500, code = 'INTERNAL_ERROR', context = {}) {
    super(message)
    this.statusCode = statusCode
    this.code = code          // machine-readable: 'GIT_COMMIT_FAILED', 'SCHEMA_INVALID', etc.
    this.context = context    // structured data for logs: { filePath, callId, exitCode }
    this.isOperational = true // vs programmer errors (bugs); both crash-log but operational ones don't restart
  }
}
```

**Layer 2 — Async route wrapper**

Every Express route handler gets wrapped so unhandled promise rejections don't silently disappear:

```javascript
// middleware/asyncHandler.js
const asyncHandler = (fn) => (req, res, next) => {
  Promise.resolve(fn(req, res, next)).catch(next)
}

// Usage in routes:
app.post('/api/edits/:id/accept', asyncHandler(async (req, res) => {
  // ... no try/catch needed here — asyncHandler catches and forwards to error middleware
}))
```

🚨 **Without this pattern**, an `async` route that throws will crash the Express process silently (in older Node versions) or hang the request forever (newer versions). This wrapper is non-negotiable.

**Layer 3 — Express error middleware (catch-all)**

```javascript
// middleware/errorHandler.js
const errorHandler = (err, req, res, next) => {
  // Log everything — even if we can't tell the client much
  console.error({
    code: err.code || 'UNKNOWN',
    message: err.message,
    context: err.context || {},
    stack: err.stack,
    path: req.path,
    method: req.method,
    timestamp: new Date().toISOString()
  })

  // Write to SQLite events table for auditability
  try {
    db.prepare(`
      INSERT INTO events (project_id, event_type, entity_type, entity_id, message)
      VALUES (?, 'server_error', ?, ?, ?)
    `).run(
      req.params.projectId || 'unknown',
      req.params.entityType || null,
      req.params.id || null,
      `${err.code || 'ERROR'}: ${err.message}`
    )
  } catch (dbErr) {
    // If we can't write to SQLite, log it and move on — don't double-fail
    console.error('Failed to write error event to SQLite:', dbErr.message)
  }

  // Send a clean response — never expose stack traces to the client
  const status = err.statusCode || 500
  res.status(status).json({
    error: {
      code: err.code || 'INTERNAL_ERROR',
      message: err.isOperational ? err.message : 'An unexpected error occurred'
    }
  })
}
```

**Layer 4 — Operation-specific try/catches**

Every dangerous operation has its own try/catch that produces a specific, diagnostic AppError:

```javascript
// File write
async function writeProjectFile(projectPath, relativeFilePath, content) {
  // Security: validate path is within project directory
  const absolutePath = path.resolve(projectPath, relativeFilePath)
  if (!absolutePath.startsWith(projectPath + path.sep)) {
    throw new AppError(
      `Path traversal rejected: ${relativeFilePath}`,
      400,
      'PATH_TRAVERSAL',
      { relativeFilePath, projectPath }
    )
  }

  try {
    await fs.writeFile(absolutePath, content, 'utf8')
  } catch (err) {
    if (err.code === 'ENOSPC') {
      throw new AppError('Disk full — cannot write file', 507, 'DISK_FULL', { absolutePath })
    }
    if (err.code === 'EACCES') {
      throw new AppError('Permission denied writing file', 500, 'FILE_PERMISSION', { absolutePath })
    }
    throw new AppError(`File write failed: ${err.message}`, 500, 'FILE_WRITE_FAILED', { absolutePath, originalCode: err.code })
  }
}
```

### 2.4 Git Wrapper

Git is the highest-risk operation. It's a subprocess — we have no control over its internals, and its failure modes are varied (non-zero exit, corrupted output, missing binary, permissions). The wrapper design:

```javascript
// git.js
const { spawn } = require('child_process')

// Check git is available on startup — fail fast, not at runtime
async function checkGitAvailable() {
  try {
    await runGit('/tmp', ['--version'])
  } catch (err) {
    throw new AppError(
      'git binary not found in PATH. Version history will not work.',
      500,
      'GIT_NOT_FOUND'
    )
  }
}

// Core git runner — always specify cwd explicitly (never use process.cwd())
async function runGit(cwd, args, options = {}) {
  return new Promise((resolve, reject) => {
    const proc = spawn('git', args, {
      cwd,            // ALWAYS explicit absolute path
      env: { ...process.env, GIT_TERMINAL_PROMPT: '0' }  // prevent git from hanging waiting for auth
    })

    let stdout = ''
    let stderr = ''

    proc.stdout.on('data', (data) => { stdout += data.toString() })
    proc.stderr.on('data', (data) => { stderr += data.toString() })

    // Timeout: kill the process if it hangs (shouldn't happen for local git, but defensive)
    const timeout = setTimeout(() => {
      proc.kill()
      reject(new AppError(
        `git ${args[0]} timed out after 30s`,
        500,
        'GIT_TIMEOUT',
        { args, cwd }
      ))
    }, 30_000)

    proc.on('close', (exitCode) => {
      clearTimeout(timeout)
      if (exitCode === 0) {
        resolve(stdout.trim())
      } else {
        reject(new AppError(
          `git ${args[0]} failed (exit ${exitCode}): ${stderr.trim()}`,
          500,
          'GIT_COMMAND_FAILED',
          { args, cwd, exitCode, stderr: stderr.trim() }
        ))
      }
    })
  })
}

// Public API: commit a file after writing it
// NOTE: this is called AFTER the file is written to disk (Principle 7: audit trail is downstream)
async function commitFile(projectDir, relativeFilePath, commitMessage) {
  try {
    await runGit(projectDir, ['add', relativeFilePath])
    await runGit(projectDir, ['commit', '-m', commitMessage, '--', relativeFilePath])
  } catch (err) {
    // Git failure is not a hard stop — the file IS written.
    // We log the failure and let the caller decide how to surface it.
    // Never block the rep from seeing their accepted edit just because git had a hiccup.
    throw new AppError(
      `File saved, but version history failed: ${err.message}`,
      207,  // 207 Multi-Status: partial success
      'GIT_COMMIT_FAILED',
      { projectDir, relativeFilePath, commitMessage, originalError: err.message }
    )
  }
}

// Get version list for a file
async function getFileVersions(projectDir, relativeFilePath) {
  try {
    const output = await runGit(projectDir, [
      'log',
      '--format=%H|||%s|||%ai',  // hash ||| subject ||| author date ISO
      '--',
      relativeFilePath
    ])
    if (!output) return []  // no commits yet for this file
    return output.split('\n').map(line => {
      const [hash, subject, date] = line.split('|||')
      return { hash, subject, date }
    })
  } catch (err) {
    throw new AppError(
      `Could not retrieve version history: ${err.message}`,
      500,
      'GIT_LOG_FAILED',
      { projectDir, relativeFilePath }
    )
  }
}

// Get diff between two versions
async function getFileDiff(projectDir, relativeFilePath, fromHash, toHash) {
  // Blind Spot Finding 5: diff must be from parent to this commit, not this commit to HEAD
  // Always: git diff <fromHash> <toHash> -- <file>
  try {
    const output = await runGit(projectDir, [
      'diff',
      fromHash,
      toHash,
      '--',
      relativeFilePath
    ])
    return parseDiff(output)  // parse unified diff → {added: [...], removed: [...]} for the frontend
  } catch (err) {
    throw new AppError(
      `Could not compute diff: ${err.message}`,
      500,
      'GIT_DIFF_FAILED',
      { projectDir, relativeFilePath, fromHash, toHash }
    )
  }
}
```

### 2.5 API Route Structure

```
POST   /api/projects                              create a new project, init git repo
GET    /api/projects/:projectId                   project metadata

GET    /api/projects/:projectId/files/:filePath   read a file's current content
POST   /api/projects/:projectId/files/:filePath   save a file (direct edit, with git commit)

GET    /api/projects/:projectId/files/:filePath/versions   git log for a file
GET    /api/projects/:projectId/files/:filePath/diff       git diff between two hashes

GET    /api/projects/:projectId/calls             list all calls
POST   /api/projects/:projectId/calls             create a call record

POST   /api/calls/:callId/process                 trigger extraction pipeline
GET    /api/calls/:callId/edits                   get proposed edits for a call

POST   /api/edits/:editId/accept                  accept one proposed edit
POST   /api/edits/:editId/skip                    skip one proposed edit
POST   /api/calls/:callId/edits/accept-all        accept all pending edits for a call

POST   /api/chat                                  AI assistant chat → proposed edits
```

**Security note:** `:filePath` is a URL parameter and must be sanitized server-side. Every route that takes a file path must run the path traversal check (see Layer 4 above) before any file operation.

### 2.6 The Stale Content Problem (Blind Spot Finding 3)

This is the trickiest correctness issue. Scenario:

1. Rep opens floor-plan.md. Frontend holds copy of file in memory.
2. Rep accepts a proposed AI edit to floor-plan.md. Backend writes new content.
3. Rep edits a different field directly — their save sends the stale in-memory copy, which **doesn't include the AI edit from step 2**. The AI edit is silently overwritten.

**Fix:** Before every direct-edit save, the backend compares the incoming `content` checksum against the current file on disk. If they differ, return `409 Conflict` with the current content. The frontend prompts: "This file was updated while you were editing. [Show diff] [Overwrite anyway] [Discard your changes]."

This is the same "optimistic concurrency control" pattern used by git itself (it won't let you push if you're behind). Implementation:

```javascript
// POST /api/projects/:projectId/files/:filePath
app.post('/api/projects/:id/files/:filePath', asyncHandler(async (req, res) => {
  const { content, clientChecksum } = req.body  // client sends checksum of what it started with
  const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(req.params.id)

  const currentContent = await fs.readFile(absolutePath, 'utf8')
  const currentChecksum = hash(currentContent)

  if (clientChecksum && currentChecksum !== clientChecksum) {
    return res.status(409).json({
      error: { code: 'CONFLICT', message: 'File was modified since you last loaded it' },
      currentContent  // send the current version so the frontend can show a diff
    })
  }

  await writeProjectFile(project.dir_path, req.params.filePath, content)
  // ... git commit, SQLite event
}))
```

🚨 **HUMAN EVALUATE:** Does this conflict resolution flow feel right? The alternative is "last write wins" (simpler but silently drops edits). I prefer 409 + user prompt, but it adds friction.

### 2.7 Claude API Integration

```javascript
// claude.js
const Anthropic = require('@anthropic-ai/sdk')

const client = new Anthropic()

const EXTRACTION_SYSTEM_PROMPT = `You are a CRM assistant for a sales team. You will be given:
1. A consolidated call record (transcript + visual descriptions from screenshots)
2. The current content of all project documents

Your task: identify only the concrete, specific facts that changed during this call and should update project records.

Return ONLY a JSON array matching this exact schema — no prose, no explanation, just the array:
[
  {
    "file_path": "floor-plan.md",         // relative path within the project
    "field_label": "Flooring material",    // human-readable label for what changed
    "old_value": "undecided",             // exact current value from the file (or empty string if new)
    "new_value": "cedar",                 // the updated value
    "confidence": "high",                 // high | medium | low
    "source_quote": "Lauren said she's now leaning toward cedar for the main floor"
  }
]

If no updates are needed, return an empty array: []

CONSTRAINTS:
- Only update content within existing document structure. Do NOT add new sections, tables, or structural elements.
- Only include changes you have high confidence about from explicit statements in the transcript.
- file_path must be one of the files provided to you. Do NOT invent file paths.`

async function extractProposedEdits(consolidatedText, projectFiles) {
  // projectFiles: { 'floor-plan.md': '...content...', 'people/lauren.md': '...' }

  const fileContext = Object.entries(projectFiles)
    .map(([path, content]) => `## ${path}\n${content}`)
    .join('\n\n---\n\n')

  const userMessage = `## Consolidated Call Record\n${consolidatedText}\n\n---\n\n## Current Project Files\n${fileContext}`

  let response
  try {
    response = await client.messages.create({
      model: 'claude-opus-4-6',
      max_tokens: 4096,
      system: EXTRACTION_SYSTEM_PROMPT,
      messages: [{ role: 'user', content: userMessage }]
    })
  } catch (err) {
    throw new AppError(
      `Claude API call failed: ${err.message}`,
      502,
      'CLAUDE_API_FAILED',
      { type: err.constructor.name }
    )
  }

  const rawText = response.content[0]?.text
  if (!rawText) {
    throw new AppError('Claude returned empty response', 502, 'CLAUDE_EMPTY_RESPONSE')
  }

  // Parse and validate — Claude sometimes wraps JSON in ```json blocks
  let parsed
  try {
    const cleaned = rawText.replace(/^```json\n?/, '').replace(/\n?```$/, '').trim()
    parsed = JSON.parse(cleaned)
  } catch (err) {
    throw new AppError(
      'Claude response is not valid JSON',
      502,
      'CLAUDE_SCHEMA_INVALID',
      { rawResponse: rawText.slice(0, 500) }  // first 500 chars for debugging
    )
  }

  // Validate schema
  if (!Array.isArray(parsed)) {
    throw new AppError('Claude response is not an array', 502, 'CLAUDE_SCHEMA_INVALID', { parsed })
  }

  const validatedEdits = []
  for (const edit of parsed) {
    const requiredFields = ['file_path', 'field_label', 'old_value', 'new_value', 'confidence', 'source_quote']
    const missing = requiredFields.filter(f => typeof edit[f] !== 'string')
    if (missing.length > 0) {
      // Log bad edit but don't fail the whole extraction — skip this one
      console.error('Skipping malformed edit (missing fields):', { missing, edit })
      continue
    }

    if (!['high', 'medium', 'low'].includes(edit.confidence)) {
      console.error('Skipping edit with invalid confidence:', edit)
      continue
    }

    // Validate file_path is in the provided files — catches hallucinated paths
    if (!projectFiles[edit.file_path]) {
      console.error('Skipping edit with unknown file_path:', edit.file_path)
      continue
    }

    validatedEdits.push(edit)
  }

  return validatedEdits
}
```

🚨 **HUMAN EVALUATE:** I'm skipping individual malformed edits rather than failing the whole extraction. If Claude returns 4 good edits and 1 bad one, the rep gets 4. Is that the right behavior? Alternative: fail the whole extraction and show an error. I lean toward "partial is better than nothing" but open to pushback.

---

## 3. Best Practices Research — Key Findings

### Node.js / Express Error Handling

**Finding:** The `asyncHandler` wrapper is considered best practice but most tutorials skip it because they don't cover production error handling. The official Express 5 (still pre-release as of 2025) makes async errors automatic — but Express 4 (what everyone actually uses) requires the wrapper.

**Finding:** Never `throw` inside synchronous Express route handlers without wrapping — an uncaught sync throw in Express 4 brings down the process, not just the request. Always use try/catch in sync handlers too.

**Finding:** `process.on('unhandledRejection', ...)` and `process.on('uncaughtException', ...)` are the safety net below error middleware. Configure these to log and exit gracefully rather than letting Node run in an undefined state.

```javascript
// server startup
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection:', reason)
  // Exit so the process restarts clean — don't try to keep running
  process.exit(1)
})

process.on('uncaughtException', (err) => {
  console.error('Uncaught Exception:', err)
  process.exit(1)
})
```

### better-sqlite3 Patterns

**Finding:** `better-sqlite3` is synchronous (blocking). This is a deliberate design decision by its author — it's faster and simpler for applications without massive concurrency. For a single-user local tool, it's the right choice. Avoid `node-sqlite3` (async but complex API).

**Pattern: WAL mode on startup**

```javascript
// db.js
const Database = require('better-sqlite3')
const db = new Database('sundial.db')

// Enable WAL mode — better performance, allows concurrent reads
db.pragma('journal_mode = WAL')
// Foreign key enforcement — SQLite disables this by default for backwards compat
db.pragma('foreign_keys = ON')
```

**Pattern: Prepared statements for everything** — prepare SQL once, run many times. Prevents SQL injection by design and is faster.

```javascript
const insertEdit = db.prepare(`
  INSERT INTO proposed_edits (id, call_id, file_path, field_label, old_value, new_value, confidence, source_quote)
  VALUES (@id, @callId, @filePath, @fieldLabel, @oldValue, @newValue, @confidence, @sourceQuote)
`)
// Usage: insertEdit.run({ id: uuid(), callId: '...', ... })
```

### Git in Node.js

**Finding:** `simple-git` npm package is a well-maintained wrapper that handles a lot of edge cases (git not found, empty repos, parsing). However, it adds a dependency. For the specific operations we need (add, commit, log, diff), the `runGit` wrapper above is cleaner and more transparent.

**Finding:** `git diff` output (unified diff format) needs to be parsed to produce the `{added, removed}` structure the frontend needs for inline highlighting. The `parse-diff` npm package handles this cleanly rather than hand-rolling a parser.

**Finding:** `git log` with `--format` is more reliable than parsing `--oneline` output which can truncate. Use `%H|||%s|||%ai` (full hash, subject, author date ISO8601) with a delimiter that won't appear in commit messages.

### Claude API

**Finding:** Always use `model: 'claude-opus-4-6'` for extraction (highest accuracy on complex JSON + document understanding). Use `claude-haiku-4-5-20251001` for the AI chat assistant if cost matters — the chat responses are less structured so accuracy is less critical. 🚨 **HUMAN EVALUATE:** Is cost a concern at this stage? Using Opus for everything is fine until it gets expensive.

**Finding:** Claude does not guarantee JSON output unless you use tool_use (Anthropic's structured output mechanism). Tool use forces Claude to produce a specific schema. Alternative to the string-parse approach:

```javascript
// More reliable: use tool_use to force structured output
await client.messages.create({
  model: 'claude-opus-4-6',
  tools: [{
    name: 'propose_edits',
    description: 'Propose edits to project files based on the call transcript',
    input_schema: {
      type: 'object',
      properties: {
        edits: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              file_path: { type: 'string' },
              field_label: { type: 'string' },
              old_value: { type: 'string' },
              new_value: { type: 'string' },
              confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
              source_quote: { type: 'string' }
            },
            required: ['file_path', 'field_label', 'old_value', 'new_value', 'confidence', 'source_quote']
          }
        }
      },
      required: ['edits']
    }
  }],
  tool_choice: { type: 'tool', name: 'propose_edits' },
  messages: [{ role: 'user', content: userMessage }]
})
// Response is in message.content[0].input.edits — always valid per schema
```

🚨 **HUMAN EVALUATE:** This is strictly better than string parsing but adds API complexity. I'd lean toward using tool_use from day one — but want your call.

---

## 4. Staff Engineer Review — Applying the Principles

Running the engineering checklist against the Epoch 1 architecture + the system design above:

### ✅ Passes

- **Every state has an exit path.** `proposed_edits.status`: pending → accepted or skipped. `calls.status`: processing → extraction_ready or extraction_failed with error_msg. Enforced at DB level with CHECK constraints.
- **Impossible states at DB level.** Triggers enforce: pending edits can't have `resolved_at`, extraction_ready calls can't have `error_msg`, etc.
- **Silent failure is worse than loud failure.** Every catch either (a) surfaces a toast to the rep or (b) returns a specific error code with diagnostic context. Nothing disappears.
- **Audit trail is downstream.** Events table is written AFTER git commit succeeds. Git commit is the source of truth, not the trigger.
- **Agent-proofing.** DB constraints and triggers can't be accidentally edited by an AI agent editing JS files. Core invariants are in SQLite.
- **Right execution model.** Express handles requests (daemon, correct). ffmpeg runs as a one-shot child process (correct). No cron jobs disguised as daemons.
- **Ownership of critical paths.** Every write to disk goes through our code. No third-party webhooks in the write path.

### ⚠️ Remaining Concerns

**No concurrent Claude call protection.** If a rep processes two calls simultaneously, both trigger `POST /api/calls/:id/process` concurrently, both hit the Claude API at the same time. For a single rep, this is unlikely but possible (e.g., processing a backlog of old calls). Fix: an in-memory call queue that serializes extraction jobs. Simple and doesn't need a real job queue at this scale.

```javascript
// callQueue.js — simple serializing queue, no external dependency needed
class CallQueue {
  constructor() { this.running = false; this.queue = [] }

  async enqueue(jobFn) {
    return new Promise((resolve, reject) => {
      this.queue.push({ jobFn, resolve, reject })
      this.drain()
    })
  }

  async drain() {
    if (this.running || this.queue.length === 0) return
    this.running = true
    const { jobFn, resolve, reject } = this.queue.shift()
    try { resolve(await jobFn()) } catch (e) { reject(e) }
    this.running = false
    this.drain()
  }
}
```

**proposed-edits.json cleanup timing (Blind Spot Finding 2).** The current plan says "clear after all edits resolved." But what if the server restarts while edits are pending? Fix: on server startup, check SQLite for calls with pending proposed_edits rows. If the corresponding `proposed-edits.json` is missing, log a warning event and mark those edits as `extraction_failed` (not pending — we don't want zombies). The UI then shows a "re-process" button instead of a blank proposed edits module.

**No authentication, not even local network protection.** Documented as accepted risk (single-user local tool). But the server binds to `localhost:3000` — it must bind to `127.0.0.1`, not `0.0.0.0`. Binding to `0.0.0.0` would expose it on the local network. This is a one-line config item, not a blocker.

**Diff parsing for non-line-based changes.** The mockup shows field-level diffs (one value changed in a field). But `git diff` returns line-level diffs. If a field value is long and changes mid-line, the diff might show the whole line as changed rather than just the field. For Phase 1 this is acceptable — we show what git gives us. For Phase 2 we should consider field-level diff computation specifically for structured markdown docs.

---

## 5. Open Questions for Human + Agent Critique

These are not rhetorical — I genuinely want pushback:

1. **better-sqlite3 sync vs async:** Is blocking the event loop acceptable for a local tool? Are there scenarios where it becomes a problem in Phase 1?

2. **tool_use for structured output:** Should we use Claude's tool_use API from day one for reliable JSON extraction, or is the string-parse fallback + schema validation sufficient?

3. **partial extraction acceptance:** If Claude returns 4 valid edits and 1 malformed one, do we show 4 or show an error for all? Current design shows 4.

4. **conflict detection on direct edits:** The 409 approach with checksum comparison adds frontend complexity (client must send checksum with every save). Is the complexity worth it, or do we start with "last write wins" and add conflict detection only if real-world usage reveals the problem?

5. **Call queue in-memory vs durable:** An in-memory call queue loses its state on server restart. If the server restarts while a call is being processed, the call stays in `processing` status and needs a startup cleanup check to move it to `extraction_failed`. Is this okay, or do we need a durable queue from the start?

6. **Workflow testing isolated from infrastructure:** The user raised wanting to test the AI editing pipeline in isolation — feed MD files and input, watch Claude propose edits — without building the full Express server. This aligns with Phase 1's "seed real data, manually test" approach. Should this become a dedicated test script (`scripts/test-extraction.js`) we can run standalone?

---

## Summary: Changes from Epoch 1

| Area | Epoch 1 | Eval Update |
|---|---|---|
| Express vs React | Decided, not explained | Explained in plain English; decision confirmed |
| SQLite schema | Table list only | Full DDL with CHECK constraints, FK, and triggers |
| Error handling | "try/catch everything" | Specific architecture: AppError class, asyncHandler, error middleware, operation-level catches |
| Git wrapper | "check exit codes" | Full implementation with timeout, absolute cwd, specific error codes |
| Stale content problem | "re-fetch before saving" | 409 + checksum pattern with frontend conflict UX |
| Claude API | "validate JSON" | Full implementation + tool_use alternative; partial edit acceptance policy |
| Concurrent extraction | Not addressed | Simple in-memory call queue |
| proposed-edits.json on restart | "never delete until resolved" | Startup cleanup check for orphaned pending rows |
| Path traversal | Flagged as risk | Explicit server-side validation function in every file write path |
| Server binding | Not addressed | Must bind to 127.0.0.1, not 0.0.0.0 |

---

## Next Steps

- [ ] ⏸ CHECKPOINT: Human + agent review this document. Critique the flagged items.
- [ ] Based on feedback: produce Epoch 2 (Hardened Architecture) or proceed to Scope Confirmation if no structural changes needed
- [ ] Consider: run the AI editing pipeline in isolation as a test script (question 6 above)
