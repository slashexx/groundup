import { useState } from 'react';
import { Icons } from '../components/Icons';

export default function SettingsPage({ project }) {
  const [projectName, setProjectName] = useState(project?.name || '');
  const [crs, setCrs] = useState(project?.crs || 'EPSG:4326 - WGS 84');
  const [datum, setDatum] = useState(project?.verticalDatum || 'MSL');
  const [ulpinPrefix, setUlpinPrefix] = useState('29-BLR-042');
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  // One operator, no sign-in, no user directory. Five named officials with
  // government email addresses were listed here, none of whom exist. Multi-user
  // access is FR-11 and needs a real identity store behind it.
  const users = [];

  return (
    <div className="settings-page">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 32 }}>
        <div>
          <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
            Project Settings
          </h2>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>
            Configure project parameters, ULPIN format, and user management
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {saved && (
            <span style={{ color: 'var(--status-success)', fontSize: 'var(--text-sm)', display: 'flex', alignItems: 'center', gap: 4 }}>
              <Icons.Check style={{ width: 14, height: 14 }} /> Saved
            </span>
          )}
          <button className="btn btn-primary" onClick={handleSave}>
            <Icons.Save style={{ width: 14, height: 14 }} /> Save Changes
          </button>
        </div>
      </div>

      {/* Project Info */}
      <div className="settings-section">
        <div className="settings-section-title">Project Information</div>
        <div className="settings-row">
          <div className="settings-row-label">
            <div className="settings-row-title">Project Name</div>
            <div className="settings-row-desc">Display name for the project</div>
          </div>
          <div className="settings-row-value">
            <input className="form-input" style={{ width: '100%' }} value={projectName}
              onChange={(e) => setProjectName(e.target.value)} />
          </div>
        </div>
        <div className="settings-row">
          <div className="settings-row-label">
            <div className="settings-row-title">Coordinate Reference System</div>
            <div className="settings-row-desc">Horizontal spatial reference</div>
          </div>
          <div className="settings-row-value">
            <select className="form-select" style={{ width: '100%' }} value={crs} onChange={(e) => setCrs(e.target.value)}>
              <option>EPSG:4326 - WGS 84</option>
              <option>EPSG:32643 - UTM Zone 43N</option>
              <option>EPSG:32644 - UTM Zone 44N</option>
            </select>
          </div>
        </div>
        <div className="settings-row">
          <div className="settings-row-label">
            <div className="settings-row-title">Vertical Datum</div>
            <div className="settings-row-desc">Height reference system</div>
          </div>
          <div className="settings-row-value">
            <select className="form-select" style={{ width: '100%' }} value={datum} onChange={(e) => setDatum(e.target.value)}>
              <option value="MSL">MSL (Mean Sea Level)</option>
              <option value="EGM96">EGM96</option>
              <option value="EGM2008">EGM2008</option>
            </select>
          </div>
        </div>
      </div>

      {/* ULPIN Configuration */}
      <div className="settings-section">
        <div className="settings-section-title">ULPIN Configuration</div>
        <div className="settings-row">
          <div className="settings-row-label">
            <div className="settings-row-title">ULPIN Prefix</div>
            <div className="settings-row-desc">State-City-Ward format prefix</div>
          </div>
          <div className="settings-row-value">
            <input className="form-input" style={{ width: '100%', fontFamily: 'var(--font-mono)' }}
              value={ulpinPrefix} onChange={(e) => setUlpinPrefix(e.target.value)} />
          </div>
        </div>
        <div className="settings-row">
          <div className="settings-row-label">
            <div className="settings-row-title">Format Pattern</div>
            <div className="settings-row-desc">ULPIN numbering scheme</div>
          </div>
          <div className="settings-row-value">
            <div style={{
              padding: '8px 12px', background: 'var(--bg-surface)', borderRadius: 'var(--radius-md)',
              fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)', color: 'var(--accent-primary)'
            }}>
              {ulpinPrefix}-[Building]-[Floor/Unit]
            </div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginTop: 4 }}>
              Example: {ulpinPrefix}-B318-F04
            </div>
          </div>
        </div>
      </div>

      {/* User Management */}
      <div className="settings-section">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, paddingBottom: 8, borderBottom: '1px solid var(--border-primary)' }}>
          <span style={{ fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--text-primary)' }}>User Management</span>
          <button className="btn btn-secondary btn-sm">
            <Icons.Plus style={{ width: 12, height: 12 }} /> Add User
          </button>
        </div>
        <div className="data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Email</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user, i) => (
                <tr key={i}>
                  <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div className="user-avatar" style={{ width: 24, height: 24, fontSize: '9px' }}>
                        {user.name.split(' ').map(n => n[0]).join('')}
                      </div>
                      {user.name}
                    </div>
                  </td>
                  <td><span className="property-tag">{user.role}</span></td>
                  <td>{user.email}</td>
                  <td>
                    <span className={`status-badge ${user.status === 'Active' ? 'approved' : 'draft'}`}>
                      {user.status}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button className="btn btn-ghost btn-sm"><Icons.Pencil style={{ width: 12, height: 12 }} /></button>
                      <button className="btn btn-ghost btn-sm"><Icons.Close style={{ width: 12, height: 12 }} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Data Sources */}
      <div className="settings-section">
        <div className="settings-section-title">Data Source Configuration</div>
        <div className="settings-row">
          <div className="settings-row-label">
            <div className="settings-row-title">Map Tile Server</div>
            <div className="settings-row-desc">Base map tile source URL</div>
          </div>
          <div className="settings-row-value">
            <input className="form-input" style={{ width: '100%', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)' }}
              defaultValue="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png" />
          </div>
        </div>
        <div className="settings-row">
          <div className="settings-row-label">
            <div className="settings-row-title">AI Model Endpoint</div>
            <div className="settings-row-desc">URL for AI/ML processing service</div>
          </div>
          <div className="settings-row-value">
            <input className="form-input" style={{ width: '100%', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)' }}
              defaultValue="https://ai.ulpin.gov.in/api/v3" />
          </div>
        </div>
      </div>
    </div>
  );
}
