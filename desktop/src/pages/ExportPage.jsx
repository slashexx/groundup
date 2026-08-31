import { useState } from 'react';
import { Icons } from '../components/Icons';

const formats = [
  { id: 'geojson', name: 'GeoJSON', desc: 'Standard geospatial format', icon: '🌐' },
  { id: 'json', name: 'JSON', desc: 'Structured data export', icon: '📋' },
  { id: 'citygml', name: 'CityGML', desc: '3D city model format', icon: '🏙️' },
  { id: 'ifc', name: 'IFC', desc: 'Building information model', icon: '🏗️' },
  { id: 'csv', name: 'CSV', desc: 'Tabular data export', icon: '📊' },
  { id: 'kml', name: 'KML', desc: 'Google Earth format', icon: '🌍' },
];

export default function ExportPage() {
  const [selectedFormat, setSelectedFormat] = useState('geojson');
  const [statusFilter, setStatusFilter] = useState('approved');
  const [dateRange, setDateRange] = useState({ from: '2025-05-01', to: '2025-05-29' });
  const [exporting, setExporting] = useState(false);
  const [exported, setExported] = useState(false);

  const recordCounts = {
    approved: 2812,
    all: 3361,
    draft: 156,
    review: 12,
  };

  const handleExport = () => {
    setExporting(true);
    setTimeout(() => {
      setExporting(false);
      setExported(true);
      setTimeout(() => setExported(false), 3000);
    }, 2000);
  };

  return (
    <div className="export-page">
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
            onClick={() => setSelectedFormat(f.id)}
          >
            <div style={{ fontSize: 28 }}>{f.icon}</div>
            <div className="export-format-name">{f.name}</div>
            <div className="export-format-desc">{f.desc}</div>
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
              <option value="approved">Approved Only</option>
              <option value="all">All Records</option>
              <option value="draft">Draft Only</option>
              <option value="review">Needs Review</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">From Date</label>
            <input className="form-input" type="date" value={dateRange.from}
              onChange={(e) => setDateRange({ ...dateRange, from: e.target.value })} />
          </div>
          <div className="form-group">
            <label className="form-label">To Date</label>
            <input className="form-input" type="date" value={dateRange.to}
              onChange={(e) => setDateRange({ ...dateRange, to: e.target.value })} />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
          <span className="search-filter-chip active">Land Parcels</span>
          <span className="search-filter-chip active">Buildings</span>
          <span className="search-filter-chip active">3D Units</span>
          <span className="search-filter-chip">Underground</span>
          <span className="search-filter-chip">Elevated</span>
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
            Format: <strong style={{ color: 'var(--text-primary)' }}>{formats.find(f => f.id === selectedFormat)?.name}</strong> ·
            Records: <strong style={{ color: 'var(--text-primary)' }}>{recordCounts[statusFilter]?.toLocaleString()}</strong> ·
            Status: <strong style={{ color: 'var(--text-primary)' }}>{statusFilter}</strong>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          {exported && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--status-success)', fontSize: 'var(--text-sm)', fontWeight: 600 }}>
              <Icons.Check style={{ width: 16, height: 16 }} /> Export complete!
            </div>
          )}
          <button className="btn btn-primary btn-lg" onClick={handleExport} disabled={exporting}>
            {exporting ? (
              <>Processing...</>
            ) : (
              <><Icons.Download style={{ width: 16, height: 16 }} /> Export {recordCounts[statusFilter]?.toLocaleString()} Records</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
