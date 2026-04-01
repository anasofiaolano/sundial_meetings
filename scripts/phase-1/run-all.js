// Runs the extraction script against all 5 transcripts and saves results to test-data/results.json
// Usage: node scripts/run-all.js
// Re-running appends a new timestamped run so you can compare across prompt iterations.

const Anthropic = require('@anthropic-ai/sdk')
const fs = require('fs')
const path = require('path')

const PROJECT_DIR = path.join(__dirname, '../../test-data/golden-eagle')
const TRANSCRIPTS_DIR = path.join(__dirname, '../../test-data/transcripts')
const RESULTS_FILE = path.join(__dirname, '../../test-data/results.json')
const client = new Anthropic()

const TRANSCRIPTS = [
  'transcript-01-golden-eagle-discovery.txt',
  'transcript-02-internal-planning.txt',
  'transcript-03-mockup-demo.txt',
  'transcript-04-feature-planning.txt',
  'transcript-05-coordination.txt'
]

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
7. If a transcript contains no new facts about the client engagement, return [].

Output a JSON array of proposed edits. If no updates are needed, output an empty array [].`

// Tool use requires type: object at root — wrap the array
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

async function extractForTranscript(transcriptFile) {
  const transcriptPath = path.join(TRANSCRIPTS_DIR, transcriptFile)
  const transcript = fs.readFileSync(transcriptPath, 'utf8')
  const projectFiles = loadProjectFiles(PROJECT_DIR)

  const fileContext = Object.entries(projectFiles)
    .map(([relPath, content]) => `[FILE: ${relPath}]\n${content}`)
    .join('\n\n---\n\n')

  const userMessage = `## Call Transcript\n${transcript}\n\n---\n\n## Current Project Files\n${fileContext}`
  const messages = [{ role: 'user', content: userMessage }]

  // Token budget check
  const count = await client.messages.countTokens({ model: 'claude-opus-4-6', system: SYSTEM_PROMPT, messages })
  console.log(`  Tokens: ${count.input_tokens.toLocaleString()}`)
  if (count.input_tokens > 160_000) throw new Error(`Token budget exceeded: ${count.input_tokens}`)

  const response = await client.messages.create({
    model: 'claude-opus-4-6',
    max_tokens: 4096,
    system: SYSTEM_PROMPT,
    messages,
    tools: [{ name: 'propose_edits', description: 'Output the proposed edits array', input_schema: TOOL_SCHEMA }],
    tool_choice: { type: 'tool', name: 'propose_edits' }
  })

  const toolUse = response.content.find(b => b.type === 'tool_use')
  if (!toolUse) throw new Error('No tool_use block in response')
  const edits = toolUse.input.edits || []

  // Validate old_values
  const knownPaths = new Set(Object.keys(projectFiles))
  const validation = edits.map(edit => {
    if (!knownPaths.has(edit.file_path)) return { ...edit, _valid: false, _error: 'hallucinated_path' }
    if (!projectFiles[edit.file_path].includes(edit.old_value)) return { ...edit, _valid: false, _error: 'old_value_not_found' }
    return { ...edit, _valid: true }
  })

  return { transcript: transcriptFile, edits: validation, token_count: count.input_tokens }
}

async function main() {
  console.log('Sundial CRM — Running all extractions\n')

  const runResults = []

  for (const transcript of TRANSCRIPTS) {
    console.log(`\n[${transcript}]`)
    try {
      const result = await extractForTranscript(transcript)
      const valid = result.edits.filter(e => e._valid).length
      const invalid = result.edits.filter(e => !e._valid).length
      console.log(`  Edits: ${result.edits.length} proposed (${valid} valid, ${invalid} validation failures)`)
      runResults.push({ ...result, error: null })
    } catch (err) {
      console.error(`  FAILED: ${err.message}`)
      runResults.push({ transcript, edits: [], token_count: 0, error: err.message })
    }
  }

  // Load or create results file
  let allRuns = []
  if (fs.existsSync(RESULTS_FILE)) {
    allRuns = JSON.parse(fs.readFileSync(RESULTS_FILE, 'utf8'))
  }

  const run = {
    run_id: allRuns.length + 1,
    timestamp: new Date().toISOString(),
    prompt_version: 'extraction-v1',
    results: runResults
  }
  allRuns.push(run)

  fs.writeFileSync(RESULTS_FILE, JSON.stringify(allRuns, null, 2))
  console.log(`\n✅ Results saved to test-data/results.json (run #${run.run_id})`)
  console.log('   Run `node scripts/report.js` to generate the HTML report.')
}

main().catch(err => {
  console.error('Fatal:', err.message)
  process.exit(1)
})
