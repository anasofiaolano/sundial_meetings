// Phase 2: Apply Edit Logic
//
// Takes proposed edits from the extraction phase and applies them to project files.
// Follows Claude Code's FileEditTool patterns for correctness and safety.
//
// Key design decisions — see docs/phase-2-apply.md for full rationale.

const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')
const Anthropic = require('@anthropic-ai/sdk')

const client = new Anthropic()

// ---------------------------------------------------------------------------
// Read-state tracking
// Mirrors Claude Code's readFileState map.
// Maps absolute file path → { content, timestamp }
// Every file must be read (and tracked here) before it can be edited.
// ---------------------------------------------------------------------------
const readFileState = new Map()

function trackRead(absolutePath) {
  const content = fs.readFileSync(absolutePath, 'utf8').replace(/\r\n/g, '\n')
  const { mtimeMs } = fs.statSync(absolutePath)
  readFileState.set(absolutePath, { content, timestamp: mtimeMs })
  return content
}

function loadProjectFiles(projectDir) {
  const files = {}
  function walk(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) walk(full)
      else if (entry.name.endsWith('.md')) {
        const rel = path.relative(projectDir, full)
        files[rel] = trackRead(full)
      }
    }
  }
  walk(projectDir)
  return files
}

// ---------------------------------------------------------------------------
// Quote normalization (copied from Claude Code FileEditTool/utils.ts)
// Claude sometimes outputs curly quotes when the file has straight quotes.
// Normalize both sides before matching so edits don't silently fail.
// ---------------------------------------------------------------------------
function normalizeQuotes(str) {
  return str
    .replace(/\u2018/g, "'").replace(/\u2019/g, "'")   // curly single ' '
    .replace(/\u201C/g, '"').replace(/\u201D/g, '"')   // curly double " "
}

function findActualString(fileContent, searchString) {
  if (fileContent.includes(searchString)) return searchString

  // Try with normalized quotes
  const normalizedSearch = normalizeQuotes(searchString)
  const normalizedFile = normalizeQuotes(fileContent)
  const idx = normalizedFile.indexOf(normalizedSearch)
  if (idx !== -1) return fileContent.substring(idx, idx + searchString.length)

  return null
}

