import { createRoot } from "react-dom/client";
import { App } from "./App";
import { API_BASE } from "./config";

// En ligne, les fichiers Remotion (voix, musique, SFX) viennent du PC, jamais d'Internet.
if (API_BASE) window.remotion_staticBase = `${API_BASE}/static`;
import "./theme.css";

createRoot(document.getElementById("root")!).render(<App />);
