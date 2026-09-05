import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Icons } from '../Icons';
import { dashboardCounts } from '../../data/cadastreApi';
import { useCadastreDocument } from '../../data/useCadastre';

const menuItems = [
  { path: '/dashboard', label: 'Dashboard', icon: 'Dashboard' },
  { path: '/map-2d', label: '2D Map', icon: 'Map2D' },
  { path: '/map-3d', label: '3D Map', icon: 'Map3D' },
  { path: '/upload', label: 'Upload Data', icon: 'Upload' },
  { path: '/create-3d', label: 'Create 3D Unit', icon: 'Create3D' },
  { path: '/ai-tools', label: 'AI Tools', icon: 'AI' },
  { path: '/errors', label: 'Check Errors', icon: 'CheckErrors', badge: 7, badgeType: 'error' },
  { path: '/review', label: 'Review Records', icon: 'Review', badge: 12, badgeType: 'warning' },
  // The two badges above are placeholders for the offline case. Live, they are replaced
  // by counts from the project document — a nav badge reading "7 errors" beside a screen
  // showing none is the same lie as a dashboard of invented numbers.
  { path: '/search', label: 'Search ULPIN', icon: 'Search' },
  { path: '/export', label: 'Export Data', icon: 'Export' },
  { path: '/history', label: 'History', icon: 'History' },
  { path: '/settings', label: 'Project Settings', icon: 'Settings' },
];

const toolbarGroups = [
  [
    { id: 'new', label: 'New', icon: 'Plus', action: 'newProject' },
    { id: 'open', label: 'Open', icon: 'FolderOpen', action: 'newProject' },
    // Every write goes straight to the GeoPackage; there is no unsaved state to flush.
    { id: 'save', label: 'Saved', icon: 'Save', inert: 'Changes are written to the project file as they happen' },
  ],
  [
    { id: 'layer-add', label: 'Add Layer', icon: 'Layers', action: 'addLayer' },
    { id: 'layer-style', label: 'Style', icon: 'Pencil', inert: 'Layer styling is not built yet' },
  ],
  [
    { id: 'select', label: 'Select', icon: 'Cursor', action: 'select', toggle: true },
    { id: 'identify', label: 'Identify', icon: 'Crosshair', action: 'identify', toggle: true },
    { id: 'measure', label: 'Measure', icon: 'Ruler', inert: 'Measuring is not built yet' },
    { id: 'draw', label: 'Draw', icon: 'Pencil', inert: 'Drawing is not built yet' },
  ],
  [
    { id: 'zoom-in', label: 'Zoom In', icon: 'ZoomIn', emit: 'map-zoom-in' },
    { id: 'zoom-out', label: 'Zoom Out', icon: 'ZoomOut', emit: 'map-zoom-out' },
    { id: 'pan', label: 'Pan', icon: 'Move', action: 'pan', toggle: true },
    { id: 'extent', label: 'Full Extent', icon: 'Maximize', emit: 'map-fit-project' },
  ],
  [
    { id: 'view-2d', label: '2D View', icon: 'Map2D', action: 'view2d', nav: '/map-2d' },
    { id: 'view-3d', label: '3D View', icon: 'Map3D', action: 'view3d', nav: '/map-3d' },
    { id: 'split', label: 'Split View', icon: 'SplitView', inert: 'Side-by-side 2D and 3D is not built yet' },
  ],
  [
    { id: 'upload', label: 'Upload', icon: 'Upload', action: 'upload', nav: '/upload' },
    { id: 'create', label: 'Create 3D', icon: 'Create3D', action: 'create3d', nav: '/create-3d' },
    { id: 'run-ai', label: 'Run AI', icon: 'AI', action: 'runAI', nav: '/ai-tools' },
  ],
  [
    { id: 'check', label: 'Errors', icon: 'CheckErrors', action: 'checkErrors', nav: '/errors' },
    { id: 'export', label: 'Export', icon: 'Export', action: 'export', nav: '/export' },
  ],
];

const menuBarItems = ['Home', 'View', 'Tools', 'Analysis', 'AI Tools', 'Validation', 'Help'];

