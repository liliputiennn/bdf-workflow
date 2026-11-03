import { useEffect, useMemo, useState } from "react";
import { api, type IdeaRow } from "../api";
import type { Fact } from "../../server/types";

const host = (u: string) => {
  try {
    return new URL(u).hostname.replace(/^www\./, "");
  } catch {
    return u;
  }
};

/** Couverture provisoire : l'accroche coupée en deux lignes, style pixel. */
export const PixelCover = ({ hook }: { hook: string }) => {
  const words = hook.replace(/\.$/, "").split(" ");
  const cut = Math.ceil(words.length / 2);
  return (
    <div className="phone">
      <div className="pixel-cover">
        <div className="l1">{words.slice(0, cut).join(" ").toUpperCase()}</div>
        <div className="l2">{words.slice(cut).join(" ").toUpperCase()}</div>
        <div className="ground" />
      </div>
    </div>
  );
};

/** Mélange stable pour un chargement de page : chaque rafraîchissement propose un ordre neuf. */
const shuffle = <T,>(arr: T[]) => {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};

/** État de vérification d'un fait, en mots simples. */
const factStatus = (f: Fact): { ok: boolean; text: string } => {
  const distinct = new Set(f.sources).size;
  if (f.check?.length) {
    const n = f.verified?.length ?? 0;
    if (n === 0) return { ok: false, text: f.verified ? "pas retrouvé dans la source : à revoir" : "vérification en attente" };
    return distinct >= 2 && n >= 2 ? { ok: true, text: "retrouvé dans 2 sources" } : { ok: true, text: "retrouvé dans la source · 2e source à ajouter" };
  }
  return distinct >= 2 ? { ok: true, text: "vérifié dans 2 sources" } : { ok: false, text: "une seule source" };
};

export const Ideas = ({ openEpisode, version }: { openEpisode: (id: string) => void; version: number }) => {
  const [ideas, setIdeas] = useState<IdeaRow[]>([]);
  const [sel, setSel] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [theme, setTheme] = useState("Tous");
  const [err, setErr] = useState("");
  const [seed, setSeed] = useState(0);

  useEffect(() => {
    api.ideas().then((l) => {
      // nouvelles idées d'abord, dans un ordre mélangé ; puis en production, puis publiées
      const order = { idea: 0, production: 1, published: 2 } as const;
      const mixed = shuffle(l).sort((a, b) => order[a.status] - order[b.status]);
      setIdeas(mixed);
      setSel((s) => (s && l.some((i) => i.slug === s) ? s : mixed[0]?.slug ?? null));
    });
  }, [version, seed]);

  const themes = useMemo(() => ["Tous", ...[...new Set(ideas.map((i) => i.theme))].sort()], [ideas]);
  const shown = ideas.filter((i) => (theme === "Tous" || i.theme === theme) && (!q || `${i.hook} ${i.theme} ${i.year}`.toLowerCase().includes(q.toLowerCase())));
  const cur = ideas.find((i) => i.slug === sel);
  const ready = ideas.filter((i) => i.status === "idea").length;

  const produce = async () => {
    if (!cur) return;
    setErr("");
    try {
      openEpisode((await api.produce(cur.slug)).id);
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  return (
    <main className="ideas">
      <section className="ideas-list">
        <div className="list-head">
          <h1>Idées vraies</h1>
          <button className="btn ghost small-btn" onClick={() => setSeed((s) => s + 1)} title="Proposer un autre ordre">
            ⟳ Mélanger
          </button>
        </div>
        <p className="muted">
          {ready} sujet{ready > 1 ? "s" : ""} prêt{ready > 1 ? "s" : ""} · chaque fait est contrôlé dans ses sources
        </p>
        <input className="search" placeholder="Chercher un sujet, un thème, une année…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Chercher un sujet" />
        <div className="chips">
          {themes.map((t) => (
            <button key={t} className={`chip ${t === theme ? "on" : ""}`} onClick={() => setTheme(t)}>
              {t}
            </button>
          ))}
        </div>
        {shown.map((i) => (
          <button key={i.slug} className={`idea ${i.slug === sel ? "on" : ""}`} onClick={() => setSel(i.slug)}>
            <span className="hook">{i.hook}</span>
            <span className="meta">
              <span>
                {i.theme} · {i.year}
                {i.status !== "idea" ? ` · ${i.status === "published" ? "publié" : "en production"}` : ""}
              </span>
              <b title="Estimation éditoriale de l'accroche, sur 10">{i.score.toFixed(1)}</b>
            </span>
          </button>
        ))}
        {shown.length === 0 && <p className="muted">Aucun sujet ne correspond.</p>}
      </section>
      <section className="ideas-stage">
        {cur && (
          <div style={{ width: 280 }}>
            <PixelCover hook={cur.hook} />
          </div>
        )}
      </section>
      <aside className="ideas-facts">
        {cur && (
          <>
            <h2>Faits</h2>
            {cur.facts.map((f) => {
              const st = factStatus(f);
              return (
                <div key={f.claim} className={`card fact ${st.ok ? "" : "weak"}`}>
                  <p>{f.claim}</p>
                  <p className="src">
                    {f.sources.map((s) => (
                      <a key={s} href={s} target="_blank" rel="noreferrer">
                        {host(s)}
                      </a>
                    ))}
                    <span className={`small ${st.ok ? "ok" : "warn"}`}>{st.ok ? "✓ " : ""}{st.text}</span>
                  </p>
                </div>
              );
            })}
            {cur.disputed.length > 0 && (
              <div className="card disputed">
                <h3>Points contestés (jamais présentés comme des faits)</h3>
                {cur.disputed.map((d) => (
                  <p key={d}>{d}</p>
                ))}
              </div>
            )}
            <p className="muted small">
              Score {cur.score.toFixed(1)} sur 10 : {cur.scoreNote}
            </p>
            {cur.status === "idea" ? (
              <button className="btn" onClick={produce}>
                Produire cet épisode
              </button>
            ) : (
              <button className="btn ghost" onClick={() => openEpisode(cur.slug)}>
                Ouvrir l'épisode
              </button>
            )}
            <button className="btn ghost" onClick={() => api.verifyIdeas()}>
              Revérifier tous les faits
            </button>
            {err && <p className="warn">{err}</p>}
          </>
        )}
      </aside>
    </main>
  );
};
