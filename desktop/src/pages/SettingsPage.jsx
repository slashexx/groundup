import { DataSourceBanner, NothingYet, useCadastreDocument } from '../data/useCadastre';

/**
 * What this project was created with.
 *
 * Every value on this screen is read from the open project's `project_settings` row, and
 * every one of them is read-only. That is not a missing feature. These numbers were
 * written once when the project was created and every unit in it already carries them:
 * the CRS its geometry is stored in, the datum its heights are measured against, the
 * strata its identifiers were minted under. Changing one here would not migrate anything
 * — it would leave a register whose units disagree with the project that holds them, and
 * whose issued identifiers no longer describe the space they name.
 *
 * The page used to be local `useState` with no call to the sidecar at all: a Save button
 * that flashed a green tick and wrote nothing, a CRS read from a key the sidecar does not
 * send (`crs` rather than `project_crs`) so it always fell back to EPSG:4326 and
 * contradicted the sidebar two inches away, a ULPIN prefix invented for one demo ward,
 * and a tile server and AI endpoint no code reads.
 */

/** One setting, as a value. Not an input: none of these can be changed here. */
function Setting({ title, desc, value, mono }) {
  return (
    <div className="settings-row">
      <div className="settings-row-label">
        <div className="settings-row-title">{title}</div>
        <div className="settings-row-desc">{desc}</div>
      </div>
      <div className="settings-row-value">
        <div style={{
          padding: '8px 12px', background: 'var(--bg-surface)',
          borderRadius: 'var(--radius-md)', fontSize: 'var(--text-sm)',
          color: 'var(--text-primary)',
          fontFamily: mono ? 'var(--font-mono)' : undefined,
        }}>
          {value ?? '—'}
        </div>
      </div>
    </div>
  );
}

const metres = (v) => (v === null || v === undefined ? null : `${Number(v).toFixed(2)} m`);

export default function SettingsPage({ project }) {
  const { doc, live, status, error, reload } = useCadastreDocument();
  const s = live && doc ? doc.project : null;

  // The scheme version as the identifier itself spells it: `v1` in the settings row is
  // `V1` in the minted string.
  const schemeField = s?.ulpin_version
    ? `V${String(s.ulpin_version).replace(/^v/i, '')}`
    : 'V…';

  return (
    <div className="settings-page">
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
          Project Settings
        </h2>
        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)', maxWidth: 720, lineHeight: 1.6 }}>
          What this project was created with. These are fixed at creation and shown here
          rather than offered for editing: every unit already carries them, and every
          identifier and tolerance in the register was issued against them. Changing one
          after the fact would not migrate anything — it would leave the record describing
          a project that no longer exists. A new frame means a new project.
        </p>
      </div>

      <div style={{ marginBottom: 16 }}>
        <DataSourceBanner status={status} error={error} onRetry={reload} />
      </div>

      {!s ? (
        <NothingYet title="No settings to show">
          The project's settings live in the GeoPackage and are read through the sidecar,
          which is not answering. Nothing is shown rather than the defaults a new project
          would have been given — those would be a description of some other project.
        </NothingYet>
      ) : (
        <>
          <div className="settings-section">
            <div className="settings-section-title">Project</div>
            <Setting title="Project name" desc="The GeoPackage's own file name"
                     value={project?.name} />
            <Setting title="Project file" desc="Where every write in this app lands"
                     value={project?.db_path} mono />
          </div>

          <div className="settings-section">
            <div className="settings-section-title">Coordinate frame</div>
            <Setting title="Coordinate reference system"
                     desc="Every footprint is stored in this CRS, in metres. Areas, distances and tolerances are computed in it directly rather than reprojected per operation."
                     value={s.project_crs} mono />
            <Setting title="Vertical datum"
                     desc="What every height in the project is measured against. A unit's base and top mean nothing without it."
                     value={s.vertical_datum} mono />
          </div>

          <div className="settings-section">
            <div className="settings-section-title">Vertical extent</div>
            <Setting title="Stratum lower limit"
                     desc="How far below the surface this project's identifiers reach. Nothing deeper can be recorded here."
                     value={metres(s.stratum_below_limit_m)} />
            <Setting title="Stratum upper limit"
                     desc="And how far above it. A tower taller than this needs a project that says so."
                     value={metres(s.stratum_above_limit_m)} />
          </div>

          <div className="settings-section">
            <div className="settings-section-title">Height derivation</div>
            <Setting title="Default plinth offset"
                     desc="Indian construction sits above the surrounding ground. Applied when a building's base is derived from a DEM, and recorded on the unit that used it."
                     value={metres(s.default_plinth_offset_m)} />
            <Setting title="Default parapet deduction"
                     desc="Fixed at zero, and the sidecar refuses anything else: the roof estimator is a median that already returns the roof slab, so a deduction on top would lower every floor in the project with every validation rule still passing."
                     value={metres(s.default_parapet_deduction_m)} />
          </div>

          <div className="settings-section">
            <div className="settings-section-title">Identifier and rules</div>
            <Setting title="ULPIN scheme version"
                     desc="The version field inside every identifier this project mints. It exists so the format can change when DoLR publishes the official specification without any issued identifier becoming ambiguous."
                     value={s.ulpin_version} mono />
            <Setting title="Identifier format"
                     desc="Minted by the sidecar, never composed here. The 14-character 2D ULPIN is carried through untouched so existing Bhu-Aadhaar records still resolve; the stratum letter and level are readable without a lookup; the last character is an ISO 7064 check character."
                     value={`[14-char parcel ULPIN]-${schemeField}-[stratum][level]-[sequence]-[check]`}
                     mono />
            <Setting title="Ruleset version"
                     desc="Which set of validation rules this project's findings were produced by."
                     value={s.ruleset_version} mono />
          </div>

          <div className="settings-section">
            <div className="settings-section-title">People</div>
            <NothingYet title="One operator, no user directory">
              This app runs as a single account with no sign-in, so there is nobody to
              list and no role to grant. Who decided what is still recorded — the sidecar
              writes the actor onto every acknowledgement, approval and suggestion review
              — but multi-user access needs a real identity store behind it, and there
              isn't one yet.
            </NothingYet>
          </div>
        </>
      )}
    </div>
  );
}
