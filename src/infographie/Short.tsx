import React from "react";
import { AbsoluteFill, staticFile, useCurrentFrame, type CalculateMetadataFunction } from "remotion";
import { Audio } from "@remotion/media";
import { Anneau, Barres, Chiffre, Courbe, Duel, ease, FPS, H, Liste, LigneTemps, Objet, Question, SceneClock, TitreGeant, W } from "./scenes";
import { Backdrop } from "./fx";
import { affiche, decoupe } from "./nombres";
import { getTheme, UI } from "./themes";
import type { Episode, Scene, ShortProps, Timings } from "./types";

/** Pause laissée après la dernière parole (boucle de fin, appel à l'abonnement). */
const TAIL = 36;
/** Durée de la transition poussée entre deux scènes, en images. */
const TR = 10;

export const calculateMetadata: CalculateMetadataFunction<ShortProps> = async ({ props }) => {
  const [episode, timings] = await Promise.all([
    fetch(staticFile(`${props.id}/episode.json`)).then((r) => r.json() as Promise<Episode>),
    fetch(staticFile(`${props.id}/timings.json`)).then((r) => r.json() as Promise<Timings>),
  ]);
  return { durationInFrames: Math.ceil(timings.total * FPS) + TAIL, fps: FPS, width: W, height: H, props: { ...props, episode, timings } };
};

const lineStart = (t: Timings, phrase: number) => t.lines[Math.min(phrase - 1, t.lines.length - 1)].start;

const SceneView: React.FC<{ s: Scene; l: number; th: ReturnType<typeof getTheme>; words: Timings["lines"][number]["words"]; t: number }> = ({ s, l, th, words, t }) => {
  const c = { l, th, words, t };
  return (
    <SceneClock.Provider value={l}>
      {(() => {
        switch (s.type) {
          case "titre-geant": return <TitreGeant {...c} p={s.params as never} />;
          case "chiffre": return <Chiffre {...c} p={s.params as never} />;
          case "barres": return <Barres {...c} p={s.params as never} />;
          case "courbe": return <Courbe {...c} p={s.params as never} />;
          case "ligne-temps": return <LigneTemps {...c} p={s.params as never} />;
          case "anneau": return <Anneau {...c} p={s.params as never} />;
          case "duel": return <Duel {...c} p={s.params as never} />;
          case "objet": return <Objet {...c} p={s.params as never} />;
          case "question": return <Question {...c} p={s.params as never} />;
          case "liste": return <Liste {...c} p={s.params as never} />;
        }
      })()}
    </SceneClock.Provider>
  );
};

type Th = ReturnType<typeof getTheme>;

/** Thème d'une scène : le sien, sinon le thème de contraste pour les gros sous-titres, sinon celui de l'épisode. */
const themeDe = (ep: Episode, s: Scene): Th => getTheme(s.theme ?? (s.type === "titre-geant" && ep.theme_accent ? ep.theme_accent : ep.theme));

