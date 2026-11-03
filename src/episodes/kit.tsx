import React from "react";
import { Audio } from "@remotion/media";
import { Sequence, staticFile, useCurrentFrame } from "remotion";
import { C, TITLE, tw } from "../lib/theme";
import type { Fx, PxScene } from "../px/Stage";

/**
 * Le « kit » commun à tous les épisodes : timings, sous-titres mot à mot, effets d'impulsion,
 * sons qui s'effacent sous la voix et musique. Un épisode n'apporte que ses scènes et ses événements.
 */

export const FPS = 30;

export type Word = { w: string; start: number; end: number };
export type Line = { start: number; end: number; words?: Word[] };
export type Timings = { total: number; lines: Line[]; provisional?: boolean };
export type ScriptLine = { text: string; hi: string };
export type Imp = { at: number; dur: number; shake?: number; aberr?: number; glitch?: number; flash?: number; flashColor?: string; zoom?: number };
export type SfxCue = { at: number; name: string; vol?: number };

/** Sons longs (nappes, parasites, alarmes) : très baissés sous la voix. Sons courts : baissés modérément. */
const LONG_SFX = new Set(["static", "static_fm", "riser_cine", "riser_7", "alarm", "alarm_severe", "rocket", "typing", "whoosh_sub", "impact_braam"]);
const WHOOSHES = ["whoosh_cine", "whoosh_short", "whoosh_clean", "whoosh_epic", "glitch_trans"];

