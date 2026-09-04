#!/usr/bin/env node
/**
 * P6 publish pipeline: obtain the project document, stamp a manifest,
 * build the read-only web app, optionally deploy.
 *
 *   node tools/publish.mjs                         # bundle = committed fixture
 *   node tools/publish.mjs --api http://127.0.0.1:8000 [--db pilot.gpkg]
 *   node tools/publish.mjs [...] --deploy          # + netlify --prod
 *
 * The bundle is the P4 export document (GET /cadastre/document), which is the
 * same shape as contracts/fixtures/demo-parcel.json — publishing the fixture
 * and publishing a live project are interchangeable by design.
 */
import { execSync } from 'node:child_process'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { basename, dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describeValidation, refusalFor, validationOf } from './bundle.mjs'

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const FIXTURE = join(WEB, '..', 'contracts', 'fixtures', 'demo-parcel.json')
const NETLIFY_SITE = '98f77c41-0f57-4936-bda4-e0416d709a2f' // sih26011-3d-ulpin

const args = process.argv.slice(2)
const flag = (name) => {
  const i = args.indexOf(name)
  return i === -1 ? undefined : (args[i + 1]?.startsWith('--') ? true : args[i + 1]) ?? true
}
const api = flag('--api')
const db = typeof flag('--db') === 'string' ? flag('--db') : 'pilot.gpkg'
const deploy = args.includes('--deploy')

const live = typeof api === 'string'

/** The latest validation run, for provenance. Its absence is not the guard - the
 *  unvalidated-unit check is; this only names the run that cleared the record. */
async function latestRun() {
  try {
    const r = await fetch(`${api}/cadastre/runs/latest?db_path=${encodeURIComponent(db)}`)
    return r.ok ? await r.json() : null
  } catch {
    return null
  }
}

async function obtainDocument() {
  if (live) {
    const url = `${api}/cadastre/document?db_path=${encodeURIComponent(db)}`
    console.log(`fetching ${url}`)
    const r = await fetch(url)
    if (!r.ok) throw new Error(`sidecar answered ${r.status}: ${(await r.text()).slice(0, 300)}`)
    // Only the file name, never the path it was read from: the manifest is served on a
    // public site, and `live · /home/someone/projects/pilot.gpkg` publishes the
    // operator's directory layout to anyone who opens the link.
    return {
      doc: await r.json(),
      source: `live · ${basename(db)}`,
      validation: validationOf({ live, run: await latestRun() }),
    }
  }
  console.log(`reading fixture ${FIXTURE}`)
  return {
    doc: JSON.parse(readFileSync(FIXTURE, 'utf8')),
    source: 'fixture · demo-parcel.json',
    validation: validationOf({ live }),
  }
}

const { doc, source, validation } = await obtainDocument()

// A broken publish must fail here, not render as a blank page — or worse, a confident
// one — for whoever opens the link. See tools/bundle.mjs for what each refusal catches.
const refusal = refusalFor(doc, { live, api, db })
if (refusal) {
  console.error(refusal)
  process.exit(1)
}

const findings = doc.findings ?? doc.expected_findings ?? []
const manifest = {
  exported_at: new Date().toISOString(),
  source,
  unit_count: doc.units.length,
  finding_count: findings.length,
  validation,
}

const dataDir = join(WEB, 'public', 'data')
mkdirSync(dataDir, { recursive: true })
writeFileSync(join(dataDir, 'document.json'), JSON.stringify(doc, null, 1))
writeFileSync(join(dataDir, 'manifest.json'), JSON.stringify(manifest, null, 1))
console.log(
  `bundle: ${manifest.unit_count} units, ${manifest.finding_count} findings, ` +
    `${describeValidation(validation)} (${source})`,
)

execSync('pnpm build', { cwd: WEB, stdio: 'inherit' })

if (deploy) {
  execSync(
    `pnpm --package=netlify-cli dlx netlify deploy --prod --dir dist --site ${NETLIFY_SITE}`,
    { cwd: WEB, stdio: 'inherit' },
  )
} else {
  console.log('built. add --deploy to push to Netlify.')
}
