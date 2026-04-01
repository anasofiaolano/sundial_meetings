# Phase 2 Test Data: Apply Edit Logic

Test fixtures for the SEARCH/REPLACE apply logic. Each fixture is a before-state file + a set of proposed edits + an expected after-state.

---

## Fixtures

### fixture-01: clean replacement
Simple `old_value → new_value` on a single line. The happy path.

**Input file:** `fixture-01-before.md`
**Edits:** `fixture-01-edits.json`
**Expected output:** `fixture-01-after.md`

### fixture-02: augmentation
`old_value` is a paragraph. `new_value` is the same paragraph with new sentences appended.

### fixture-03: old_value not found
`old_value` doesn't exist in the file. Should return error: `OLD_VALUE_NOT_FOUND`. File must not be modified.

### fixture-04: duplicate old_value
`old_value` appears twice in the file. Ambiguous — should return error: `AMBIGUOUS_MATCH`. File must not be modified.

### fixture-05: empty → something
`old_value` is `(no notes yet)`. `new_value` is a full section. The new-file case.

### fixture-06: multiple edits, one file
Three proposed edits to the same file applied in sequence. Each subsequent edit must use the post-previous-edit file state.

---

## Test cases

| # | Fixture | Expected result |
|---|---------|----------------|
| T1 | fixture-01 | File updated, new_value found verbatim in output |
| T2 | fixture-02 | File updated, new content appended, old content preserved |
| T3 | fixture-03 | Error returned, file unchanged |
| T4 | fixture-04 | Error returned, file unchanged |
| T5 | fixture-05 | File updated, placeholder replaced with full content |
| T6 | fixture-06 | All 3 edits applied, final state matches expected |
