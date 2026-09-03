# Verify p6-web

Build + serve:

```bash
pnpm build && pnpm preview --port 4199   # production; dev: pnpm dev --port 5199
```

Drive with playwright-core against installed Chrome (no browser download):

```js
import { chromium } from 'playwright-core'
const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true,
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'], // WebGL in headless
})
```

The drive script must live inside this package dir (ESM resolution of playwright-core).

Flows worth driving:
- Wait for `.p6-web3d canvas`, then ~4.5s for Cesium zoomTo to settle.
- Search: fill `.p5-search`, press Enter → `.p5-ulpin` shows the match; both viewers highlight.
- 3D pick: click center of `.p6-web3d canvas` → panel updates.
- Slice/underground: click `text=Floor slice` / `text=Underground view`; the range input is
  React-controlled — set via native value setter + `dispatchEvent(new Event('input', {bubbles:true}))`.
- Offline proof: `page.on('request')` — anything not `localhost` or same-origin `blob:` is a failure.
- Empty states: garbage search + Enter → `.p5-panel-empty`; all status chips off → both viewers empty.

Gotchas:
- In dev, `window.__p5map` exposes the MapLibre instance (`isStyleLoaded()`,
  `querySourceFeatures('units')`, `getFilter('units-fill')`) — first stop when the 2D pane is blank.
- A blank 2D pane with background rendered = style stalled on source/worker load, not GL failure.
- maplibre-gl must stay on v5: v6 splits the worker into `maplibre-gl-worker.mjs` which 404s
  under Vite prebundling/build (style never fires `load`). Don't upgrade without solving that.
- After changing deps, restart `pnpm dev` (stale prebundle keeps serving the old package).
