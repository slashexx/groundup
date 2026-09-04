/**
 * What the publish pipeline refuses, and what it must not refuse.
 *
 *   cd web && pnpm test
 *
 * `node:test` and nothing else: a publish script does not need a test framework, and a
 * guard that only holds when a dependency is installed is not much of a guard.
 *
 * The negative cases matter as much as the positive ones. A publish gate that refuses
 * everything is not a gate, and the fixture path — the one used for every demo so far —
 * has to keep working.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { describeValidation, refusalFor, validationOf } from './bundle.mjs'

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const FIXTURE = join(WEB, '..', 'contracts', 'fixtures', 'demo-parcel.json')

const LIVE = { live: true, api: 'http://127.0.0.1:8000', db: 'pilot.gpkg' }
const project = { project_crs: 'EPSG:32643' }
const unit = (state) => ({ unit_id: `u-${state}`, validation_state: state })

test('a document with no units is refused', () => {
  assert.match(refusalFor({ project, units: [] }, LIVE), /no units/)
  assert.match(refusalFor(null, LIVE), /no units/)
})

test('a document with no project settings is refused', () => {
  assert.match(refusalFor({ units: [unit('passed')] }, LIVE), /project settings/)
})

test('a live project the latest run did not cover is refused', () => {
  // The case this guard exists for: ingest and derive ran, validation did not, and
  // `findings: []` would publish as a clean bill of health for a record nobody checked.
  const doc = { project, units: [unit('passed'), unit('unvalidated')] }
  const refusal = refusalFor(doc, LIVE)
  assert.match(refusal, /1 of 2 units are not covered/)
  assert.match(refusal, /cadastre\/validate/) // and says how to fix it
})

test('a unit with no validation_state at all counts as uncovered', () => {
  // Absent is not "fine": the column defaults to unvalidated for a reason.
  assert.match(refusalFor({ project, units: [{ unit_id: 'u' }] }, LIVE), /not covered/)
})

test('a fully validated live project is published', () => {
  const doc = { project, units: [unit('passed'), unit('failed'), unit('warnings')] }
  assert.equal(refusalFor(doc, LIVE), null)
})

test('failed units do not block a publish', () => {
  // Publishing a record that has errors is the point — the viewer colours them red.
  // What must not be published is a record nobody looked at.
  assert.equal(refusalFor({ project, units: [unit('failed')] }, LIVE), null)
})

test('the committed fixture still publishes, unvalidated units and all', () => {
  // 14 of the fixture's 16 units are deliberately `unvalidated`: they are authored
  // content, not the residue of a run. Applying the live guard to them would break
  // `pnpm publish:fixture`, which is the demo path.
  const fixture = JSON.parse(readFileSync(FIXTURE, 'utf8'))
  assert.ok(fixture.units.some((u) => u.validation_state === 'unvalidated'))
  assert.equal(refusalFor(fixture, { live: false }), null)
  assert.match(refusalFor(fixture, LIVE) ?? '', /not covered/) // ...but only because it is the fixture
})

test('provenance names the run that cleared a live record', () => {
  const v = validationOf({ live: true, run: { run_id: 'ba182e23-d6e9-4973', ruleset_version: 'r1' } })
  assert.deepEqual(v, { kind: 'run', run_id: 'ba182e23-d6e9-4973', ruleset_version: 'r1' })
  assert.equal(describeValidation(v), 'run ba182e23 · ruleset r1')
})

test('provenance says so when the fixture supplied the findings', () => {
  assert.equal(describeValidation(validationOf({ live: false })), 'fixture expectations')
})

test('an unreachable run endpoint degrades to "unavailable", never to "checked"', () => {
  // The refusal above has already established the units were covered; what is missing
  // here is only the run's name. Claiming a check we cannot name would be worse.
  assert.equal(validationOf({ live: true, run: null }), null)
  assert.equal(describeValidation(null), 'provenance unavailable')
  assert.equal(describeValidation(validationOf({ live: true, run: {} })), 'provenance unavailable')
})