export const makeKit = (script: ScriptLine[], timings: Timings, alertLines: number[] = [], accent: string = C.accent) => {
  const T = timings;
  const FRAMES = Math.ceil(T.total * FPS);
  const L = T.lines.map((l) => Math.round(l.start * FPS));
  const at = (i: number, frac = 0) => {
    const st = L[i];
    const en = L[i + 1] ?? st + 60;
    return Math.round(st + (en - st) * frac);
  };

  /** Mots horodatés de chaque phrase (estimés au prorata des lettres si la voix n'est pas encore calée). */
  const WORDS: Word[][] = T.lines.map((l, i) => {
    if (l.words?.length) return l.words;
    const toks = script[i].text.replace("…", " ").split(/\s+/).filter(Boolean);
    const tot = toks.reduce((s, w) => s + w.length + 2, 0);
    let acc = l.start;
    return toks.map((w) => {
      const d = ((l.end - l.start) * (w.length + 2)) / tot;
      const o = { w, start: acc, end: acc + d };
      acc += d;
      return o;
    });
  });

  const speakingAt = (fr: number) => {
    const t = fr / FPS;
    return T.lines.some((l) => t >= l.start - 0.08 && t <= l.end + 0.12);
  };

  /** Impulsions de l'épisode + punch-in sur chaque mot-clé + petit coup d'aberration à chaque changement de scène. */
  const makeFx = (impulses: Imp[], scenes: PxScene[]) => {
    const all = [...impulses];
    WORDS.forEach((ws, i) => {
      const hi = script[i].hi.split(/\s+/)[0].toLowerCase();
      const w = ws.find((x) => x.w.toLowerCase().startsWith(hi.slice(0, Math.max(2, hi.length - 1))));
      if (w) all.push({ at: Math.round(w.start * FPS), dur: 9, zoom: 0.045, aberr: 1.2 });
    });
    scenes.slice(1).forEach((s) => all.push({ at: s.from, dur: 6, aberr: 2 }));
    return (f: number): Fx => {
      const out: Fx = { shake: 0, aberr: 0, glitch: 0, flash: 0, zoom: 1 };
      for (const im of all) {
        const k = f - im.at;
        if (k < 0 || k >= im.dur) continue;
        const e = 1 - k / im.dur;
        out.shake = Math.max(out.shake, (im.shake ?? 0) * e);
        out.aberr = Math.max(out.aberr, (im.aberr ?? 0) * e);
        out.glitch = Math.max(out.glitch, (im.glitch ?? 0) * e);
        if ((im.flash ?? 0) * e * e > out.flash) {
          out.flash = (im.flash ?? 0) * e * e;
          out.flashColor = im.flashColor;
        }
        out.zoom = Math.max(out.zoom, 1 + (im.zoom ?? 0) * e * e);
      }
      out.zoom *= 1 + 0.012 * Math.sin(f / 40);
      return out;
    };
  };

  /** Sous-titres mot à mot, mot-clé en vert (ou en rouge sur les phrases d'alerte). */
  const Captions: React.FC = () => {
    const f = useCurrentFrame();
    const t = f / FPS;
    let i = T.lines.findIndex((l, k) => t >= l.start - 0.05 && t < (T.lines[k + 1]?.start ?? 1e9) - 0.05);
    if (i < 0) i = 0;
    const words = WORDS[i];
    const text = script[i].text;
    const hi = script[i].hi.toLowerCase();
    const hiStart = text.toLowerCase().indexOf(hi);
    let cursor = 0;
    const alert = alertLines.includes(i);
    return (
      <div
        style={{
          position: "absolute",
          top: 205,
          left: 60,
          width: 960,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          columnGap: 18,
          rowGap: 4,
          fontFamily: TITLE,
          fontSize: 68,
          lineHeight: 1.12,
        }}
      >
        {words.map((w, k) => {
          const pos = text.indexOf(w.w, cursor);
          cursor = pos >= 0 ? pos + w.w.length : cursor;
          const isHi = hiStart >= 0 && pos >= hiStart && pos < hiStart + hi.length;
          const age = f - Math.round(w.start * FPS);
          const pop = age < 0 ? 0 : age < 4 ? [1.2, 1.08, 1.02, 1][age] : 1;
          const color = isHi ? (alert ? C.alert : accent) : C.white;
          return (
            <span
              key={k}
              style={{
                display: "inline-block",
                opacity: age >= 0 ? 1 : 0,
                scale: String(pop),
                color,
                textShadow: `0 6px 0 ${C.ink}, 5px 0 0 ${C.ink}, -5px 0 0 ${C.ink}, 0 -5px 0 ${C.ink}, 4px 4px 0 ${C.ink}, -4px 4px 0 ${C.ink}${isHi ? `, 0 0 26px ${color}` : ""}`,
              }}
            >
              {w.w}
            </span>
          );
        })}
      </div>
    );
  };

  const Sfx: React.FC<{ at: number; name: string; volume?: number; gain?: number }> = ({ at: a, name, volume = 1, gain = 1 }) =>
    a < 0 ? null : (
      <Sequence from={a} durationInFrames={10 * FPS} layout="none">
        <Audio src={staticFile(`fx/${name}.wav`)} volume={(fr) => gain * volume * (speakingAt(a + fr) ? (LONG_SFX.has(name) ? 0.22 : 0.45) : 1)} />
      </Sequence>
    );

  /** Un whoosh avant chaque changement de scène, un petit glitch sur les transitions pixel. */
  const transitionSfx = (scenes: PxScene[]): SfxCue[] => [
    ...scenes.slice(1).map((s, i) => ({ at: s.from - 4, name: WHOOSHES[i % WHOOSHES.length], vol: 0.55 })),
    ...scenes.slice(1).filter((s) => s.tin === "pixelate").map((s) => ({ at: s.from, name: "glitch_sfx", vol: 0.3 })),
  ];

  /** Musique : pré-baissée sous la voix (le mixage final la compresse en plus par la voix). */
  const musicVolume = (fr: number) => {
    const base = speakingAt(fr) ? 0.3 : 0.42;
    return base * tw(fr, [0, 15], [0, 1]) * tw(fr, [FRAMES - 45, FRAMES], [1, 0]);
  };

  return { T, FRAMES, L, at, WORDS, speakingAt, makeFx, Captions, Sfx, transitionSfx, musicVolume };
};
