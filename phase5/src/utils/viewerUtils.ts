import type {
  ExpressionSpecification,
  FilterSpecification,
  LngLatBoundsLike,
} from "maplibre-gl";

import type {
  UnitFeature,
  UnitProperties,
  FilterState,
  UnitType,
  UnitStatus,
} from "../types/viewer";

/* =========================================================
   CONSTANTS
========================================================= */

export const ALL_TYPES: UnitType[] = [
  "parcel",
  "building",
  "floor",
  "apartment",
  "underground",
];

export const ALL_STATUSES: UnitStatus[] = [
  "approved",
  "checked",
  "draft",
  "error",
];

/* =========================================================
   COLORS
========================================================= */

export const BG_COLOR = "#e8edf0";
export const LINE_COLOR = "#334155";
export const SELECTED_COLOR = "#111827";

export const STATUS_COLORS: Record<string, string> = {
  approved: "#0d6b58",
  checked: "#c9a227",
  draft: "#c9a227",
  error: "#b3402a",
};

export const STATUS_COLOR: ExpressionSpecification = [
  "match",
  ["get", "status"],
  "approved",
  "#0d6b58",
  "error",
  "#b3402a",
  "#c9a227",
];

/* =========================================================
   STATUS HELPERS
========================================================= */

export function getStatusColor(
  status: UnitStatus,
): string {
  return STATUS_COLORS[status] ?? "#94a3b8";
}

/* =========================================================
   UNIT TYPE LABEL
========================================================= */

export function getUnitTypeLabel(
  type: UnitType,
): string {
  switch (type) {
    case "parcel":
      return "Parcel";

    case "building":
      return "Building";

    case "floor":
      return "Floor";

    case "apartment":
      return "Apartment";

    case "underground":
      return "Underground";

    default:
      return type;
  }
}

/* =========================================================
   TOGGLE ITEM

   Existing SearchFilter.tsx calls:

   toggleItem(ALL_TYPES, filter.types, type)

   and

   toggleItem(ALL_STATUSES, filter.statuses, status)
========================================================= */

export function toggleItem<T>(
  allItems: T[],
  selectedItems: T[] | undefined,
  item: T | undefined,
): T[] {
  if (item === undefined) {
    return selectedItems ?? allItems;
  }

  const current = selectedItems ?? allItems;

  if (current.includes(item)) {
    return current.filter(
      (value) => value !== item,
    );
  }

  return [...current, item];
}

/* =========================================================
   GEOJSON BOUNDS
========================================================= */

export function computeBounds(
  features: UnitFeature[],
): LngLatBoundsLike | null {
  if (!features.length) {
    return null;
  }

  let minLng = Infinity;
  let maxLng = -Infinity;
  let minLat = Infinity;
  let maxLat = -Infinity;

  const addCoordinate = (
    coordinate: number[],
  ) => {
    const lng = Number(coordinate[0]);
    const lat = Number(coordinate[1]);

    if (
      !Number.isFinite(lng) ||
      !Number.isFinite(lat)
    ) {
      return;
    }

    minLng = Math.min(minLng, lng);
    maxLng = Math.max(maxLng, lng);
    minLat = Math.min(minLat, lat);
    maxLat = Math.max(maxLat, lat);
  };

  for (const feature of features) {
    if (!feature.geometry) {
      continue;
    }

    if (feature.geometry.type === "Polygon") {
      const coordinates =
        feature.geometry.coordinates as number[][][];

      for (const ring of coordinates) {
        for (const coordinate of ring) {
          addCoordinate(coordinate);
        }
      }
    }

    if (
      feature.geometry.type ===
      "MultiPolygon"
    ) {
      const coordinates =
        feature.geometry.coordinates as number[][][][];

      for (const polygon of coordinates) {
        for (const ring of polygon) {
          for (const coordinate of ring) {
            addCoordinate(coordinate);
          }
        }
      }
    }
  }

  if (
    !Number.isFinite(minLng) ||
    !Number.isFinite(maxLng) ||
    !Number.isFinite(minLat) ||
    !Number.isFinite(maxLat)
  ) {
    return null;
  }

  return [
    [minLng, minLat],
    [maxLng, maxLat],
  ];
}

/* =========================================================
   BUILD MAP FILTER
========================================================= */

