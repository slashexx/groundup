import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, Polygon, Popup, Marker, useMap } from 'react-leaflet';
import L from 'leaflet';
import { Icons } from '../components/Icons';
import { MAP_LAYERS } from '../data/layers';
import { useCadastreDocument } from '../data/useCadastre';
// P5 owns the projected-CRS-to-WGS84 conversion. Importing it rather than copying it
// keeps one implementation: the desktop app and the published web build have to agree
// on where a building is, exactly, and two copies of that maths would drift.
import { fromP4Document } from '../../../viewer/src/lib/adapter';

/** Units from the live document, split for the two Leaflet layers. */
function useProjectGeometry() {
  const { doc } = useCadastreDocument();
  return useMemo(() => {
    if (!doc) return { parcels: [], buildings: [], bounds: null };

    const units = fromP4Document(doc);
    // Leaflet wants [lat, lng]; the adapter returns GeoJSON order.
    const latlng = (u) => u.ring.map(([lon, lat]) => [lat, lon]);

    const parcels = units.filter((u) => u.unit_type === 'land_parcel');
    const buildings = units.filter((u) => u.unit_type === 'building');

    let bounds = null;
    for (const u of units) {
      for (const [lon, lat] of u.ring) {
        bounds = bounds
          ? [[Math.min(bounds[0][0], lat), Math.min(bounds[0][1], lon)],
             [Math.max(bounds[1][0], lat), Math.max(bounds[1][1], lon)]]
          : [[lat, lon], [lat, lon]];
      }
    }
    return {
      parcels: parcels.map((u) => ({ unit: u, positions: latlng(u) })),
      buildings: buildings.map((u) => ({ unit: u, positions: latlng(u) })),
      bounds,
    };
  }, [doc]);
}

/** Frame the project once its geometry arrives, and answer the toolbar. */
function FitToProject({ bounds }) {
  const map = useMap();
  useEffect(() => {
    if (bounds) map.fitBounds(bounds, { padding: [40, 40] });
  }, [bounds, map]);

  // The toolbar owns no map instance, so it asks by event and this answers.
  useEffect(() => {
    const zoomIn = () => map.zoomIn();
    const zoomOut = () => map.zoomOut();
    const fit = () => bounds && map.fitBounds(bounds, { padding: [40, 40] });
    window.addEventListener('map-zoom-in', zoomIn);
    window.addEventListener('map-zoom-out', zoomOut);
    window.addEventListener('map-fit-project', fit);
    return () => {
      window.removeEventListener('map-zoom-in', zoomIn);
      window.removeEventListener('map-zoom-out', zoomOut);
      window.removeEventListener('map-fit-project', fit);
    };
  }, [map, bounds]);
  return null;
}

/* Fix default Leaflet icon path issue */
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

/* Generate polygon coordinates around a center point */
function generateParcelPolygon(center, size = 0.001) {
  const [lat, lng] = center;
  const half = size / 2;
  return [
    [lat - half, lng - half],
    [lat - half, lng + half],
    [lat + half, lng + half],
    [lat + half, lng - half],
  ];
}

function generateBuildingPolygon(center, size = 0.0005) {
  const [lat, lng] = center;
  const half = size / 2;
  return [
    [lat - half, lng - half * 0.8],
    [lat - half, lng + half * 0.8],
    [lat + half * 0.7, lng + half],
    [lat + half, lng - half * 0.3],
  ];
}

