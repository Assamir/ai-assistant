import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** `resources/` (VRM + ikona buildera) kopiuje się na root dist / serwera dev — `./model.vrm` obok `index.html`. */
export default defineConfig({
  plugins: [react()],
  root: ".",
  base: "./",
  publicDir: "resources",
  build: { outDir: "dist", emptyOutDir: true },
});
