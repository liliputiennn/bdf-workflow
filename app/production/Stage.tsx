import { Player, type PlayerRef } from "@remotion/player";
import { useEffect, useMemo, useRef } from "react";
import type { Episode } from "../../server/types";
import type { RegistryEntry } from "../../src/episodes/registry";

export const Stage = ({ entry, ep, onFrame }: { entry: RegistryEntry | undefined; ep: Episode; onFrame: (f: number) => void }) => {
  const ref = useRef<PlayerRef>(null);
  const inputProps = useMemo(
    () => ({ voice: ep.voice.chosen ? `${ep.publicDir}/${ep.voice.chosen}` : "", mix: ep.mix }),
    [ep.publicDir, ep.voice.chosen, ep.mix.music, ep.mix.sfx],
  );
  useEffect(() => {
    const p = ref.current;
    if (!p) return;
    const h = (e: { detail: { frame: number } }) => onFrame(e.detail.frame);
    p.addEventListener("frameupdate", h);
    return () => p.removeEventListener("frameupdate", h);
  }, [entry, onFrame]);
  if (!entry)
    return (
      <div className="stage empty">
        <div>
          <p>Les scènes de cet épisode ne sont pas encore codées.</p>
          <p className="muted">Ouvre l'étape « Scènes » et copie le brief pour Claude.</p>
        </div>
      </div>
    );
  return (
    <div className="stage">
      <div className="player-box">
        <Player
          ref={ref}
          component={entry.component}
          inputProps={inputProps}
          durationInFrames={entry.frames}
          fps={entry.fps}
          compositionWidth={1080}
          compositionHeight={1920}
          controls
          acknowledgeRemotionLicense
          style={{ width: "100%", height: "100%" }}
        />
      </div>
    </div>
  );
};
