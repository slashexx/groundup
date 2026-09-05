import { useState } from 'react';
import { Icons } from '../components/Icons';
import { UNIT_TYPE_LABELS, searchRows } from '../data/cadastreApi';
import { DataSourceBanner, useCadastreDocument } from '../data/useCadastre';

// Live, the types are the six the contract defines — not a free-text list.
const LIVE_TYPES = ['All Types', ...Object.values(UNIT_TYPE_LABELS)];
const LIVE_STATUSES = ['All Status', 'draft', 'processing', 'needs_review', 'approved', 'replaced', 'closed'];

export default function SearchPage() {
  const { doc, live, status: loadStatus, error: loadError, reload } = useCadastreDocument();
  const [query, setQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('All Types');
  const [statusFilter, setStatusFilter] = useState('All Status');
  const [results, setResults] = useState([]);
  const [searched, setSearched] = useState(false);

  // The filters name the unit types and statuses this system actually has, not a
  // second vocabulary for when it is offline.
  const filterOptions = LIVE_TYPES;
  const statusFilters = LIVE_STATUSES;

  const handleSearch = () => {
    setSearched(true);
    if (live && doc) {
      // Every unit is searchable, including ones whose identifier is still provisional.
      setResults(searchRows(doc, query).map(r => ({
        ulpin: r.ulpin,
        provisional: r.provisional,
        type: r.type,
        building: r.unitId,
        floor: r.floor ?? '—',
        status: r.status,
        validationState: r.validationState,
        address: r.lower === null || r.upper === null
          ? 'height unknown — recorded as absent, never guessed'
          : `${r.lower} m → ${r.upper} m ${r.datum}`,
      })));
      return;
    }
    // Nothing to search when the sidecar is not answering. An empty result is the
    // honest answer; a filtered list of invented ULPINs is not.
    setResults([]);
  };

  const filtered = results.filter(r => {
    if (typeFilter !== 'All Types' && r.type !== typeFilter) return false;
    if (statusFilter !== 'All Status' && r.status !== statusFilter) return false;
    return true;
  });

  return (
    <div className="search-page">
      <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
        Search ULPIN
      </h2>
      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)', marginBottom: 12 }}>
        Search by ULPIN, parcel number, address, building name, or property type
      </p>
      <div style={{ marginBottom: 16 }}>
        <DataSourceBanner status={loadStatus} error={loadError} onRetry={reload} />
      </div>

      {/* Search Bar */}
      <div className="search-bar">
        <input
          className="form-input"
          type="text"
          placeholder="Enter ULPIN, address, building name, parcel number..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          autoFocus
        />
        <button className="btn btn-primary btn-lg" onClick={handleSearch}>
          <Icons.Search style={{ width: 18, height: 18 }} /> Search
        </button>
      </div>

      {/* Filters */}
      <div className="search-filters">
        {filterOptions.map(f => (
          <button key={f} className={`search-filter-chip ${typeFilter === f ? 'active' : ''}`}
            onClick={() => setTypeFilter(f)}>
            {f}
          </button>
        ))}
        <span style={{ width: 1, height: 20, background: 'var(--border-primary)', margin: '0 4px' }} />
        {statusFilters.map(f => (
          <button key={f} className={`search-filter-chip ${statusFilter === f ? 'active' : ''}`}
            onClick={() => setStatusFilter(f)}>
            {f}
          </button>
        ))}
      </div>

      {/* Results */}
      {searched && (
        <div>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)', marginBottom: 16 }}>
            {filtered.length} results found
          </div>
          <div className="search-results">
            {filtered.map((result, i) => (
              <div className="search-result-card" key={i}>
                <div style={{
                  width: 44, height: 44, borderRadius: 'var(--radius-md)',
                  background: result.status === 'Approved' ? 'var(--status-success-bg)' : 'var(--bg-surface)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                }}>
                  <Icons.Create3D style={{
                    width: 22, height: 22,
                    color: result.status === 'Approved' ? 'var(--status-success)' : 'var(--text-tertiary)'
                  }} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontFamily: 'var(--font-mono)', fontSize: 'var(--text-md)', fontWeight: 700,
                    color: 'var(--accent-primary)', marginBottom: 2
                  }}>
                    {result.ulpin}
                    {result.provisional && (
                      <span style={{ marginLeft: 8, fontFamily: 'var(--font-family)', fontSize: '10px', fontWeight: 400, color: 'var(--text-muted)' }}>
                        provisional
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                    {result.type} · {result.building} · Floor {result.floor}
                  </div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginTop: 2 }}>
                    {result.address}
                  </div>
                </div>
                <span className={`status-badge ${result.status.toLowerCase()}`}>{result.status}</span>
                <button className="btn btn-secondary btn-sm">
                  <Icons.Map2D style={{ width: 14, height: 14 }} /> View on Map
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {!searched && (
        <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
          <Icons.Search style={{ width: 48, height: 48, opacity: 0.2, marginBottom: 16 }} />
          <div style={{ fontSize: 'var(--text-md)' }}>Enter a search query to find properties</div>
          <div style={{ fontSize: 'var(--text-xs)', marginTop: 8 }}>
            Search by ULPIN code, parcel number, building name, address, or floor
          </div>
        </div>
      )}
    </div>
  );
}
