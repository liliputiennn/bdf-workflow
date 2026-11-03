import React from "react";
import type { Theme } from "./themes";

export const ICONES = ["carte", "hotdog", "magasin", "pieces", "panier"] as const;
export type Icone = (typeof ICONES)[number];

/** Icônes vectorielles simples (viewBox 200×200), colorées par le thème. */
export const Icon: React.FC<{ nom: Icone; th: Theme; size?: number }> = ({ nom, th, size = 420 }) => {
  const s = { width: size, height: size } as const;
  switch (nom) {
    case "carte":
      return (
        <svg {...s} viewBox="0 0 200 200">
          <rect x="10" y="40" width="180" height="120" rx="18" fill={th.accent} />
          <rect x="10" y="62" width="180" height="22" fill={th.deep} opacity=".55" />
          <rect x="28" y="104" width="36" height="28" rx="6" fill={th.hot} />
          <rect x="78" y="108" width="84" height="8" rx="4" fill={th.onAccent} opacity=".85" />
          <rect x="78" y="124" width="52" height="8" rx="4" fill={th.onAccent} opacity=".6" />
        </svg>
      );
    case "hotdog":
      return (
        <svg {...s} viewBox="0 0 200 200">
          <rect x="8" y="70" width="184" height="64" rx="32" fill="#E8B063" />
          <rect x="22" y="84" width="156" height="36" rx="18" fill="#CF4B34" />
          <path d="M34 102 l16 -9 16 18 16 -18 16 18 16 -18 16 18 16 -18 16 18" stroke={th.hot} strokeWidth="7" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "magasin":
      return (
        <svg {...s} viewBox="0 0 200 200">
          <rect x="22" y="78" width="156" height="96" rx="8" fill={th.card} stroke={th.line} strokeWidth="4" />
          <path d="M14 78 L30 30 H170 L186 78 Z" fill={th.accent} />
          <path d="M14 78 h172 v14 q-14 14 -28 0 q-14 14 -28 0 q-14 14 -28 0 q-14 14 -28 0 q-14 14 -28 0 q-14 14 -28 0 z" fill={th.deep} />
          <rect x="84" y="118" width="32" height="56" rx="4" fill={th.deep} />
          <rect x="36" y="112" width="34" height="34" rx="4" fill={th.line} />
          <rect x="130" y="112" width="34" height="34" rx="4" fill={th.line} />
        </svg>
      );
    case "pieces":
      return (
        <svg {...s} viewBox="0 0 200 200">
          {[[70, 130], [120, 112], [92, 82]].map(([x, y], i) => (
            <g key={i}>
              <circle cx={x} cy={y} r="44" fill={th.hot} stroke={th.deep} strokeWidth="5" opacity={0.95 - i * 0.05} />
              <circle cx={x} cy={y} r="30" fill="none" stroke={th.deep} strokeWidth="3" opacity=".5" />
              <text x={x} y={y + 14} textAnchor="middle" fontSize="40" fontWeight="700" fill={th.deep} fontFamily="sans-serif">$</text>
            </g>
          ))}
        </svg>
      );
    case "panier":
      return (
        <svg {...s} viewBox="0 0 200 200">
          <path d="M12 40 h28 l22 90 h98 l18 -64 H54" fill="none" stroke={th.muted} strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M60 76 H174 l-14 50 H72 Z" fill={th.line} />
          <circle cx="84" cy="158" r="12" fill={th.muted} />
          <circle cx="146" cy="158" r="12" fill={th.muted} />
        </svg>
      );
  }
};
