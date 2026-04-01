# Workstream: AI Extraction — MD Files from Transcript

*Part of: Sundial Meetings CRM*
*Dependencies: none — this is the first piecemeal piece to validate*
*Dependents: ws-file-write (Piece 4), ws-apply-edit (Piece 6), full Express API*

---

## Objective

Validate the core AI loop in complete isolation before building any infrastructure around it. Given a set of markdown project files and a `consolidated.txt` (transcript + screenshot descriptions), call Claude and get back a valid JSON array of proposed edits. This is a standalone test script — no Express server, no SQLite, no git. Just: files in, edits out.

Success here means the intelligence works. Everything else is plumbing.

---

## Status

**Current:** Not Started
**Last Updated:** 2026-03-31

---

## Implementation

### Approach

1. Seed realistic Golden Eagle test data (MD files + 3 fixture `consolidated.txt` files written by hand)
2. Write `scripts/test-extraction.js` — a standalone Node script that loads files, calls Claude, prints results
3. Iterate on system prompt until extraction is reliable across all 3 fixtures
4. Add a fourth fixture: null case (no changes in transcript → should return `[]`)
5. Lock the system prompt version once stable — this becomes `extraction-v1`

### Files

```
scripts/
  test-extraction.js            — standalone test script (runs with: node scripts/test-extraction.js)

test-data/
  golden-eagle/
    floor-plan.md               — realistic GE floor plan with actual fields
    project-overview.md         — stage, value, blockers, next action
    people/
      lauren-thompson.md        — contact profile with role, notes, sentiment

  transcripts/
    fixture-01-floor-plan.txt   — transcript where flooring material + dimensions change
    fixture-02-people.txt       — transcript where Lauren's concerns + role are updated
    fixture-03-overview.txt     — transcript where project stage + next action change
    fixture-04-null-case.txt    — scheduling call, no project file changes
```

### Key Decisions

| Decision | Choice | Why | Date |
|----------|--------|-----|------|
| Structured output API | `output_config.format` with `json_schema` | GA on Opus 4.6/Sonnet 4.6, constrained decoding at token level — no JSON.parse errors possible | 2026-03-31 |
| Edit format | `{old_value, new_value}` pairs | Enables SEARCH/REPLACE apply logic (Aider pattern) — unambiguous, auditable | 2026-03-31 |
| Model | `claude-opus-4-6` for test, `claude-sonnet-4-6` for later comparison | Establish correctness baseline on best model first, then check if Sonnet matches | 2026-03-31 |
| Context selection | All project files for Phase 1 | 5-10 small files is manageable; add topic-based chunking if token budget check fails | 2026-03-31 |

---

## Script Design

### `scripts/test-extraction.js`

```javascript
// Usage: node scripts/test-extraction.js [fixture-path]
// Example: node scripts/test-extraction.js test-data/transcripts/fixture-01-floor-plan.txt

const Anthropic = require('@anthropic-ai/sdk')
const fs = require('fs')
const path = require('path')

const PROJECT_DIR = path.join(__dirname, '../test-data/golden-eagle')
const client = new Anthropic()

// Load all project files
function loadProjectFiles(dir) {
  const files = {}
  function walk(d) {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const fullPath = path.join(d, entry.name)
      if (entry.isDirectory()) walk(fullPath)
      else if (entry.name.endsWith('.md')) {
        const relPath = path.relative(dir, fullPath)
        files[relPath] = fs.readFileSync(fullPath, 'utf8')
      }
    }
  }
  walk(dir)
  return files
}

// Token budget check before calling
async function checkTokenBudget(messages, system) {
  const count = await client.messages.countTokens({
    model: 'claude-opus-4-6',
    system,
    messages
  })
  console.log(`Token count: ${count.input_tokens} (limit: 180,000)`)
  if (count.input_tokens > 160_000) {
    throw new Error(`Token budget exceeded: ${count.input_tokens}. Split the context.`)
  }
  return count.input_tokens
}

const SYSTEM_PROMPT = `You are an expert sales data analyst. Your job is to read a call transcript and propose targeted updates to the project's files. You propose only — the rep reviews and accepts.

## Rules
1. Only propose edits to facts EXPLICITLY stated in the call — not implied or inferred.
2. If the current value in the file is already correct, do not propose an edit.
3. Do not add new sections, headings, or structural elements — only update values within existing structure.
4. For each proposed edit, quote the exact sentence from the transcript that justifies it.
5. If you are unsure whether a value changed, do not propose the edit.
6. Propose nothing for fields not mentioned in the transcript.
7. old_value must be the exact current text from the file — copy it verbatim.

Output a JSON array of proposed edits. If no updates are needed, output an empty array [].`

async function runExtraction(fixturePath) {
  const consolidated = fs.readFileSync(fixturePath, 'utf8')
  const projectFiles = loadProjectFiles(PROJECT_DIR)

  const fileContext = Object.entries(projectFiles)
    .map(([relPath, content]) => `[FILE: ${relPath}]\n${content}`)
    .join('\n\n---\n\n')

  const userMessage = `## Call Transcript + Screen Analysis\n${consolidated}\n\n---\n\n## Current Project Files\n${fileContext}`

  const messages = [{ role: 'user', content: userMessage }]

  await checkTokenBudget(messages, SYSTEM_PROMPT)

  console.log('\nCalling Claude...\n')
  const response = await client.messages.create({
    model: 'claude-opus-4-6',
    max_tokens: 4096,
    system: SYSTEM_PROMPT,
    messages,
    output_config: {
      format: {
        type: 'json_schema',
        schema: {
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
      }
    }
  })

  const edits = JSON.parse(response.content[0].text)
  return edits
}

