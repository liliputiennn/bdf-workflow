import type { RegistryEntry } from "../../src/episodes/registry";

const pct = (frames: number, total: number) => `${(frames / total) * 100}%`;

export const Timeline = ({ entry, frame }: { entry: RegistryEntry | undefined; frame: number }) => {
  if (!entry) return <div className="timeline empty muted">La timeline apparaîtra une fois les scènes codées.</div>;
  const total = entry.frames;
  const fps = entry.fps;
  const marks = Array.from({ length: 7 }, (_, i) => Math.round((i / 6) * total));
  const fmt = (f: number) => `${Math.floor(f / fps / 60)}:${String(Math.floor(f / fps) % 60).padStart(2, "0")}`;
  return (
    <div className="timeline" aria-label="Timeline en lecture seule">
      <div className="ruler">
        {marks.map((m) => (
          <span key={m}>{fmt(m)}</span>
        ))}
      </div>
      <div className="track">
        <label>Scènes</label>
        <div className="lane">
          {entry.sceneStarts.map((s, i) => {
            const end = entry.sceneStarts[i + 1] ?? total;
            return <div key={s} className={`clip scene ${i % 2 ? "alt" : ""}`} style={{ left: pct(s, total), width: pct(end - s - 2, total) }} />;
          })}
        </div>
      </div>
      <div className="track">
        <label>Voix</label>
        <div className="lane">
          {entry.timings.lines.map((l) => (
            <div key={l.start} className="clip voice" style={{ left: pct(l.start * fps, total), width: pct((l.end - l.start) * fps, total) }} />
          ))}
        </div>
      </div>
      <div className="track">
        <label>SFX</label>
        <div className="lane">
          {entry.sfxFrames.map((s, i) => (
            <div key={i} className="clip sfx" style={{ left: pct(s, total) }} />
          ))}
        </div>
      </div>
      <div className="track">
        <label>Musique</label>
        <div className="lane">
          <div className="clip music" style={{ left: 0, width: "100%" }} />
        </div>
      </div>
      <div className="head" style={{ left: `calc(102px + (100% - 120px) * ${frame / total})` }} />
    </div>
  );
};
