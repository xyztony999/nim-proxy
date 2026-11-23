import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served under /admin by the backend (Workers static assets / server StaticFiles).
export default defineConfig({
  base: "/admin/",
  plugins: [react()],
  build: { outDir: "dist", sourcemap: false },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});
