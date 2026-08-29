export type ViewerMode = '2d' | '3d';
export type UnitType = 'parcel' | 'building' | 'floor' | 'apartment' | 'underground';
export type UnitStatus = 'draft' | 'checked' | 'approved' | 'error';
export type FindingLevel = 'error' | 'warning' | 'info';

export interface Finding {
  level: FindingLevel;
  msg: string;
}

export interface UnitProperties {
  ulpin: string;
  unit_type: UnitType;
  parent_ulpin: string | null;
  base_height: number;
  top_height: number;
  status: UnitStatus;
  owner: string;
  source: string;
  confidence: number;
  findings: Finding[];
  id?: string | number;
  name?: string;
  level?: number;
  description?: string;
  [key: string]: unknown;
}

export interface UnitGeometry {
  type: string;
  coordinates: number[][][] | number[][][][] | unknown;
}

export interface UnitFeature {
  type: 'Feature';
  id?: string | number;
  properties: UnitProperties;
  geometry: UnitGeometry;
}

export interface UnitFeatureCollection {
  type: 'FeatureCollection';
  name?: string;
  description?: string;
  features: UnitFeature[];
}

export interface FilterCriteria {
  query?: string;
  types?: UnitType[];
  statuses?: UnitStatus[];
  searchTerm?: string;
  type?: string;
  status?: string;
  level?: number;
}

export type FilterState = FilterCriteria;

export type MapViewMode = '2d' | '2.5d';

export interface Map2DProps {
  units: UnitFeature[];
  selectedUlpin: string | null;
  filter: FilterState;
  showUnderground: boolean;
  viewMode: MapViewMode;
  onSelect: (ulpin: string | null) => void;
  className?: string;
}

export interface Viewer3DProps {
  units: UnitFeature[];
  selectedUlpin: string | null;
  filter: FilterState;
  sliceHeight: number | null;
  showUnderground: boolean;
  onSelect: (ulpin: string | null) => void;
  className?: string;
}

export interface SearchFilterProps {
  units: UnitFeature[];
  filter: FilterState;
  onFilterChange: (filter: FilterState) => void;
  onSelect: (ulpin: string | null) => void;
  className?: string;
}

export interface DetailsPanelProps {
  units: UnitFeature[];
  selectedUlpin: string | null;
  onSelect: (ulpin: string | null) => void;
  onClose?: () => void;
  className?: string;
}
