import React, { useLayoutEffect, useMemo, useRef } from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { Gfx, H, hash, SCALE, W } from "./gfx";

export type SceneCtx = {
  /** image globale */
  f: number;
  /** images depuis le début de la scène */
  t: number;
  /** durée de la scène */
  d: number;
  /** début (local) de la phrase i, fraction de la phrase */
  at: (line: number, frac?: number) => number;
};

export type Transition = "cut" | "pixelate" | "dissolve" | "wipe" | "iris" | "slide";

export type PxScene = {
  name: string;
  from: number;
  to: number;
  draw: (g: Gfx, s: SceneCtx) => void;
  /** transition d'entrée et sa durée */
  tin?: Transition;
  tlen?: number;
};

export type Fx = { shake: number; aberr: number; glitch: number; flash: number; flashColor?: string; zoom: number };

const TRANS_DEFAULT = 10;

const mix = (out: Gfx, a: Gfx, b: Gfx, kind: Transition, p: number, f: number) => {
  const A = a.buf;
  const B = b.buf;
  const O = out.buf;
  if (kind === "pixelate") {
    // première moitié : A se pixelise, seconde : B se dé-pixelise
    const src = p < 0.5 ? A : B;
    const k = p < 0.5 ? p * 2 : (1 - p) * 2;
    const block = Math.max(1, Math.round(1 + k * 14));
    for (let y = 0; y < H; y++)
      for (let x = 0; x < W; x++) {
        const sx = Math.min(W - 1, Math.floor(x / block) * block + (block >> 1));
        const sy = Math.min(H - 1, Math.floor(y / block) * block + (block >> 1));
        O[y * W + x] = src[sy * W + sx];
      }
    return;
  }
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      const i = y * W + x;
      let useB = false;
      if (kind === "dissolve") useB = hash2b(x >> 1, y >> 1) < p;
      else if (kind === "wipe") useB = (x + (H - y) * 0.56) / (W + H * 0.56) < p * 1.08 - (hash2b(x >> 2, y >> 2) * 0.08);
      else if (kind === "iris") useB = Math.hypot(x - W / 2, y - H / 2) < p * 230 + (hash2b(x >> 2, y >> 2) - 0.5) * 6;
      else if (kind === "slide") {
        const off = Math.round(p * W);
        O[i] = x < W - off ? A[y * W + x + off] : B[y * W + x - (W - off)];
        continue;
      } else useB = p >= 0.5;
      O[i] = useB ? B[i] : A[i];
    }
  void f;
};
const hash2b = (x: number, y: number) => hash(x * 12.989 + y * 78.233);

const postFx = (g: Gfx, tmp: Gfx, fx: Fx, f: number) => {
  const S = g.buf;
  if (fx.glitch > 0) {
    tmp.copyFrom(g);
    const T = tmp.buf;
    const bands = 3 + Math.floor(fx.glitch * 6);
    for (let b = 0; b < bands; b++) {
      if (hash(f * 3.1 + b) > fx.glitch + 0.15) continue;
      const y0 = Math.floor(hash(f * 7.3 + b * 11) * H);
      const h = 2 + Math.floor(hash(f * 5.9 + b) * 14);
      const off = Math.round((hash(f * 2.7 + b * 3) - 0.5) * 40 * fx.glitch);
      for (let y = y0; y < Math.min(H, y0 + h); y++)
        for (let x = 0; x < W; x++) S[y * W + x] = T[y * W + Math.min(W - 1, Math.max(0, x - off))];
    }
  }
  if (fx.aberr >= 1) {
    tmp.copyFrom(g);
    const T = tmp.buf;
    const a = Math.round(fx.aberr);
    for (let y = 0; y < H; y++)
      for (let x = 0; x < W; x++) {
        const r = T[y * W + Math.max(0, x - a)] & 0xff;
        const gg = T[y * W + x] & 0xff00;
        const bb = T[y * W + Math.min(W - 1, x + a)] & 0xff0000;
        S[y * W + x] = (0xff000000 | bb | gg | r) >>> 0;
      }
  }
};

