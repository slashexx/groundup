/**
 * The two decisions the publish pipeline makes about a document, kept pure so they can
 * be tested without fetching, building or writing anything.
 *
 * `publish.mjs` is a script: importing it fetches, writes and shells out to a build.
 * These are the parts worth asserting, so they live here.
 */

/**
 * Why this bundle's findings should be believed.
 *
 * A finding count means nothing on its own: zero findings from a real run is a clean
 * record, zero from a project nobody validated is no information at all, and on a
 * published page they render as the same reassuring zero.
 */
export function validationOf({ live, run }) {
  if (!live) {
    // The fixture's states and findings are authored expectations, not the residue of a
    // run over it. Saying so is the difference between provenance and decoration.
    return { kind: 'fixture-expectations', run_id: null, ruleset_version: null }
  }
  if (!run || !run.run_id) return null
  return { kind: 'run', run_id: run.run_id, ruleset_version: run.ruleset_version ?? null }
}

/**
 * The reason to refuse this document, or null to publish it.
 *
 * A broken publish has to fail here rather than render as a blank page, or worse as a
 * confident one, for whoever opens the link.
 */
export function refusalFor(doc, { live, api, db } = {}) {
  if (!doc || typeof doc !== 'object' || !Array.isArray(doc.units) || doc.units.length === 0) {
    return 'refusing to publish: document has no units[]'
  }
  if (!doc.project || typeof doc.project !== 'object') {
    return 'refusing to publish: document has no project settings'
  }
  // `validation_state` is the honest signal that a run covered a unit: `save_run` writes
  // it back only for the units its run actually looked at, so a unit left `unvalidated`
  // means either nobody validated the project or it was validated before `derive` added
  // its floors. Both would publish "0 findings" for a record nobody checked.
  //
  // Live only. The fixture is exempt because its states are content, not residue -
  // 14 of its 16 units are deliberately `unvalidated`.
  if (live) {
    const uncovered = doc.units.filter(
      (u) => (u.validation_state ?? 'unvalidated') === 'unvalidated',
    )
    if (uncovered.length > 0) {
      return (
        `refusing to publish: ${uncovered.length} of ${doc.units.length} units are not ` +
        'covered by a validation run, so the site would show "0 findings" for a record ' +
        'nobody checked. Run validation first:\n' +
        `  curl -X POST ${api}/cadastre/validate -H 'content-type: application/json' ` +
        `-d '{"db_path":"${db}"}'`
      )
    }
  }
  return null
}

/** One line naming what produced this bundle's findings. */
export function describeValidation(validation) {
  if (validation?.kind === 'run' && validation.run_id) {
    return `run ${validation.run_id.slice(0, 8)} · ruleset ${validation.ruleset_version}`
  }
  if (validation?.kind === 'fixture-expectations') return 'fixture expectations'
  return 'provenance unavailable'
}
