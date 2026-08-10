import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Mini App nginx ostida /app/ pathда beriladi (base). Dev'да "/".
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    host: true,
    port: 5178,
    proxy: {
      // Dev tekshiruvи: jonli backendга proksi (secure HTTPS)
      "/api": { target: "https://slotadmin.138.249.248.136.nip.io", changeOrigin: true, secure: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
