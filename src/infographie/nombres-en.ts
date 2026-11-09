import type { Word } from "./types";

/**
 * Sous-titres anglais : la voix lit des nombres écrits en toutes lettres (« twelve thousand dollars »), l'écran les montre en chiffres (« $12,000 »).
 * Même principe que `nombres.ts` pour le français : on ne change que l'affichage, jamais le texte parlé ni le calage des mots.
 * Pur et sans dépendance Remotion : testé par `tests/nombres.test.ts`.
 */

const UNITES: Record<string, number> = { zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9 };
const ONZE_DIX_NEUF: Record<string, number> = { ten: 10, eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18, nineteen: 19 };
const DIZAINES: Record<string, number> = { twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90 };
const ECHELLES: Record<string, number> = { thousand: 1e3, million: 1e6, billion: 1e9, trillion: 1e12 };
const MONNAIES: Record<string, string> = { dollar: "$", dollars: "$", euro: "€", euros: "€", pound: "£", pounds: "£" };
/** « one » seul est un pronom (« one of them ») : il n'est un nombre que devant ces mots. */
const CONTEXTE_UN = new Set(["hundred", "thousand", "million", "billion", "trillion", "percent", "point", "dollar", "dollars", "euro", "euros", "pound", "pounds"]);
const CONTEXTE_ANNEE = new Set(["in", "since", "by", "until", "before", "after", "during", "from", "of", "circa", "around"]);

type Sub = { s: string; mot: number };
const nettoie = (m: string) => m.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z-]/g, "");
const groupe = (n: number) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");

/** Entier écrit en lettres commençant en `i` : { valeur, fin (exclu), echelle } ou null. */
const lisEntier = (t: Sub[], i: number): { valeur: number; fin: number; coef: number; echelle: number } | null => {
  let total = 0, cur = 0, k = i, vu = false;
  let dernier: "debut" | "unite" | "dix" | "dizaine" | "cent" | "echelle" = "debut";
  let coef = 0, echelle = 0;
  while (k < t.length) {
    const s = t[k].s;
    if (s === "and" && (dernier === "cent" || dernier === "echelle") && t[k + 1] && (t[k + 1].s in UNITES || t[k + 1].s in ONZE_DIX_NEUF || t[k + 1].s in DIZAINES)) { k++; continue; }
    if (s in UNITES) {
      const v = UNITES[s];
      if (v === 0) { if (vu) break; cur = 0; vu = true; dernier = "unite"; k++; continue; }
      if (!(dernier === "debut" || dernier === "dizaine" || dernier === "cent" || dernier === "echelle")) break;
      cur += v; dernier = "unite"; vu = true; k++; continue;
    }
    if (s in ONZE_DIX_NEUF) {
      if (!(dernier === "debut" || dernier === "cent" || dernier === "echelle")) break;
      cur += ONZE_DIX_NEUF[s]; dernier = "dix"; vu = true; k++; continue;
    }
    if (s in DIZAINES) {
      if (!(dernier === "debut" || dernier === "cent" || dernier === "echelle")) break;
      cur += DIZAINES[s]; dernier = "dizaine"; vu = true; k++; continue;
    }
    if (s === "hundred") {
      if (!vu || dernier !== "unite" || cur % 100 === 0 || cur % 100 > 9) break; // « three hundred » : un chiffre devant
      cur = cur - (cur % 100) + (cur % 100) * 100; dernier = "cent"; k++; continue;
    }
    if (s in ECHELLES) {
      if (!vu) break;
      const grand = ECHELLES[s];
      const c = cur || 1;
      if (total === 0 && grand >= 1e6) coef = c;
      total += c * grand; cur = 0; dernier = "echelle"; echelle = grand; k++; continue;
    }
    break;
  }
  if (!vu) return null;
  const net = echelle >= 1e6 && cur === 0 && total === coef * echelle;
  return { valeur: total + cur, fin: k, coef: net ? coef : 0, echelle: net ? echelle : 0 };
};

const NOM_ECHELLE: Record<number, string> = { 1e6: "million", 1e9: "billion", 1e12: "trillion" };

