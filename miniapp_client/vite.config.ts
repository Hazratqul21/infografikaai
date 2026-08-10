import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Mijoz Mini App'i. Admin ilovasidan ALOHIDA quriladi va alohida beriladi.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    host: true,
    port: 5179,                    // admin 5178 — to'qnashmasin
    proxy: {
      // Dev: lokal superapp backendiga (uvicorn 127.0.0.1:8100)
      "/api": { target: "http://127.0.0.1:8100", changeOrigin: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
