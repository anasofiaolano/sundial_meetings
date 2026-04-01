// Sundial CRM — local dogfood server
// Usage: node server.js
// Opens at http://localhost:3001

const express = require('express')
const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')
const Anthropic = require('@anthropic-ai/sdk')
const { applyBatch, trackRead } = require('./scripts/phase-2/apply-edits')

const app = express()
app.use(express.json({ limit: '2mb' }))
app.use(express.static(path.join(__dirname, 'app')))

const PROJECT_DIR = path.join(__dirname, 'test-data/golden-eagle')
const CALLS_LOG   = path.join(__dirname, 'test-data/calls.json')
const client      = new Anthropic()

// ── Shared extraction config (mirrors scripts/phase-1/run-all.js) ──────────

const SYSTEM_PROMPT = `You are an expert sales data analyst for a consulting firm. Your job is to read a call transcript and propose targeted updates to the engagement's project files. You propose only — the consultant reviews and accepts.

## Context
These files track a consulting engagement. They are completely free-form markdown — no fixed structure, no required fields. Each file evolves naturally based on what comes up in calls.

## How edits work
Every edit is a find-and-replace: old_value is the exact text currently in the file, new_value is what replaces it. This covers everything:
- Replacing a placeholder: old_value = "(no notes yet)", new_value = actual content
- Updating a fact: old_value = old sentence/paragraph, new_value = corrected version
- Augmenting: old_value = existing paragraph, new_value = same paragraph with new sentences added
- Adding a section: old_value = last line of file, new_value = that line + new section below it

The files are the ground truth. You have been given their full content above — your old_value MUST come verbatim from that content. If you cannot find the exact text you want to replace, do not propose the edit.

## Rules
1. Only propose edits for facts EXPLICITLY stated in the call — not implied or inferred.
2. If the information is already captured in the file, do not re-propose it.
3. old_value must be copied verbatim from the file content provided. No paraphrasing.
4. For each edit, quote the exact sentence or phrase from the transcript that justifies it.
5. If you are unsure, do not propose.
6. Let the content determine its own structure — add sections, prose, bullet points, whatever fits naturally.
7. If a transcript contains no new facts about the client engagement, return [].`

const TOOL_SCHEMA = {
  type: 'object',
  properties: {
    edits: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file_path:    { type: 'string' },
          field_label:  { type: 'string' },
          old_value:    { type: 'string' },
          new_value:    { type: 'string' },
          confidence:   { type: 'string', enum: ['high', 'medium', 'low'] },
          source_quote: { type: 'string' }
        },
        required: ['file_path', 'field_label', 'old_value', 'new_value', 'confidence', 'source_quote'],
        additionalProperties: false
      }
    }
  },
  required: ['edits']
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function loadProjectFiles() {
  const files = {}
  function walk(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) walk(full)
      else if (entry.name.endsWith('.md')) {
        const rel = path.relative(PROJECT_DIR, full)
        files[rel] = fs.readFileSync(full, 'utf8')
      }
    }
  }
  walk(PROJECT_DIR)
  return files
}

function loadCallsLog() {
  if (!fs.existsSync(CALLS_LOG)) return []
  return JSON.parse(fs.readFileSync(CALLS_LOG, 'utf8'))
}

function saveCallsLog(calls) {
  fs.writeFileSync(CALLS_LOG, JSON.stringify(calls, null, 2))
}

// ── Routes ───────────────────────────────────────────────────────────────────

