// Mock data for the 3D ULPIN System

export const mockUser = {
  name: 'Arjun Rao',
  role: 'GIS Operator',
  initials: 'AR',
  email: 'arjun.rao@ulpin.gov.in'
};

export const mockProjects = [
  {
    id: 'proj-001',
    name: 'Bengaluru Ward 42',
    location: 'Bengaluru, Karnataka',
    crs: 'EPSG:4326 - WGS 84',
    verticalDatum: 'MSL',
    area: '12.45 km²',
    parcels: 1248,
    buildings: 467,
    units3d: 3361,
    lastModified: '29 May 2025, 10:25 AM',
    createdOn: '10 May 2025',
    status: 'active'
  },
  {
    id: 'proj-002',
    name: 'Hyderabad Zone III',
    location: 'Hyderabad, Telangana',
    crs: 'EPSG:4326 - WGS 84',
    verticalDatum: 'MSL',
    area: '8.72 km²',
    parcels: 892,
    buildings: 324,
    units3d: 2104,
    lastModified: '28 May 2025, 3:15 PM',
    createdOn: '5 Apr 2025',
    status: 'active'
  },
  {
    id: 'proj-003',
    name: 'Delhi Sector 21',
    location: 'New Delhi, NCR',
    crs: 'EPSG:4326 - WGS 84',
    verticalDatum: 'MSL',
    area: '5.30 km²',
    parcels: 560,
    buildings: 198,
    units3d: 1420,
    lastModified: '27 May 2025, 11:00 AM',
    createdOn: '15 Mar 2025',
    status: 'active'
  },
  {
    id: 'proj-004',
    name: 'Mumbai Ward F/S',
    location: 'Mumbai, Maharashtra',
    crs: 'EPSG:4326 - WGS 84',
    verticalDatum: 'MSL',
    area: '3.80 km²',
    parcels: 345,
    buildings: 156,
    units3d: 980,
    lastModified: '20 May 2025, 9:45 AM',
    createdOn: '1 Feb 2025',
    status: 'draft'
  }
];

export const mockDashboardKPIs = [
  { label: 'Total Parcels', value: '1,248', icon: 'parcel', color: 'teal' },
  { label: 'Buildings & Floors', value: '467 / 2.8K', icon: 'building', color: 'blue' },
  { label: '3D Property Units', value: '3,361', icon: 'unit3d', color: 'purple' },
  { label: 'Underground Features', value: '142', icon: 'underground', color: 'amber' },
  { label: 'Pending Review', value: '12', icon: 'review', color: 'red' },
  { label: 'Data Warnings', value: '23', icon: 'warning', color: 'amber' }
];

export const mockUploadStatus = {
  totalDatasets: 12,
  uploaded: 10,
  processing: 2,
  failed: 0,
  percent: 85
};

export const mockJobs = [
  { name: 'Building Extraction', type: 'AI', status: 'Completed', time: '10:20 AM' },
  { name: 'Floor Segmentation', type: 'AI', status: 'Completed', time: '10:15 AM' },
  { name: 'Vertical Unit Detection', type: 'AI', status: 'In Progress', time: '10:12 AM' },
  { name: 'Change Detection', type: 'AI', status: 'Queued', time: '—' },
  { name: 'Error Check', type: 'Validation', status: 'Completed', time: '09:55 AM' }
];

export const mockErrors = {
  total: 10,
  errors: 3,
  warnings: 7,
  info: 0,
  recent: [
    { id: 'B318', text: 'B318 – Outside Parcel Boundary', severity: 'error', tag: 'Error' },
    { id: 'F05', text: 'F05 – Overlap with F04', severity: 'warning', tag: 'Warning' },
    { id: 'B321', text: 'B321 – Missing Height', severity: 'warning', tag: 'Warning' }
  ]
};

export const mockRecordsByStatus = {
  total: 3361,
  draft: 156,
  processing: 234,
  needsReview: 12,
  approved: 2812,
  replaced: 45,
  closed: 102
};

