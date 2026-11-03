import React from "react";
import { useCurrentFrame } from "remotion";
import { C, PIXEL, TITLE, tw } from "../lib/theme";
import type { Pal } from "./palettes";

/** Briques d'affichage (texte net au-dessus du pixel art), partagées par tous les types de scène. */

const abs: React.CSSProperties = { position: "absolute" };

/** La police pixel (Silkscreen) n'a pas le signe € : on l'écrit avec la police des titres. */
export const euro = (node: React.ReactNode): React.ReactNode =>
  typeof node === "string" && node.includes("€")
    ? node.split("€").flatMap((part, i) => (i ? [<span key={i} style={{ fontFamily: TITLE }}>€</span>, part] : [part]))
    : node;
export const outline = (px = 6) => `0 ${px}px 0 ${C.ink}, ${px - 1}px 0 0 ${C.ink}, -${px - 1}px 0 0 ${C.ink}, 0 -${px - 1}px 0 ${C.ink}`;

/** Rebond d'apparition : échelle, opacité, petit glissement. */
export const usePop = (at: number, from: "up" | "down" | "left" | "right" | "none" = "up") => {
  const f = useCurrentFrame();
  const k = f - at;
  if (k < 0) return null;
  const s = k < 7 ? [0.5, 0.85, 1.12, 1.08, 1.03, 1.01, 1][k] : 1;
  const d = tw(k, [0, 8], [1, 0]) * 60;
  const [dx, dy] = { up: [0, d], down: [0, -d], left: [-d, 0], right: [d, 0], none: [0, 0] }[from];
  return { scale: String(s), translate: `calc(-50% + ${dx}px) calc(-50% + ${dy}px)`, opacity: Math.min(1, k / 3 + 0.3) } as React.CSSProperties;
};

/** Encadré de texte (le « cadre arrondi » des vidéos de référence), qui s'adapte au fond clair. */
export const Card: React.FC<{
  at: number;
  x: number;
  y: number;
  pal: Pal;
  children: React.ReactNode;
  size?: number;
  width?: number;
  hot?: boolean;
  from?: "up" | "down" | "left" | "right" | "none";
  font?: "title" | "pixel";
  color?: string;
}> = ({ at, x, y, pal, children, size = 46, width, hot, from = "up", font = "title", color }) => {
  const pop = usePop(at, from);
  if (!pop) return null;
  const bg = pal.light ? "#fffaf0" : C.ink;
  const fg = color ?? (pal.light ? C.ink : C.white);
  return (
    <div
      style={{
        ...abs,
        left: x,
        top: y,
        ...pop,
        width,
        maxWidth: 940,
        padding: font === "pixel" ? "12px 20px" : "18px 28px",
        background: hot ? pal.accent : bg,
        color: hot ? C.ink : fg,
        border: `5px solid ${pal.light ? C.ink : pal.accent}`,
        borderRadius: font === "title" ? 22 : 0,
        boxShadow: `8px 8px 0 ${pal.light ? "#00000033" : pal.deep}`,
        fontFamily: font === "title" ? TITLE : PIXEL,
        fontSize: size,
        lineHeight: 1.12,
        letterSpacing: font === "pixel" ? 2 : 0,
        textAlign: "center",
        textWrap: "balance",
      }}
    >
      {font === "pixel" ? euro(children) : children}
    </div>
  );
};

/** Grand texte détouré (chiffre, titre). */
export const Big: React.FC<{ at: number; x: number; y: number; size: number; color: string; children: React.ReactNode; from?: "up" | "down" | "none" }> = ({
  at,
  x,
  y,
  size,
  color,
  children,
  from = "none",
}) => {
  const pop = usePop(at, from);
  if (!pop) return null;
  return (
    <div style={{ ...abs, left: x, top: y, ...pop, fontFamily: TITLE, fontSize: size, color, whiteSpace: "nowrap", lineHeight: 1, textShadow: `${outline(8)}, 0 0 36px ${color}66` }}>
      {children}
    </div>
  );
};

/** Bulle de dialogue avec texte qui se tape lettre par lettre. */
export const Bubble: React.FC<{ at: number; x: number; y: number; text: string; pal: Pal; tail?: "left" | "right" | "down" }> = ({ at, x, y, text, pal, tail = "down" }) => {
  const f = useCurrentFrame();
  const pop = usePop(at, "none");
  if (!pop) return null;
  const n = Math.floor(Math.max(0, f - at - 4) * 1.6);
  const shown = text.slice(0, n);
  return (
    <div style={{ ...abs, left: x, top: y, ...pop, width: 820 }}>
      <div
        style={{
          position: "relative",
          padding: "26px 34px",
          background: "#fffaf0",
          color: C.ink,
          border: `6px solid ${C.ink}`,
          borderRadius: 28,
          boxShadow: `10px 10px 0 ${pal.light ? "#00000033" : pal.deep}`,
          fontFamily: TITLE,
          fontSize: 50,
          lineHeight: 1.15,
          textAlign: "center",
        }}
      >
        <span>{shown}</span>
        <span style={{ opacity: 0 }}>{text.slice(shown.length)}</span>
        <div
          style={{
            ...abs,
            width: 44,
            height: 44,
            background: "#fffaf0",
            borderRight: `6px solid ${C.ink}`,
            borderBottom: `6px solid ${C.ink}`,
            rotate: "45deg",
            ...(tail === "down" ? { left: "50%", bottom: -27, marginLeft: -22 } : tail === "left" ? { left: 90, bottom: -27 } : { right: 90, bottom: -27 }),
          }}
        />
      </div>
    </div>
  );
};

/** Petite pastille (numéro, « VS », date). */
export const Badge: React.FC<{ at: number; x: number; y: number; pal: Pal; children: React.ReactNode; size?: number; round?: boolean }> = ({ at, x, y, pal, children, size = 44, round }) => {
  const pop = usePop(at, "none");
  if (!pop) return null;
  return (
    <div
      style={{
        ...abs,
        left: x,
        top: y,
        ...pop,
        minWidth: size * 1.6,
        height: size * 1.6,
        padding: "0 14px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: round ? 999 : 8,
        background: pal.accent,
        color: C.ink,
        border: `5px solid ${C.ink}`,
        fontFamily: PIXEL,
        fontWeight: 700,
        fontSize: size,
        whiteSpace: "nowrap",
      }}
    >
      {euro(children)}
    </div>
  );
};