export const Short: React.FC<ShortProps> = ({ id, episode, timings }) => {
  const f = useCurrentFrame();
  if (!episode || !timings) return null;
  const t = f / FPS;

  const sceneAt = (tt: number) => {
    let k = 0;
    episode.scenes.forEach((s, j) => { if (tt >= lineStart(timings, s.phrase) - 0.02) k = j; });
    return k;
  };
  const lineAt = (tt: number) => {
    let k = 0;
    timings.lines.forEach((ln, j) => { if (tt >= ln.start - 0.02) k = j; });
    return k;
  };
  const startF = (k: number) => Math.round(lineStart(timings, episode.scenes[k].phrase) * FPS);

  const si = sceneAt(t);
  const scene = episode.scenes[si];
  const l = f - startF(si);
  const line = timings.lines[lineAt(t)];
  // à l'écran : nombres en chiffres, puis morceaux courts (un seul affiché à la fois, celui qu'on entend)
  const mots = affiche(line.words);
  const morceaux = decoupe(mots);
  const ck = morceaux.reduce((acc, c, k) => (t >= c[0].start - 0.02 ? k : acc), 0);
  const morceau = morceaux[ck];
  const morceauF = f - Math.round(morceau[0].start * FPS);
  const giant = scene.type === "titre-geant";
  const th = themeDe(episode, scene);
  const prevTh = si > 0 ? themeDe(episode, episode.scenes[si - 1]) : th;

  // transition poussée : la scène précédente sort pendant que la nouvelle entre, en sens alternés
  const dir = si % 2 ? 1 : -1;
  const enter = ease(l, 0, TR);
  const showPrev = si > 0 && l < TR + 2;
  const prevT = (startF(si) - 1) / FPS;
  const prevLine = timings.lines[lineAt(prevT)];
  const camera = 1 + Math.min(l, 150) * 0.0005;

  return (
    <AbsoluteFill style={{ background: th.bg[0], fontFamily: UI, overflow: "hidden" }}>
      <Backdrop th={th} f={f} w={W} h={H} />
      {/* changement de thème entre deux scènes : l'ancien fond se fond dans le nouveau */}
      {showPrev && prevTh.id !== th.id && <Backdrop th={prevTh} f={f} w={W} h={H} opacity={1 - enter} />}

      {/* en-tête : chaîne + progression par scène */}
      <div style={{ position: "absolute", left: 60, top: 78, display: "flex", alignItems: "center", gap: 18 }}>
        <div style={{ width: 26, height: 26, borderRadius: 8, background: th.accent, boxShadow: `0 0 ${18 + 10 * Math.sin(f / 9)}px ${th.accent}` }} />
        <div style={{ fontSize: 34, fontWeight: 700, letterSpacing: 6, color: th.ink, textTransform: "uppercase" }}>{episode.chaine}</div>
      </div>
      <div style={{ position: "absolute", left: 60, right: 60, top: 150, display: "flex", gap: 8 }}>
        {episode.scenes.map((_, k) => (
          <div key={k} style={{ flex: 1, height: 8, borderRadius: 4, background: th.line, overflow: "hidden" }}>
            <div style={{ width: k < si ? "100%" : k === si ? `${ease(l, 0, 24) * 100}%` : "0%", height: "100%", background: th.accent, boxShadow: `0 0 12px ${th.accent}` }} />
          </div>
        ))}
      </div>

      {/* caméra : respiration lente + léger roulis, la scène entière bouge ensemble */}
      <AbsoluteFill style={{ transform: `scale(${camera}) rotate(${Math.sin(f / 70) * 0.3}deg)`, transformOrigin: "50% 45%" }}>
        {showPrev && (
          <AbsoluteFill key={`p${si}`} style={{ opacity: 1 - enter, transform: `translateX(${-dir * enter * 160}px) scale(${1 - 0.07 * enter})`, filter: `blur(${enter * 16}px)` }}>
            <SceneView s={episode.scenes[si - 1]} l={f - startF(si - 1)} th={prevTh} words={affiche(prevLine.words)} t={prevT} />
          </AbsoluteFill>
        )}
        <AbsoluteFill key={si} style={{ opacity: ease(l, 0, 6), transform: `perspective(1800px) translateX(${(1 - enter) * dir * 180}px) scale(${1.08 - 0.08 * enter}) rotateY(${(1 - enter) * dir * -7}deg)`, filter: `blur(${(1 - enter) * 14}px)` }}>
          <SceneView s={scene} l={l} th={th} words={mots} t={t} />
        </AbsoluteFill>
      </AbsoluteFill>

      {/* éclair de couleur au changement de scène */}
      {si > 0 && l < 14 && (
        <div style={{ position: "absolute", top: -200, bottom: -200, width: 190, left: `${(dir > 0 ? ease(l, 0, 12, 120, -25) : ease(l, 0, 12, -25, 120))}%`, transform: "skewX(-16deg)", background: `linear-gradient(90deg, transparent, ${th.accent}, ${th.hot}, transparent)`, opacity: 0.9 * (1 - l / 14), filter: "blur(6px)", pointerEvents: "none" }} />
      )}

      {/* sous-titres : bandeau sauf quand les gros mots font office de sous-titres */}
      {!giant && (
        <div style={{ position: "absolute", left: 50, right: 50, bottom: 330, display: "flex", justifyContent: "center", opacity: ease(morceauF, 0, 4), transform: `translateY(${ease(morceauF, 0, 8, 30, 0)}px)` }}>
          <div style={{ background: th.dark ? `${th.card}dd` : "rgba(255,255,255,.9)", backdropFilter: "blur(14px)", border: `2px solid ${th.line}`, borderRadius: 40, padding: "26px 40px", display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "4px 18px", boxShadow: `0 20px 50px rgba(0,0,0,.14), 0 0 60px ${th.accent}22` }}>
            {morceau.map((w, k) => {
              const act = t >= w.start && t < w.end;
              const past = t >= w.end;
              const pop = ease(f, w.start * FPS, w.start * FPS + 6);
              return <span key={k} style={{ display: "inline-block", fontSize: morceau.length > 5 ? 64 : 74, fontWeight: 700, lineHeight: 1.2, padding: "0 12px", borderRadius: 16, color: act ? th.onAccent : past ? th.ink : th.muted, background: act ? th.accent : "transparent", boxShadow: act ? `0 0 34px ${th.accent}aa` : "none", transform: act ? `scale(${1 + 0.1 * pop}) translateY(${-6 * pop}px)` : "none" }}>{w.w}</span>;
            })}
          </div>
        </div>
      )}
      {/* vignette : recentre le regard */}
      <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 45%, transparent 55%, rgba(0,0,0,${th.dark ? 0.32 : 0.1}) 100%)`, pointerEvents: "none" }} />
      <Audio src={staticFile(`${id}/voice.wav`)} />
    </AbsoluteFill>
  );
};
