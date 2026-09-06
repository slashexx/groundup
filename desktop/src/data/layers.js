/** The layers the map panel offers.
 *
 * Every entry here is something one of the two map views genuinely draws, and toggling
 * it changes what is on screen. The panel used to list eleven: satellite imagery, roads,
 * underground utilities, elevated structures, DEM, DSM, survey points and control points
 * — none of which this app renders — over a `toggleLayer` nothing read, so all eleven
 * checkboxes and eleven opacity pills were decoration on a map that drew its parcels,
 * buildings and tiles unconditionally. A control that reports a state it does not have
 * is worse than no control: it answers "is the DEM showing?" with a checkmark.
 *
 * `views` is which map can draw it. `unitType` is the contract unit type an entry
 * renders, and is what the panel checks against the open project: a project holding no
 * underground features shows that row disabled and says so, rather than offering a
 * toggle that would do nothing.
 *
 * Rasters (DEM, DSM, orthophoto) are deliberately absent. A project registers them as
 * sources and `derive` reads them off disk, but nothing in this app draws a raster, so
 * a row for one could only ever be a switch with no wire behind it.
 */
export const MAP_LAYERS = {
  base: [
    {
      id: 'basemap',
      label: 'OpenStreetMap basemap',
      checked: true,
      opacity: 100,
      views: ['2d'],
    },
    {
      id: 'parcels',
      label: 'Land parcels',
      checked: true,
      opacity: 80,
      views: ['2d', '3d'],
      unitType: 'land_parcel',
    },
  ],
  buildings: [
    {
      id: 'footprints',
      label: 'Building footprints',
      checked: true,
      opacity: 80,
      views: ['2d'],
      unitType: 'building',
    },
    {
      id: 'envelopes',
      label: 'Building envelopes',
      checked: true,
      opacity: 100,
      views: ['3d'],
      unitType: 'building',
    },
  ],
  infrastructure: [
    {
      id: 'underground',
      label: 'Underground features',
      checked: true,
      opacity: 100,
      views: ['3d'],
      unitType: 'underground_feature',
    },
    {
      id: 'elevated',
      label: 'Elevated structures',
      checked: true,
      opacity: 100,
      views: ['3d'],
      unitType: 'elevated_structure',
    },
  ],
}

export const LAYER_GROUP_LABELS = {
  base: 'Base Layers',
  buildings: 'Buildings',
  infrastructure: 'Infrastructure',
}
