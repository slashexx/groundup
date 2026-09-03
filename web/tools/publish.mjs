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
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

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

async function obtainDocument() {
  if (typeof api === 'string') {
    const url = `${api}/cadastre/document?db_path=${encodeURIComponent(db)}`
    console.log(`fetching ${url}`)
    const r = await fetch(url)
    if (!r.ok) throw new Error(`sidecar answered ${r.status}: ${(await r.text()).slice(0, 300)}`)
    return { doc: await r.json(), source: `live · ${db}` }
  }
  console.log(`reading fixture ${FIXTURE}`)
  return { doc: JSON.parse(readFileSync(FIXTURE, 'utf8')), source: 'fixture · demo-parcel.json' }
}

const { doc, source } = await obtainDocument()

// Refuse to publish an empty or shapeless bundle — a broken publish must fail
// here, not render as a blank page for a judge.
if (!doc || typeof doc !== 'object' || !Array.isArray(doc.units) || doc.units.length === 0) {
  console.error('refusing to publish: document has no units[]')
  process.exit(1)
}
if (!doc.project || typeof doc.project !== 'object') {
  console.error('refusing to publish: document has no project settings')
  process.exit(1)
}

const findings = doc.findings ?? doc.expected_findings ?? []
const manifest = {
  exported_at: new Date().toISOString(),
  source,
  unit_count: doc.units.length,
  finding_count: findings.length,
}

const dataDir = join(WEB, 'public', 'data')
mkdirSync(dataDir, { recursive: true })
writeFileSync(join(dataDir, 'document.json'), JSON.stringify(doc, null, 1))
writeFileSync(join(dataDir, 'manifest.json'), JSON.stringify(manifest, null, 1))
console.log(`bundle: ${manifest.unit_count} units, ${manifest.finding_count} findings (${source})`)

execSync('pnpm build', { cwd: WEB, stdio: 'inherit' })

if (deploy) {
  execSync(
    `pnpm --package=netlify-cli dlx netlify deploy --prod --dir dist --site ${NETLIFY_SITE}`,
    { cwd: WEB, stdio: 'inherit' },
  )
} else {
  console.log('built. add --deploy to push to Netlify.')
}
