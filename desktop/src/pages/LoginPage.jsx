import { useState } from 'react';
import { Icons } from '../components/Icons';

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('GIS Operator');
  const [remember, setRemember] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      onLogin(role);
    }, 800);
  };

  return (
    <div className="login-page">
      <div className="login-left">
        <div className="login-card">
          <div className="login-logo">
            <div className="login-logo-icon">
              <Icons.Logo style={{ width: 28, height: 28, color: '#0a0e1a' }} />
            </div>
            <div className="login-logo-text">
              <span className="login-logo-title">3D ULPIN System</span>
              <span className="login-logo-subtitle">Vertical Property Mapping</span>
            </div>
          </div>

          <form className="login-form" onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label" htmlFor="login-username">Username</label>
              <input
                id="login-username"
                className="form-input"
                type="text"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="login-password">Password</label>
              <input
                id="login-password"
                className="form-input"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="login-role">Role</label>
              <select
                id="login-role"
                className="form-select"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option>Administrator</option>
                <option>GIS Operator</option>
                <option>Surveyor</option>
                <option>Reviewer</option>
                <option>Planner</option>
                <option>Utility Team</option>
                <option>Read-Only</option>
              </select>
            </div>

            <div className="form-checkbox-row">
              <input
                id="login-remember"
                type="checkbox"
                className="form-checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
              />
              <label htmlFor="login-remember" className="form-label" style={{ cursor: 'pointer' }}>
                Remember me
              </label>
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-lg btn-full"
              disabled={loading}
              style={{ marginTop: 8 }}
            >
              {loading ? (
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="spinner" />
                  Signing in...
                </span>
              ) : (
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Icons.Lock style={{ width: 16, height: 16 }} />
                  Sign In
                </span>
              )}
            </button>
          </form>

          <div style={{ marginTop: 24, textAlign: 'center' }}>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
              Government of India — Land Records Modernization
            </span>
          </div>
        </div>
      </div>

      <div className="login-right">
        <div className="login-illustration">
          {/* Animated 3D grid visualization */}
          <svg viewBox="0 0 500 500" style={{ width: '80%', height: '80%', opacity: 0.7 }}>
            {/* Ground grid */}
            {Array.from({ length: 11 }).map((_, i) => (
              <line key={`gh${i}`} x1={50 + i * 40} y1={300} x2={100 + i * 40} y2={400}
                stroke="rgba(0,212,170,0.15)" strokeWidth="0.5" />
            ))}
            {Array.from({ length: 11 }).map((_, i) => (
              <line key={`gv${i}`} x1={50} y1={300 + i * 10} x2={450} y2={300 + i * 10}
                stroke="rgba(14,165,233,0.1)" strokeWidth="0.5"
                transform={`translate(${i * 5}, ${i * 10})`} />
            ))}

            {/* Building 1 */}
            <g style={{ animation: 'fadeIn 1s ease 0.2s both' }}>
              <rect x="120" y="140" width="80" height="160" fill="rgba(0,212,170,0.08)" stroke="rgba(0,212,170,0.3)" strokeWidth="1" rx="2" />
              {[0, 1, 2, 3, 4].map((f) => (
                <g key={f}>
                  <line x1="120" y1={140 + f * 32} x2="200" y2={140 + f * 32} stroke="rgba(0,212,170,0.2)" strokeWidth="0.5" />
                  <rect x="130" y={145 + f * 32} width="12" height="18" fill="rgba(14,165,233,0.15)" rx="1" />
                  <rect x="150" y={145 + f * 32} width="12" height="18" fill="rgba(14,165,233,0.15)" rx="1" />
                  <rect x="170" y={145 + f * 32} width="12" height="18" fill="rgba(14,165,233,0.15)" rx="1" />
                </g>
              ))}
            </g>

            {/* Building 2 */}
            <g style={{ animation: 'fadeIn 1s ease 0.5s both' }}>
              <rect x="240" y="100" width="100" height="200" fill="rgba(14,165,233,0.06)" stroke="rgba(14,165,233,0.25)" strokeWidth="1" rx="2" />
              {[0, 1, 2, 3, 4, 5].map((f) => (
                <g key={f}>
                  <line x1="240" y1={100 + f * 33} x2="340" y2={100 + f * 33} stroke="rgba(14,165,233,0.15)" strokeWidth="0.5" />
                  <rect x="252" y={106 + f * 33} width="14" height="18" fill="rgba(0,212,170,0.1)" rx="1" />
                  <rect x="274" y={106 + f * 33} width="14" height="18" fill="rgba(0,212,170,0.1)" rx="1" />
                  <rect x="296" y={106 + f * 33} width="14" height="18" fill="rgba(0,212,170,0.1)" rx="1" />
                  <rect x="318" y={106 + f * 33} width="14" height="18" fill="rgba(0,212,170,0.1)" rx="1" />
                </g>
              ))}
            </g>

            {/* Building 3 */}
            <g style={{ animation: 'fadeIn 1s ease 0.8s both' }}>
              <rect x="380" y="180" width="60" height="120" fill="rgba(139,92,246,0.06)" stroke="rgba(139,92,246,0.25)" strokeWidth="1" rx="2" />
              {[0, 1, 2].map((f) => (
                <g key={f}>
                  <line x1="380" y1={180 + f * 40} x2="440" y2={180 + f * 40} stroke="rgba(139,92,246,0.15)" strokeWidth="0.5" />
                  <rect x="390" y={188 + f * 40} width="12" height="20" fill="rgba(139,92,246,0.12)" rx="1" />
                  <rect x="410" y={188 + f * 40} width="12" height="20" fill="rgba(139,92,246,0.12)" rx="1" />
                </g>
              ))}
            </g>

            {/* Underground */}
            <g style={{ animation: 'fadeIn 1s ease 1.1s both' }}>
              <line x1="80" y1="340" x2="460" y2="340" stroke="rgba(245,158,11,0.3)" strokeWidth="1" strokeDasharray="4 4" />
              <rect x="140" y="345" width="60" height="25" fill="rgba(245,158,11,0.06)" stroke="rgba(245,158,11,0.2)" strokeWidth="0.5" rx="2" />
              <rect x="260" y="350" width="80" height="20" fill="rgba(245,158,11,0.06)" stroke="rgba(245,158,11,0.2)" strokeWidth="0.5" rx="2" />
              <text x="170" y="361" fill="rgba(245,158,11,0.4)" fontSize="8" textAnchor="middle">PIPE</text>
              <text x="300" y="364" fill="rgba(245,158,11,0.4)" fontSize="8" textAnchor="middle">TUNNEL</text>
            </g>

            {/* Labels */}
            <text x="160" y="128" fill="rgba(0,212,170,0.5)" fontSize="10" textAnchor="middle" fontWeight="600">B318</text>
            <text x="290" y="88" fill="rgba(14,165,233,0.5)" fontSize="10" textAnchor="middle" fontWeight="600">B320</text>
            <text x="410" y="170" fill="rgba(139,92,246,0.5)" fontSize="10" textAnchor="middle" fontWeight="600">B315</text>

            {/* Title */}
            <text x="250" y="440" fill="rgba(255,255,255,0.15)" fontSize="14" textAnchor="middle" fontWeight="700" letterSpacing="4">
              3D CADASTRAL FRAMEWORK
            </text>
            <text x="250" y="460" fill="rgba(255,255,255,0.08)" fontSize="10" textAnchor="middle" letterSpacing="2">
              VERTICAL PROPERTY MAPPING
            </text>
          </svg>
        </div>
      </div>
    </div>
  );
}
