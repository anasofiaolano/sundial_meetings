// Phase 2 test: runs all apply-edit fixtures and reports pass/fail
// Usage: node scripts/phase-2/test-apply.js

const fs = require('fs')
const path = require('path')
const { applyBatch, trackRead } = require('./apply-edits')

const FIXTURES_DIR = path.join(__dirname, '../../test-data/phase-2')

const FIXTURES = [
  {
    id: 'F1',
    name: 'Clean replacement (empty → something)',
    before: 'fixture-01-before.md',
    edits: 'fixture-01-edits.json',
    after: 'fixture-01-after.md',
    expectSuccess: true
  },
  {
    id: 'F2',
    name: 'Augmentation (append to existing)',
    before: 'fixture-02-before.md',
    edits: 'fixture-02-edits.json',
    after: 'fixture-02-after.md',
    expectSuccess: true
  },
  {
    id: 'F3',
    name: 'old_value not found — must fail, file unchanged',
    before: 'fixture-01-before.md',
    edits: 'fixture-03-edits.json',
    after: null,
    expectSuccess: false,
    expectError: 'OLD_VALUE_NOT_FOUND'
  },
  {
    id: 'F4',
    name: 'Duplicate old_value — must fail, file unchanged',
    before: 'fixture-04-before.md',
    edits: 'fixture-04-edits.json',
    after: null,
    expectSuccess: false,
    expectError: 'AMBIGUOUS_MATCH'
  },
  {
    id: 'F6',
    name: 'Sequential edits — 3 edits building on each other',
    before: 'fixture-06-before.md',
    edits: 'fixture-06-edits.json',
    after: 'fixture-06-after.md',
    expectSuccess: true
  }
]

// Run a fixture in isolation using a temp copy of the before file
async function runFixture(fixture) {
  const beforePath = path.join(FIXTURES_DIR, fixture.before)
  const editsPath = path.join(FIXTURES_DIR, fixture.edits)

  // Work on a temp copy so fixtures are reusable
  const tmpDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sundial-test-'))
  const tmpFile = path.join(tmpDir, fixture.before)
  fs.copyFileSync(beforePath, tmpFile)

  const edits = JSON.parse(fs.readFileSync(editsPath, 'utf8'))

  // Remap file_path in edits to the temp filename
  const remappedEdits = edits.map(e => ({ ...e, file_path: fixture.before }))

  // Track the temp file as read
  trackRead(tmpFile)

  try {
    const result = await applyBatch(
      remappedEdits,
      tmpDir,
      'test transcript',
      fixture.id,
      { skipRetry: !fixture.expectSuccess }
    )

    if (fixture.expectSuccess) {
      // Check output matches expected after file
      const actualContent = fs.readFileSync(tmpFile, 'utf8')
      const expectedContent = fs.readFileSync(
        path.join(FIXTURES_DIR, fixture.after), 'utf8'
      )
      const match = actualContent.trim() === expectedContent.trim()

      if (result.applied.length === 0) {
        return { pass: false, reason: 'No edits were applied' }
      }
      if (!match) {
        return {
          pass: false,
          reason: 'Output does not match expected',
          actual: actualContent,
          expected: expectedContent
        }
      }
      return { pass: true, applied: result.applied.length }

    } else {
      // Expect failure
      const hasExpectedError = result.failed.some(f => f.error === fixture.expectError)
      const fileUnchanged = fs.readFileSync(tmpFile, 'utf8') ===
                            fs.readFileSync(beforePath, 'utf8')

      if (!hasExpectedError) {
        return { pass: false, reason: `Expected error ${fixture.expectError} but got: ${JSON.stringify(result.failed)}` }
      }
      if (!fileUnchanged) {
        return { pass: false, reason: 'File was modified despite expected failure' }
      }
      return { pass: true, error: fixture.expectError }
    }

  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true })
  }
}

async function main() {
  console.log('Phase 2: Apply Edit Tests\n' + '='.repeat(50))

  let passed = 0
  let failed = 0

  for (const fixture of FIXTURES) {
    process.stdout.write(`[${fixture.id}] ${fixture.name} ... `)
    try {
      const result = await runFixture(fixture)
      if (result.pass) {
        const detail = result.applied != null
          ? `${result.applied} edit(s) applied`
          : `correctly errored: ${result.error}`
        console.log(`✅ PASS (${detail})`)
        passed++
      } else {
        console.log(`❌ FAIL: ${result.reason}`)
        if (result.actual) {
          console.log(`   ACTUAL:   ${JSON.stringify(result.actual.trim())}`)
          console.log(`   EXPECTED: ${JSON.stringify(result.expected.trim())}`)
        }
        failed++
      }
    } catch (err) {
      console.log(`❌ ERROR: ${err.message}`)
      failed++
    }
  }

  console.log('\n' + '='.repeat(50))
  console.log(`${passed} passed, ${failed} failed`)
  if (failed > 0) process.exit(1)
}

main().catch(err => {
  console.error('Fatal:', err.message)
  process.exit(1)
})
