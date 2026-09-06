import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const host = process.env.TAURI_DEV_HOST;

// The status bar used to read "Version 1.0.0", written into the JSX. Read the one number
// that is actually shipped instead, so a build can never announce a version it is not.
const { version } = JSON.parse(
  readFileSync(fileURLToPath(new URL("./package.json", import.meta.url)), "utf8"),
);

// https://vite.dev/config/
export default defineConfig(async () => ({
  plugins: [react()],

  define: {
    __APP_VERSION__: JSON.stringify(version),
  },

  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  //
  // 1. prevent Vite from obscuring rust errors
  clearScreen: false,
  // 2. tauri expects a fixed port, fail if that port is not available
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      // 3. tell Vite to ignore watching `src-tauri`
      ignored: ["**/src-tauri/**"],
    },
    // 4. let this app import P5's adapter from ../viewer.
    //
    // The projected-CRS-to-WGS84 conversion is the one piece of geometry logic the
    // desktop app and the published web build must agree on exactly, and P5 already
    // owns it. Copying it here would be a second implementation of the same maths,
    // free to drift; there is no root workspace yet, so this is the narrowest way to
    // share the one that exists. When a workspace lands, this becomes a package import
    // and this allowance goes away.
    fs: { allow: [".", "../viewer"] },
  },
}));
