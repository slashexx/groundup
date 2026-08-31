import { useState } from 'react';
import { Icons } from '../components/Icons';

const unitTypes = ['Apartment', 'Commercial', 'Office', 'Parking', 'Storage', 'Industrial', 'Mixed Use'];
const sources = ['Existing Map Data', 'Floor Plan', 'LiDAR / 3D Points', 'AI Suggestion', 'Manual Drawing'];

export default function Create3DUnitPage() {
  const [step, setStep] = useState(1);
  const [unitType, setUnitType] = useState('Apartment');
  const [source, setSource] = useState('');
  const [bottomHeight, setBottomHeight] = useState('12.00');
  const [topHeight, setTopHeight] = useState('15.20');
  const [parentBuilding, setParentBuilding] = useState('BLR-042-B318');
  const [parentParcel, setParentParcel] = useState('PAR-042-184');

  const steps = [
    { num: 1, label: 'Select Source' },
    { num: 2, label: 'Define Geometry' },
    { num: 3, label: 'Set Attributes' },
    { num: 4, label: 'Generate ULPIN' },
  ];

  const generatedULPIN = '29-BLR-042-B318-F09';

  return (
    <div className="create-unit-page">
      <div className="create-unit-wizard">
        <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
          Create 3D Property Unit
        </h2>
        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)', marginBottom: 24 }}>
          Define a new vertical property unit with spatial boundaries
        </p>

        {/* Wizard Steps */}
        <div className="wizard-steps">
          {steps.map((s, i) => (
            <div key={s.num} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div className={`wizard-step ${step === s.num ? 'active' : step > s.num ? 'completed' : ''}`}>
                <div className="wizard-step-number">
                  {step > s.num ? '✓' : s.num}
                </div>
                <span>{s.label}</span>
              </div>
              {i < steps.length - 1 && <div className="wizard-step-connector" />}
            </div>
          ))}
        </div>

        {/* Wizard Content */}
        <div className="wizard-content">
          {step === 1 && (
            <div>
              <h3 style={{ fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>
                Select Data Source
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {sources.map(s => (
                  <div key={s} onClick={() => setSource(s)}
                    style={{
                      padding: '12px 16px', background: source === s ? 'var(--accent-primary-dim)' : 'var(--bg-surface)',
                      border: `1px solid ${source === s ? 'var(--accent-primary)' : 'var(--border-primary)'}`,
                      borderRadius: 'var(--radius-md)', cursor: 'pointer', transition: 'all 0.15s',
                      display: 'flex', alignItems: 'center', gap: 12
                    }}>
                    <div style={{
                      width: 16, height: 16, borderRadius: '50%',
                      border: `2px solid ${source === s ? 'var(--accent-primary)' : 'var(--border-secondary)'}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center'
                    }}>
                      {source === s && <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-primary)' }} />}
                    </div>
                    <span style={{ color: source === s ? 'var(--accent-primary)' : 'var(--text-secondary)', fontSize: 'var(--text-sm)', fontWeight: 500 }}>
                      {s}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <h3 style={{ fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>
                Define Geometry
              </h3>
              <div className="login-form">
                <div className="form-group">
                  <label className="form-label">Bottom Height (m MSL)</label>
                  <input className="form-input" type="number" step="0.01" value={bottomHeight}
                    onChange={(e) => setBottomHeight(e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label">Top Height (m MSL)</label>
                  <input className="form-input" type="number" step="0.01" value={topHeight}
                    onChange={(e) => setTopHeight(e.target.value)} />
                </div>
                <div style={{ padding: '12px 16px', background: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', fontSize: 'var(--text-sm)' }}>
                  <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>Calculated Volume</div>
                  <div style={{ color: 'var(--text-primary)', fontWeight: 700, fontSize: 'var(--text-lg)' }}>
                    {((topHeight - bottomHeight) * 55.73).toFixed(2)} m³
                  </div>
                </div>
                <div style={{ padding: 12, background: 'var(--status-info-bg)', borderRadius: 'var(--radius-md)', fontSize: 'var(--text-xs)', color: 'var(--status-info)' }}>
                  ℹ️ Draw or select the footprint boundary on the map, or use AI-detected geometry
                </div>
              </div>
            </div>
          )}

          {step === 3 && (
            <div>
              <h3 style={{ fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>
                Set Attributes
              </h3>
              <div className="login-form">
                <div className="form-group">
                  <label className="form-label">Unit Type</label>
                  <select className="form-select" value={unitType} onChange={(e) => setUnitType(e.target.value)}>
                    {unitTypes.map(t => <option key={t}>{t}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Parent Building</label>
                  <input className="form-input" value={parentBuilding} onChange={(e) => setParentBuilding(e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label">Parent Parcel</label>
                  <input className="form-input" value={parentParcel} onChange={(e) => setParentParcel(e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label">Related Units</label>
                  <input className="form-input" placeholder="Search or add related units..." />
                </div>
              </div>
            </div>
          )}

          {step === 4 && (
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <div style={{
                width: 64, height: 64, borderRadius: '50%', background: 'var(--status-success-bg)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px'
              }}>
                <Icons.Check style={{ width: 32, height: 32, color: 'var(--status-success)' }} />
              </div>
              <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
                Temporary ULPIN Generated
              </h3>
              <div style={{
                padding: '12px 24px', background: 'var(--bg-surface)', borderRadius: 'var(--radius-lg)',
                display: 'inline-block', margin: '12px 0', fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--accent-primary)',
                border: '1px solid var(--border-accent)'
              }}>
                {generatedULPIN}
              </div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)', marginTop: 8 }}>
                Status: <span className="status-badge draft">Draft</span>
              </div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginTop: 16 }}>
                This unit requires review and approval before it becomes an official record.
              </div>
            </div>
          )}

          {/* Navigation */}
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 24, paddingTop: 16, borderTop: '1px solid var(--border-primary)' }}>
            <button className="btn btn-ghost" onClick={() => setStep(Math.max(1, step - 1))} disabled={step === 1}>
              <Icons.ArrowLeft style={{ width: 14, height: 14 }} /> Back
            </button>
            {step < 4 ? (
              <button className="btn btn-primary" onClick={() => setStep(step + 1)}
                disabled={step === 1 && !source}>
                Next <Icons.ArrowRight style={{ width: 14, height: 14 }} />
              </button>
            ) : (
              <button className="btn btn-success" onClick={() => setStep(1)}>
                <Icons.Plus style={{ width: 14, height: 14 }} /> Create Another
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Preview */}
      <div className="create-unit-preview">
        <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
          <Icons.Create3D style={{ width: 48, height: 48, opacity: 0.3, marginBottom: 12 }} />
          <div style={{ fontSize: 'var(--text-sm)' }}>3D Preview</div>
          <div style={{ fontSize: 'var(--text-xs)', marginTop: 4 }}>
            Unit geometry will appear here
          </div>
          {step >= 2 && (
            <div style={{ marginTop: 24, padding: 16 }}>
              <svg viewBox="0 0 200 200" width="200" height="200">
                {/* Simple 3D box preview */}
                <polygon points="40,140 100,170 160,140 100,110" fill="rgba(0,212,170,0.1)" stroke="rgba(0,212,170,0.4)" strokeWidth="1" />
                <polygon points="40,140 40,80 100,50 100,110" fill="rgba(0,212,170,0.08)" stroke="rgba(0,212,170,0.3)" strokeWidth="1" />
                <polygon points="100,110 100,50 160,80 160,140" fill="rgba(0,212,170,0.15)" stroke="rgba(0,212,170,0.4)" strokeWidth="1" />
                <text x="100" y="95" fill="rgba(0,212,170,0.6)" fontSize="10" textAnchor="middle" fontWeight="600">
                  {topHeight - bottomHeight}m
                </text>
                <text x="100" y="185" fill="rgba(255,255,255,0.3)" fontSize="8" textAnchor="middle">
                  {bottomHeight}m — {topHeight}m MSL
                </text>
              </svg>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