export const mockHistory = [
  { text: 'Surveyor 1 uploaded LiDAR data', time: '29 May 2025, 09:45 AM', type: 'upload' },
  { text: 'AI Floor Segmentation completed', time: '29 May 2025, 09:50 AM', type: 'ai' },
  { text: 'GIS Operator edited B318-F04', time: '29 May 2025, 10:01 AM', type: 'edit' },
  { text: 'Reviewer 2 approved B318-F03', time: '29 May 2025, 10:12 AM', type: 'approve' }
];

export const mockSelectedProperty = {
  ulpin: '29-BLR-042-B318-F04',
  propertyType: 'Apartment',
  floor: 4,
  status: 'Approved',
  bottomHeight: '12.00 m (MSL)',
  topHeight: '15.20 m (MSL)',
  parentBuilding: 'BLR-042-B318',
  parentParcel: 'PAR-042-184',
  volume: '178.35 m³',
  sourceData: ['LiDAR', 'Floor Plan', 'Drone Image'],
  accuracy: '97.31%',
  aiConfidence: '94.85%',
  lastUpdated: '29 May 2025, 10:18 AM',
  createdBy: 'Surveyor 1',
  relatedProperties: [
    { id: '29-BLR-042-B318-F03', floor: 'Floor 3', status: 'Approved' },
    { id: '29-BLR-042-B318-F05', floor: 'Floor 5', status: 'Approved' },
    { id: '29-BLR-042-B318-B1', floor: 'Basement 1', status: 'Approved' }
  ]
};

export const mockLayers = {
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
};

export const mockParcels = [
  { id: 'P183', coords: [12.9716, 77.5946], area: '450 sqm', type: 'Residential' },
  { id: 'P184', coords: [12.9720, 77.5950], area: '380 sqm', type: 'Residential' },
  { id: 'P185', coords: [12.9725, 77.5955], area: '520 sqm', type: 'Commercial' },
  { id: 'P186', coords: [12.9730, 77.5960], area: '290 sqm', type: 'Residential' },
  { id: 'P189', coords: [12.9710, 77.5940], area: '610 sqm', type: 'Mixed Use' },
  { id: 'P193', coords: [12.9735, 77.5945], area: '340 sqm', type: 'Residential' }
];

export const mockBuildings = [
  {
    id: 'B318', parcel: 'P184', name: 'Prestige Tower',
    coords: [12.9720, 77.5950], floors: 8, basement: 1,
    height: 28, footprintArea: 200,
    units: [
      { id: 'B318-F01', floor: 1, type: 'Commercial', status: 'Approved' },
      { id: 'B318-F02', floor: 2, type: 'Apartment', status: 'Approved' },
      { id: 'B318-F03', floor: 3, type: 'Apartment', status: 'Approved' },
      { id: 'B318-F04', floor: 4, type: 'Apartment', status: 'Approved' },
      { id: 'B318-F05', floor: 5, type: 'Apartment', status: 'Approved' },
      { id: 'B318-F06', floor: 6, type: 'Apartment', status: 'Review' },
      { id: 'B318-F07', floor: 7, type: 'Apartment', status: 'Draft' },
      { id: 'B318-F08', floor: 8, type: 'Apartment', status: 'Draft' },
      { id: 'B318-B1', floor: -1, type: 'Parking', status: 'Approved' }
    ]
  },
  {
    id: 'B320', parcel: 'P185', name: 'City Center Mall',
    coords: [12.9725, 77.5955], floors: 5, basement: 2,
    height: 22, footprintArea: 450,
    units: [
      { id: 'B320-F01', floor: 1, type: 'Commercial', status: 'Approved' },
      { id: 'B320-F02', floor: 2, type: 'Commercial', status: 'Approved' },
      { id: 'B320-F03', floor: 3, type: 'Commercial', status: 'Review' },
      { id: 'B320-F04', floor: 4, type: 'Office', status: 'Processing' },
      { id: 'B320-F05', floor: 5, type: 'Office', status: 'Draft' },
      { id: 'B320-B1', floor: -1, type: 'Parking', status: 'Approved' },
      { id: 'B320-B2', floor: -2, type: 'Storage', status: 'Approved' }
    ]
  },
  {
    id: 'B315', parcel: 'P183', name: 'Green Heights',
    coords: [12.9716, 77.5946], floors: 6, basement: 1,
    height: 20, footprintArea: 180,
    units: []
  }
];

