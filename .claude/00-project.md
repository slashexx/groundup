# The problem

**SIH 2026 · Problem Statement SIH26011** — *3D ULPIN Generation and Vertical Property
Mapping System*. Ministry of Rural Development, Department of Land Resources (DoLR).
Software category, Space Technology theme, central government.

Idea submission deadline: **20 September 2026**.
Scored Extreme difficulty (76/100), competition opportunity 34/100.

## What is actually being asked

India's land records describe land as a **flat polygon**. That is adequate for a field
and inadequate for a city. Nothing in the current system can uniquely identify:

- an individual apartment on the 7th floor
- basement or podium parking
- an underground water main, cable duct or metro tunnel
- an elevated road, walkway or viaduct
- air rights above a parcel, or the space below it

The PS asks for a 3D cadastre: unique spatial identities for surface parcels,
multi-storey units, and underground infrastructure, built by fusing drone imagery,
LiDAR, GIS parcel layers, floor plans, GNSS/CORS coordinates and DEM/DSM, with AI for
building extraction, floor segmentation, vertical parcel delineation and topology
validation.

## Domain background that is NOT in the problem statement

The PS reads as though 3D cadastre is greenfield. It is not, and knowing this is worth
a lot when presenting.

**ULPIN already exists.** It is the 14-character alphanumeric identifier known as
*Bhu-Aadhaar*, rolled out under DILRMP by this exact department. It is derived from the
parcel centroid's geo-coordinates plus administrative codes. It is strictly 2D: one
parcel, one identifier, no z. Our scheme **extends it and never replaces it** — the
14-char string is preserved as a parent key so every existing record still resolves.

> Verify the exact field layout against DoLR's own ULPIN guidelines before finalising.
> We are confident about the 14-character length; not about every internal field width.

**SVAMITVA** is DoLR's own drone-survey programme for rural inhabited areas, already
issuing property cards at scale. **NAKSHA** is its urban counterpart (drone-based urban
land record survey, piloted across roughly 150 ULBs from early 2025). Both stop at 2D
footprints. The pitch line: *"SVAMITVA already flew the drones and produced a footprint.
We turn that same flight into a stack of ownable volumes."*

**Vertical rights already exist in Indian law.** State Apartment Ownership Acts grant an
exclusive right to the apartment plus an undivided share in the land; RERA defines carpet
area; Mumbai's DCPR 2034 trades air rights as TDR; metro corridors take sub-surface
easements. So the gap is **not legal, it is spatial-registry**: rights are recognised but
never geometrically registered.

Do not claim "India has no vertical ownership law." It is wrong and a judge will catch it.

**Standards to conform to**, and to name explicitly:

| Standard | Why |
|---|---|
| ISO 19152 **LADM** (2nd ed., 2024) | The land administration domain model; explicitly supports 3D spatial units |
| **CityGML 3.0** | 3D city exchange; its space model maps onto our unit types |
| **IFC** | BIM / floor plans |
| **IndoorGML** | units within storeys |

"Interoperable" means nothing on its own. *"Our 3D spatial unit serialises to LADM
`LA_SpatialUnit` with an `LA_BoundaryFaceString` set"* means everything.

**Prior art in working 3D cadastre:** Netherlands (Kadaster, legal 3D parcels),
Queensland and NSW (volumetric lots — the oldest working example), Singapore
(subterranean space), Sweden, Norway, Dubai.

## Team and scope

Six people, six blocks. **This repository contains only our block.**

| Block | Scope | Owner |
|---|---|---|
| P1 | Desktop app shell and review UX | bibisha |
| P2 | Geo data pipeline, CRS and datum harmonisation | soumyadipta |
| P3 | AI detection — building extraction, floor estimation | unassigned |
| **P4** | **3D units, ULPIN, validation → `cadastre/`** | **dhruv, shankhanil** |
| P5 | Cesium + MapLibre viewer components | rudraksha, pragati |
| P6 | Static web app, publish, demo | unassigned |

Repo: `slashexx/groundup`. Other blocks live in their own folders, added by their owners.
Do not scaffold, design, or prescribe implementation for blocks that are not ours.

## What P4 is, in one sentence

Everything upstream produces flat shapes and loose numbers. Everything downstream only
displays and exports. **P4 is the only block that turns shapes into owned volumes with
names, and then proves those volumes are mutually consistent.** It is what makes this a
cadastre rather than a 3D model viewer.