// GET /api/files — all project markdown files
app.get('/api/files', (req, res) => {
  try {
    res.json(loadProjectFiles())
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// GET /api/calls — call log history
app.get('/api/calls', (req, res) => {
  res.json(loadCallsLog())
})

// POST /api/extract — run Claude extraction on a pasted transcript
// Body: { transcript: string, callName: string }
app.post('/api/extract', async (req, res) => {
  const { transcript, callName, callDate } = req.body
  if (!transcript?.trim()) return res.status(400).json({ error: 'transcript is required' })

  try {
    const projectFiles = loadProjectFiles()
    const fileContext = Object.entries(projectFiles)
      .map(([rel, content]) => `[FILE: ${rel}]\n${content}`)
      .join('\n\n---\n\n')

    const userMessage = `## Call Transcript\n${transcript}\n\n---\n\n## Current Project Files\n${fileContext}`
    const messages = [{ role: 'user', content: userMessage }]

    const count = await client.messages.countTokens({
      model: 'claude-opus-4-6', system: SYSTEM_PROMPT, messages
    })

    if (count.input_tokens > 160_000) {
      return res.status(400).json({ error: `Token budget exceeded: ${count.input_tokens.toLocaleString()}` })
    }

    const response = await client.messages.create({
      model: 'claude-opus-4-6',
      max_tokens: 4096,
      system: SYSTEM_PROMPT,
      messages,
      tools: [{ name: 'propose_edits', description: 'Output the proposed edits array', input_schema: TOOL_SCHEMA }],
      tool_choice: { type: 'tool', name: 'propose_edits' }
    })

    const toolUse = response.content.find(b => b.type === 'tool_use')
    if (!toolUse) return res.status(500).json({ error: 'No tool_use block in response' })

    const rawEdits = toolUse.input.edits || []
    const knownPaths = new Set(Object.keys(projectFiles))

    // Validate old_values against current file content
    const edits = rawEdits.map(edit => ({
      ...edit,
      _valid: knownPaths.has(edit.file_path) && projectFiles[edit.file_path].includes(edit.old_value),
      _error: !knownPaths.has(edit.file_path) ? 'hallucinated_path'
            : !projectFiles[edit.file_path].includes(edit.old_value) ? 'old_value_not_found'
            : null
    }))

    // Save to calls log
    const callId = `call_${Date.now()}`
    const calls = loadCallsLog()
    calls.push({
      id: callId,
      name: callName || `Call ${calls.length + 1}`,
      date: callDate || null,
      timestamp: new Date().toISOString(),
      token_count: count.input_tokens,
      edits,
      status: 'pending'
    })
    saveCallsLog(calls)

    res.json({ callId, edits, token_count: count.input_tokens })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// POST /api/apply — apply a subset of accepted edits
// Body: { callId: string, edits: array }
app.post('/api/apply', async (req, res) => {
  const { callId, edits } = req.body
  if (!edits?.length) return res.status(400).json({ error: 'edits array is required' })

  try {
    // Pre-AI snapshot — commit current state before touching anything
    // This is the rollback point if the AI edits need to be undone
    const callName = (() => {
      const calls = loadCallsLog()
      return calls.find(c => c.id === callId)?.name || callId || 'unknown'
    })()
    try {
      execSync(`git -C "${PROJECT_DIR}" add -A`, { stdio: 'pipe' })
      execSync(`git -C "${PROJECT_DIR}" commit -m "snapshot: before ${callName}"`, { stdio: 'pipe' })
    } catch (_) {
      // Nothing to commit (no unsaved changes) — that's fine, snapshot isn't needed
    }

    // Track all files as read before applying
    const projectFiles = loadProjectFiles()
    for (const relPath of Object.keys(projectFiles)) {
      trackRead(path.join(PROJECT_DIR, relPath))
    }

    const result = await applyBatch(edits, PROJECT_DIR, 'dogfood', callId || 'manual')

    // Update call status in log
    if (callId) {
      const calls = loadCallsLog()
      const call = calls.find(c => c.id === callId)
      if (call) {
        call.status = 'applied'
        call.applied_at = new Date().toISOString()
        call.commit_hash = result.commitHash
        call.applied_edits = edits  // the exact edits that were accepted and applied
        saveCallsLog(calls)
      }
    }

    // Return updated file content so UI can refresh
    const updatedFiles = loadProjectFiles()

    res.json({
      applied: result.applied.length,
      failed: result.failed,
      skipped: result.skipped,
      commitHash: result.commitHash,
      files: updatedFiles
    })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// POST /api/new-file — create a new project markdown file
// Body: { name: string, location: 'people' | 'root' }
app.post('/api/new-file', (req, res) => {
  const { name, location } = req.body
  if (!name?.trim()) return res.status(400).json({ error: 'name is required' })

  const slug = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
  const relPath = location === 'people' ? `people/${slug}.md` : `${slug}.md`
  const absolutePath = path.join(PROJECT_DIR, relPath)

  if (!absolutePath.startsWith(PROJECT_DIR)) return res.status(400).json({ error: 'Invalid path' })
  if (fs.existsSync(absolutePath)) return res.status(409).json({ error: 'File already exists' })

  const title = name.trim()
  const starter = location === 'people'
    ? `# ${title}\nGolden Eagle Log Homes\n\n(no notes yet)\n`
    : `# ${title}\n\n(no notes yet)\n`

  try {
    fs.mkdirSync(path.dirname(absolutePath), { recursive: true })
    fs.writeFileSync(absolutePath, starter, 'utf8')

    try {
      execSync(`git -C "${PROJECT_DIR}" add "${absolutePath}"`, { stdio: 'pipe' })
      execSync(`git -C "${PROJECT_DIR}" commit -m "new file: ${relPath}"`, { stdio: 'pipe' })
    } catch (_) {}

    res.json({ relPath, content: starter })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// POST /api/save-file — autosave: write to disk only, no git commit
// Body: { file_path: string, content: string }
app.post('/api/save-file', (req, res) => {
  const { file_path, content } = req.body
  if (!file_path || content === undefined) {
    return res.status(400).json({ error: 'file_path and content are required' })
  }

  const absolutePath = path.join(PROJECT_DIR, file_path)
  if (!absolutePath.startsWith(PROJECT_DIR)) {
    return res.status(400).json({ error: 'Invalid file path' })
  }
  if (!fs.existsSync(absolutePath)) {
    return res.status(404).json({ error: 'File not found' })
  }

  try {
    fs.writeFileSync(absolutePath, content, 'utf8')
    res.json({ ok: true })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// POST /api/commit-checkpoint — git commit for manual Cmd+S saves
// Body: { file_path: string, content: string }
app.post('/api/commit-checkpoint', (req, res) => {
  const { file_path, content } = req.body
  if (!file_path || content === undefined) {
    return res.status(400).json({ error: 'file_path and content are required' })
  }

  const absolutePath = path.join(PROJECT_DIR, file_path)
  if (!absolutePath.startsWith(PROJECT_DIR)) {
    return res.status(400).json({ error: 'Invalid file path' })
  }
  if (!fs.existsSync(absolutePath)) {
    return res.status(404).json({ error: 'File not found' })
  }

  try {
    fs.writeFileSync(absolutePath, content, 'utf8')

    let commitHash = null
    try {
      execSync(`git -C "${PROJECT_DIR}" add "${absolutePath}"`, { stdio: 'pipe' })
      execSync(`git -C "${PROJECT_DIR}" commit -m "checkpoint: ${file_path}"`, { stdio: 'pipe' })
      commitHash = execSync(`git -C "${PROJECT_DIR}" rev-parse --short HEAD`, { stdio: 'pipe' }).toString().trim()
    } catch (_) {
      // Nothing to commit — file unchanged since last save
    }

    res.json({ ok: true, commitHash })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// GET /api/history — structured git log with age, type, named flag
const NAMED_VERSIONS_FILE = path.join(__dirname, 'test-data/named-versions.json')

function loadNamedVersions() {
  if (!fs.existsSync(NAMED_VERSIONS_FILE)) return []
  return JSON.parse(fs.readFileSync(NAMED_VERSIONS_FILE, 'utf8'))
}

function formatAge(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins  = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days  = Math.floor(diff / 86400000)
  if (mins  <  1) return 'just now'
  if (mins  < 60) return `${mins}m ago`
  if (hours < 24) return `${hours}h ago`
  return `${days}d ago`
}

function classifyCommit(subject) {
  if (subject.startsWith('call:'))          return 'ai-post'
  if (subject.startsWith('snapshot:'))      return 'ai-pre'
  if (subject.startsWith('checkpoint:'))    return 'checkpoint'
  if (subject.startsWith('new file:'))      return 'new-file'
  if (subject.startsWith('manual edit:'))   return 'manual'
  return 'other'
}

app.get('/api/history', (req, res) => {
  try {
    const raw = execSync(
      `git -C "${PROJECT_DIR}" log --format="%H|%h|%s|%aI" -50`,
      { stdio: 'pipe' }
    ).toString().trim()

    if (!raw) return res.json([])

    const named = loadNamedVersions()
    const namedByHash = Object.fromEntries(named.map(n => [n.hash, n]))

    const entries = raw.split('\n').map(line => {
      const [hash, shortHash, subject, date] = line.split('|')
      return {
        hash,
        shortHash,
        subject,
        date,
        age: formatAge(date),
        type: classifyCommit(subject),
        named: namedByHash[hash] || null
      }
    })

    res.json(entries)
  } catch (err) {
    res.json([])
  }
})

// ── Start ────────────────────────────────────────────────────────────────────

const PORT = 3001
app.listen(PORT, () => {
  console.log(`\nSundial CRM running at http://localhost:${PORT}\n`)
})