/** Toile pixel unique pour toute la vidéo : scènes, transitions, post-effets, halo lumineux. */
export const PixelStage: React.FC<{ scenes: PxScene[]; lineStarts: number[]; fx: (f: number) => Fx; glow?: number }> = ({
  scenes,
  lineStarts,
  fx,
  glow = 0.85,
}) => {
  const f = useCurrentFrame();
  const main = useRef<HTMLCanvasElement>(null);
  const bloom = useRef<HTMLCanvasElement>(null);
  const bufs = useMemo(() => ({ a: new Gfx(), b: new Gfx(), out: new Gfx(), tmp: new Gfx() }), []);
  const e = fx(f);

  useLayoutEffect(() => {
    const idx = scenes.findIndex((s) => f >= s.from && f < s.to);
    const s = scenes[Math.max(0, idx)];
    const ctxFor = (sc: PxScene): SceneCtx => ({
      f,
      t: f - sc.from,
      d: sc.to - sc.from,
      at: (line, frac = 0) => {
        const st = lineStarts[line];
        const en = lineStarts[line + 1] ?? st + 60;
        return Math.round(st + (en - st) * frac) - sc.from;
      },
    });
    const drawInto = (g: Gfx, sc: PxScene) => {
      g.ox = 0;
      g.oy = 0;
      g.fill("#020604");
      sc.draw(g, ctxFor(sc));
      g.ox = 0;
      g.oy = 0;
    };
    const len = s.tlen ?? TRANS_DEFAULT;
    const prev = idx > 0 ? scenes[idx - 1] : null;
    if (prev && s.tin && s.tin !== "cut" && f - s.from < len) {
      drawInto(bufs.a, prev);
      drawInto(bufs.b, s);
      mix(bufs.out, bufs.a, bufs.b, s.tin, (f - s.from + 1) / (len + 1), f);
    } else {
      drawInto(bufs.out, s);
    }
    postFx(bufs.out, bufs.tmp, e, f);

    const c = main.current!.getContext("2d")!;
    const img = c.createImageData(W, H);
    img.data.set(new Uint8Array(bufs.out.buf.buffer));
    c.putImageData(img, 0, 0);
    const b = bloom.current!.getContext("2d")!;
    b.clearRect(0, 0, W, H);
    b.filter = "brightness(0.75) contrast(2.6)";
    b.drawImage(main.current!, 0, 0);
    b.filter = "none";
  }, [f, scenes, lineStarts, bufs, e]);

  const sx = Math.round(((hash(f * 1.7) - 0.5) * 2 * e.shake) / 1) * SCALE;
  const sy = Math.round(((hash(f * 2.3 + 9) - 0.5) * 2 * e.shake) / 1) * SCALE;
  const canvasStyle: React.CSSProperties = {
    position: "absolute",
    left: 0,
    top: 0,
    width: W * SCALE,
    height: H * SCALE,
    imageRendering: "pixelated",
  };
  return (
    <AbsoluteFill style={{ backgroundColor: "#020604", overflow: "hidden" }}>
      <AbsoluteFill style={{ translate: `${sx}px ${sy}px`, scale: String(e.zoom) }}>
        <canvas ref={main} width={W} height={H} style={canvasStyle} />
        <canvas
          ref={bloom}
          width={W}
          height={H}
          style={{ ...canvasStyle, filter: "blur(16px)", mixBlendMode: "screen", opacity: glow }}
        />
      </AbsoluteFill>
      {e.flash > 0 && (
        <AbsoluteFill style={{ backgroundColor: e.flashColor ?? "#f2f0e6", opacity: Math.min(0.9, e.flash), mixBlendMode: "screen" }} />
      )}
    </AbsoluteFill>
  );
};
