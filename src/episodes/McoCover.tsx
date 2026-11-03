import React, { useLayoutEffect, useRef } from "react";
import { AbsoluteFill } from "remotion";
import { CrtOverlay, Stamp } from "../lib/components";
import { C, PIXEL, TITLE } from "../lib/theme";
import { space } from "../px/common";
import { Gfx, H, SCALE, W } from "../px/gfx";
import { drawMars, drawProbe } from "../px/objects";
import { particles } from "../px/common";

/** Miniature de la grille de profil : titre 2 lignes, la sonde qui s'embrase, une étiquette. */
export const McoCover: React.FC = () => {
  const ref = useRef<HTMLCanvasElement>(null);
  const bloom = useRef<HTMLCanvasElement>(null);
  useLayoutEffect(() => {
    const g = new Gfx();
    g.fill("#020604");
    space(g, 40, { dx: 30 });
    g.glow(30, 40, 50, "#ffc23d", 0.25);
    drawMars(g, 108, 560, 230, 0.2);
    particles(g, 60, { seed: 3, x: 98, y: 245, rate: 3, life: 22, vx: -0.6, vy: -1.6, spread: 0.6, ramp: ["#fff2b0", "#ffc23d", "#ff7a00", "#c24400", "#6e1d00"], size: 2, grow: 0.1 });
    drawProbe(g, 112, 215, 3, 40, 0.75);
    g.glow(112, 245, 40, "#ff7a00", 0.4);
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
        <div style={{ fontSize: 96, color: C.white, lineHeight: 1, textShadow: outline }}>327 MILLIONS</div>
        <div style={{ fontSize: 158, color: C.accent, lineHeight: 1.05, marginTop: 6, textShadow: `${outline}, 0 0 40px ${C.accent}` }}>PERDUS</div>
      </div>
      <Stamp text="DÉTRUITE" at={-10} x={540} y={1330} size={120} />
      <div style={{ position: "absolute", left: "50%", top: 1500, translate: "-50% 0", padding: "14px 24px", background: C.ink, border: `4px solid ${C.white}`, color: C.white, fontFamily: PIXEL, fontSize: 40, letterSpacing: 2, whiteSpace: "nowrap" }}>
        LIVRES-FORCE ≠ NEWTONS
      </div>
      <CrtOverlay />
    </AbsoluteFill>
  );
};
