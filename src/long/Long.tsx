import React from "react";
import { AbsoluteFill, staticFile, useCurrentFrame, type CalculateMetadataFunction } from "remotion";
import { Audio } from "@remotion/media";
import { Backdrop } from "../infographie/fx";
import { affiche, decoupe } from "../infographie/nombres";
import { LangueCtx } from "../infographie/langue";
import { ease, FPS, SceneClock } from "../infographie/scenes";
import { getTheme, GIANT, UI, type Theme } from "../infographie/themes";
import type { Scene, Timings, Word } from "../infographie/types";
import { chapitresTemps, flatten, type ChapitreTemps } from "./plan";
import { Annonce, Anneau, Barres, Carte, Chiffre, Citation, Clip, Courbe, Duel, Fiche, Frise, LH, Liste, LigneTemps, LW, Objet, Photo, Question, TitreGeant } from "./scenes";
import type { EpisodeLong, LongProps } from "./types";

/** Pause laissée après la dernière parole (fin de vidéo). */
const TAIL = 60;
/** La carte de titre reste un peu après la reprise de la voix. */
const CARTE_APRES = 0.3;
/** Durée de la transition poussée entre deux scènes, en images. */
const TR = 10;

export const calculateMetadata: CalculateMetadataFunction<LongProps> = async ({ props }) => {
  const [episode, timings] = await Promise.all([
    fetch(staticFile(`${props.id}/episode-long.json`)).then((r) => r.json() as Promise<EpisodeLong>),
    fetch(staticFile(`${props.id}/timings.json`)).then((r) => r.json() as Promise<Timings>),
  ]);
  return { durationInFrames: Math.ceil(timings.total * FPS) + TAIL, fps: FPS, width: LW, height: LH, props: { ...props, episode, timings } };
};

const SceneView: React.FC<{ s: Scene; l: number; th: Theme; words: Word[]; t: number }> = ({ s, l, th, words, t }) => {
  const c = { l, th, words, t };
  return <SceneClock.Provider value={l}>{vue(s, c)}</SceneClock.Provider>;
};

const vue = (s: Scene, c: { l: number; th: Theme; words: Word[]; t: number }) => {
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
    case "frise": return <Frise {...c} p={s.params as never} />;
    case "carte": return <Carte {...c} p={s.params as never} />;
    case "citation": return <Citation {...c} p={s.params as never} />;
    case "liste": return <Liste {...c} p={s.params as never} />;
    case "fiche": return <Fiche {...c} p={s.params as never} />;
    case "annonce": return <Annonce {...c} p={s.params as never} />;
    case "photo": return <Photo {...c} p={s.params as never} />;
    case "clip": return <Clip {...c} p={s.params as never} />;
  }
};

const lineChars = (words: Word[]) => words.reduce((a, w) => a + w.w.length + 1, 0);

/** Une ou deux rangées de sous-titres, coupées au plus près du milieu (jamais un mot seul sur la 2e ligne). */
const rangees = (words: Word[]): Word[][] => {
  const total = lineChars(words);
  if (total <= 56 || words.length < 2) return [words];
  let cut = 1, best = Infinity, acc = 0;
  for (let k = 0; k < words.length - 1; k++) {
    acc += words[k].w.length + 1;
    const d = Math.abs(acc - (total - acc));
    if (d < best) { best = d; cut = k + 1; }
  }
  return [words.slice(0, cut), words.slice(cut)];
};

const Fond: React.FC<{ th: Theme; f: number }> = ({ th, f }) => <Backdrop th={th} f={f} w={LW} h={LH} />;

