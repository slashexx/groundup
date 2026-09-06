import { useMemo, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { save } from '@tauri-apps/plugin-dialog';
import { Icons } from '../components/Icons';
import { UNIT_TYPE_LABELS, cadastre, unitsToCsv, unitsToGeoJson } from '../data/cadastreApi';
import { DataSourceBanner, useCadastreDocument } from '../data/useCadastre';

/** The document narrowed to a selection of units, with nothing left pointing at a unit
 *  the file does not contain.
 *
 *  Filtering only the `units` array was the obvious version and the wrong one: a
 *  relationship naming a parcel that was filtered out, or a finding raised against a unit
 *  nobody exported, is a dangling reference that validates against the schema and breaks
 *  in whatever reads it. A finding is kept when any unit it concerns survives, because it
 *  is still a fact about a unit in this file.
 */
function restrict(doc, units) {
  const kept = new Set(units.map(u => u.unit_id));
  const findings = (doc.findings ?? []).filter(
    f => kept.has(f.unit_id) || (f.related_unit_ids ?? []).some(id => kept.has(id)),
  );
  return {
    ...doc,
    units,
    relationships: (doc.relationships ?? []).filter(
      r => kept.has(r.from_unit_id) && kept.has(r.to_unit_id),
    ),
    findings,
    expected_findings: findings,
  };
}

/** `serialise` is what makes a format real. The three without one are listed anyway
 *  because the operator needs to know they are not available yet — a card that quietly
 *  disappeared would leave them hunting for a feature nobody removed on purpose. */
const formats = [
  {
    id: 'geojson', name: 'GeoJSON', desc: 'Standard geospatial format', icon: '🌐', ext: 'geojson',
    serialise: (doc, units) => JSON.stringify(unitsToGeoJson(units, doc.project.project_crs), null, 2),
  },
  {
    id: 'json', name: 'JSON', desc: 'Structured data export', icon: '📋', ext: 'json',
    serialise: (doc, units) => JSON.stringify(restrict(doc, units), null, 2),
  },
  {
    id: 'citygml', name: 'CityGML', desc: '3D city model format', icon: '🏙️',
    unavailable: 'CityGML needs a semantic city model this block does not hold — no thematic surfaces, no LoD. Writing one from prisms would produce a file that claims more than the data supports.',
  },
  {
    id: 'ifc', name: 'IFC', desc: 'Building information model', icon: '🏗️',
    unavailable: 'IFC describes a designed building, not a surveyed volume. Nothing in the cadastre document maps onto its element hierarchy.',
  },
  {
    id: 'csv', name: 'CSV', desc: 'Tabular data export', icon: '📊', ext: 'csv',
    serialise: (doc, units) => unitsToCsv(units),
  },
  {
    id: 'kml', name: 'KML', desc: 'Google Earth format', icon: '🌍',
    unavailable: 'KML is defined in WGS84 degrees. These footprints are in the project CRS in metres, and reprojecting them here would put a second, unrecorded transform in the chain.',
  },
];

const STATUS_FILTERS = {
  approved: { label: 'Approved Only', match: (u) => u.status === 'approved' },
  all: { label: 'All Records', match: () => true },
  draft: { label: 'Draft Only', match: (u) => u.status === 'draft' },
  review: { label: 'Needs Review', match: (u) => u.status === 'needs_review' },
};

const UNIT_TYPES = Object.keys(UNIT_TYPE_LABELS);

export default function ExportPage() {
  const { doc, live, status, error: loadError, reload } = useCadastreDocument();
  const [selectedFormat, setSelectedFormat] = useState('geojson');
  const [statusFilter, setStatusFilter] = useState('approved');
  const [types, setTypes] = useState(UNIT_TYPES);
  const [exporting, setExporting] = useState(false);
  const [exported, setExported] = useState(null);
  const [exportError, setExportError] = useState(null);

  const format = formats.find(f => f.id === selectedFormat);

  const selectUnits = useMemo(() => {
    const match = STATUS_FILTERS[statusFilter].match;
    return (d) => (d.units ?? []).filter(u => match(u) && types.includes(u.unit_type));
  }, [statusFilter, types]);

  // Counted from the open project. The number on the button was hardcoded once, and an
  // operator reading "2,812 records" out of an empty project has no way to tell.
  const selectedCount = live && doc ? selectUnits(doc).length : null;

  const toggleType = (t) =>
    setTypes(prev => (prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t]));

  // The document is re-read rather than exported from the copy this screen was drawn
  // with: an export is a record, and one written from a document fetched before somebody
  // else's approval landed is wrong in the one way nobody checks.
  const handleExport = async () => {
    setExporting(true);
    setExported(null);
    setExportError(null);
    try {
      const fresh = await cadastre.document();
      const units = selectUnits(fresh);
      const contents = format.serialise(fresh, units);
      const path = await save({
        defaultPath: `cadastre-${statusFilter}.${format.ext}`,
        filters: [{ name: format.name, extensions: [format.ext] }],
      });
      if (path === null) return;                 // the operator cancelled; not a failure
      await invoke('write_export', { path, contents });
      setExported({ path, units: units.length });
    } catch (e) {
      // Outside the Tauri shell there is no save dialog and no writer, and the runtime
      // reports that as a property missing on an internal object. Naming the actual
      // problem beats passing on "cannot read properties of undefined".
      setExportError(
        typeof window !== 'undefined' && !('__TAURI_INTERNALS__' in window)
          ? 'Saving a file needs the desktop shell. This page is running in a plain browser, which has nowhere to write to.'
          : String(e.message ?? e),
      );
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="export-page">
      <DataSourceBanner status={status} error={loadError} onRetry={reload} />
      <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
        Export Data
      </h2>
      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)', marginBottom: 24 }}>
        Export approved property records in standard geospatial formats
      </p>

      {/* Format Selection */}
      <h3 style={{ fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>
        Select Export Format
      </h3>
      <div className="export-format-grid">
        {formats.map(f => (
          <div key={f.id}
            className={`export-format-card ${selectedFormat === f.id ? 'selected' : ''}`}
            onClick={() => !f.unavailable && setSelectedFormat(f.id)}
            title={f.unavailable ?? `Export as ${f.name}`}
            style={f.unavailable ? { opacity: 0.4, cursor: 'not-allowed' } : undefined}
          >
            <div style={{ fontSize: 28 }}>{f.icon}</div>
            <div className="export-format-name">{f.name}</div>
            <div className="export-format-desc">{f.unavailable ? 'Not available' : f.desc}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)', padding: 24, marginBottom: 24 }}>
        <h3 style={{ fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>
          Filter Records
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
          <div className="form-group">
            <label className="form-label">Record Status</label>
            <select className="form-select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              {Object.entries(STATUS_FILTERS).map(([id, f]) => (
                <option key={id} value={id}>{f.label}</option>
              ))}
            </select>
          </div>
          {/* `recorded_from` is optional in `contracts/outbound/unit.schema.json`, so a date
              range would drop every unit that carries no date without saying which. */}
          <div className="form-group">
            <label className="form-label">From Date</label>
            <input className="form-input" type="date" disabled
              title="Record dates are optional in the outbound contract, so filtering on them would silently omit every unit that has none." />
          </div>
          <div className="form-group">
            <label className="form-label">To Date</label>
            <input className="form-input" type="date" disabled
              title="Record dates are optional in the outbound contract, so filtering on them would silently omit every unit that has none." />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
          {UNIT_TYPES.map(t => (
            <button key={t} className={`search-filter-chip ${types.includes(t) ? 'active' : ''}`}
              onClick={() => toggleType(t)}>
              {UNIT_TYPE_LABELS[t]}
            </button>
          ))}
        </div>
      </div>

      {/* Export Summary */}
      <div style={{
        background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
        padding: 24, display: 'flex', alignItems: 'center', justifyContent: 'space-between'
      }}>
        <div>
          <div style={{ fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
            Export Summary
          </div>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>
            Format: <strong style={{ color: 'var(--text-primary)' }}>{format.name}</strong> ·
            Records: <strong style={{ color: 'var(--text-primary)' }}>
              {selectedCount === null ? 'unknown — no project open' : selectedCount.toLocaleString()}
            </strong> ·
            Status: <strong style={{ color: 'var(--text-primary)' }}>{statusFilter}</strong>
          </div>
          {exportError && (
            <div style={{ marginTop: 8, fontSize: 'var(--text-sm)', color: 'var(--status-error)' }}>
              Export failed: {exportError}
            </div>
          )}
          {exported && (
            <div style={{ marginTop: 8, fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>
              {exported.units.toLocaleString()} record(s) written to {exported.path}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          {exported && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--status-success)', fontSize: 'var(--text-sm)', fontWeight: 600 }}>
              <Icons.Check style={{ width: 16, height: 16 }} /> Export complete!
            </div>
          )}
          <button className="btn btn-primary btn-lg" onClick={handleExport}
            disabled={!live || exporting || selectedCount === 0}
            title={!live ? 'Requires the cadastre sidecar'
              : selectedCount === 0 ? 'Nothing matches these filters'
                : 'Re-read the project and write the selection to a file'}>
            {exporting ? (
              <>Processing...</>
            ) : (
              <><Icons.Download style={{ width: 16, height: 16 }} /> Export {selectedCount === null ? '' : `${selectedCount.toLocaleString()} `}Records</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
