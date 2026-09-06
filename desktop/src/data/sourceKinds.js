/** What a project may be built from, and what each kind of file is worth.
 *
 * One table, read by both screens that can add a source: the creation wizard and the
 * Upload Data screen. They held separate copies with different numbers, and a project
 * does not care whether a file arrived at the start or an hour later — the same
 * footprint layer was registered at 0.30 m through the wizard and 2.00 m through
 * Upload. Every geometric tolerance P4 computes is `k * sqrt(acc_a^2 + acc_b^2)` over
 * exactly these values, so the same file produced different tolerances, different
 * findings and a different review queue depending on which screen the operator happened
 * to use. That is not a styling difference; it is two answers to one measurement.
 *
 * The keys are the sidecar's own `source_type` values (`project.SOURCE_TYPES`), checked
 * against `GET /cadastre/source-types` by the wizard on mount — a key here that the
 * backend does not handle is a file the operator picks and the project silently drops.
 *
 * `accuracy` is `[horizontal_m, vertical_m]` and is the conservative end of each
 * instrument's usual range, never the optimistic one. Where the two old tables
 * disagreed, the looser number won: under-claiming accuracy is safe, while over-claiming
 * it turns ordinary measurement noise into reported encroachments and fills the review
 * queue with false positives until reviewers stop reading it. These are a starting
 * point for the operator to correct per file, not a claim about their data — both
 * screens leave the fields editable, and the sidecar refuses a source without them.
 */
export const SOURCE_KINDS = {
  parcel_map: {
    label: 'GIS parcel layer',
    hint: 'Cadastral parcel polygons. The only source that carries the existing 14-character ULPIN every unit inherits.',
    accept: { name: 'Vector', extensions: ['geojson', 'json', 'gpkg', 'shp'] },
    accuracy: [0.30, 0.50], datum: 'EGM2008', required: true,
  },
  footprint: {
    label: 'Building footprints',
    hint: 'Building outlines. Attached to a parcel that holds more than half of each one.',
    accept: { name: 'Vector', extensions: ['geojson', 'json', 'gpkg', 'shp'] },
    accuracy: [2.00, 5.00], datum: 'EGM2008',
  },
  utility: {
    label: 'Utility lines — underground or elevated',
    hint: 'Water, sewer, power, telecom, metro, walkway. Becomes an easement corridor, which is allowed to cross parcel boundaries.',
    accept: { name: 'Vector', extensions: ['geojson', 'json', 'gpkg', 'shp'] },
    accuracy: [1.00, 1.00], datum: 'EGM2008',
  },
  dem: {
    label: 'DEM — bare-earth elevation',
    hint: 'Ground level under the buildings. Without it heights stay absent, which is FR-03 working rather than failing.',
    accept: { name: 'Raster', extensions: ['tif', 'tiff'] },
    accuracy: [0.50, 0.30], datum: 'EGM2008',
  },
  dsm: {
    label: 'DSM — surface elevation',
    hint: 'Roof level. Paired with the DEM to extrude a building and divide it into floors.',
    accept: { name: 'Raster', extensions: ['tif', 'tiff'] },
    accuracy: [0.50, 0.30], datum: 'EGM2008',
  },
  ortho: {
    label: 'Drone imagery / orthophoto',
    hint: 'Basemap and visual evidence for review.',
    accept: { name: 'Raster', extensions: ['tif', 'tiff', 'jpg', 'png'] },
    accuracy: [0.20, 1.00], datum: 'EGM2008',
  },
  pointcloud: {
    label: 'LiDAR / 3D point cloud',
    hint: 'Registered as provenance. The system reads a DEM and DSM derived from it, never the tile itself — so add those too.',
    accept: { name: 'Point cloud', extensions: ['las', 'laz'] },
    accuracy: [0.15, 0.10], datum: 'WGS84_ELLIPSOID',
  },
  floorplan: {
    label: 'Building floor plan',
    hint: 'Provenance for interior subdivision. Floor plans use a local datum: ground floor level is 0.000.',
    accept: { name: 'Plan', extensions: ['pdf', 'dxf', 'dwg', 'png', 'jpg'] },
    accuracy: [0.10, 0.10], datum: 'LOCAL_FFL',
  },
  survey_control: {
    label: 'GNSS / CORS survey control',
    hint: 'Control points the rest of the data is tied to. The most accurate thing in a project, and usually the smallest.',
    accept: { name: 'Survey', extensions: ['csv', 'txt', 'geojson', 'json'] },
    accuracy: [0.02, 0.03], datum: 'WGS84_ELLIPSOID',
  },
}

/** The same table as a list, for screens that render it as cards or options. */
export const SOURCE_KIND_LIST = Object.entries(SOURCE_KINDS).map(
  ([id, spec]) => ({ id, ...spec }),
)