/** Carte de titre animée, affichée pendant le silence qui précède chaque chapitre. */
const CarteChapitre: React.FC<{ c: ChapitreTemps; total: number; th: Theme; l: number; dur: number }> = ({ c, total, th, l, dur }) => {
  const out = ease(l, dur - 9, dur, 1, 0);
  return (
    <AbsoluteFill style={{ opacity: ease(l, 0, 7) * out }}>
      <Fond th={th} f={l} />
      <div style={{ position: "absolute", left: 120, top: 0, bottom: 0, display: "flex", alignItems: "center", gap: 90 }}>
        <div style={{ fontFamily: GIANT, fontSize: 560, lineHeight: 1, color: th.accent, transform: `translateX(${ease(l, 0, 16, -160, 0)}px)`, opacity: ease(l, 0, 12) }}>{String(c.n).padStart(2, "0")}</div>
        <div style={{ width: 1000 }}>
          <div style={{ fontFamily: UI, fontSize: 38, fontWeight: 700, letterSpacing: 8, textTransform: "uppercase", color: th.muted, opacity: ease(l, 6, 18) }}>Chapitre {c.n} sur {total}</div>
          <div style={{ height: 10, borderRadius: 5, background: th.hot, width: 220 * ease(l, 8, 28), margin: "24px 0 28px" }} />
          <div style={{ fontFamily: GIANT, fontSize: c.titre.length > 28 ? 118 : 150, lineHeight: 1.05, textTransform: "uppercase", color: th.ink, opacity: ease(l, 10, 24), transform: `translateY(${ease(l, 10, 24, 50, 0)}px)` }}>{c.titre}</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const Long: React.FC<LongProps> = ({ id, episode, timings }) => {
  const f = useCurrentFrame();
  if (!episode || !timings) return null;
  const t = f / FPS;
  const plan = flatten(episode);
  const chaps = chapitresTemps(plan, timings);
  const lineStart = (p: number) => timings.lines[Math.min(p - 1, timings.lines.length - 1)].start;
  const sceneAt = (tt: number) => {
    let k = 0;
    plan.scenes.forEach((s, j) => { if (tt >= lineStart(s.phrase) - 0.02) k = j; });
    return k;
  };
  const lineAt = (tt: number) => {
    let k = 0;
    timings.lines.forEach((ln, j) => { if (tt >= ln.start - 0.02) k = j; });
    return k;
  };
  const themeDe = (s: Scene) => getTheme(s.theme ?? (s.type === "titre-geant" && episode.theme_accent ? episode.theme_accent : episode.theme));
  const startF = (k: number) => Math.round(lineStart(plan.scenes[k].phrase) * FPS);

  const si = sceneAt(t);
  const scene = plan.scenes[si];
  const th = themeDe(scene);
  const base = getTheme(episode.theme);
  const prevTh = si > 0 ? themeDe(plan.scenes[si - 1]) : th;
  const l = f - startF(si);
  const line = timings.lines[lineAt(t)];
  // à l'écran : nombres en chiffres, puis morceaux courts (un seul affiché à la fois, celui qu'on entend)
  const mots = affiche(line.words, episode.langue);
  const morceaux = decoupe(mots, 9, 52);
  const ck = morceaux.reduce((acc, c, k) => (t >= c[0].start - 0.02 ? k : acc), 0);
  const morceau = morceaux[ck];
  const morceauF = f - Math.round(morceau[0].start * FPS);
  let ci = 0;
  chaps.forEach((c, k) => { if (t >= c.borne - 0.001) ci = k; });
  const chap = chaps[ci];
  const carte = chaps.find((c) => c.carteDe !== null && t >= c.carteDe && t < c.start + CARTE_APRES);
  const giant = scene.type === "titre-geant";

  // transition poussée : la scène précédente sort pendant que la nouvelle entre, en sens alternés
  const dir = si % 2 ? 1 : -1;
  const enter = ease(l, 0, TR);
  const showPrev = si > 0 && l < TR + 2;
  const prevT = (startF(si) - 1) / FPS;
  const prevMots = affiche(timings.lines[lineAt(prevT)].words, episode.langue);
  const camera = 1 + Math.min(l, 240) * 0.0002;

  return (
    <LangueCtx.Provider value={episode.langue}>
    <AbsoluteFill style={{ background: th.bg[0], fontFamily: UI, overflow: "hidden" }}>
      <Fond th={th} f={f} />
      {showPrev && prevTh.id !== th.id && <Backdrop th={prevTh} f={f} w={LW} h={LH} opacity={1 - enter} />}

      <div style={{ position: "absolute", left: 90, top: 40, display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ width: 22, height: 22, borderRadius: 7, background: th.accent, boxShadow: `0 0 ${14 + 8 * Math.sin(f / 9)}px ${th.accent}` }} />
        <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: 5, color: th.ink, textTransform: "uppercase" }}>{episode.chaine}</div>
      </div>
      <div style={{ position: "absolute", right: 90, top: 40, fontSize: 26, fontWeight: 700, letterSpacing: 2, color: th.muted, textTransform: "uppercase" }}>
        <span style={{ color: th.accent }}>{chap.n}/{chaps.length}</span> · {chap.titre}
      </div>

      {/* caméra : respiration lente + léger roulis */}
      <AbsoluteFill style={{ transform: `scale(${camera}) rotate(${Math.sin(f / 90) * 0.15}deg)`, transformOrigin: "50% 45%" }}>
        {showPrev && (
          <AbsoluteFill key={`p${si}`} style={{ opacity: 1 - enter, transform: `translateX(${-dir * enter * 200}px) scale(${1 - 0.06 * enter})`, filter: `blur(${enter * 14}px)` }}>
            <SceneView s={plan.scenes[si - 1]} l={f - startF(si - 1)} th={prevTh} words={prevMots} t={prevT} />
          </AbsoluteFill>
        )}
        <AbsoluteFill key={si} style={{ opacity: ease(l, 0, 6), transform: `perspective(2200px) translateX(${(1 - enter) * dir * 220}px) scale(${1.06 - 0.06 * enter}) rotateY(${(1 - enter) * dir * -5}deg)`, filter: `blur(${(1 - enter) * 12}px)` }}>
          <SceneView s={scene} l={l} th={th} words={mots} t={t} />
        </AbsoluteFill>
      </AbsoluteFill>

      {/* éclair de couleur au changement de scène */}
      {si > 0 && l < 14 && (
        <div style={{ position: "absolute", top: -200, bottom: -200, width: 220, left: `${dir > 0 ? ease(l, 0, 12, 120, -20) : ease(l, 0, 12, -20, 120)}%`, transform: "skewX(-16deg)", background: `linear-gradient(90deg, transparent, ${th.accent}, ${th.hot}, transparent)`, opacity: 0.8 * (1 - l / 14), filter: "blur(6px)", pointerEvents: "none" }} />
      )}

      {!giant && (
        <div style={{ position: "absolute", left: 120, right: 120, bottom: 88, display: "flex", justifyContent: "center", opacity: ease(morceauF, 0, 4), transform: `translateY(${ease(morceauF, 0, 8, 26, 0)}px)` }}>
          <div style={{ background: th.dark ? `${th.card}dd` : "rgba(255,255,255,.92)", backdropFilter: "blur(14px)", border: `2px solid ${th.line}`, borderRadius: 32, padding: "14px 34px", display: "flex", flexDirection: "column", alignItems: "center", boxShadow: `0 16px 40px rgba(0,0,0,.14), 0 0 50px ${th.accent}22` }}>
            {rangees(morceau).map((row, r) => (
              <div key={r} style={{ display: "flex", justifyContent: "center", gap: "0 8px" }}>
                {row.map((w, k) => {
                  const act = t >= w.start && t < w.end;
                  const past = t >= w.end;
                  const pop = ease(f, w.start * FPS, w.start * FPS + 6);
                  return <span key={k} style={{ display: "inline-block", fontSize: 56, fontWeight: 700, lineHeight: 1.25, padding: "0 8px", borderRadius: 12, color: act ? th.onAccent : past ? th.ink : th.muted, background: act ? th.accent : "transparent", boxShadow: act ? `0 0 28px ${th.accent}aa` : "none", transform: act ? `scale(${1 + 0.08 * pop})` : "none" }}>{w.w}</span>;
                })}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* barre de progression : un segment par chapitre, proportionnel à sa durée */}
      <div style={{ position: "absolute", left: 90, right: 90, bottom: 36, display: "flex", gap: 8 }}>
        {chaps.map((c, k) => {
          const span = c.fin - c.borne;
          const done = Math.max(0, Math.min(1, (t - c.borne) / span));
          return (
            <div key={k} style={{ flex: span, height: 10, borderRadius: 5, background: th.line, overflow: "hidden" }}>
              <div style={{ width: `${done * 100}%`, height: "100%", background: k === ci ? th.accent : th.deep, boxShadow: k === ci ? `0 0 12px ${th.accent}` : "none" }} />
            </div>
          );
        })}
      </div>

      {carte && carte.carteDe !== null && (
        <CarteChapitre c={carte} total={chaps.length} th={base} l={f - Math.round(carte.carteDe * FPS)} dur={Math.round((carte.start + CARTE_APRES - carte.carteDe) * FPS)} />
      )}
      <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 45%, transparent 58%, rgba(0,0,0,${th.dark ? 0.3 : 0.08}) 100%)`, pointerEvents: "none" }} />
      <Audio src={staticFile(`${id}/voice.wav`)} />
    </AbsoluteFill>
    </LangueCtx.Provider>
  );
};