export function buildMapFilter(
  filter: FilterState,
  showUnderground: boolean,
): FilterSpecification | null {
  const conditions: ExpressionSpecification[] =
    [];

  const types =
    filter.types ?? ALL_TYPES;

  const statuses =
    filter.statuses ?? ALL_STATUSES;

  /* TYPE FILTER */

  if (types.length === 0) {
    conditions.push([
      "==",
      ["get", "unit_type"],
      "",
    ]);
  } else if (
    types.length < ALL_TYPES.length
  ) {
    conditions.push([
      "in",
      ["get", "unit_type"],
      ["literal", types],
    ]);
  }

  /* STATUS FILTER */

  if (statuses.length === 0) {
    conditions.push([
      "==",
      ["get", "status"],
      "",
    ]);
  } else if (
    statuses.length < ALL_STATUSES.length
  ) {
    conditions.push([
      "in",
      ["get", "status"],
      ["literal", statuses],
    ]);
  }

  /* UNDERGROUND */

  if (!showUnderground) {
    conditions.push([
      "!=",
      ["get", "unit_type"],
      "underground",
    ]);
  }

  if (conditions.length === 0) {
    return null;
  }

  if (conditions.length === 1) {
    return conditions[0] as FilterSpecification;
  }

  return [
    "all",
    ...conditions,
  ] as FilterSpecification;
}

/* =========================================================
   UNIT ID
========================================================= */

function getUnitId(
  unit: UnitFeature,
): string {
  return String(
    unit.properties?.ulpin ??
      unit.id ??
      "",
  );
}

/* =========================================================
   PARENT ID
========================================================= */

function getParentId(
  unit: UnitFeature,
): string | null {
  const properties =
    unit.properties as Record<
      string,
      unknown
    >;

  const parent =
    properties.parent_ulpin ??
    properties.parentUlpin ??
    properties.parent_id ??
    properties.parentId ??
    properties.parent ??
    null;

  if (parent == null) {
    return null;
  }

  return String(parent);
}

/* =========================================================
   ANCESTORS

   Existing DetailsPanel.tsx calls:

   getAncestors(units, p.ulpin)
========================================================= */

export function getAncestors(
  units: UnitFeature[],
  ulpin: string,
): UnitFeature[] {
  const ancestors: UnitFeature[] = [];

  const visited = new Set<string>();

  let currentId = String(ulpin);

  while (currentId && !visited.has(currentId)) {
    visited.add(currentId);

    const current = units.find(
      (unit) =>
        getUnitId(unit) === currentId,
    );

    if (!current) {
      break;
    }

    const parentId =
      getParentId(current);

    if (!parentId) {
      break;
    }

    const parent = units.find(
      (unit) =>
        getUnitId(unit) === parentId,
    );

    if (!parent) {
      break;
    }

    ancestors.unshift(parent);

    currentId = parentId;
  }

  return ancestors;
}

/* =========================================================
   CHILDREN

   Existing DetailsPanel.tsx calls:

   getChildren(units, p.ulpin)
========================================================= */

export function getChildren(
  units: UnitFeature[],
  ulpin: string,
): UnitFeature[] {
  const parentId = String(ulpin);

  return units.filter(
    (unit) =>
      getParentId(unit) === parentId,
  );
}

/* =========================================================
   UNIT COLOR

   Viewer3D passes UnitProperties, NOT UnitFeature.
========================================================= */

export function getUnitColorHex(
  properties: UnitProperties,
): string {
  const status =
    properties.status as
      | UnitStatus
      | undefined;

  return status
    ? getStatusColor(status)
    : "#94a3b8";
}

/* =========================================================
   UNIT VISIBILITY

   Existing Viewer3D.tsx calls:

   isUnitVisible(
     p,
     filter,
     sliceHeight,
     showUnderground
   )

   p = UnitProperties
========================================================= */

export function isUnitVisible(
  properties: UnitProperties,
  filter: FilterState,
  sliceHeight: number,
  showUnderground: boolean,
): boolean {
  const type =
    properties.unit_type as
      | UnitType
      | undefined;

  const status =
    properties.status as
      | UnitStatus
      | undefined;

  /* UNDERGROUND */

  if (
    !showUnderground &&
    type === "underground"
  ) {
    return false;
  }

  /* TYPE FILTER */

  if (
    filter.types &&
    filter.types.length > 0 &&
    type &&
    !filter.types.includes(type)
  ) {
    return false;
  }

  /* STATUS FILTER */

  if (
    filter.statuses &&
    filter.statuses.length > 0 &&
    status &&
    !filter.statuses.includes(status)
  ) {
    return false;
  }

  /* SLICE HEIGHT */

  const props =
    properties as Record<
      string,
      unknown
    >;

  const baseHeight = Number(
    props.base_height ??
      props.baseHeight ??
      0,
  );

  const topHeight = Number(
    props.top_height ??
      props.topHeight ??
      baseHeight,
  );

  /*
   * If sliceHeight is not active,
   * don't apply height filtering.
   */
  if (
    Number.isFinite(sliceHeight) &&
    sliceHeight > 0
  ) {
    if (
      baseHeight > sliceHeight ||
      topHeight < sliceHeight
    ) {
      return false;
    }
  }

  return true;
}