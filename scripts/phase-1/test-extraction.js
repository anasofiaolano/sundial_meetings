// Usage: node scripts/test-extraction.js <path-to-transcript.txt>
// Example: node scripts/test-extraction.js test-data/transcripts/transcript-01-golden-eagle-discovery.txt
//
// Loads all .md files from test-data/golden-eagle/, sends them + the transcript to Claude,
// prints proposed edits, then validates: file paths are real, old_values exist in files.

const Anthropic = require('@anthropic-ai/sdk')
const fs = require('fs')
const path = require('path')

const PROJECT_DIR = path.join(__dirname, '../../test-data/golden-eagle')
const client = new Anthropic()

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

async function checkTokenBudget(messages, system) {
  const count = await client.messages.countTokens({
    model: 'claude-opus-4-6',
    system,
    messages
  })
  console.log(`Token count: ${count.input_tokens.toLocaleString()} (limit: 160,000)`)
  if (count.input_tokens > 160_000) {
    throw new Error(`Token budget exceeded: ${count.input_tokens}. Split the context.`)
  }
  return count.input_tokens
}

const SYSTEM_PROMPT = `You are an expert sales data analyst for a consulting firm. Your job is to read a call transcript and propose targeted updates to the engagement's project files. You propose only — the consultant reviews and accepts.

## Context
These files track a consulting engagement. They include project overview and individual contact profiles. The goal is to keep them current after every call.

## Rules
1. Only propose edits to facts EXPLICITLY stated in the call — not implied or inferred.
2. If the current value in the file is already correct, do not propose an edit.
3. Do not add new sections, headings, or structural elements — only update values within existing structure.
4. For each proposed edit, quote the exact sentence or phrase from the transcript that justifies it.
5. If you are unsure whether a value changed, do not propose the edit.
6. Propose nothing for fields not mentioned in the transcript.
7. old_value must be the exact current text from the file — copy it verbatim.
8. If a transcript is an internal team call with no new facts about the client engagement, return [].

Output a JSON array of proposed edits. If no updates are needed, output an empty array [].`

const EDIT_SCHEMA = {
  type: 'array',
  items: {
    type: 'object',
    properties: {
      file_path:    { type: 'string', description: 'Relative path to the file, e.g. project-overview.md or people/jay-eichinger.md' },
      field_label:  { type: 'string', description: 'Human-readable name for the field being changed' },
      old_value:    { type: 'string', description: 'Exact current text from the file — verbatim copy' },
      new_value:    { type: 'string', description: 'Replacement value' },
      confidence:   { type: 'string', enum: ['high', 'medium', 'low'] },
      source_quote: { type: 'string', description: 'The exact sentence/phrase from the transcript justifying this edit' }
    },
    required: ['file_path', 'field_label', 'old_value', 'new_value', 'confidence', 'source_quote'],
    additionalProperties: false
  }
}

async function runExtraction(fixturePath) {
  const transcript = fs.readFileSync(fixturePath, 'utf8')
  const projectFiles = loadProjectFiles(PROJECT_DIR)

  const fileContext = Object.entries(projectFiles)
    .map(([relPath, content]) => `[FILE: ${relPath}]\n${content}`)
    .join('\n\n---\n\n')

  const userMessage = `## Call Transcript\n${transcript}\n\n---\n\n## Current Project Files\n${fileContext}`
  const messages = [{ role: 'user', content: userMessage }]

  await checkTokenBudget(messages, SYSTEM_PROMPT)

  console.log('\nCalling Claude (claude-opus-4-6)...\n')

  let response
  try {
    response = await client.messages.create({
      model: 'claude-opus-4-6',
      max_tokens: 4096,
      system: SYSTEM_PROMPT,
      messages,
      betas: ['output-128k-2025-02-19'],
      output_config: {
        format: {
          type: 'json_schema',
          name: 'proposed_edits',
          schema: EDIT_SCHEMA
        }
      }
    })
  } catch (err) {
    // output_config may not be available — fall back to tool use for structured output
    if (err.status === 400 || err.message?.includes('output_config')) {
      console.log('output_config not available, falling back to tool use...\n')
      response = await client.messages.create({
        model: 'claude-opus-4-6',
        max_tokens: 4096,
        system: SYSTEM_PROMPT,
        messages,
        tools: [{
          name: 'propose_edits',
          description: 'Output the array of proposed edits',
          input_schema: EDIT_SCHEMA
        }],
        tool_choice: { type: 'tool', name: 'propose_edits' }
      })
      const toolUse = response.content.find(b => b.type === 'tool_use')
      if (!toolUse) throw new Error('No tool_use block in response')
      return { edits: toolUse.input, projectFiles }
    }
    throw err
  }

  const edits = JSON.parse(response.content[0].text)
  return { edits, projectFiles }
}

async function main() {
  const fixturePath = process.argv[2]
  if (!fixturePath) {
    console.error('Usage: node scripts/test-extraction.js <path-to-transcript.txt>')
    process.exit(1)
  }

  const absPath = path.resolve(fixturePath)
  if (!fs.existsSync(absPath)) {
    console.error(`File not found: ${absPath}`)
    process.exit(1)
  }

  console.log(`\nTranscript: ${path.basename(absPath)}`)
  console.log('='.repeat(60))

  try {
    const { edits, projectFiles } = await runExtraction(absPath)

    console.log(`\n=== PROPOSED EDITS (${edits.length}) ===\n`)

    if (edits.length === 0) {
      console.log('(empty — no changes proposed)')
    }

    for (const edit of edits) {
      console.log(`FILE:    ${edit.file_path}`)
      console.log(`FIELD:   ${edit.field_label}`)
      console.log(`FROM:    "${edit.old_value}"`)
      console.log(`TO:      "${edit.new_value}"`)
      console.log(`CONF:    ${edit.confidence}`)
      console.log(`SOURCE:  "${edit.source_quote}"`)
      console.log()
    }

    // Validation
    console.log('=== VALIDATION ===\n')
    const knownPaths = new Set(Object.keys(projectFiles))
    let issues = 0

    for (const edit of edits) {
      if (!knownPaths.has(edit.file_path)) {
        console.warn(`⚠️  HALLUCINATED FILE PATH: "${edit.file_path}"`)
        issues++
      } else {
        const content = projectFiles[edit.file_path]
        if (!content.includes(edit.old_value)) {
          console.warn(`⚠️  OLD_VALUE NOT FOUND in ${edit.file_path}`)
          console.warn(`    Looking for: "${edit.old_value}"`)
          issues++
        }
      }
    }

    if (issues === 0 && edits.length > 0) console.log('✅ All validation checks passed')
    else if (issues === 0 && edits.length === 0) console.log('✅ Empty result — validation N/A')
    else console.log(`\n⚠️  ${issues} validation issue(s) found`)

  } catch (err) {
    console.error('\nExtraction failed:', err.message)
    if (err.status) console.error('HTTP status:', err.status)
    process.exit(1)
  }
}

main()
