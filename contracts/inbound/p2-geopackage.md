# P2 → P4 · GeoPackage contract

What P4 needs to find in the harmonized `.gpkg`. P2 owns this schema; P4 is a consumer.
Freeze on day 1.

Everything is in the **project CRS** (a projected CRS in metres — P4 does area and
distance maths and must not reproject per operation).

---

## Vector layers

### `parcel`
| Column | Type | Req | Notes |
|---|---|---|---|
| `parcel_local_id` | TEXT | yes | unique within project |
| `parent_ulpin_14` | TEXT | no | the existing 2D Bhu-Aadhaar, if known. P4 uses it as the ULPIN prefix. |
| `source_id` | TEXT | yes | FK → `source` |
| `geom` | POLYGON | yes | |

### `building_footprint`
| Column | Type | Req | Notes |
|---|---|---|---|
| `building_local_id` | TEXT | yes | |
| `parcel_local_id` | TEXT | no | NULL is allowed — P4 will spatially resolve and flag ambiguity |
| `source_id` | TEXT | yes | |
| `geom` | POLYGON | yes | |

### `utility_line` (optional, for the underground/elevated story)
| Column | Type | Req | Notes |
|---|---|---|---|
| `utility_local_id` | TEXT | yes | |
| `utility_kind` | TEXT | yes | water / sewer / power / telecom / metro / walkway |
| `stratum` | TEXT | yes | `below` or `above` |
| `depth_top_m`, `depth_bottom_m` | REAL | yes | relative to ground, signed |
| `corridor_width_m` | REAL | yes | P4 buffers the line by width/2 to make the easement volume |
| `source_id` | TEXT | yes | |
| `geom` | LINESTRING | yes | |

---

## Registry tables

### `source` — **this table drives P4's validation tolerances**
| Column | Type | Req |
|---|---|---|
| `source_id` | TEXT | yes |
| `source_type` | TEXT | yes — `parcel_map` / `footprint` / `dem` / `dsm` / `ortho` / `pointcloud` / `floorplan` |
| `name`, `provider` | TEXT | yes |
| `capture_date` | DATE | yes |
| `crs` | TEXT | yes |
| `vertical_datum` | TEXT | yes |
| **`horizontal_accuracy_m`** | REAL | **yes** |
| **`vertical_accuracy_m`** | REAL | **yes** |
| `coverage_wkt` | TEXT | yes |
| `processing_status` | TEXT | yes |

> The two accuracy columns are **mandatory, not optional**. P4 derives every geometric
> comparison tolerance from them: `tol = k * sqrt(acc_a² + acc_b²)`. If they are NULL,
> P4 cannot distinguish a real encroachment from measurement noise and will fall back
> to flagging everything, which makes the review queue useless.
>
> If accuracy is genuinely unknown for a source, record a conservative estimate and set
> `processing_status = 'accuracy_estimated'` — do not leave it NULL.
>
> **And do not supply an optimistic default.** A writer defaulting to, say, 0.05 m makes
> every source silently claim survey-grade accuracy. Tolerances are derived from these
> numbers, so a too-tight value turns ordinary measurement noise into reported
> encroachments — the review queue fills with false positives and reviewers learn to
> dismiss warnings. Under-claiming accuracy is safe; over-claiming is not.

### `raster` — rasters live as files; this is the registry
| Column | Type | Req |
|---|---|---|
| `raster_id` | TEXT | yes |
| `kind` | TEXT | yes — `DEM` / `DSM` / `ORTHO` |
| `path` | TEXT | yes — relative to the project folder |
| `crs`, `vertical_datum` | TEXT | yes |
| `resolution_m` | REAL | yes |
| `source_id` | TEXT | yes |

### `project_settings` — single row
| Column | Notes |
|---|---|
| `project_crs` | e.g. `EPSG:32643` |
| `vertical_datum` | **exactly `EGM2008`** — a free-text mismatch such as `MSL_EGM2008` raises `DATUM_MISMATCH` on every unit |
| `stratum_below_limit_m`, `stratum_above_limit_m` | defines a parcel's z-extent, e.g. −30 / +150 |
| `default_plinth_offset_m` | e.g. 0.6 |
| `default_parapet_deduction_m` | **0.0.** Was 1.0 in an earlier revision of this contract; that is now wrong. `roof_level` uses a median, which returns the roof slab directly, so a deduction on top lowers every floor by that amount and **every validation rule still passes**. The cadastre block raises `EstimatorMismatch` on any non-zero value rather than accept it. |
| `ulpin_version` | e.g. `v1` |
| `ruleset_version` | which validation rule set and severity thresholds apply. Current: `r1` |

---

## The one thing that will silently break everything

**Vertical datum handling.** LiDAR and photogrammetry produce *ellipsoidal* heights.
Survey of India topo data and DEMs are *orthometric* (MSL, via a geoid model). Floor
plans use a *local* datum ("finished floor level of ground floor = 0.000").

If ellipsoidal heights get treated as orthometric, every building sits tens of metres
off vertically — **and P4's validation will pass it cleanly**, because all the relative
relationships between floors remain internally consistent. A whole-building vertical
offset is invisible to relative checks.

So: record `vertical_datum` **per source**, never assume, and transform explicitly with
pyproj. P4 raises `DATUM_MISMATCH` when a unit's sources disagree, but P4 cannot detect
a uniform offset applied to everything.