export const mockReviewRecords = [
  {
    id: 'REV-001',
    ulpin: '29-BLR-042-B318-F06',
    type: 'Apartment',
    building: 'B318 - Prestige Tower',
    floor: 6,
    submittedBy: 'Surveyor 1',
    submittedDate: '28 May 2025',
    aiConfidence: '92.3%',
    errors: 0,
    warnings: 1,
    status: 'Needs Review',
    state: 'review'
  },
  {
    id: 'REV-002',
    ulpin: '29-BLR-042-B320-F03',
    type: 'Commercial',
    building: 'B320 - City Center Mall',
    floor: 3,
    submittedBy: 'GIS Op 2',
    submittedDate: '27 May 2025',
    aiConfidence: '88.7%',
    errors: 1,
    warnings: 2,
    status: 'Needs Review',
    state: 'review'
  },
  {
    id: 'REV-003',
    ulpin: '29-BLR-042-B320-F04',
    type: 'Office',
    building: 'B320 - City Center Mall',
    floor: 4,
    submittedBy: 'GIS Op 1',
    submittedDate: '26 May 2025',
    aiConfidence: '95.1%',
    errors: 0,
    warnings: 0,
    status: 'Needs Review',
    state: 'review'
  }
];

export const mockAITools = [
  {
    id: 'building-extraction',
    name: 'Building Extraction',
    description: 'Detect and extract building outlines from satellite imagery and drone photos',
    icon: 'building',
    modelVersion: 'v3.2.1',
    lastRun: '29 May 2025, 10:20 AM',
    status: 'Ready'
  },
  {
    id: 'height-estimation',
    name: 'Height Estimation',
    description: 'Estimate building heights from LiDAR point clouds and stereo imagery',
    icon: 'height',
    modelVersion: 'v2.8.0',
    lastRun: '29 May 2025, 10:15 AM',
    status: 'Ready'
  },
  {
    id: 'floor-segmentation',
    name: 'Floor Segmentation',
    description: 'Segment buildings into individual floors based on height analysis',
    icon: 'layers',
    modelVersion: 'v2.5.3',
    lastRun: '29 May 2025, 10:15 AM',
    status: 'Ready'
  },
  {
    id: 'vertical-unit-detection',
    name: 'Vertical Unit Detection',
    description: 'Identify individual property units within multi-storey buildings',
    icon: 'scan',
    modelVersion: 'v1.9.0',
    lastRun: '29 May 2025, 10:12 AM',
    status: 'In Progress'
  },
  {
    id: 'change-detection',
    name: 'Change Detection',
    description: 'Compare temporal datasets to detect new construction and modifications',
    icon: 'diff',
    modelVersion: 'v2.1.0',
    lastRun: '—',
    status: 'Queued'
  }
];

