// Reads test-data/results.json + test-data/expected-outputs.json
// Generates test-data/report.html — open in any browser, no server needed
// Usage: node scripts/report.js [run-id]   (defaults to latest run)

const fs = require('fs')
const path = require('path')

const RESULTS_FILE = path.join(__dirname, '../../test-data/results.json')
const EXPECTED_FILE = path.join(__dirname, '../../test-data/expected-outputs.json')
const REPORT_FILE = path.join(__dirname, '../../test-data/report.html')

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

// Match an actual edit to an expected edit: same file_path, and new_value contains the expected substring
function matchEdit(actual, expected) {
  if (actual.file_path !== expected.file_path) return false
  const nv = (actual.new_value || '').toLowerCase()
  return nv.includes(expected.new_value_contains.toLowerCase())
}

function scoreTranscript(actualEdits, expectedEdits) {
  const hits = []
  const misses = []
  const hallucinations = []

  // One actual edit can satisfy multiple expected edits (Claude bundles info into one edit per file)
  for (const exp of expectedEdits) {
    const match = actualEdits.find(act => matchEdit(act, exp))
    if (match) {
      hits.push({ expected: exp, actual: match })
    } else {
      misses.push({ expected: exp })
    }
  }

  // Hallucination: actual edit that doesn't satisfy any expected edit
  for (const act of actualEdits) {
    if (!expectedEdits.some(exp => matchEdit(act, exp))) {
      hallucinations.push({ actual: act })
    }
  }

  return { hits, misses, hallucinations }
}

function validationBadge(edit) {
  if (!edit._valid) {
    const label = edit._error === 'hallucinated_path' ? 'bad path' : 'old_value mismatch'
    return `<span class="badge badge-error">${label}</span>`
  }
  return `<span class="badge badge-ok">✓ valid</span>`
}

function confidenceBadge(conf) {
  const cls = conf === 'high' ? 'conf-high' : conf === 'medium' ? 'conf-med' : 'conf-low'
  return `<span class="conf ${cls}">${conf}</span>`
}

function renderTranscriptCard(transcriptMeta, actualResult, score) {
  const { hits, misses, hallucinations } = score
  const total = transcriptMeta.expected_edits.length
  const hitRate = total === 0 ? null : Math.round((hits.length / total) * 100)
  const isNullCase = total === 0

  let headerClass = 'card-neutral'
  if (isNullCase) {
    headerClass = actualResult.edits.length === 0 ? 'card-good' : 'card-warn'
  } else if (hitRate >= 80) headerClass = 'card-good'
  else if (hitRate >= 50) headerClass = 'card-warn'
  else headerClass = 'card-bad'

  const hitRateLabel = isNullCase
    ? (actualResult.edits.length === 0 ? '✓ correctly empty' : `⚠ ${actualResult.edits.length} unexpected edits`)
    : `${hits.length}/${total} expected (${hitRate}%)`

  const validationFailures = actualResult.edits.filter(e => !e._valid).length

  let hitsHtml = ''
  if (hits.length > 0) {
    hitsHtml = `
      <div class="section-label green-label">✅ Hits (${hits.length})</div>
      ${hits.map(({ expected, actual }) => `
        <div class="edit-row hit-row">
          <div class="edit-meta">
            <span class="file-tag">${escapeHtml(actual.file_path)}</span>
            <span class="field-tag">${escapeHtml(actual.field_label)}</span>
            ${confidenceBadge(actual.confidence)}
            ${validationBadge(actual)}
          </div>
          <div class="edit-values">
            <span class="old-val">"${escapeHtml(actual.old_value)}"</span>
            <span class="arrow">→</span>
            <span class="new-val">"${escapeHtml(actual.new_value)}"</span>
          </div>
          <div class="source-quote">"${escapeHtml(actual.source_quote)}"</div>
        </div>
      `).join('')}
    `
  }

  let missesHtml = ''
  if (misses.length > 0) {
    missesHtml = `
      <div class="section-label red-label">❌ Missed (${misses.length})</div>
      ${misses.map(({ expected }) => `
        <div class="edit-row miss-row">
          <div class="edit-meta">
            <span class="file-tag">${escapeHtml(expected.file_path)}</span>
            <span class="field-tag">${escapeHtml(expected.field_label)}</span>
            <span class="conf conf-${expected.confidence}">${expected.confidence}</span>
          </div>
          <div class="expected-note">${escapeHtml(expected.description || `Expected new value to contain: "${expected.new_value_contains}"`)}</div>
        </div>
      `).join('')}
    `
  }

  let hallucinationsHtml = ''
  if (hallucinations.length > 0) {
    hallucinationsHtml = `
      <div class="section-label yellow-label">⚠️ Not expected (${hallucinations.length})</div>
      ${hallucinations.map(({ actual }) => `
        <div class="edit-row hallucination-row">
          <div class="edit-meta">
            <span class="file-tag">${escapeHtml(actual.file_path)}</span>
            <span class="field-tag">${escapeHtml(actual.field_label)}</span>
            ${confidenceBadge(actual.confidence)}
            ${validationBadge(actual)}
          </div>
          <div class="edit-values">
            <span class="old-val">"${escapeHtml(actual.old_value)}"</span>
            <span class="arrow">→</span>
            <span class="new-val">"${escapeHtml(actual.new_value)}"</span>
          </div>
          <div class="source-quote">"${escapeHtml(actual.source_quote)}"</div>
        </div>
      `).join('')}
    `
  }

  const tokenCount = actualResult.token_count ? `${actualResult.token_count.toLocaleString()} tokens` : ''

  return `
    <div class="transcript-card">
      <div class="card-header ${headerClass}">
        <div class="card-title">
          <span class="transcript-id">${escapeHtml(transcriptMeta.id)}</span>
          <span class="transcript-name">${escapeHtml(transcriptMeta.name)}</span>
          <span class="transcript-date">${escapeHtml(transcriptMeta.date)}</span>
        </div>
        <div class="card-stats">
          <span class="hit-rate">${hitRateLabel}</span>
          ${validationFailures > 0 ? `<span class="badge badge-error">${validationFailures} validation fail</span>` : ''}
          ${tokenCount ? `<span class="token-count">${tokenCount}</span>` : ''}
        </div>
      </div>
      <div class="card-note">${escapeHtml(transcriptMeta.note)}</div>
      <div class="card-body">
        ${hitsHtml}
        ${missesHtml}
        ${hallucinationsHtml}
        ${hits.length === 0 && misses.length === 0 && hallucinations.length === 0 ? '<div class="empty-state">No edits proposed or expected.</div>' : ''}
      </div>
    </div>
  `
}