/** Convertit les nombres anglais écrits en lettres en chiffres ; fusionne les mots concernés (début du premier, fin du dernier). */
export const afficheEn = (words: Word[]): Word[] => {
  const subs: Sub[] = [];
  const debutMot: number[] = [];
  words.forEach((w, idx) => {
    debutMot[idx] = subs.length;
    const parts = nettoie(w.w).split("-").filter(Boolean);
    if (parts.length === 0) subs.push({ s: "", mot: idx });
    else parts.forEach((p) => subs.push({ s: p, mot: idx }));
  });
  const finMot = (subFin: number) => (subFin >= subs.length ? words.length : subs[subFin].mot);
  const frontiere = (fin: number) => fin >= subs.length || subs[fin].mot !== subs[fin - 1].mot;

  const out: Word[] = [];
  let m = 0;
  while (m < words.length) {
    const i = debutMot[m];
    let lu = lisEntier(subs, i);
    let annee: number | null = null;
    // années : « in twenty twenty-four », « since nineteen ninety-nine »
    const prec = i > 0 ? subs[i - 1].s : "";
    if (lu && (subs[i].s === "twenty" || subs[i].s === "nineteen") && CONTEXTE_ANNEE.has(prec) && lu.fin === i + 1) {
      const suite = lisEntier(subs, i + 1);
      if (suite && suite.valeur >= 10 && suite.valeur <= 99) { annee = (subs[i].s === "twenty" ? 2000 : 1900) + suite.valeur; lu = { ...suite, valeur: annee, fin: suite.fin, coef: 0, echelle: 0 }; }
    }
    if (!lu) { out.push(words[m]); m++; continue; }
    const suivant = subs[lu.fin]?.s ?? "";
    if (lu.fin - i === 1 && subs[i].s === "one" && !CONTEXTE_UN.has(suivant)) { out.push(words[m]); m++; continue; }
    if (lu.fin - i === 1 && subs[i].s === "zero" && !CONTEXTE_UN.has(suivant)) { out.push(words[m]); m++; continue; }
    let fin = lu.fin;
    if (!frontiere(fin)) { out.push(words[m]); m++; continue; }

    let texte: string;
    if (subs[fin]?.s === "point") {
      // décimales : « two point five », « zero point zero five »
      let k = fin + 1, dec = "";
      while (k < subs.length && subs[k].s in UNITES) { dec += String(UNITES[subs[k].s]); k++; }
      if (dec && frontiere(k)) { texte = `${lu.valeur}.${dec}`; fin = k; } else texte = String(lu.valeur);
    } else if (annee !== null) texte = String(annee);
    else if (lu.echelle && lu.coef) texte = `${lu.coef} ${NOM_ECHELLE[lu.echelle]}`;
    else if (lu.valeur >= 10000) texte = groupe(lu.valeur);
    else texte = String(lu.valeur);

    // unités collées au nombre
    const u = subs[fin]?.s ?? "";
    let prefixe = "", suffixe = "";
    if (u === "percent") { suffixe = "%"; fin += 1; }
    else if (u in MONNAIES) {
      prefixe = MONNAIES[u]; fin += 1;
      if (lu.valeur >= 1000 && !lu.echelle && annee === null) texte = groupe(lu.valeur);
    }
    if ((prefixe || suffixe) && fin < subs.length && subs[fin].mot === subs[fin - 1].mot) { out.push(words[m]); m++; continue; }

    const dernierMot = Math.min(finMot(fin), words.length) - 1;
    const premier = words[m], dernierW = words[Math.max(dernierMot, m)];
    const avant = premier.w.match(/^[^\p{L}\p{N}]*/u)?.[0] ?? "";
    const apres = dernierW.w.match(/[^\p{L}\p{N}]*$/u)?.[0] ?? "";
    out.push({ w: `${avant}${prefixe}${texte}${suffixe}${apres}`, start: premier.start, end: dernierW.end });
    m = Math.max(dernierMot, m) + 1;
  }
  return out;
};
