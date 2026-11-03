import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import type { SpriteDef } from "./sprites";
import { C, CHANNEL, PIXEL, TITLE, rand, stepped, tw } from "./theme";

const abs: React.CSSProperties = { position: "absolute" };

/* ───────── Sprite pixel art, toujours net ───────── */

export const Sprite: React.FC<{
  def: SpriteDef;
  unit: number;
  cx: number;
  cy: number;
  style?: React.CSSProperties;
  flip?: boolean;
}> = ({ def, unit, cx, cy, style, flip }) => (
  <svg
    width={def.w * unit}
    height={def.h * unit}
    viewBox={`0 0 ${def.w} ${def.h}`}
    shapeRendering="crispEdges"
    style={{
      ...abs,
      left: Math.round(cx - (def.w * unit) / 2),
      top: Math.round(cy - (def.h * unit) / 2),
      overflow: "visible",
      scale: flip ? "-1 1" : undefined,
      ...style,
    }}
  >
    {def.cells.map((c, i) => (
      <rect key={i} x={c[0]} y={c[1]} width={c[2]} height={c[3]} fill={c[4]} />
    ))}
  </svg>
);

/* ───────── Fond : noir teinté, poussière, lignes CRT, vignettage ───────── */

export const Backdrop: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{ background: `radial-gradient(90% 60% at 50% 50%, ${C.bgHi}, ${C.bg} 70%, ${C.ink})` }}
    >
      {Array.from({ length: 46 }).map((_, i) => {
        const x = rand(i) * 1080;
        const y = (rand(i + 50) * 1920 - stepped(f, 3) * (0.4 + rand(i + 9) * 0.8) + 1920 * 4) % 1920;
        const s = 4 + Math.floor(rand(i + 3) * 3) * 2;
        return (
          <div
            key={i}
            style={{
              ...abs,
              left: Math.round(x / 2) * 2,
              top: Math.round(y / 2) * 2,
              width: s,
              height: s,
              background: rand(i + 20) > 0.8 ? C.accent : C.white,
              opacity: 0.12 + 0.25 * rand(i * 3 + Math.floor(f / 8)),
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

export const CrtOverlay: React.FC = () => (
  <AbsoluteFill style={{ pointerEvents: "none" }}>
    <AbsoluteFill
      style={{
        background: "repeating-linear-gradient(0deg, rgba(0,0,0,.16) 0px, rgba(0,0,0,.16) 2px, transparent 2px, transparent 6px)",
      }}
    />
    <AbsoluteFill
      style={{ background: "radial-gradient(110% 80% at 50% 50%, transparent 60%, rgba(0,0,0,.65) 100%)" }}
    />
  </AbsoluteFill>
);

/* ───────── HUD permanent ───────── */

/** `tint` : couleurs d'accent d'une palette d'épisode (par défaut, le vert de la chaîne). */
export const Hud: React.FC<{ episode: number; date: string; dateKey: number; tint?: { accent: string; dim: string; deep: string } }> = ({
  episode,
  date,
  dateKey,
  tint = { accent: C.accent, dim: C.accentDim, deep: C.accentDeep },
}) => {
  const f = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const flick = f - dateKey < 8 && Math.floor((f - dateKey) / 2) % 2 === 0;
  const corner = (s: React.CSSProperties): React.CSSProperties => ({
    ...abs,
    width: 44,
    height: 44,
    borderColor: tint.dim,
    borderStyle: "solid",
    borderWidth: 0,
    ...s,
  });
  return (
    <AbsoluteFill style={{ fontFamily: PIXEL }}>
      <div style={corner({ left: 40, top: 40, borderLeftWidth: 4, borderTopWidth: 4 })} />
      <div style={corner({ right: 40, top: 40, borderRightWidth: 4, borderTopWidth: 4 })} />
      <div style={corner({ left: 40, bottom: 40, borderLeftWidth: 4, borderBottomWidth: 4 })} />
      <div style={corner({ right: 40, bottom: 40, borderRightWidth: 4, borderBottomWidth: 4 })} />
      <div style={{ ...abs, left: 72, top: 72, display: "flex", alignItems: "stretch", fontSize: 26, letterSpacing: 2 }}>
        <div style={{ padding: "8px 14px", border: `3px solid ${tint.accent}`, color: tint.accent }}>{CHANNEL}</div>
        <div style={{ padding: "8px 14px", background: tint.accent, color: C.ink, fontWeight: 700 }}>
          N°{String(episode).padStart(2, "0")}
        </div>
      </div>
      <div style={{ ...abs, right: 72, top: 66, textAlign: "right" }}>
        <div style={{ fontSize: 20, color: C.grey, letterSpacing: 3 }}>DOSSIER</div>
        <div style={{ fontSize: 40, color: tint.accent, fontWeight: 700, opacity: flick ? 0.2 : 1 }}>{date}</div>
      </div>
      <div style={{ ...abs, left: 72, top: 150, width: 936, height: 8, background: tint.deep }}>
        <div style={{ width: `${(stepped(f, 6) / durationInFrames) * 100}%`, height: "100%", background: tint.accent }} />
      </div>
    </AbsoluteFill>
  );
};

/* ───────── Sous-titres : une phrase, mot-clé en vert ───────── */

export type CaptionLine = { text: string; hi: string; from: number; to: number; alert?: boolean };

export const Captions: React.FC<{ lines: CaptionLine[] }> = ({ lines }) => {
  const f = useCurrentFrame();
  const line = lines.find((l) => f >= l.from && f < l.to);
  if (!line) return null;
  const local = f - line.from;
  const i = line.text.indexOf(line.hi);
  const parts = i < 0 ? [line.text, "", ""] : [line.text.slice(0, i), line.hi, line.text.slice(i + line.hi.length)];
  return (
    <div
      style={{
        ...abs,
        top: 210,
        left: 70,
        width: 940,
        textAlign: "center",
        fontFamily: TITLE,
        fontSize: 64,
        lineHeight: 1.14,
        color: C.white,
        textShadow: `0 5px 0 ${C.ink}, 4px 0 0 ${C.ink}, -4px 0 0 ${C.ink}, 0 -4px 0 ${C.ink}`,
        translate: `0px ${local < 4 ? 14 - stepped(local, 2) * 4 : 0}px`,
        opacity: local < 2 ? 0.4 : 1,
      }}
    >
      {parts[0]}
      <span style={{ color: line.alert ? C.alert : C.accent }}>{parts[1]}</span>
      {parts[2]}
    </div>
  );
};

/* ───────── Étiquette de donnée, tapée à la machine ───────── */

export const DataLabel: React.FC<{
  text: string;
  at: number;
  x: number;
  y: number;
  color?: string;
  size?: number;
  anchor?: "left" | "center" | "right";
}> = ({ text, at, x, y, color = C.white, size = 30, anchor = "center" }) => {
  const f = useCurrentFrame();
  if (f < at) return null;
  const shown = text.slice(0, Math.floor((f - at) * 2.5) + 1);
  const shift = anchor === "center" ? "-50%" : anchor === "right" ? "-100%" : "0%";
  return (
    <div
      style={{
        ...abs,
        left: x,
        top: y,
        translate: `${shift} -50%`,
        padding: "10px 18px",
        background: C.ink,
        border: `3px solid ${color}`,
        color,
        fontFamily: PIXEL,
        fontSize: size,
        letterSpacing: 2,
        whiteSpace: "nowrap",
      }}
    >
      {shown}
    </div>
  );
};

/* ───────── Chiffre géant qui défile ───────── */

export const fmt = (n: number, dec = 0) =>
  n.toLocaleString("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec }).replace(/\u202f|\u00a0/g, " ");

export const BigCounter: React.FC<{
  from: number;
  to: number;
  at: number;
  dur: number;
  x: number;
  y: number;
  suffix?: string;
  prefix?: string;
  dec?: number;
  size?: number;
  color?: string;
}> = ({ from, to, at, dur, x, y, suffix = "", prefix = "", dec = 0, size = 112, color = C.accent }) => {
  const f = useCurrentFrame();
  if (f < at) return null;
  const v = tw(stepped(f, 2), [at, at + dur], [from, to]);
  return (
    <div
      style={{
        ...abs,
        left: x,
        top: y,
        translate: "-50% -50%",
        fontFamily: PIXEL,
        fontWeight: 700,
        fontSize: size,
        color,
        whiteSpace: "nowrap",
        textShadow: `0 6px 0 ${C.ink}`,
      }}
    >
      {prefix}
      {fmt(v, dec)}
      {suffix}
    </div>
  );
};

/* ───────── Tampon qui claque ───────── */

export const Stamp: React.FC<{
  text: string;
  at: number;
  x: number;
  y: number;
  color?: string;
  size?: number;
  rotate?: number;
}> = ({ text, at, x, y, color = C.alert, size = 92, rotate = -10 }) => {
  const f = useCurrentFrame();
  if (f < at) return null;
  const k = f - at;
  const s = k < 6 ? [2.4, 1.8, 1.3, 1.0, 0.94, 1.0][k] : 1;
  return (
    <div
      style={{
        ...abs,
        left: x,
        top: y,
        translate: "-50% -50%",
        rotate: `${rotate}deg`,
        scale: String(s),
        opacity: k < 1 ? 0.5 : 0.95,
        padding: "8px 26px",
        border: `10px solid ${color}`,
        color,
        fontFamily: TITLE,
        fontSize: size,
        letterSpacing: 4,
        whiteSpace: "nowrap",
        overflow: "hidden",
      }}
    >
      {text}
      {Array.from({ length: 34 }).map((_, i) => (
        <div
          key={i}
          style={{
            ...abs,
            left: `${rand(i + text.length) * 100}%`,
            top: `${rand(i * 7 + 1) * 100}%`,
            width: 4 + rand(i) * 7,
            height: 3 + rand(i + 2) * 4,
            background: C.bg,
            opacity: 0.85,
          }}
        />
      ))}
    </div>
  );
};

/* ───────── Fiche dossier ───────── */

export const DossierCard: React.FC<{
  at: number;
  x: number;
  y: number;
  name: string;
  role: string;
  fromLeft?: boolean;
  children: React.ReactNode;
}> = ({ at, x, y, name, role, fromLeft = true, children }) => {
  const f = useCurrentFrame();
  if (f < at) return null;
  const slide = tw(stepped(f - at, 2), [0, 10], [fromLeft ? -900 : 900, 0]);
  return (
    <div style={{ ...abs, left: x, top: y, width: 860, height: 300, translate: `${slide}px 0px` }}>
      <div style={{ ...abs, left: 0, top: 0, width: 260, height: 36, background: "#c9a86a" }} />
      <div
        style={{
          ...abs,
          left: 0,
          top: 30,
          width: 860,
          height: 270,
          background: "#c9a86a",
          padding: 18,
          boxSizing: "border-box",
        }}
      >
        <div style={{ ...abs, left: 18, top: 18, width: 230, height: 234, background: C.ink, overflow: "hidden" }}>
          {children}
        </div>
        <div style={{ ...abs, left: 280, top: 40, fontFamily: PIXEL, color: C.ink }}>
          <div style={{ fontSize: 22, letterSpacing: 3, opacity: 0.7 }}>NOM</div>
          <div style={{ fontSize: 46, fontWeight: 700, lineHeight: 1.1 }}>{name}</div>
          <div style={{ fontSize: 22, letterSpacing: 3, opacity: 0.7, marginTop: 22 }}>RÔLE</div>
          <div style={{ fontSize: 30, fontWeight: 700, color: C.accentDeep }}>{role}</div>
        </div>
      </div>
    </div>
  );
};

/* ───────── Tremblement d'écran ───────── */

export const Shake: React.FC<{ at: number[]; amp?: number; children: React.ReactNode }> = ({
  at,
  amp = 18,
  children,
}) => {
  const f = useCurrentFrame();
  const k = at.map((a) => f - a).find((d) => d >= 0 && d < 10);
  const a = k === undefined ? 0 : amp * (1 - k / 10);
  return (
    <AbsoluteFill
      style={{
        translate: `${Math.round((rand(f) - 0.5) * 2 * a)}px ${Math.round((rand(f + 99) - 0.5) * 2 * a)}px`,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

/** Affiche ses enfants seulement dans la fenêtre [from, to[ (temps absolu). */
export const Window: React.FC<{ from: number; to: number; children: React.ReactNode }> = ({
  from,
  to,
  children,
}) => {
  const f = useCurrentFrame();
  return f >= from && f < to ? <AbsoluteFill>{children}</AbsoluteFill> : null;
};
