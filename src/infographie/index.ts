import React from "react";
import { Composition, registerRoot } from "remotion";
import { calculateMetadata, Short } from "./Short";
import { FPS, H, W } from "./scenes";

/**
 * Point d'entrée Remotion du moteur « infographie » (Shorts 9:16).
 * Rendu : npx remotion render src/infographie/index.ts Short <sortie.mp4> --props='{"id":"<épisode>"}' --public-dir=episodes-b
 */
const Root: React.FC = () =>
  React.createElement(Composition, {
    id: "Short", component: Short, durationInFrames: 300, fps: FPS, width: W, height: H,
    defaultProps: { id: "costco-carte-membre" }, calculateMetadata,
  });

registerRoot(Root);
