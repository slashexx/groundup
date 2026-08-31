import { useState } from 'react';
import { Icons } from '../components/Icons';

const fileTypes = [
  { ext: 'GeoJSON', desc: 'Land parcel maps', icon: '📐' },
  { ext: 'Shapefile', desc: 'Building footprints', icon: '🏗️' },
  { ext: 'PDF/DXF', desc: 'Floor plans', icon: '📄' },
  { ext: 'JPEG/PNG', desc: 'Drone images', icon: '🛸' },
  { ext: 'LAS/LAZ', desc: 'LiDAR point clouds', icon: '📡' },
  { ext: 'GeoTIFF', desc: 'DEM/DSM elevation', icon: '🏔️' },
];

const mockUploadedFiles = [
  { name: 'ward42_parcels.geojson', size: '2.4 MB', type: 'GeoJSON', status: 'complete', progress: 100,
    validation: { crs: true, height: true, geometry: true, fields: false, accuracy: true },
    errors: 0, warnings: 1, message: 'Missing "owner_name" field in 3 records' },
  { name: 'block_b_drone_ortho.tif', size: '145 MB', type: 'GeoTIFF', status: 'complete', progress: 100,
    validation: { crs: true, height: true, geometry: true, fields: true, accuracy: true },
    errors: 0, warnings: 0, message: 'All checks passed' },
  { name: 'b318_lidar.las', size: '89 MB', type: 'LAS', status: 'processing', progress: 67,
    validation: { crs: true, height: null, geometry: null, fields: null, accuracy: null },
    errors: 0, warnings: 0, message: 'Processing...' },
  { name: 'b320_floorplan_f3.pdf', size: '3.1 MB', type: 'PDF', status: 'complete', progress: 100,
    validation: { crs: false, height: false, geometry: true, fields: true, accuracy: false },
    errors: 2, warnings: 0, message: 'Missing CRS and height reference' },
];

export default function UploadDataPage() {
  const [files, setFiles] = useState(mockUploadedFiles);
  const [dragOver, setDragOver] = useState(false);

  const totalErrors = files.reduce((sum, f) => sum + f.errors, 0);
  const totalWarnings = files.reduce((sum, f) => sum + f.warnings, 0);
  const allComplete = files.filter(f => f.status === 'complete').length;

  return (
    <div className="upload-page">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>Upload Data</h2>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>Upload source data for processing and 3D unit creation</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <span className="status-badge approved">{allComplete} Uploaded</span>
          {totalErrors > 0 && <span className="status-badge error-badge">{totalErrors} Errors</span>}
          {totalWarnings > 0 && <span className="status-badge warning-badge">{totalWarnings} Warnings</span>}
        </div>
      </div>

      {/* Supported formats */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {fileTypes.map(ft => (
          <div key={ft.ext} style={{
            padding: '8px 16px', background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
            borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: 8, fontSize: 'var(--text-xs)'
          }}>
            <span style={{ fontSize: 16 }}>{ft.icon}</span>
            <div>
              <div style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{ft.ext}</div>
              <div style={{ color: 'var(--text-muted)' }}>{ft.desc}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Dropzone */}
      <div
        className={`upload-dropzone${dragOver ? ' drag-over' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); }}
      >
        <div className="upload-dropzone-icon">
          <Icons.Upload style={{ width: 28, height: 28 }} />
        </div>
        <div className="upload-dropzone-title">Drop files here or click to browse</div>
        <div className="upload-dropzone-subtitle">
          Supports GeoJSON, Shapefile, GeoTIFF, LAS/LAZ, DXF, PDF, JPEG/PNG
        </div>
        <button className="btn btn-primary" style={{ marginTop: 8 }}>
          <Icons.Upload style={{ width: 14, height: 14 }} />
          Browse Files
        </button>
      </div>

      {/* Uploaded Files */}
      <div>
        <h3 style={{ fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>
          Uploaded Files ({files.length})
        </h3>
        <div className="upload-file-list">
          {files.map((file, i) => (
            <div className="upload-file-item" key={i}>
              <div className="upload-file-icon">
                <Icons.File style={{ width: 18, height: 18 }} />
              </div>
              <div className="upload-file-info" style={{ flex: 1 }}>
                <div className="upload-file-name">{file.name}</div>
                <div className="upload-file-size">{file.size} · {file.type}</div>
                {file.status === 'processing' && (
                  <div className="upload-progress" style={{ marginTop: 6 }}>
                    <div className="upload-progress-bar" style={{ width: `${file.progress}%` }} />
                  </div>
                )}
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
                {/* Validation checks */}
                {file.validation && Object.entries(file.validation).map(([key, val]) => (
                  <div key={key} title={key} style={{
                    width: 18, height: 18, borderRadius: '50%', fontSize: 9, fontWeight: 700,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: val === true ? 'var(--status-success-bg)' : val === false ? 'var(--status-error-bg)' : 'var(--bg-surface)',
                    color: val === true ? 'var(--status-success)' : val === false ? 'var(--status-error)' : 'var(--text-muted)',
                  }}>
                    {val === true ? '✓' : val === false ? '✗' : '…'}
                  </div>
                ))}
              </div>
              <span className={`status-badge ${file.status === 'complete' ? (file.errors > 0 ? 'error-badge' : 'completed') : 'processing'}`}>
                {file.status === 'complete' ? (file.errors > 0 ? `${file.errors} errors` : 'Ready') : `${file.progress}%`}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Summary */}
      <div style={{
        padding: '16px 24px', background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
        borderRadius: 'var(--radius-lg)', display: 'flex', alignItems: 'center', gap: 16
      }}>
        <Icons.Check style={{ width: 24, height: 24, color: 'var(--status-success)' }} />
        <div>
          <div style={{ fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--text-primary)' }}>
            Upload Summary
          </div>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>
            {allComplete} of {files.length} complete · {totalErrors} errors · {totalWarnings} warnings · {files.filter(f => f.errors === 0 && f.status === 'complete').length} ready for processing
          </div>
        </div>
        <div style={{ flex: 1 }} />
        <button className="btn btn-primary">Process Ready Files</button>
      </div>
    </div>
  );
}