async function main() {
  const fixturePath = process.argv[2]
  if (!fixturePath) {
    console.error('Usage: node scripts/test-extraction.js <path-to-consolidated.txt>')
    process.exit(1)
  }

  try {
    const edits = await runExtraction(fixturePath)

    console.log(`\n=== PROPOSED EDITS (${edits.length}) ===\n`)
    for (const edit of edits) {
      console.log(`FILE:    ${edit.file_path}`)
      console.log(`FIELD:   ${edit.field_label}`)
      console.log(`FROM:    "${edit.old_value}"`)
      console.log(`TO:      "${edit.new_value}"`)
      console.log(`CONF:    ${edit.confidence}`)
      console.log(`SOURCE:  "${edit.source_quote}"`)
      console.log()
    }

    // Validation checks (printed, not thrown — this is a test script)
    const projectFiles = loadProjectFiles(PROJECT_DIR)
    const knownPaths = new Set(Object.keys(projectFiles))
    let issues = 0

    for (const edit of edits) {
      // Check: file_path is a real file
      if (!knownPaths.has(edit.file_path)) {
        console.warn(`⚠️  HALLUCINATED FILE PATH: "${edit.file_path}"`)
        issues++
      } else {
        // Check: old_value exists in the file
        const content = projectFiles[edit.file_path]
        if (!content.includes(edit.old_value)) {
          console.warn(`⚠️  OLD_VALUE NOT FOUND in ${edit.file_path}: "${edit.old_value}"`)
          issues++
        }
      }
    }

    if (issues === 0) console.log('✅ All validation checks passed')
    else console.log(`\n⚠️  ${issues} validation issue(s) found — review above`)

  } catch (err) {
    console.error('Extraction failed:', err.message)
    process.exit(1)
  }
}

main()
```

### What success looks like per fixture

| Fixture | Expected edits | Key checks |
|---------|---------------|------------|
| `fixture-01-floor-plan.txt` | 2–3 edits to `floor-plan.md` | All `file_path` = `floor-plan.md`, all `old_value` found in file |
| `fixture-02-people.txt` | 1–2 edits to `people/lauren-thompson.md` | Correct person targeted, `old_value` exact match |
| `fixture-03-overview.txt` | 1–2 edits to `project-overview.md` | Stage/value updated correctly |
| `fixture-04-null-case.txt` | `[]` (empty array) | No hallucinated edits when nothing changed |

---

## Test Cases (6 total)

**T1 — Schema conformance:** Output is always a valid JSON array matching the schema. Run across all 4 fixtures × 3 runs = 12 calls. All 12 must return valid schema. Zero tolerance.

**T2 — File path accuracy:** `file_path` in every proposed edit is a real file from the project directory. No hallucinated paths. Zero tolerance.

**T3 — old_value accuracy:** `old_value` in every proposed edit exists verbatim in the referenced file at the time of extraction. Failures here mean the SEARCH/REPLACE apply logic will silently fail downstream.

**T4 — Field recall:** For fixtures 01–03, manually annotate the expected changes. Assert all annotated changes are captured. Target: 100% on high-confidence fields (explicit numeric values, named decisions), >80% overall.

**T5 — Precision (no hallucination):** No proposed edits for fields not mentioned in the transcript. Run fixture-04 (null case) — must return `[]`.

**T6 — Token budget:** Token count check passes for all fixtures. If any fixture hits >160K tokens, the context selection strategy needs to change.

---

## System Prompt Iteration Log

*Append here as the prompt evolves. Never delete.*

**Version: extraction-v1 (initial)**
- Prompt: see script above
- Status: not yet tested
- Known issues: none yet

---

## Progress Log

*Never delete entries. Always append.*

### 2026-03-31
- **Did:** Created workstream file, designed script, specified all 6 test cases, defined fixture requirements
- **Why:** First piecemeal piece per eval-2 plan — validate AI intelligence before building infrastructure
- **Files:** `epochs/03-WORKSTREAMS/ws-ai-extraction.md`
- **Status:** Not started — seed data and script need to be created
- **Impacts:** none yet

---

## Blockers

| Blocker | Since | Depends On | Status |
|---------|-------|------------|--------|
| Test data not seeded — need realistic GE MD files + 4 fixture transcripts | 2026-03-31 | Human to provide or approve seeded content | Open |

---

## Completion Checklist

- [ ] `test-data/golden-eagle/` seeded with realistic MD files (floor-plan, project-overview, people/lauren-thompson)
- [ ] 4 fixture `consolidated.txt` files written (3 with changes + 1 null case)
- [ ] `scripts/test-extraction.js` created and runs without errors
- [ ] All 6 test cases pass across all fixtures
- [ ] System prompt version locked as `extraction-v1`
- [ ] Token budget check passes for all fixtures
- [ ] Any failing `old_value` checks resolved by adjusting prompt
- [ ] Findings documented in progress log above
- [ ] STATE.md updated
- [ ] DECISION-LOG.md updated
- [ ] ws-apply-edit notified: `old_value` / `new_value` schema confirmed stable
