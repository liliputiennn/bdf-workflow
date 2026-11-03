import React, { useLayoutEffect, useRef } from "react";
import { AbsoluteFill } from "remotion";
import { CrtOverlay } from "../lib/components";
import { C, PIXEL, TITLE } from "../lib/theme";
import { Gfx, H, SCALE, W } from "../px/gfx";
import { dataBackdrop } from "./backdrops";
import { drawIcon } from "./icons";
import { PALS } from "./palettes";
import type { ScenesFile } from "./schema";

/** Couverture tirée du scenes.json : titre sur 2 lignes, héros pixel, étiquette de donnée. */
export const makeDataCover = (scenes: ScenesFile): React.FC => {
  const pal = PALS[scenes.palette];
  const { haut, bas, heros, etiquette } = scenes.couverture;
  const Cover: React.FC = () => {
    const ref = useRef<HTMLCanvasElement>(null);
    const bloom = useRef<HTMLCanvasElement>(null);
    useLayoutEffect(() => {
      const g = new Gfx();
      dataBackdrop(g, 40, pal);
      g.glow(108, 250, 70, pal.accent, 0.35);
      drawIcon(g, heros, 108, 250, 9, 20, pal);
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
    const big = bas.length > 10 ? 120 : 150;
    return (
      <AbsoluteFill style={{ backgroundColor: pal.sky[0] }}>
        <canvas ref={ref} width={W} height={H} style={cs} />
        <canvas ref={bloom} width={W} height={H} style={{ ...cs, filter: "blur(16px)", mixBlendMode: "screen", opacity: pal.light ? 0.2 : 0.85 }} />
        <div style={{ position: "absolute", top: 190, width: "100%", textAlign: "center", fontFamily: TITLE }}>
          <div style={{ fontSize: haut.length > 12 ? 80 : 96, color: C.white, lineHeight: 1, textShadow: outline }}>{haut.toUpperCase()}</div>
          <div style={{ fontSize: big, color: pal.accent, lineHeight: 1.05, marginTop: 6, textShadow: `${outline}, 0 0 40px ${pal.accent}` }}>{bas.toUpperCase()}</div>
        </div>
        <div
          style={{
            position: "absolute", left: "50%", top: 1520, translate: "-50% 0", padding: "14px 24px", background: C.ink,
            border: `4px solid ${C.white}`, color: C.white, fontFamily: PIXEL, fontSize: 40, letterSpacing: 2, whiteSpace: "nowrap",
          }}
        >
          {etiquette.toUpperCase()}
        </div>
        <CrtOverlay />
      </AbsoluteFill>
    );
  };
  return Cover;
};
