# Trivandrum pilot data

## What is real

**`buildings.geojson`** — 910 building footprints cut from Microsoft's Global ML
Building Footprints (quadkey `123321123`, 2026-08-13 release), central Trivandrum,
76.943-76.949E 8.493-8.499N, roughly 660 x 660 m. WGS84. Median footprint 123 m2.

## What is not real, and why

**`parcels.geojson`** — a single rectangle covering the cut, standing in for the ward.
It is not surveyed cadastre.

Kerala's Bhunaksha portal has the real parcel geometry, and `index.json` lists the eight
Thiruvananthapuram taluk villages with their bounding boxes. But those extents are in a
**local grid with no published projection**: a sample corner reads `7103300, 3779839`,
which matches no standard CRS for the area (checked against EPSG 3857, 32643, 24378,
7755, 7756, 24343, 24373). The extents themselves are sensible - 2.6 x 3.0 km for a
village - so the units are almost certainly metres about an unknown origin. Without that
origin the parcels cannot be placed against the footprints, so they are not used here.

**Elevation** — generated. Microsoft's footprints carry a `height` property, but for
India it is `-1.0` on **every** building: 0 of 227,943 in the Trivandrum tile, 0 of
52,055 in the neighbouring one. There is no vertical data in that dataset for this
country.

The real source would be **TALD** (Thiruvananthapuram Airborne LiDAR dataset, IIST), which
is available on request from Dr Anandakumar M Ramiya. Until that arrives, heights are
synthesised - and everything derived from them is marked `created_by: derived` with the
synthetic source recorded as `provider: generated - not a survey`.

## Regenerating

    python sidecar/cadastre/tools/make_trivandrum_project.py data/trivandrum/pilot.gpkg
