import React from "react";
import { Composition, registerRoot } from "remotion";
import { calculateMetadata, Long } from "./Long";
import { FPS } from "../infographie/scenes";
import { LH, LW } from "./scenes";

/**
 * Point d'entrée Remotion du moteur « long » (vidéo 16:9, 1920×1080).
 * Rendu : npx remotion render src/long/index.tsx Long <sortie.mp4> --props='{"id":"<épisode>"}' --public-dir=episodes-b --muted --concurrency=2
 */
const Root: React.FC = () => (
  <Composition id="Long" component={Long} durationInFrames={300} fps={FPS} width={LW} height={LH} defaultProps={{ id: "_demo-long" }} calculateMetadata={calculateMetadata} />
);

registerRoot(Root);