// When old_value matched via quote normalization, apply the same quote style
// to new_value so the file's typography is preserved.
function preserveQuoteStyle(oldValue, actualOldValue, newValue) {
  if (oldValue === actualOldValue) return newValue

  const hasCurlyDouble = /[\u201C\u201D]/.test(actualOldValue)
  const hasCurlySingle = /[\u2018\u2019]/.test(actualOldValue)

  let result = newValue
  if (hasCurlyDouble) {
    result = result.replace(/"/g, (_, offset, str) => {
      const prev = str[offset - 1] || ''
      const isOpening = !prev || /[\s(\[{]/.test(prev)
      return isOpening ? '\u201C' : '\u201D'
    })
  }
  if (hasCurlySingle) {
    result = result.replace(/'/g, (_, offset, str) => {
      const prev = str[offset - 1] || ''
      const next = str[offset + 1] || ''
      if (/\p{L}/u.test(prev) && /\p{L}/u.test(next)) return '\u2019' // apostrophe
      return /[\s(\[{]/.test(prev) || !prev ? '\u2018' : '\u2019'
    })
  }
  return result
}

// ---------------------------------------------------------------------------
// clarifyOldValue — called when old_value is not found or is ambiguous.
// Uses Haiku (sufficient for this task) with the full transcript for context.
// new_value is never passed to Claude — we keep the original throughout.
// ---------------------------------------------------------------------------
async function clarifyOldValue(content, edit, error, transcript) {
  const problem = error === 'AMBIGUOUS_MATCH'
    ? `The old_value you chose appears more than once in the file, so it's ambiguous which occurrence to replace.`
    : `The old_value you chose was not found verbatim in the file. It may have been slightly paraphrased or misquoted.`

  const response = await client.messages.create({
    model: 'claude-haiku-4-5-20251001',
    max_tokens: 512,
    messages: [{
      role: 'user',
      content: `You are maintaining a set of markdown files that get updated as new information comes in.
The way edits work is: you choose an old_value (exact text currently in the file) and
a new_value (what replaces it). This is a find-and-replace — old_value must exist
verbatim and exactly once in the file.

You proposed this edit:

  old_value: "${edit.old_value}"
  new_value: "${edit.new_value}"

Problem: ${problem}

Here is the transcript you were working from:
---
${transcript}
---

Here is the current file content:
---
${content}
---

Please choose a revised old_value that exists verbatim and exactly once in the file
above, and still correctly identifies the text you intended to replace.
The new_value does not change — only old_value needs to be fixed.`
    }],
    tools: [{
      name: 'revised_old_value',
      description: 'Return only the corrected old_value',
      input_schema: {
        type: 'object',
        properties: {
          old_value: { type: 'string' }
        },
        required: ['old_value']
      }
    }],
    tool_choice: { type: 'tool', name: 'revised_old_value' }
  })

  const toolUse = response.content.find(b => b.type === 'tool_use')
  if (!toolUse) return null

  const revised = toolUse.input.old_value

  // Sanity check: must exist exactly once
  const first = content.indexOf(revised)
  if (first === -1) return null
  if (content.indexOf(revised, first + 1) !== -1) return null

  return revised
}

// ---------------------------------------------------------------------------
// applyEditToContent — pure function, no I/O
// Applies one edit to a string and returns the updated string.
// Handles trailing-newline cleanup when new_value is empty (deletion).
// ---------------------------------------------------------------------------
function applyEditToContent(content, actualOldValue, actualNewValue) {
  if (actualNewValue !== '') {
    return content.replace(actualOldValue, () => actualNewValue)
  }
  // Deletion: strip the trailing newline too so we don't leave a blank line
  if (!actualOldValue.endsWith('\n') && content.includes(actualOldValue + '\n')) {
    return content.replace(actualOldValue + '\n', () => '')
  }
  return content.replace(actualOldValue, () => '')
}

// ---------------------------------------------------------------------------
// applySingleEdit — applies one edit to the running content in memory.
// Retries once via clarifyOldValue on NOT_FOUND or AMBIGUOUS.
// Returns { success, content, error, edit }
// ---------------------------------------------------------------------------
async function applySingleEdit(currentContent, edit, transcript, retrying = false, skipRetry = false) {
  const actualOldValue = findActualString(currentContent, edit.old_value)

  if (!actualOldValue) {
    if (retrying || skipRetry) return { success: false, error: 'OLD_VALUE_NOT_FOUND', edit }
    const revised = await clarifyOldValue(currentContent, edit, 'OLD_VALUE_NOT_FOUND', transcript)
    if (!revised) return { success: false, error: 'OLD_VALUE_NOT_FOUND', edit }
    return applySingleEdit(currentContent, { ...edit, old_value: revised }, transcript, true, skipRetry)
  }

  const matches = currentContent.split(actualOldValue).length - 1
  if (matches > 1) {
    if (retrying || skipRetry) return { success: false, error: 'AMBIGUOUS_MATCH', count: matches, edit }
    const revised = await clarifyOldValue(currentContent, edit, 'AMBIGUOUS_MATCH', transcript)
    if (!revised) return { success: false, error: 'AMBIGUOUS_MATCH', edit }
    return applySingleEdit(currentContent, { ...edit, old_value: revised }, transcript, true, skipRetry)
  }

  const actualNewValue = preserveQuoteStyle(edit.old_value, actualOldValue, edit.new_value)
  const updatedContent = applyEditToContent(currentContent, actualOldValue, actualNewValue)

  if (updatedContent === currentContent) {
    return { success: false, error: 'NO_CHANGE', edit }
  }

  return { success: true, content: updatedContent, edit }
}

// ---------------------------------------------------------------------------
// applyBatch — applies a full set of proposed edits to project files.
//
// Flow:
//   1. Load all project files into readFileState
//   2. Group edits by file_path
//   3. Per file: apply edits sequentially against running in-memory state
//      — check old_value ⊄ previous new_value (Claude Code multi-edit safety)
//   4. Hold all updates in memory — write nothing yet
//   5. Staleness check (mtime) immediately before write
//   6. Write all files synchronously — no awaits between read and write
//   7. Git commit
//
// Returns { applied, failed, skipped, commitHash }
// ---------------------------------------------------------------------------
async function applyBatch(proposedEdits, projectDir, transcript, transcriptName, options = {}) {
  const { skipRetry = false } = options
  // 1. Load all files
  const projectFiles = loadProjectFiles(projectDir)
  const knownPaths = new Set(Object.keys(projectFiles))

  // Separate valid edits from hallucinated file paths upfront
  const validEdits = []
  const skipped = []
  for (const edit of proposedEdits) {
    if (!knownPaths.has(edit.file_path)) {
      skipped.push({ edit, reason: 'UNKNOWN_FILE_PATH' })
    } else {
      validEdits.push(edit)
    }
  }

  // 2. Group by file
  const byFile = {}
  for (const edit of validEdits) {
    if (!byFile[edit.file_path]) byFile[edit.file_path] = []
    byFile[edit.file_path].push(edit)
  }

  // 3. Apply edits per file, in memory
  const pendingWrites = new Map()  // relPath → updatedContent
  const applied = []
  const failed = []

  for (const [relPath, edits] of Object.entries(byFile)) {
    const absolutePath = path.join(projectDir, relPath)
    let runningContent = readFileState.get(absolutePath).content
    const appliedNewValues = []

    for (const edit of edits) {
      // Claude Code multi-edit safety: old_value must not be ⊂ a previous new_value
      const isSubstringOfPrevious = appliedNewValues.some(prev =>
        edit.old_value !== '' && prev.includes(edit.old_value)
      )
      if (isSubstringOfPrevious) {
        failed.push({ edit, error: 'OLD_VALUE_SUBSET_OF_PREVIOUS_NEW_VALUE' })
        continue
      }

      const result = await applySingleEdit(runningContent, edit, transcript, false, skipRetry)
      if (result.success) {
        runningContent = result.content
        appliedNewValues.push(edit.new_value)
        applied.push({ edit, file: relPath })
      } else {
        failed.push({ edit, error: result.error })
      }
    }

    if (runningContent !== readFileState.get(absolutePath).content) {
      pendingWrites.set(absolutePath, runningContent)
    }
  }

  // 4 + 5 + 6. Staleness check + synchronous write — no awaits in this block
  if (pendingWrites.size > 0) {
    for (const [absolutePath, updatedContent] of pendingWrites) {
      const state = readFileState.get(absolutePath)
      const { mtimeMs } = fs.statSync(absolutePath)
      if (mtimeMs > state.timestamp) {
        // File changed on disk since we read it — abort this file
        const rel = path.relative(projectDir, absolutePath)
        failed.push({ file: rel, error: 'FILE_MODIFIED_SINCE_READ' })
        pendingWrites.delete(absolutePath)
      }
    }

    // Synchronous writes — no awaits between reads and writes (atomicity)
    for (const [absolutePath, updatedContent] of pendingWrites) {
      fs.writeFileSync(absolutePath, updatedContent, 'utf8')
      // Update readFileState so subsequent operations see current state
      const { mtimeMs } = fs.statSync(absolutePath)
      readFileState.set(absolutePath, { content: updatedContent, timestamp: mtimeMs })
    }

    // 7. Git commit
    let commitHash = null
    try {
      const files = [...pendingWrites.keys()].map(p => `"${p}"`).join(' ')
      execSync(`git -C "${projectDir}" add ${files}`, { stdio: 'pipe' })
      const msg = `call: ${transcriptName} — ${applied.length} edit${applied.length !== 1 ? 's' : ''} applied`
      execSync(`git -C "${projectDir}" commit -m "${msg}"`, { stdio: 'pipe' })
      commitHash = execSync(`git -C "${projectDir}" rev-parse --short HEAD`, { stdio: 'pipe' }).toString().trim()
    } catch (err) {
      // Git not available or no changes to commit — non-fatal
      console.warn(`  git commit skipped: ${err.message.split('\n')[0]}`)
    }

    return { applied, failed, skipped, commitHash }
  }

  return { applied, failed, skipped, commitHash: null }
}

module.exports = { applyBatch, loadProjectFiles, trackRead }
