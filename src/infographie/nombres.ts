import type { Word } from "./types";

/**
 * Sous-titres : la voix lit des nombres écrits en lettres (c'est ce que le moteur de voix prononce le mieux),
 * l'écran les montre en chiffres. Rien ici ne touche au texte parlé ni au calage : on ne change que l'affichage.
 * Pur et sans dépendance Remotion : testé par `tests/nombres.test.ts`.
 */

const NBSP = " ";

const UNITES: Record<string, number> = { zero: 0, un: 1, une: 1, deux: 2, trois: 3, quatre: 4, cinq: 5, six: 6, sept: 7, huit: 8, neuf: 9 };
const ONZE_SEIZE: Record<string, number> = { onze: 11, douze: 12, treize: 13, quatorze: 14, quinze: 15, seize: 16 };
const DIZAINES: Record<string, number> = { vingt: 20, vingts: 20, trente: 30, quarante: 40, cinquante: 50, soixante: 60 };

/** Un mot « un », « une » ou « neuf » seul n'est un nombre que devant ces mots (sinon : article, ou « neuf » = pas vieux). */
const CONTEXTE_FAIBLE = new Set(["virgule", "million", "millions", "milliard", "milliards", "euro", "euros", "dollar", "dollars", "centime", "centimes", "pour"]);
const CONTEXTE_NEUF = new Set(["mois", "ans", "jours", "semaines", "heures", "fois", "pour", "euros", "dollars", "virgule", "millions", "milliards"]);

type Sub = { s: string; mot: number };

const nettoie = (m: string) => m.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z-]/g, "");

/** Valeur d'un nombre écrit en lettres commençant en `i` : { valeur, fin (exclu), echelle } ou null. */
const lisEntier = (t: Sub[], i: number): { valeur: number; fin: number; coef: number; echelle: "" | "million" | "milliard" } | null => {
  let total = 0, cur = 0, k = i, vu = false;
  let dernier: "debut" | "unite" | "onze" | "dix" | "dizaine" | "qv" | "cent" | "mille" | "echelle" = "debut";
  let echelle: "" | "million" | "milliard" = "";
  let coef = 0;
  const peu = (k2: number) => (t[k2] ? t[k2].s : "");
  while (k < t.length) {
    const s = t[k].s;
    if (s === "et" && (dernier === "dizaine" || dernier === "qv") && (peu(k + 1) === "un" || peu(k + 1) === "une" || peu(k + 1) === "onze")) { k++; continue; }
    if (s === "quatre" && (peu(k + 1) === "vingt" || peu(k + 1) === "vingts") && ["debut", "cent", "mille", "echelle"].includes(dernier)) { cur += 80; k += 2; dernier = "qv"; vu = true; continue; }
    if (s in UNITES) {
      const v = UNITES[s];
      if (v === 0) { if (vu) break; cur = 0; vu = true; dernier = "unite"; k++; continue; }
      const ok = ["debut", "dizaine", "qv", "cent", "mille", "echelle"].includes(dernier) || (dernier === "dix" && v >= 7);
      if (!ok) break;
      cur += v; dernier = "unite"; vu = true; k++; continue;
    }
    if (s in ONZE_SEIZE) {
      const ok = ["debut", "cent", "mille", "echelle"].includes(dernier) || ((dernier === "dizaine" || dernier === "qv") && (cur % 100 === 60 || cur % 100 === 80));
      if (!ok) break;
      cur += ONZE_SEIZE[s]; dernier = "onze"; vu = true; k++; continue;
    }
    if (s === "dix") {
      const ok = ["debut", "cent", "mille", "echelle"].includes(dernier) || ((dernier === "dizaine" || dernier === "qv") && (cur % 100 === 60 || cur % 100 === 80));
      if (!ok) break;
      cur += 10; dernier = "dix"; vu = true; k++; continue;
    }
    if (s in DIZAINES) {
      if (!["debut", "cent", "mille", "echelle"].includes(dernier)) break;
      cur += DIZAINES[s]; dernier = "dizaine"; vu = true; k++; continue;
    }
    if (s === "cent" || s === "cents") {
      if (dernier === "unite" && cur % 100 >= 2 && cur % 100 <= 9) { cur = cur - (cur % 100) + (cur % 100) * 100; dernier = "cent"; k++; continue; }
      if (dernier === "debut" || dernier === "mille" || dernier === "echelle") { cur += 100; dernier = "cent"; vu = true; k++; continue; }
      break;
    }
    if (s === "mille") {
      if (!vu && dernier === "debut") { total += 1000; dernier = "mille"; vu = true; k++; continue; }
      if (cur === 0 && dernier !== "debut" && dernier !== "echelle") break;
      total += (cur || 1) * 1000; cur = 0; dernier = "mille"; vu = true; k++; continue;
    }
    if (s === "million" || s === "millions" || s === "milliard" || s === "milliards") {
      if (!vu) break;
      const grand = s.startsWith("milliard") ? 1e9 : 1e6;
      const c = cur || 1;
      if (total === 0) coef = c;
      total += c * grand; cur = 0; dernier = "echelle"; echelle = grand === 1e9 ? "milliard" : "million"; k++; continue;
    }
    break;
  }
  if (!vu) return null;
  const net = echelle !== "" && cur === 0 && total === coef * (echelle === "milliard" ? 1e9 : 1e6);
  return { valeur: total + cur, fin: k, coef: net ? coef : 0, echelle: net ? echelle : "" };
};

