/** The AI operations P3 offers, as a catalogue for the AI Tools screen.
 *
 * Descriptions and model identity only. `lastRun` and `status` were fields here
 * once, carrying invented values - a screen reporting that a model 'last ran at
 * 10:20 AM' when nothing had ever run is exactly the kind of detail nobody thinks
 * to doubt. What actually ran comes from the sidecar or is not claimed at all.
 */
export const AI_TOOLS = [
  {
    id: 'building-extraction',
    name: 'Building Extraction',
    description: 'Detect and extract building outlines from satellite imagery and drone photos',
    icon: 'building',
    modelVersion: 'v3.2.1'
  },
  {
    id: 'height-estimation',
    name: 'Height Estimation',
    description: 'Estimate building heights from LiDAR point clouds and stereo imagery',
    icon: 'height',
    modelVersion: 'v2.8.0'
  },
  {
    id: 'floor-segmentation',
    name: 'Floor Segmentation',
    description: 'Segment buildings into individual floors based on height analysis',
    icon: 'layers',
    modelVersion: 'v2.5.3'
  },
  {
    id: 'vertical-unit-detection',
    name: 'Vertical Unit Detection',
    description: 'Identify individual property units within multi-storey buildings',
    icon: 'scan',
    modelVersion: 'v1.9.0'
  },
  {
    id: 'change-detection',
    name: 'Change Detection',
    description: 'Compare temporal datasets to detect new construction and modifications',
    icon: 'diff',
    modelVersion: 'v2.1.0'
  }
]
