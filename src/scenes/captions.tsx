import React from "react";
import { useCurrentFrame } from "remotion";
import { C, TITLE } from "../lib/theme";
import type { ScriptLine, Timings, Word } from "../episodes/kit";
import { chunkWords } from "./plan";

/**
 * Sous-titres « TikTok » : 2 à 3 mots à la fois, très gros, en majuscules ; chaque mot apparaît
 * quand il est dit, le mot-clé de la phrase en vert. Un nouveau groupe rebondit en arrivant.
 */

const FPS = 30;
const norm = (s: string) =>
  s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/g, "");

export const makeChunkCaptions = (script: ScriptLine[], T: Timings, words: Word[][], accent: string, alertLines: number[]) => {
  const chunks = chunkWords(words, T.lines);
  const hiWords = script.map((l) => new Set(l.hi.split(/\s+/).map(norm).filter(Boolean)));
  const Captions: React.FC = () => {
    const f = useCurrentFrame();
    const t = f / FPS;
    const c = chunks.find((x) => t >= x.start - 0.04 && t < x.end);
    if (!c) return null;
    const age = f - Math.round(c.start * FPS);
    const pop = age < 5 ? [1.28, 1.14, 1.04, 0.98, 1][Math.max(0, age)] : 1;
    const alert = alertLines.includes(c.line);
    return (
      <div
        style={{
          position: "absolute", top: 300, left: 50, width: 980, translate: "0 -50%", scale: String(pop),
          display: "flex", flexWrap: "wrap", justifyContent: "center", columnGap: 22, rowGap: 0,
          fontFamily: TITLE, fontSize: 104, lineHeight: 1.04, textTransform: "uppercase",
        }}
      >
        {c.words.map((w, k) => {
          const on = f >= Math.round(w.start * FPS) - 1;
          const hi = hiWords[c.line].has(norm(w.w));
          const color = hi ? (alert ? C.alert : accent) : C.white;
          return (
            <span
              key={k}
              style={{
                display: "inline-block", opacity: on ? 1 : 0.18, color,
                textShadow: `0 9px 0 ${C.ink}, 7px 0 0 ${C.ink}, -7px 0 0 ${C.ink}, 0 -7px 0 ${C.ink}, 6px 6px 0 ${C.ink}, -6px 6px 0 ${C.ink}${hi ? `, 0 0 30px ${color}` : ""}`,
              }}
            >
              {w.w}
            </span>
          );
        })}
      </div>
    );
  };
  return Captions;
};
