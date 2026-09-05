import { useState } from 'react';
import { Icons } from '../components/Icons';
import { AI_TOOLS } from '../data/aiTools';

const iconMap = {
  building: Icons.Building,
  height: Icons.Height,
  layers: Icons.Layers,
  scan: Icons.Scan,
  diff: Icons.Diff,
};

// Suggestions come from P3 through the sidecar. Until a detection run has
// happened there are none, and inventing a few with confidence scores attached
// would put a number next to a building nobody detected.

export default function AIToolsPage() {
  const [selectedTool, setSelectedTool] = useState(null);
  const [results, setResults] = useState([]);
  const [runningJob, setRunningJob] = useState(null);

  const handleRun = (tool) => {
    setRunningJob(tool.id);
    setTimeout(() => setRunningJob(null), 2000);
  };

  const handleAccept = (id) => {
    setResults(prev => prev.map(r => r.id === id ? { ...r, status: 'accepted' } : r));
  };

  const handleReject = (id) => {
    setResults(prev => prev.map(r => r.id === id ? { ...r, status: 'rejected' } : r));
  };

  return (
    <div className="ai-page">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
            AI Processing Tools
          </h2>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>
            Automated building extraction, height estimation, and floor segmentation
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>AI results require manual review</span>
        </div>
      </div>

      {/* AI Tool Cards */}
      <div className="ai-tool-grid">
        {AI_TOOLS.map(tool => {
          const ToolIcon = iconMap[tool.icon] || Icons.AI;
          return (
            <div className="ai-tool-card" key={tool.id} onClick={() => setSelectedTool(tool)}>
              <div className="ai-tool-icon">
                <ToolIcon style={{ width: 22, height: 22 }} />
              </div>
              <div className="ai-tool-name">{tool.name}</div>
              <div className="ai-tool-desc">{tool.description}</div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16 }}>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                  Model {tool.modelVersion}
                </span>
                <span className={`status-badge ${tool.status === 'Ready' ? 'approved' : tool.status === 'In Progress' ? 'in-progress' : 'queued'}`}>
                  {tool.status}
                </span>
              </div>
              <div style={{ marginTop: 12 }}>
                <button
                  className="btn btn-primary btn-sm btn-full"
                  onClick={(e) => { e.stopPropagation(); handleRun(tool); }}
                  disabled={runningJob === tool.id}
                >
                  {runningJob === tool.id ? (
                    <>Processing...</>
                  ) : (
                    <><Icons.Play style={{ width: 12, height: 12 }} /> Run Analysis</>
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* AI Results */}
      <div>
        <h3 style={{ fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>
          AI Results — Pending Review ({results.filter(r => r.status === 'pending').length})
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {results.map(result => (
            <div key={result.id} style={{
              padding: '16px 20px', background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
              borderRadius: 'var(--radius-lg)', display: 'flex', gap: 20, alignItems: 'flex-start'
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 'var(--text-md)' }}>
                    {result.tool}
                  </span>
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                    {result.building}
                  </span>
                </div>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)', marginBottom: 8 }}>
                  {result.description}
                </div>
                <div style={{ display: 'flex', gap: 16, fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                  <span>Model: {result.modelVersion}</span>
                  <span>ID: {result.id}</span>
                </div>
              </div>

              {/* Confidence */}
              <div style={{ textAlign: 'center', minWidth: 80 }}>
                <div style={{
                  fontSize: 'var(--text-xl)', fontWeight: 800,
                  color: result.confidence > 90 ? 'var(--status-success)' : result.confidence > 80 ? 'var(--status-warning)' : 'var(--status-error)'
                }}>
                  {result.confidence}%
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Confidence</div>
                <div className="ai-confidence-bar" style={{ marginTop: 6, width: 80 }}>
                  <div className={`ai-confidence-fill ${result.confidence > 90 ? 'high' : result.confidence > 80 ? 'medium' : 'low'}`}
                    style={{ width: `${result.confidence}%` }} />
                </div>
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 100 }}>
                {result.status === 'pending' ? (
                  <>
                    <button className="btn btn-success btn-sm" onClick={() => handleAccept(result.id)}>
                      <Icons.Check style={{ width: 12, height: 12 }} /> Accept
                    </button>
                    <button className="btn btn-secondary btn-sm">
                      <Icons.Pencil style={{ width: 12, height: 12 }} /> Edit
                    </button>
                    <button className="btn btn-danger btn-sm" onClick={() => handleReject(result.id)}>
                      <Icons.Close style={{ width: 12, height: 12 }} /> Reject
                    </button>
                  </>
                ) : (
                  <span className={`status-badge ${result.status === 'accepted' ? 'approved' : 'rejected'}`}>
                    {result.status === 'accepted' ? 'Accepted' : 'Rejected'}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
