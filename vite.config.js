import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],

  server: {
    port: 5173,
    // Proxy API calls to a local backend during development.
    // Set VITE_API_BASE_URL=/api and point the target at your server.
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET || "http://localhost:8080",
        changeOrigin: true,
      },
    },
  },

  build: {
    outDir: "dist",
    sourcemap: true,
  },

  // Vitest configuration (component + page tests live in ./tests).
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./tests/setup.js",
    css: false,
    include: ["tests/**/*.{test,spec}.{js,jsx}"],
  },
});