const groupe = (n: number) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);

/** Convertit les nombres écrits en lettres en chiffres ; fusionne les mots concernés (début du premier, fin du dernier). */
export const affiche = (words: Word[]): Word[] => {
  const subs: Sub[] = [];
  const debutMot: number[] = [];
  words.forEach((w, idx) => {
    debutMot[idx] = subs.length;
    const parts = nettoie(w.w).split("-").filter(Boolean);
    if (parts.length === 0) subs.push({ s: "", mot: idx });
    else parts.forEach((p) => subs.push({ s: p, mot: idx }));
  });
  const finMot = (subFin: number) => (subFin >= subs.length ? words.length : subs[subFin].mot); // premier mot non consommé

  const out: Word[] = [];
  let m = 0;
  while (m < words.length) {
    const i = debutMot[m];
    const lu = lisEntier(subs, i);
    const suivant = lu ? subs[lu.fin]?.s ?? "" : "";
    // seul « un », « une » ou « neuf » : exige un contexte chiffré
    const seul = lu && lu.fin - i === 1 && (subs[i].s === "un" || subs[i].s === "une");
    const seulNeuf = lu && lu.fin - i === 1 && subs[i].s === "neuf";
    if (!lu || (seul && !CONTEXTE_FAIBLE.has(suivant)) || (seulNeuf && !CONTEXTE_NEUF.has(suivant))) { out.push(words[m]); m++; continue; }

    let fin = lu.fin;
    // le calage de mots : on n'accepte que si l'on s'arrête à une frontière de mot
    if (fin < subs.length && subs[fin].mot === subs[fin - 1].mot) { out.push(words[m]); m++; continue; }

    let texte: string;
    if (subs[fin]?.s === "virgule") {
      // décimales : « zéro virgule zéro cinq », « un virgule cinq », « deux virgule quarante-cinq »
      let k = fin + 1, dec = "";
      while (k < subs.length && subs[k].s === "zero") { dec += "0"; k++; }
      const d = lisEntier(subs, k);
      if (d) { dec += String(d.valeur); k = d.fin; }
      if (dec && (k >= subs.length || subs[k].mot !== subs[k - 1].mot)) { texte = `${lu.valeur},${dec}`; fin = k; }
      else texte = String(lu.valeur);
    } else if (lu.echelle && lu.coef) texte = `${lu.coef} ${lu.echelle}${lu.coef > 1 ? "s" : ""}`;
    else if (lu.valeur >= 10000 || (lu.valeur >= 1000 && ["euro", "euros", "dollar", "dollars"].includes(subs[fin]?.s ?? ""))) texte = groupe(lu.valeur);
    else texte = String(lu.valeur);

    // unités collées au nombre
    const u = subs[fin]?.s ?? "";
    let unite = "";
    if (u === "pour" && subs[fin + 1]?.s === "cent") { unite = `${NBSP}%`; fin += 2; }
    else if (u === "euro" || u === "euros") { unite = `${NBSP}€`; fin += 1; }
    else if (u === "dollar" || u === "dollars") { unite = `${NBSP}$`; fin += 1; }
    if (unite && fin < subs.length && subs[fin].mot === subs[fin - 1].mot) { out.push(words[m]); m++; continue; }

    const dernierMot = Math.min(finMot(fin), words.length) - 1;
    const premier = words[m], dernierW = words[Math.max(dernierMot, m)];
    const avant = premier.w.match(/^[^\p{L}\p{N}]*/u)?.[0] ?? "";
    const apres = dernierW.w.match(/[^\p{L}\p{N}]*$/u)?.[0] ?? "";
    out.push({ w: `${avant}${texte}${unite}${apres}`, start: premier.start, end: dernierW.end });
    m = Math.max(dernierMot, m) + 1;
  }
  return out;
};

/** Coupe une phrase en morceaux courts (au plus `maxMots` mots et `maxCar` caractères), de préférence après une ponctuation. */
export const decoupe = (words: Word[], maxMots = 6, maxCar = 34): Word[][] => {
  const longueur = (ws: Word[]) => ws.reduce((a, w) => a + w.w.length + 1, -1);
  const trop = (ws: Word[]) => ws.length > maxMots || longueur(ws) > maxCar;
  const coupe = (ws: Word[]): Word[][] => {
    if (!trop(ws) || ws.length < 2) return [ws];
    let meilleur = -1, score = Infinity;
    for (let k = 1; k < ws.length; k++) {
      const g = ws.slice(0, k), d = ws.slice(k);
      let s = Math.abs(longueur(g) - longueur(d));
      if (/[.,;:!?…]$/.test(ws[k - 1].w)) s -= 14;
      if (trop(g)) s += 40;
      if (trop(d)) s += 12;
      if (k === 1 || k === ws.length - 1) s += 6; // évite un morceau d'un seul mot
      if (s < score) { score = s; meilleur = k; }
    }
    return [...coupe(ws.slice(0, meilleur)), ...coupe(ws.slice(meilleur))];
  };
  return coupe(words);
};
