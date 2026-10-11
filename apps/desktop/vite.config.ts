/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { engineBridge } from "./vite-engine-bridge";

// Tauri loads the dev server from a fixed port, so fail rather than pick another.
export default defineConfig({
  plugins: [react(), engineBridge()],
  clearScreen: false,
  server: { port: 1420, strictPort: true, watch: { ignored: ["**/src-tauri/**"] } },
  envPrefix: ["VITE_", "TAURI_ENV_"],
  build: { target: "es2022" },
  test: { environment: "node" },
});
