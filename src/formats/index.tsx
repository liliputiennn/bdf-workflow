// Compositions des formats « créateur » : le contenu arrive en props JSON (--props) depuis autopilot/formats/rendu_remotion.py.
import React from "react";
import { Composition } from "remotion";
import { BoucleDecor, type BoucleProps } from "./BoucleDecor";
import { LangueVideo, type LangueProps } from "./LangueVideo";

const DEMO_LANGUE: LangueProps = {
  w: 1080, h: 1920, fps: 30, total: 6, chaine: "La Débrouille", langue: "Anglais", situation: "Au café", t_outro: 5.2,
  lecons: [{ fr: "Je voudrais un café, s'il vous plaît.", cible: "I would like a coffee, please.", phonetique: "aï woud laïk a kofi, pliz", t_f: 1, t_c: 1.5, t_l: 3, fin_l: 4, suite: 5.2,
    mots_c: [], mots_l: [] }],
};
const DEMO_BOUCLE: BoucleProps = { w: 1280, h: 720, fps: 15, boucle: 30, format: "sommeil", decor: "nuit-etoilee", graine: 7 };

export const FormatsRoot: React.FC = () => (
  <>
    <Composition id="Fmt-Langue" component={LangueVideo} width={1080} height={1920} fps={30} durationInFrames={180} defaultProps={DEMO_LANGUE}
      calculateMetadata={({ props }) => ({ durationInFrames: Math.round(props.total * props.fps), fps: props.fps, width: props.w, height: props.h })} />
    <Composition id="Fmt-Boucle" component={BoucleDecor} width={1280} height={720} fps={15} durationInFrames={450} defaultProps={DEMO_BOUCLE}
      calculateMetadata={({ props }) => ({ durationInFrames: Math.round(props.boucle * props.fps), fps: props.fps, width: props.w, height: props.h })} />
  </>
);
