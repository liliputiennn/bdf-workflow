import React from "react";
import { registerRoot, Still } from "remotion";
import { calculateMetadata, H, MiniatureView, W } from "./Miniature";

/**
 * Point d'entrée Remotion des miniatures YouTube (1280×720).
 * Rendu : npx remotion still src/miniature/index.ts Miniature <sortie.png> --props=<fichier.json> --public-dir=episodes-b
 * (props : { "id": "<épisode>", "style"?, "theme"?, "miniature"?, "masque"? } — voir autopilot/miniature.py)
 */
const Root: React.FC = () =>
  React.createElement(Still, {
    id: "Miniature", component: MiniatureView, width: W, height: H,
    defaultProps: { id: "costco-carte-membre" }, calculateMetadata,
  });

registerRoot(Root);
