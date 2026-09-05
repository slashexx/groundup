/** Which layers the map panel offers, and their default visibility.
 *
 * UI configuration, not project data: these are the toggles, not what lies under
 * them. A layer listed here with nothing in the project simply draws nothing.
 */
export const MAP_LAYERS = {
  base: [
    { id: 'satellite', label: 'Satellite Imagery', checked: true, opacity: 100 },
    { id: 'roads', label: 'Roads', checked: true, opacity: 100 },
    { id: 'parcels', label: 'Land Parcels', checked: true, opacity: 80 }
  ],
  buildings: [
    { id: 'footprints', label: 'Building Footprints', checked: true, opacity: 80 },
    { id: 'building3d', label: 'Building 3D', checked: true, opacity: 100 }
  ],
  infrastructure: [
    { id: 'underground', label: 'Underground Utilities', checked: false, opacity: 60 },
    { id: 'elevated', label: 'Elevated Structures', checked: false, opacity: 60 }
  ],
  elevation: [
    { id: 'dem', label: 'DEM', checked: false, opacity: 60 },
    { id: 'dsm', label: 'DSM', checked: false, opacity: 60 }
  ],
  survey: [
    { id: 'surveypts', label: 'Survey Points', checked: false, opacity: 100 },
    { id: 'controlpts', label: 'Control Points', checked: false, opacity: 100 }
  ]
}