export default function AppShell({ children, project, user, onChangeProject }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [activeTool, setActiveTool] = useState('select');
  const [searchQuery, setSearchQuery] = useState('');
  const { doc, live } = useCadastreDocument();

  const counts = live && doc ? dashboardCounts(doc) : null;
  const navItems = counts
    ? menuItems.map(item =>
      item.path === '/errors' ? { ...item, badge: counts.errors || null }
        : item.path === '/review' ? { ...item, badge: counts.needsReview || null }
          : item)
    : menuItems;

  const handleToolbarClick = (tool) => {
    if (tool.nav) {
      navigate(tool.nav);
    } else if (tool.toggle) {
      setActiveTool(tool.id);
    } else if (tool.emit) {
      // The map owns its own camera; the toolbar only asks.
      window.dispatchEvent(new Event(tool.emit));
    } else if (tool.action === 'addLayer') {
      window.dispatchEvent(new Event('toggle-layers'));
    } else if (tool.action === 'newProject') {
      onChangeProject?.();
    }
  };

  const currentTime = new Date().toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: true
  });

  return (
    <div className="app-shell">
      {/* Title Bar */}
      <div className="titlebar">
        <div className="titlebar-brand">
          <Icons.Logo style={{ width: 20, height: 20, color: '#00d4aa' }} />
          <span>3D ULPIN</span>
          <span style={{ color: 'var(--text-tertiary)', fontWeight: 400, fontSize: 'var(--text-xs)' }}>– Vertical Property Mapping System</span>
        </div>

        <div className="titlebar-project">
          <span>Project:</span>
          <span className="titlebar-project-name">{project.name}</span>
          <span className="status-badge active" style={{ marginLeft: 4 }}>Active</span>
          <button 
            onClick={onChangeProject}
            style={{ 
              marginLeft: 8, 
              background: 'var(--bg-hover)', 
              border: '1px solid var(--border-primary)', 
              color: 'var(--text-secondary)', 
              borderRadius: 'var(--radius-sm)',
              padding: '2px 8px',
              fontSize: '10px',
              cursor: 'pointer'
            }}
            onMouseOver={(e) => { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.borderColor = 'var(--accent-primary)'; }}
            onMouseOut={(e) => { e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.borderColor = 'var(--border-primary)'; }}
          >
            Switch
          </button>
        </div>

        <div className="titlebar-spacer" />

        <div className="titlebar-search">
          <Icons.Search className="titlebar-search-icon" />
          <input
            type="text"
            placeholder="Search ULPIN / Parcel / Address..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') navigate('/search'); }}
          />
        </div>

        <div className="titlebar-actions">
          <button className="titlebar-btn" disabled
                  title="Notifications are not built yet">
            <Icons.Bell style={{ width: 16, height: 16 }} />
          </button>
          <button className="titlebar-btn" title="Settings" onClick={() => navigate('/settings')}>
            <Icons.Settings style={{ width: 16, height: 16 }} />
          </button>
        </div>

        <div className="user-info">
          <div className="user-avatar">{user.initials}</div>
          <div className="user-info-text">
            <span className="user-info-name">{user.name}</span>
            <span className="user-info-role">{user.role}</span>
          </div>
        </div>
      </div>

      {/* Menu Bar */}
      <div className="menubar">
        {menuBarItems.map((item) => (
          <div key={item} className="menubar-item" title={`${item} menu is not built yet`}>
            {item}
          </div>
        ))}
      </div>

      {/* Toolbar */}
      <div className="toolbar">
        {toolbarGroups.map((group, gi) => (
          <div className="toolbar-group" key={gi}>
            {group.map((tool) => {
              const IconComponent = Icons[tool.icon];
              return (
                <button
                  key={tool.id}
                  className={`toolbar-btn${activeTool === tool.id ? ' active' : ''}`}
                  title={tool.inert ?? tool.label}
                  disabled={Boolean(tool.inert)}
                  onClick={() => handleToolbarClick(tool)}
                >
                  {IconComponent && <IconComponent />}
                  <span>{tool.label}</span>
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {/* Main Layout */}
      <div className="main-layout">
        {/* Sidebar */}
        <div className="sidebar">
          <div className="sidebar-header">
            <span className="sidebar-header-label">Menu</span>
          </div>
          <nav className="sidebar-nav">
            {navItems.map((item) => {
              const IconComponent = Icons[item.icon];
              const isActive = location.pathname === item.path;
              return (
                <div
                  key={item.path}
                  className={`sidebar-item${isActive ? ' active' : ''}`}
                  onClick={() => navigate(item.path)}
                >
                  {IconComponent && <IconComponent />}
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className={`badge ${item.badgeType}`}>{item.badge}</span>
                  )}
                </div>
              );
            })}
          </nav>
          <div className="sidebar-footer">
            <div className="sidebar-footer-row">
              <span className="sidebar-footer-label">Project:</span>
              <span>{project.name}</span>
            </div>
            <div className="sidebar-footer-row">
              <span className="sidebar-footer-label">CRS:</span>
              <span>{project.project_crs ?? project.crs ?? '—'}</span>
            </div>
            <div className="sidebar-footer-row">
              <span className="sidebar-footer-label">Vertical Datum:</span>
              <span>{project.vertical_datum ?? project.verticalDatum ?? '—'}</span>
            </div>
            <div className="sidebar-footer-row">
              <span className="sidebar-footer-label">Area:</span>
              <span>{project.area_of_interest ?? project.area ?? '—'}</span>
            </div>
            <div className="sidebar-footer-row">
              <span className="sidebar-footer-label">Created On:</span>
              <span>{project.created_on ?? project.createdOn ?? '—'}</span>
            </div>
            <div className="sidebar-footer-row">
              <span className="sidebar-footer-label">File:</span>
              <span style={{ fontSize: '10px' }}>
                {project.db_path ?? project.lastModified ?? '—'}
              </span>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="content-area">
          {children}
        </div>
      </div>

      {/* Status Bar */}
      <div className="statusbar">
        <div className="statusbar-left">
          <div className="statusbar-item">
            <span>Version 1.0.0</span>
          </div>
          <div className="statusbar-item">
            <span className="statusbar-dot" />
            <span>Connected</span>
          </div>
        </div>
        <div className="statusbar-right">
          <div className="statusbar-item">
            <span>Lat: 12.9716°</span>
          </div>
          <div className="statusbar-item">
            <span>Lon: 77.5946°</span>
          </div>
          <div className="statusbar-item">
            <span>Elev: 920.45 m</span>
          </div>
          <div className="statusbar-item">
            <span>Scale 1:2,500</span>
          </div>
          <div className="statusbar-item">
            <Icons.Network style={{ width: 12, height: 12 }} />
            <span>Network</span>
          </div>
          <div className="statusbar-item">
            <span>{currentTime}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
