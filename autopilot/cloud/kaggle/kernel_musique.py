"""Script exécuté SUR Kaggle (GPU T4). Généré par lancer_musique.py : les marqueurs __…_B64__ sont remplacés (entrée de la chanson, alignement.py).

1. installe uv, clone ACE-Step 1.5 (licence MIT) et prépare son environnement (uv sync) ; télécharge les modèles ;
2. génère `essais` versions de la chanson (graines différentes) avec les paroles et le style fournis ;
3. fait transcrire chaque version par Whisper (faster-whisper, MIT), aligne les paroles (alignement.py), garde la version la mieux appariée ;
4. dépose sortie/chanson.wav, sortie/alignement.json et sortie/etat.json (code 0 ok, 1 échec avec la raison, lu par lancer_musique.py).
"""
import base64, json, os, shutil, subprocess, sys, time
from pathlib import Path

ENTREE = json.loads(base64.b64decode("__INPUT_B64__"))  # {caption, paroles, duree, bpm, langue, lignes}
OPTIONS = json.loads(base64.b64decode("__OPTIONS_B64__"))  # {essais, whisper, modele_dit}
W = Path("/kaggle/working")
SORTIE = W / "sortie"
SORTIE.mkdir(parents=True, exist_ok=True)
(W / "alignement.py").write_bytes(base64.b64decode("__ALIGN_B64__"))
sys.path.insert(0, str(W))
t0 = time.time()
REPO = W / "ACE-Step-1.5"
TAKES = W / "takes"
GEN = r'''
import json, sys, traceback
from pathlib import Path
from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music
cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
repo, out = cfg["repo"], Path(cfg["out"]); out.mkdir(exist_ok=True)
dit = AceStepHandler()
dit.initialize_service(project_root=repo, config_path=cfg["modele_dit"], device="cuda")
llm = LLMHandler()
res = []
for i, graine in enumerate(cfg["graines"]):
    try:
        p = GenerationParams(task_type="text2music", caption=cfg["caption"], lyrics=cfg["paroles"], duration=float(cfg["duree"]), bpm=int(cfg["bpm"]),
                             vocal_language=cfg["langue"], seed=int(graine), inference_steps=8, shift=3.0, thinking=False)
        c = GenerationConfig(batch_size=1, audio_format="wav", use_random_seed=False, seeds=[int(graine)])
        r = generate_music(dit, llm, p, c, save_dir=str(out / f"t{i}"))
        if not r.success:
            print("ECHEC essai", i, r.error, flush=True); continue
        res.append({"i": i, "graine": graine, "path": r.audios[0]["path"]})
    except Exception:
        traceback.print_exc(); continue
Path(cfg["out"], "liste.json").write_text(json.dumps(res), encoding="utf-8")
'''


def fin(code, message, extra=None):
    (SORTIE / "etat.json").write_text(json.dumps({"code": code, "message": message, "duree_s": round(time.time() - t0), **(extra or {})}, ensure_ascii=False), encoding="utf-8")
    print("ETAT", code, message, flush=True)
    sys.exit(0 if code == 0 else 1)


def lancer(cmd, **kw):
    print("$", " ".join(map(str, cmd)), flush=True)
    return subprocess.run(cmd, **kw)


try:
    if lancer([sys.executable, "-m", "pip", "install", "-q", "uv", "faster-whisper", "soundfile"]).returncode:
        fin(1, "pip install a échoué (accès internet activé sur le notebook ?)")
    if lancer(["git", "clone", "--depth", "1", "https://github.com/ACE-Step/ACE-Step-1.5.git", str(REPO)]).returncode:
        fin(1, "git clone ACE-Step a échoué")
    lic = (REPO / "LICENSE").read_text(encoding="utf-8", errors="replace")[:60] if (REPO / "LICENSE").exists() else ""
    if "MIT" not in lic:  # garde-fou de licence : on ne chante qu'avec du MIT
        fin(1, f"licence ACE-Step inattendue ({lic.strip()!r}) : arrêt par prudence")
    if lancer([sys.executable, "-m", "uv", "sync"], cwd=str(REPO)).returncode:
        fin(1, "uv sync (environnement ACE-Step) a échoué")
    lancer([sys.executable, "-m", "uv", "run", "acestep-download"], cwd=str(REPO))  # télécharge les modèles (sans effet s'il télécharge au premier appel)
    essais = int(OPTIONS.get("essais", 2))
    cfg = {"repo": str(REPO), "out": str(TAKES), "modele_dit": OPTIONS.get("modele_dit", "acestep-v15-turbo"), "graines": [1000 + 17 * k for k in range(essais)], **ENTREE}
    (W / "cfg.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    (W / "gen.py").write_text(GEN, encoding="utf-8")
    r = lancer([sys.executable, "-m", "uv", "run", "python", str(W / "gen.py"), str(W / "cfg.json")], cwd=str(REPO))
    liste = json.loads((TAKES / "liste.json").read_text(encoding="utf-8")) if (TAKES / "liste.json").exists() else []
    if not liste:
        fin(1, f"ACE-Step n'a produit aucune version (code {r.returncode})")

    # transcription et alignement de chaque version
    import numpy as np, soundfile as sf
    import alignement
    from faster_whisper import WhisperModel
    wm = WhisperModel(OPTIONS.get("whisper", "small"), device="cuda", compute_type="float16")
    meilleur = None
    for t in liste:
        x, sr = sf.read(t["path"], dtype="float32")
        mono = x.mean(axis=1) if x.ndim > 1 else x
        segs, _ = wm.transcribe(mono if sr == 16000 else np.interp(np.arange(0, len(mono), sr / 16000), np.arange(len(mono)), mono).astype("float32"),
                                language=ENTREE.get("langue", "fr"), word_timestamps=True, vad_filter=False, condition_on_previous_text=False)
        mots = [{"mot": w.word, "debut": w.start, "fin": w.end} for s in segs for w in (s.words or [])]
        duree = len(mono) / sr
        al = alignement.aligner(ENTREE["lignes"], mots, duree)
        al.update(duree=round(duree, 2), graine=t["graine"], mots_entendus=len(mots))
        ecart = abs(duree - ENTREE["duree"]) / ENTREE["duree"]
        note = al["appariement"] - 0.5 * max(0.0, ecart - 0.25)
        print(f"essai {t['i']} : appariement {al['appariement']} durée {duree:.0f}s note {note:.2f}", flush=True)
        if meilleur is None or note > meilleur[0]:
            meilleur = (note, t, al, sr)
    note, t, al, sr = meilleur
    shutil.copy(t["path"], SORTIE / "chanson.wav")
    if abs(al["duree"] - ENTREE["duree"]) / ENTREE["duree"] > 0.4:
        al["a_ecouter"] = f"durée de la chanson ({al['duree']:.0f} s) très différente de la durée demandée ({ENTREE['duree']} s) : paroles peut-être tronquées ou étirées"
    (SORTIE / "alignement.json").write_text(json.dumps(al, ensure_ascii=False), encoding="utf-8")
    fin(0, "ok", {"appariement": al["appariement"], "essais": len(liste)})
except SystemExit:
    raise
except Exception as e:  # noqa: BLE001
    fin(1, f"exception : {e!r}")