export const mockErrorChecks = [
  { id: 'ERR-001', type: 'error', category: 'Boundary', description: 'B318 – Building extends outside parcel P184 boundary', parcel: 'P184', severity: 'Critical' },
  { id: 'ERR-002', type: 'error', category: 'Overlap', description: 'B318-F04 overlaps with B318-F05 by 2.3 sqm', parcel: 'B318', severity: 'High' },
  { id: 'ERR-003', type: 'error', category: 'Geometry', description: 'B315 has invalid 3D shape (self-intersecting polygon)', parcel: 'P183', severity: 'Critical' },
  { id: 'WRN-001', type: 'warning', category: 'Height', description: 'B321 – Missing height data for floor 3', parcel: 'P186', severity: 'Medium' },
  { id: 'WRN-002', type: 'warning', category: 'Order', description: 'B318 – Floor 7 height below floor 6', parcel: 'P184', severity: 'Medium' },
  { id: 'WRN-003', type: 'warning', category: 'Source', description: 'B320-F04 – Missing source approval reference', parcel: 'P185', severity: 'Low' },
  { id: 'WRN-004', type: 'warning', category: 'Alignment', description: 'Parcel P189 boundary misaligned with survey data by 0.8m', parcel: 'P189', severity: 'Medium' },
  { id: 'WRN-005', type: 'warning', category: 'Duplicate', description: 'Potential duplicate geometry for B315-F02 and B315-F03', parcel: 'P183', severity: 'Low' },
  { id: 'WRN-006', type: 'warning', category: 'Height', description: 'B320 – DSM height exceeds building model by 3.2m', parcel: 'P185', severity: 'Medium' },
  { id: 'WRN-007', type: 'warning', category: 'Source', description: 'B318-F08 – No LiDAR coverage available', parcel: 'P184', severity: 'Low' }
];

export const mockSearchResults = [
  { ulpin: '29-BLR-042-B318-F04', type: 'Apartment', building: 'Prestige Tower', floor: 4, status: 'Approved', address: 'Plot 184, Ward 42, Bengaluru' },
  { ulpin: '29-BLR-042-B318-F03', type: 'Apartment', building: 'Prestige Tower', floor: 3, status: 'Approved', address: 'Plot 184, Ward 42, Bengaluru' },
  { ulpin: '29-BLR-042-B320-F01', type: 'Commercial', building: 'City Center Mall', floor: 1, status: 'Approved', address: 'Plot 185, Ward 42, Bengaluru' },
  { ulpin: '29-BLR-042-B315-F01', type: 'Residential', building: 'Green Heights', floor: 1, status: 'Draft', address: 'Plot 183, Ward 42, Bengaluru' }
];

export const mockFullHistory = [
  { text: 'Surveyor 1 uploaded LiDAR data', time: '29 May 2025, 09:45 AM', type: 'upload', user: 'Surveyor 1' },
  { text: 'AI Floor Segmentation completed for B318', time: '29 May 2025, 09:50 AM', type: 'ai', user: 'System' },
  { text: 'GIS Operator edited B318-F04 geometry', time: '29 May 2025, 10:01 AM', type: 'edit', user: 'Arjun Rao' },
  { text: 'Error check completed — 3 errors, 7 warnings', time: '29 May 2025, 10:05 AM', type: 'validation', user: 'System' },
  { text: 'Reviewer 2 approved B318-F03', time: '29 May 2025, 10:12 AM', type: 'approve', user: 'Reviewer 2' },
  { text: 'GIS Operator created 3D unit B320-F04', time: '28 May 2025, 04:30 PM', type: 'create', user: 'GIS Op 1' },
  { text: 'Drone imagery uploaded for Ward 42 sector B', time: '28 May 2025, 02:15 PM', type: 'upload', user: 'Surveyor 2' },
  { text: 'AI Building Extraction completed', time: '28 May 2025, 01:00 PM', type: 'ai', user: 'System' },
  { text: 'Admin updated project CRS settings', time: '27 May 2025, 11:30 AM', type: 'settings', user: 'Admin' },
  { text: 'Reviewer 1 rejected B315-F02 (geometry issues)', time: '27 May 2025, 10:00 AM', type: 'reject', user: 'Reviewer 1' },
  { text: 'Bulk export of 450 approved records', time: '26 May 2025, 05:00 PM', type: 'export', user: 'Planner 1' },
  { text: 'AI Change Detection completed', time: '26 May 2025, 03:30 PM', type: 'ai', user: 'System' }
];