/* Layer Panel component */
function LayerPanel({ layers, onToggle, onClose }) {
  const groupLabels = {
    base: 'Base Layers',
    buildings: 'Buildings',
    infrastructure: 'Infrastructure',
    elevation: 'Elevation',
    survey: 'Survey'
  };

  return (
    <div className="context-panel">
      <div className="context-panel-header">
        <span className="context-panel-title">LAYERS</span>
        <button className="context-panel-close" onClick={onClose}>
          <Icons.Close style={{ width: 14, height: 14 }} />
        </button>
      </div>
      <div className="context-panel-body">
        <input className="layer-search" placeholder="Search layers..." />
        {Object.entries(layers).map(([groupKey, items]) => (
          <div className="layer-group" key={groupKey}>
            <div className="layer-group-title">{groupLabels[groupKey]}</div>
            {items.map((layer) => (
              <div className="layer-item" key={layer.id}>
                <label>
                  <input type="checkbox" checked={layer.checked}
                    onChange={() => onToggle(groupKey, layer.id)} />
                  <span>{layer.label}</span>
                </label>
                <div className="layer-opacity">
                  <span>{layer.opacity}%</span>
                  <button className={`opacity-toggle ${layer.checked ? 'active' : ''}`}
                    onClick={() => onToggle(groupKey, layer.id)} />
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/* Property Panel component */
function PropertyPanel({ property, onClose }) {
  if (!property) return null;
  return (
    <div className="property-panel">
      <div className="property-panel-header">
        <span className="property-panel-title">PROPERTY DETAILS</span>
        <button className="context-panel-close" onClick={onClose}>
          <Icons.Close style={{ width: 14, height: 14 }} />
        </button>
      </div>
      <div className="property-panel-body">
        <div className="property-ulpin">
          <span className="property-ulpin-code">{property.ulpin}</span>
          <span className={`status-badge ${property.status.toLowerCase()}`}>{property.status}</span>
        </div>

        <div className="property-field">
          <span className="property-field-label">Property Type</span>
          <span className="property-field-value">{property.propertyType}</span>
        </div>
        <div className="property-field">
          <span className="property-field-label">Floor / Level</span>
          <span className="property-field-value">{property.floor}</span>
        </div>
        <div className="property-field">
          <span className="property-field-label">Status</span>
          <span className="property-field-value" style={{ color: 'var(--status-success)' }}>{property.status}</span>
        </div>
        <div className="property-field">
          <span className="property-field-label">Bottom Height</span>
          <span className="property-field-value">{property.bottomHeight}</span>
        </div>
        <div className="property-field">
          <span className="property-field-label">Top Height</span>
          <span className="property-field-value">{property.topHeight}</span>
        </div>
        <div className="property-field">
          <span className="property-field-label">Parent Building</span>
          <span className="property-field-value" style={{ color: 'var(--accent-secondary)' }}>{property.parentBuilding}</span>
        </div>
        <div className="property-field">
          <span className="property-field-label">Parent Parcel</span>
          <span className="property-field-value" style={{ color: 'var(--accent-secondary)' }}>{property.parentParcel}</span>
        </div>
        <div className="property-field">
          <span className="property-field-label">3D Shape Volume</span>
          <span className="property-field-value">{property.volume}</span>
        </div>

        <div className="property-section">
          <div className="property-section-title">Source Data</div>
          <div>
            {property.sourceData.map((s) => (
              <span className="property-tag" key={s}>{s}</span>
            ))}
          </div>
        </div>

        <div className="property-field">
          <span className="property-field-label">Accuracy</span>
          <span className="property-field-value" style={{ color: 'var(--status-success)' }}>{property.accuracy}</span>
        </div>
        <div className="property-field">
          <span className="property-field-label">AI Confidence</span>
          <span className="property-field-value" style={{ color: 'var(--status-success)' }}>{property.aiConfidence}</span>
        </div>
        <div className="property-field">
          <span className="property-field-label">Last Updated</span>
          <span className="property-field-value">{property.lastUpdated}</span>
        </div>
        <div className="property-field">
          <span className="property-field-label">Created By</span>
          <span className="property-field-value">{property.createdBy}</span>
        </div>

        <div className="property-section">
          <div className="property-section-title">Actions</div>
          <div className="property-actions">
            <button className="btn btn-secondary btn-sm" onClick={() => navigate('/map-3d')}>
              <Icons.Map3D style={{ width: 14, height: 14 }} /> View in 3D
            </button>
            <button className="btn btn-secondary btn-sm" disabled
                    title="Editing a unit is not built yet">
              <Icons.Pencil style={{ width: 14, height: 14 }} /> Edit
            </button>
            <button className="btn btn-secondary btn-sm" onClick={() => navigate('/history')}>
              <Icons.History style={{ width: 14, height: 14 }} /> Open History
            </button>
          </div>
        </div>

        <div className="property-section">
          <div className="property-section-title">Related Properties</div>
          {property.relatedProperties.map((rp) => (
            <div className="related-property" key={rp.id}>
              <div>
                <div className="related-property-id">{rp.id}</div>
                <div className="related-property-info">{rp.floor}</div>
              </div>
              <span className={`status-badge ${rp.status.toLowerCase()}`}>{rp.status}</span>
            </div>
          ))}
          <div style={{ textAlign: 'center', marginTop: 8 }}>
            <a style={{ fontSize: 'var(--text-xs)', color: 'var(--accent-secondary)', cursor: 'pointer' }}>View All</a>
          </div>
        </div>
      </div>
    </div>
  );
}

/* 3D Scene with Three.js */
function ThreeScene({ selectedBuilding, onSelectBuilding, activeFloor }) {
  const canvasRef = useRef(null);
  const rendererRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const animFrameRef = useRef(null);

  useEffect(() => {
    let THREE;
    let mounted = true;

    async function initScene() {
      THREE = await import('three');
      if (!mounted || !canvasRef.current) return;

      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0x0a0e1a);
      scene.fog = new THREE.FogExp2(0x0a0e1a, 0.015);
      sceneRef.current = scene;

      const w = canvasRef.current.clientWidth;
      const h = canvasRef.current.clientHeight;
      const camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 500);
      camera.position.set(25, 20, 25);
      camera.lookAt(0, 3, 0);
      cameraRef.current = camera;

      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setSize(w, h);
      renderer.setPixelRatio(window.devicePixelRatio);
      renderer.shadowMap.enabled = true;
      canvasRef.current.appendChild(renderer.domElement);
      rendererRef.current = renderer;

      // Lights
      const ambientLight = new THREE.AmbientLight(0x404060, 0.6);
      scene.add(ambientLight);
      const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
      dirLight.position.set(20, 30, 20);
      dirLight.castShadow = true;
      scene.add(dirLight);
      const pointLight = new THREE.PointLight(0x00d4aa, 0.3, 50);
      pointLight.position.set(-10, 15, -10);
      scene.add(pointLight);

      // Ground plane
      const groundGeom = new THREE.PlaneGeometry(60, 60);
      const groundMat = new THREE.MeshStandardMaterial({
        color: 0x111827, roughness: 0.9, metalness: 0.1
      });
      const ground = new THREE.Mesh(groundGeom, groundMat);
      ground.rotation.x = -Math.PI / 2;
      ground.receiveShadow = true;
      scene.add(ground);

      // Grid
      const gridHelper = new THREE.GridHelper(60, 60, 0x1e293b, 0x1a2035);
      gridHelper.position.y = 0.01;
      scene.add(gridHelper);

      // Parcel boundaries (green outlines on ground)
      const parcelPositions = [
        { x: -8, z: -5, w: 8, d: 8 },
        { x: 2, z: -3, w: 10, d: 10 },
        { x: 14, z: -6, w: 6, d: 7 },
      ];
      parcelPositions.forEach(p => {
        const shape = new THREE.Shape();
        shape.moveTo(p.x, p.z);
        shape.lineTo(p.x + p.w, p.z);
        shape.lineTo(p.x + p.w, p.z + p.d);
        shape.lineTo(p.x, p.z + p.d);
        shape.lineTo(p.x, p.z);
        const points = shape.getPoints();
        const geom = new THREE.BufferGeometry().setFromPoints(
          points.map(pt => new THREE.Vector3(pt.x, 0.05, pt.y))
        );
        const mat = new THREE.LineBasicMaterial({ color: 0x00d4aa, opacity: 0.4, transparent: true });
        const line = new THREE.Line(geom, mat);
        scene.add(line);

        // Parcel labels
        const labelPos = new THREE.Vector3(p.x + p.w / 2, 0.1, p.z + p.d / 2);
        const labelId = `P${183 + parcelPositions.indexOf(p)}`;
        // We'll skip canvas labels for simplicity - the buildings serve as indicators
      });

      // Buildings
      const buildingData = [
        { id: 'B318', x: -5, z: -2, w: 4, d: 3.5, floors: 8, basement: 1, color: 0x00d4aa },
        { id: 'B320', x: 4, z: 0, w: 5.5, d: 4, floors: 5, basement: 2, color: 0x0ea5e9 },
        { id: 'B315', x: 15, z: -3, w: 3, d: 3, floors: 6, basement: 1, color: 0x8b5cf6 },
      ];

      const floorHeight = 3;

      buildingData.forEach(bd => {
        // Basement floors
        for (let b = 0; b < bd.basement; b++) {
          const y = -(b + 1) * floorHeight;
          const geom = new THREE.BoxGeometry(bd.w, floorHeight - 0.15, bd.d);
          const mat = new THREE.MeshStandardMaterial({
            color: 0xf59e0b, opacity: 0.3, transparent: true, roughness: 0.7
          });
          const mesh = new THREE.Mesh(geom, mat);
          mesh.position.set(bd.x, y + floorHeight / 2, bd.z);
          mesh.castShadow = true;
          mesh.userData = { buildingId: bd.id, floor: -(b + 1), type: 'basement' };
          scene.add(mesh);

          // wireframe
          const wireGeo = new THREE.EdgesGeometry(geom);
          const wireMat = new THREE.LineBasicMaterial({ color: 0xf59e0b, opacity: 0.5, transparent: true });
          const wire = new THREE.LineSegments(wireGeo, wireMat);
          wire.position.copy(mesh.position);
          scene.add(wire);
        }

        // Above-ground floors
        for (let f = 0; f < bd.floors; f++) {
          const y = f * floorHeight;
          const isSelected = selectedBuilding === bd.id;
          const isActiveFloor = isSelected && activeFloor === f + 1;

          const geom = new THREE.BoxGeometry(bd.w, floorHeight - 0.15, bd.d);
          const opacity = isSelected ? (isActiveFloor ? 0.9 : 0.5) : 0.6;
          const color = isActiveFloor ? 0x00ff88 : bd.color;

          const mat = new THREE.MeshStandardMaterial({
            color, opacity, transparent: true, roughness: 0.5, metalness: 0.1
          });
          const mesh = new THREE.Mesh(geom, mat);
          mesh.position.set(bd.x, y + floorHeight / 2, bd.z);
          mesh.castShadow = true;
          mesh.userData = { buildingId: bd.id, floor: f + 1 };
          scene.add(mesh);

          // wireframe
          const wireGeo = new THREE.EdgesGeometry(geom);
          const wireMat = new THREE.LineBasicMaterial({
            color: isActiveFloor ? 0x00ff88 : bd.color,
            opacity: isActiveFloor ? 1 : 0.4, transparent: true
          });
          const wire = new THREE.LineSegments(wireGeo, wireMat);
          wire.position.copy(mesh.position);
          scene.add(wire);
        }

        // Building ID label using a thin bar on top
        const topY = bd.floors * floorHeight;
        const labelGeo = new THREE.BoxGeometry(bd.w, 0.08, bd.d);
        const labelMat = new THREE.MeshStandardMaterial({ color: bd.color, emissive: bd.color, emissiveIntensity: 0.3 });
        const labelMesh = new THREE.Mesh(labelGeo, labelMat);
        labelMesh.position.set(bd.x, topY + 0.1, bd.z);
        scene.add(labelMesh);
      });

      // Underground pipes
      const pipeGeo = new THREE.CylinderGeometry(0.15, 0.15, 30, 8);
      const pipeMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, opacity: 0.35, transparent: true });
      const pipe = new THREE.Mesh(pipeGeo, pipeMat);
      pipe.rotation.z = Math.PI / 2;
      pipe.position.set(0, -2, 5);
      scene.add(pipe);

      const pipe2Geo = new THREE.CylinderGeometry(0.12, 0.12, 20, 8);
      const pipe2 = new THREE.Mesh(pipe2Geo, pipeMat.clone());
      pipe2.rotation.x = Math.PI / 2;
      pipe2.position.set(-5, -3, 0);
      scene.add(pipe2);

      // Elevated road
      const roadGeo = new THREE.BoxGeometry(35, 0.3, 2);
      const roadMat = new THREE.MeshStandardMaterial({ color: 0x3b82f6, opacity: 0.25, transparent: true });
      const road = new THREE.Mesh(roadGeo, roadMat);
      road.position.set(0, 12, -10);
      scene.add(road);
      // Road supports
      for (let i = -15; i <= 15; i += 6) {
        const pillarGeo = new THREE.BoxGeometry(0.3, 12, 0.3);
        const pillar = new THREE.Mesh(pillarGeo, roadMat.clone());
        pillar.position.set(i, 6, -10);
        scene.add(pillar);
      }

      // Camera auto-rotation
      let angle = Math.PI / 4;
      const rotateSpeed = 0.002;
      const radius = 35;

      function animate() {
        animFrameRef.current = requestAnimationFrame(animate);
        angle += rotateSpeed;
        camera.position.x = Math.cos(angle) * radius;
        camera.position.z = Math.sin(angle) * radius;
        camera.position.y = 20;
        camera.lookAt(0, 5, 0);
        renderer.render(scene, camera);
      }
      animate();

      // Handle resize
      const handleResize = () => {
        if (!canvasRef.current) return;
        const w = canvasRef.current.clientWidth;
        const h = canvasRef.current.clientHeight;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
      };
      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('resize', handleResize);
      };
    }

    initScene();

    return () => {
      mounted = false;
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      if (rendererRef.current) {
        rendererRef.current.dispose();
        if (canvasRef.current && rendererRef.current.domElement.parentNode === canvasRef.current) {
          canvasRef.current.removeChild(rendererRef.current.domElement);
        }
      }
    };
  }, [selectedBuilding, activeFloor]);

  return <div ref={canvasRef} className="three-canvas-wrapper" />;
}

/* Floor slider for 3D view */
function FloorSlider({ building, activeFloor, onFloorChange }) {
  if (!building) return null;
  const floors = [];
  if (building.basement) {
    for (let b = building.basement; b >= 1; b--) floors.push({ label: `B${b}`, value: -b });
  }
  for (let f = 1; f <= building.floors; f++) {
    floors.push({ label: f === building.floors ? 'Roof' : `${f}F`, value: f });
  }
  floors.reverse();

  return (
    <div className="floor-slider">
      {floors.map((f) => (
        <button
          key={f.value}
          className={`floor-btn${activeFloor === f.value ? ' active' : ''}`}
          onClick={() => onFloorChange(f.value)}
        >
          {f.label}
        </button>
      ))}
    </div>
  );
}

export default function MapPage({ project, view = '2d' }) {
  const navigate = useNavigate();
  const [showLayers, setShowLayers] = useState(true);
  const [layers, setLayers] = useState(MAP_LAYERS);
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [selectedBuildingId, setSelectedBuildingId] = useState('B318');
  const [activeFloor, setActiveFloor] = useState(4);

  useEffect(() => {
    const handleToggleLayers = () => setShowLayers(prev => !prev);
    window.addEventListener('toggle-layers', handleToggleLayers);
    return () => window.removeEventListener('toggle-layers', handleToggleLayers);
  }, []);

  const center = [12.9720, 77.5950];

  const toggleLayer = (group, id) => {
    setLayers(prev => ({
      ...prev,
      [group]: prev[group].map(l => l.id === id ? { ...l, checked: !l.checked } : l)
    }));
  };

  const handleBuildingClick = (building) => {
    setSelectedBuildingId(building.id);
    // Details come from the unit that was actually picked, or the panel stays shut.
    setSelectedProperty(null);
  };

  const { parcels: livePercels, buildings: liveBuildings, bounds } = useProjectGeometry();
  const selectedBuildingData = liveBuildings.find(b => b.unit.unit_id === selectedBuildingId)?.unit;

  return (
    <>
      {showLayers && <LayerPanel layers={layers} onToggle={toggleLayer} onClose={() => setShowLayers(false)} />}
      <div className="map-container">
        <div className="map-tabs">
          <button className={`map-tab${view === '2d' ? ' active' : ''}`}
            onClick={() => navigate('/map-2d')}>2D Map</button>
          <span style={{ color: 'var(--text-muted)', padding: '0 4px', fontSize: 'var(--text-xs)', alignSelf: 'center' }}>|</span>
          <button className={`map-tab${view === '3d' ? ' active' : ''}`}
            onClick={() => navigate('/map-3d')}>3D Map</button>

          <div style={{ flex: 1 }} />

          {/* Map mini toolbar */}
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            {!showLayers && (
              <button className="map-floating-btn" style={{ width: 26, height: 26 }} onClick={() => setShowLayers(true)} title="Show Layers">
                <Icons.Layers style={{ width: 13, height: 13 }} />
              </button>
            )}
            {[Icons.Cursor, Icons.Crosshair, Icons.Ruler, Icons.Pencil, Icons.Move].map((Ic, i) => (
              <button key={i} className="map-floating-btn" disabled
                      title="Map tools are not built yet"
                      style={{ width: 26, height: 26 }}>
                <Ic style={{ width: 13, height: 13 }} />
              </button>
            ))}
          </div>
        </div>

        <div className="map-view">
          {view === '2d' ? (
            <>
              <MapContainer center={center} zoom={17} style={{ height: '100%', width: '100%' }}
                zoomControl={true} attributionControl={true}>
                {/* OpenStreetMap, which needs no key. CARTO's dark tiles now require
                    registration and serve an "API KEY REQUIRED" watermark across every
                    tile without one — not something to discover during a demo. The dark
                    treatment is a CSS filter on the tile pane instead. */}
                <TileLayer
                  url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                  className="basemap-dark"
                  maxZoom={19}
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                />

                <FitToProject bounds={bounds} />

                {/* Parcel polygons, from the project */}
                {livePercels.map(({ unit: parcel, positions }) => (
                  <Polygon
                    key={parcel.unit_id}
                    positions={positions}
                    pathOptions={{
                      color: '#00d4aa', weight: 1.5, fillColor: '#00d4aa',
                      fillOpacity: 0.08, dashArray: '4 4'
                    }}
                  >
                    <Popup>
                      <div style={{ fontFamily: 'Inter, sans-serif' }}>
                        <div style={{ fontWeight: 700, color: '#00d4aa', marginBottom: 4 }}>{parcel.label}</div>
                        <div style={{ fontSize: 12, color: '#94a3b8' }}>Land parcel</div>
                        <div style={{ fontSize: 12, color: '#94a3b8' }}>{parcel.status}</div>
                      </div>
                    </Popup>
                  </Polygon>
                ))}

                {/* Building footprints, from the project */}
                {liveBuildings.map(({ unit: building, positions }) => (
                  <Polygon
                    key={building.unit_id}
                    positions={positions}
                    pathOptions={{
                      color: '#0ea5e9', weight: 2, fillColor: '#0ea5e9',
                      fillOpacity: 0.15
                    }}
                    eventHandlers={{
                      click: () => handleBuildingClick(building)
                    }}
                  >
                    <Popup>
                      <div style={{ fontFamily: 'Inter, sans-serif' }}>
                        <div style={{ fontWeight: 700, color: '#0ea5e9', marginBottom: 4 }}>
                          {building.label}
                        </div>
                        <div style={{ fontSize: 12, color: '#94a3b8' }}>
                          {building.base_m === null || building.top_m === null
                            ? 'Height unknown'
                            : `${(building.top_m - building.base_m).toFixed(1)} m tall`}
                        </div>
                        <div style={{ fontSize: 12, color: '#94a3b8' }}>{building.status}</div>
                      </div>
                    </Popup>
                  </Polygon>
                ))}
              </MapContainer>

              <div className="map-info-overlay">
                <span>Lat: 12.9716°</span>
                <span>Lon: 77.5946°</span>
                <span>Elev: 920.45 m</span>
                <span>Scale 1:2,500</span>
              </div>
            </>
          ) : (
            <>
              <ThreeScene
                selectedBuilding={selectedBuildingId}
                onSelectBuilding={setSelectedBuildingId}
                activeFloor={activeFloor}
              />
              <FloorSlider
                building={selectedBuildingData}
                activeFloor={activeFloor}
                onFloorChange={setActiveFloor}
              />
              <div className="map-info-overlay">
                <span>Building: {selectedBuildingId}</span>
                <span>Floor: {activeFloor}</span>
                <span>Mode: Orbit</span>
              </div>
            </>
          )}
        </div>
      </div>

      {selectedProperty && (
        <PropertyPanel property={selectedProperty} onClose={() => setSelectedProperty(null)} />
      )}
    </>
  );
}
