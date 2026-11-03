import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig(({ command }) => ({
  root: path.resolve(__dirname),
  // En local, Vite sert public/ (voix, musique, SFX). Pour la mise en ligne, rien de public/ n'est publié :
  // le lecteur va chercher ces fichiers sur l'API du PC (voir main.tsx).
  // (sauf app/static/ : pages légales publiques, confidentialité et conditions, copiées à la racine du site)
  publicDir: command === "build" ? path.resolve(__dirname, "static") : path.resolve(__dirname, "..", "public"),
  plugins: [react()],
  build: { outDir: path.resolve(__dirname, "..", "dist-console"), emptyOutDir: true, chunkSizeWarningLimit: 4000 },
  server: {
    host: "127.0.0.1",
    port: 5180,
    strictPort: true,
    proxy: { "/api/": "http://127.0.0.1:5181", "/files/": "http://127.0.0.1:5181" },
  },
}));
