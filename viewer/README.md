# viewer — P5 visualization components

MapLibre 2D map + Cesium 3D viewer for groundup's property units: search/filter by
ULPIN, click-to-inspect details panel, floor slice and underground view. Fully offline —
no Cesium Ion, no external tiles.

```bash
pnpm install
pnpm dev        # demo app rendering contracts/fixtures/demo-parcel.json
pnpm build      # production bundle in dist/
```

`src/lib/` is the importable library (used by the demo, later by P1's shell and P6's web
build); `src/lib/adapter.ts` translates the P4 outbound contract (projected-CRS
footprints, datum heights) into display form.

Context, interface and decisions: [`../.claude/blocks/p5-viewer.md`](../.claude/blocks/p5-viewer.md).
Verification recipe: [`.claude/skills/verify/SKILL.md`](.claude/skills/verify/SKILL.md).
