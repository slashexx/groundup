import { useState } from 'react';
import { Icons } from '../components/Icons';

export default function ProjectSelectPage({ projects, user, onSelectProject, onLogout }) {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProject, setNewProject] = useState({ name: '', location: '', crs: 'EPSG:4326 - WGS 84' });

  const handleCreate = () => {
    const created = {
      id: `proj-${Date.now()}`,
      name: newProject.name || 'New Project',
      location: newProject.location || 'India',
      crs: newProject.crs,
      verticalDatum: 'MSL',
      area: '0 km²',
      parcels: 0,
      buildings: 0,
      units3d: 0,
      lastModified: new Date().toLocaleString(),
      createdOn: new Date().toLocaleDateString(),
      status: 'draft'
    };
    setShowCreateModal(false);
    onSelectProject(created);
  };

  return (
    <div className="project-select-page">
      <div className="project-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
            <Icons.Logo style={{ width: 28, height: 28, color: '#00d4aa' }} />
            <h1 className="project-header-title">3D ULPIN — Select Project</h1>
          </div>
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>
            Welcome back, {user.name} · {user.role}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn btn-secondary" onClick={onLogout}>
            <Icons.Logout style={{ width: 14, height: 14 }} />
            Sign Out
          </button>
        </div>
      </div>

      <div className="project-grid">
        {/* Create New Project Card */}
        <div className="project-card project-card-new" onClick={() => setShowCreateModal(true)}>
          <Icons.Plus style={{ width: 40, height: 40 }} />
          <span style={{ fontSize: 'var(--text-md)', fontWeight: 600 }}>Create New Project</span>
          <span style={{ fontSize: 'var(--text-xs)' }}>Ward, village, city block, or area</span>
        </div>

        {/* Project Cards */}
        {projects.map((project) => (
          <div key={project.id} className="project-card" onClick={() => onSelectProject(project)}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div className="project-card-name">{project.name}</div>
                <div className="project-card-location">{project.location}</div>
              </div>
              <span className={`status-badge ${project.status === 'active' ? 'approved' : 'draft'}`}>
                {project.status === 'active' ? 'Active' : 'Draft'}
              </span>
            </div>

            <div className="project-card-stats">
              <div className="project-card-stat">
                <span className="project-card-stat-value">{project.parcels.toLocaleString()}</span>
                <span className="project-card-stat-label">Land Parcels</span>
              </div>
              <div className="project-card-stat">
                <span className="project-card-stat-value">{project.buildings.toLocaleString()}</span>
                <span className="project-card-stat-label">Buildings</span>
              </div>
              <div className="project-card-stat">
                <span className="project-card-stat-value">{project.units3d.toLocaleString()}</span>
                <span className="project-card-stat-label">3D Units</span>
              </div>
              <div className="project-card-stat">
                <span className="project-card-stat-value">{project.area}</span>
                <span className="project-card-stat-label">Area</span>
              </div>
            </div>

            <div className="project-card-footer">
              <span className="project-card-date">Last modified: {project.lastModified}</span>
              <Icons.ChevronRight style={{ width: 16, height: 16, color: 'var(--text-muted)' }} />
            </div>
          </div>
        ))}
      </div>

      {/* Create Project Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">Create New Project</span>
              <button className="context-panel-close" onClick={() => setShowCreateModal(false)}>
                <Icons.Close style={{ width: 16, height: 16 }} />
              </button>
            </div>
            <div className="modal-body">
              <div className="login-form">
                <div className="form-group">
                  <label className="form-label" htmlFor="proj-name">Project Name</label>
                  <input id="proj-name" className="form-input" type="text" placeholder="e.g. Bengaluru Ward 42"
                    value={newProject.name} onChange={(e) => setNewProject({ ...newProject, name: e.target.value })} autoFocus />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="proj-location">Location</label>
                  <input id="proj-location" className="form-input" type="text" placeholder="e.g. Bengaluru, Karnataka"
                    value={newProject.location} onChange={(e) => setNewProject({ ...newProject, location: e.target.value })} />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="proj-crs">Coordinate Reference System</label>
                  <select id="proj-crs" className="form-select" value={newProject.crs}
                    onChange={(e) => setNewProject({ ...newProject, crs: e.target.value })}>
                    <option>EPSG:4326 - WGS 84</option>
                    <option>EPSG:32643 - UTM Zone 43N</option>
                    <option>EPSG:32644 - UTM Zone 44N</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="proj-datum">Vertical Datum</label>
                  <select id="proj-datum" className="form-select">
                    <option>MSL (Mean Sea Level)</option>
                    <option>EGM96</option>
                    <option>EGM2008</option>
                  </select>
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowCreateModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleCreate}>
                <Icons.Plus style={{ width: 14, height: 14 }} />
                Create Project
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
