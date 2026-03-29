import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/analyze": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/suggest": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/autofill": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/login": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/register": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/profile": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/health": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/chat": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/test-ai": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
