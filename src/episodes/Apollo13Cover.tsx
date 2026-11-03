import React, { useLayoutEffect, useRef } from "react";
import { AbsoluteFill } from "remotion";
import { CrtOverlay } from "../lib/components";
import { C, PIXEL, TITLE } from "../lib/theme";
import { drawStack, drawTapeRoll, drawMoon } from "../px/apolloObjects";
import { space } from "../px/common";
import { Gfx, H, SCALE, W } from "../px/gfx";
import { drawEarth } from "../px/objects";

/** Miniature : « SAUVÉS PAR / DU SCOTCH », le vaisseau blessé et le rouleau de scotch. */
export const Apollo13Cover: React.FC = () => {
  const ref = useRef<HTMLCanvasElement>(null);
  const bloom = useRef<HTMLCanvasElement>(null);
  useLayoutEffect(() => {
    const g = new Gfx();
    g.fill("#020604");
    space(g, 40, { dx: 20 });
    drawEarth(g, 30, 340, 26, 0.6);
    drawMoon(g, 186, 110, 18, 0.2);
    drawStack(g, 108, 200, 3, 30, 1);
    drawTapeRoll(g, 108, 270, 26, 12, 60);
    const c = ref.current!.getContext("2d")!;
    const img = c.createImageData(W, H);
    img.data.set(new Uint8Array(g.buf.buffer));
    c.putImageData(img, 0, 0);
    const b = bloom.current!.getContext("2d")!;
    b.filter = "brightness(0.75) contrast(2.6)";
    b.drawImage(ref.current!, 0, 0);
  }, []);
  const cs: React.CSSProperties = { position: "absolute", width: W * SCALE, height: H * SCALE, imageRendering: "pixelated" };
  const outline = `0 8px 0 ${C.ink}, 6px 0 0 ${C.ink}, -6px 0 0 ${C.ink}, 0 -6px 0 ${C.ink}`;
  return (
    <AbsoluteFill style={{ backgroundColor: "#020604" }}>
      <canvas ref={ref} width={W} height={H} style={cs} />
      <canvas ref={bloom} width={W} height={H} style={{ ...cs, filter: "blur(16px)", mixBlendMode: "screen", opacity: 0.85 }} />
      <div style={{ position: "absolute", top: 190, width: "100%", textAlign: "center", fontFamily: TITLE }}>
        <div style={{ fontSize: 96, color: C.white, lineHeight: 1, textShadow: outline }}>SAUVÉS PAR</div>
        <div style={{ fontSize: 150, color: C.accent, lineHeight: 1.05, marginTop: 6, textShadow: `${outline}, 0 0 40px ${C.accent}` }}>DU SCOTCH</div>
      </div>
      <div style={{ position: "absolute", left: "50%", top: 1520, translate: "-50% 0", padding: "14px 24px", background: C.ink, border: `4px solid ${C.white}`, color: C.white, fontFamily: PIXEL, fontSize: 40, letterSpacing: 2, whiteSpace: "nowrap" }}>
        APOLLO 13 · 1970
      </div>
      <CrtOverlay />
    </AbsoluteFill>
  );
};