function generateHtml(run, expected) {
  const cards = []
  let totalExpected = 0, totalHits = 0, totalHallucinations = 0, totalValidationFails = 0

  for (const transcriptMeta of expected.transcripts) {
    const actualResult = run.results.find(r => r.transcript === transcriptMeta.file)
    if (!actualResult) continue

    const score = scoreTranscript(actualResult.edits, transcriptMeta.expected_edits)
    totalExpected += transcriptMeta.expected_edits.length
    totalHits += score.hits.length
    totalHallucinations += score.hallucinations.length
    totalValidationFails += actualResult.edits.filter(e => !e._valid).length

    cards.push(renderTranscriptCard(transcriptMeta, actualResult, score))
  }

  const overallRate = totalExpected > 0 ? Math.round((totalHits / totalExpected) * 100) : 0
  const rateColor = overallRate >= 80 ? '#16a34a' : overallRate >= 60 ? '#d97706' : '#dc2626'

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sundial CRM — Extraction Test Report</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8fafc; color: #1e293b; padding: 24px; }
    .page { max-width: 960px; margin: 0 auto; }

    /* Header */
    .page-header { margin-bottom: 32px; }
    .page-title { font-size: 22px; font-weight: 700; color: #0f172a; }
    .page-meta { font-size: 13px; color: #64748b; margin-top: 4px; }
    .prompt-ver { display: inline-block; background: #e2e8f0; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 600; color: #475569; margin-left: 8px; }

    /* Summary bar */
    .summary-bar { display: flex; gap: 16px; background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px 24px; margin-bottom: 28px; align-items: center; flex-wrap: wrap; }
    .summary-stat { text-align: center; min-width: 80px; }
    .summary-stat .stat-num { font-size: 28px; font-weight: 700; }
    .summary-stat .stat-label { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px; }
    .divider { width: 1px; height: 48px; background: #e2e8f0; }

    /* Cards */
    .transcript-card { background: white; border: 1px solid #e2e8f0; border-radius: 10px; margin-bottom: 20px; overflow: hidden; }
    .card-header { padding: 16px 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
    .card-good { background: #f0fdf4; border-bottom: 1px solid #bbf7d0; }
    .card-warn { background: #fffbeb; border-bottom: 1px solid #fde68a; }
    .card-bad  { background: #fef2f2; border-bottom: 1px solid #fecaca; }
    .card-neutral { background: #f8fafc; border-bottom: 1px solid #e2e8f0; }
    .card-title { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .transcript-id { font-weight: 700; font-size: 13px; background: #1e293b; color: white; border-radius: 4px; padding: 2px 8px; }
    .transcript-name { font-weight: 600; font-size: 15px; }
    .transcript-date { font-size: 12px; color: #64748b; }
    .card-stats { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .hit-rate { font-size: 14px; font-weight: 600; color: #0f172a; }
    .token-count { font-size: 11px; color: #94a3b8; }
    .card-note { padding: 8px 20px; font-size: 12px; color: #64748b; font-style: italic; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }
    .card-body { padding: 16px 20px; display: flex; flex-direction: column; gap: 12px; }

    /* Section labels */
    .section-label { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; padding: 4px 0; margin-top: 4px; }
    .green-label { color: #16a34a; }
    .red-label { color: #dc2626; }
    .yellow-label { color: #b45309; }

    /* Edit rows */
    .edit-row { border-radius: 6px; padding: 10px 12px; font-size: 13px; display: flex; flex-direction: column; gap: 5px; }
    .hit-row { background: #f0fdf4; border: 1px solid #bbf7d0; }
    .miss-row { background: #fef2f2; border: 1px solid #fecaca; }
    .hallucination-row { background: #fffbeb; border: 1px solid #fde68a; }
    .edit-meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    .file-tag { background: #1e293b; color: white; font-size: 11px; border-radius: 3px; padding: 1px 6px; font-family: monospace; }
    .field-tag { font-weight: 600; font-size: 12px; color: #334155; }
    .edit-values { display: flex; flex-direction: column; gap: 4px; }
    .edit-values .arrow { color: #94a3b8; font-size: 11px; padding-left: 2px; }
    .old-val { color: #ef4444; font-size: 12px; font-family: monospace; word-break: break-word; white-space: pre-wrap; }
    .new-val { color: #16a34a; font-size: 12px; font-family: monospace; word-break: break-word; white-space: pre-wrap; }
    .arrow { color: #94a3b8; flex-shrink: 0; }
    .source-quote { font-size: 11px; color: #64748b; font-style: italic; border-left: 2px solid #cbd5e1; padding-left: 8px; word-break: break-word; }
    .expected-note { font-size: 12px; color: #7f1d1d; }
    .empty-state { color: #94a3b8; font-size: 13px; font-style: italic; }

    /* Badges */
    .badge { font-size: 10px; font-weight: 600; border-radius: 4px; padding: 2px 6px; text-transform: uppercase; }
    .badge-ok { background: #dcfce7; color: #16a34a; }
    .badge-error { background: #fee2e2; color: #dc2626; }
    .conf { font-size: 10px; border-radius: 3px; padding: 1px 5px; font-weight: 600; }
    .conf-high { background: #dcfce7; color: #166534; }
    .conf-med  { background: #fef3c7; color: #92400e; }
    .conf-low  { background: #fee2e2; color: #991b1b; }
  </style>
</head>
<body>
  <div class="page">
    <div class="page-header">
      <div class="page-title">Sundial CRM — Extraction Test Report</div>
      <div class="page-meta">
        Run #${run.run_id} · ${new Date(run.timestamp).toLocaleString()}
        <span class="prompt-ver">${escapeHtml(run.prompt_version)}</span>
      </div>
    </div>

    <div class="summary-bar">
      <div class="summary-stat">
        <div class="stat-num" style="color: ${rateColor}">${overallRate}%</div>
        <div class="stat-label">Hit Rate</div>
      </div>
      <div class="divider"></div>
      <div class="summary-stat">
        <div class="stat-num" style="color: #16a34a">${totalHits}</div>
        <div class="stat-label">Hits</div>
      </div>
      <div class="summary-stat">
        <div class="stat-num" style="color: #dc2626">${totalExpected - totalHits}</div>
        <div class="stat-label">Misses</div>
      </div>
      <div class="summary-stat">
        <div class="stat-num" style="color: #d97706">${totalHallucinations}</div>
        <div class="stat-label">Unexpected</div>
      </div>
      <div class="summary-stat">
        <div class="stat-num" style="color: #dc2626">${totalValidationFails}</div>
        <div class="stat-label">Val. Failures</div>
      </div>
      <div class="divider"></div>
      <div class="summary-stat">
        <div class="stat-num" style="color: #64748b">${totalExpected}</div>
        <div class="stat-label">Expected</div>
      </div>
    </div>

    ${cards.join('\n')}
  </div>
</body>
</html>`
}

function main() {
  if (!fs.existsSync(RESULTS_FILE)) {
    console.error('No results.json found. Run `node scripts/run-all.js` first.')
    process.exit(1)
  }

  const allRuns = JSON.parse(fs.readFileSync(RESULTS_FILE, 'utf8'))
  const expected = JSON.parse(fs.readFileSync(EXPECTED_FILE, 'utf8'))

  const runIdArg = process.argv[2]
  const run = runIdArg
    ? allRuns.find(r => r.run_id === parseInt(runIdArg))
    : allRuns[allRuns.length - 1]

  if (!run) {
    console.error(`Run not found. Available runs: ${allRuns.map(r => r.run_id).join(', ')}`)
    process.exit(1)
  }

  console.log(`Generating report for run #${run.run_id} (${run.timestamp})...`)

  const html = generateHtml(run, expected)
  fs.writeFileSync(REPORT_FILE, html)

  console.log(`✅ Report written to test-data/report.html`)
  console.log(`   Open with: open test-data/report.html`)
}

main()
