"""Script exécuté SUR Kaggle (GPU). Généré par lancer_voix.py : INPUT_B64 est remplacé par le texte de l'épisode.

Il retrouve les modèles dans les jeux de données privés (/kaggle/input), installe les paquets, lance autopilot/voice.py
tel quel (variables BDF_*), puis dépose voice.wav, timings.json, voice_report.json et cache/ dans /kaggle/working/sortie.
Même en cas d'échec, sortie/etat.json explique pourquoi (lu par lancer_voix.py).
"""
import base64, json, os, shutil, subprocess, sys, time
from pathlib import Path

INPUT_B64 = "__INPUT_B64__"
VOICE_B64 = "__VOICE_B64__"  # autopilot/voice.py, embarqué : Kaggle n'envoie que ce fichier
OPTIONS = json.loads(base64.b64decode("__OPTIONS_B64__"))  # {"essais": 4, "seuil": 0.9, "budget_s": 0, "fichier": "episode.json"}
W = Path("/kaggle/working")
SORTIE = W / "sortie"
SORTIE.mkdir(parents=True, exist_ok=True)
t0 = time.time()


def trouver(pred, racine="/kaggle/input"):
    for p in Path(racine).rglob("*"):
        if pred(p):
            return p
    return None


def fin(code, message, extra=None):
    (SORTIE / "etat.json").write_text(json.dumps({"code": code, "message": message, "duree_s": round(time.time() - t0), **(extra or {})}, ensure_ascii=False), encoding="utf-8")
    print("ETAT", code, message, flush=True)
    sys.exit(0 if code in (0, 3) else 1)


def lancer(cmd, **kw):
    print("$", " ".join(map(str, cmd)), flush=True)
    return subprocess.run(cmd, **kw)


try:
    # 1. paquets (même versions que le PC)
    r = lancer([sys.executable, "-m", "pip", "install", "-q", "qwen-tts==0.1.1", "faster-whisper==1.2.1", "av==15.1.0", "soundfile", "truststore"])
    if r.returncode:
        fin(1, "pip install a échoué (accès internet activé sur le notebook ?)")

    # 2. modèles et voix de référence, retrouvés quel que soit le nom des jeux de données
    modele_hf = OPTIONS.get("modele_hf") or ""  # ex. Qwen/Qwen3-TTS-12Hz-1.7B-Base : téléchargé depuis Hugging Face au lieu du jeu de données
    modele = modele_hf or trouver(lambda p: p.is_dir() and (p / "config.json").exists() and (p / "model.safetensors").exists() and (p / "speech_tokenizer").is_dir())
    whisper = trouver(lambda p: p.is_file() and p.name == "model.bin")
    ref_wav = trouver(lambda p: p.is_file() and p.name == "ref.wav")
    manque = [n for n, v in (("modèle Qwen3-TTS", modele), ("Whisper", whisper), ("ref.wav", ref_wav)) if v is None]
    if manque:
        fin(1, "introuvable dans les jeux de données Kaggle : " + ", ".join(manque))
    voix = ref_wav.parent  # le jeu de données de voix fournit aussi la chaîne de nettoyage (même avec une voix intégrée)

    # 3. dépôt du code de voix : voice.py est embarqué dans ce script
    ici = W
    (ici / "voice.py").write_bytes(base64.b64decode(VOICE_B64))
    ep = W / "ep"
    ep.mkdir(exist_ok=True)
    (ep / OPTIONS["fichier"]).write_bytes(base64.b64decode(INPUT_B64))
    env = {**os.environ, "BDF_MODEL": str(modele), "BDF_WHISPER": str(whisper.parent), "BDF_REF_WAV": str(ref_wav),
           "BDF_REF_TXT": str(voix / "ref.txt"), "BDF_CHAIN": str(voix / "chaine-nettoyage.txt"),
           "BDF_DTYPE": os.environ.get("BDF_DTYPE", "bfloat16"), "BDF_WHISPER_DEVICE": "cpu",
           "HF_HUB_OFFLINE": "0" if modele_hf else "1", "TRANSFORMERS_OFFLINE": "0" if modele_hf else "1",
           "BDF_VITESSE": str(OPTIONS.get("vitesse", 1.10)), "PYTHONIOENCODING": "utf-8", "PYTHONWARNINGS": "ignore"}
    if OPTIONS.get("langue"):
        env["BDF_LANGUE"] = OPTIONS["langue"]
    if OPTIONS.get("locuteur"):  # voix intégrée : le modèle CustomVoice est téléchargé (modele_hf), pas de clonage
        env.update({"BDF_LOCUTEUR": OPTIONS["locuteur"], "BDF_STYLE": OPTIONS.get("style") or "", "BDF_MODEL_CUSTOM": modele_hf})
    cmd = [sys.executable, str(ici / "voice.py"), str(ep), "--episode-file", OPTIONS["fichier"], "--essais", str(OPTIONS["essais"]),
           "--seuil", str(OPTIONS["seuil"])]
    if OPTIONS.get("budget_s"):
        cmd += ["--budget-s", str(OPTIONS["budget_s"])]
    # on garde la fin du journal de voice.py : elle est rapportée dans etat.json en cas d'échec
    p = subprocess.Popen(cmd, env=env, cwd=str(W), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    fin_log = []
    for ligne in p.stdout:
        print(ligne, end="", flush=True)
        fin_log = (fin_log + [ligne.rstrip()])[-25:]
    p.wait()
    r = p
    r.returncode = p.returncode
    for nom in ("voice.wav", "timings.json", "voice_report.json"):
        if (ep / nom).exists():
            shutil.copy(ep / nom, SORTIE / nom)
    if (ep / "cache").exists():
        shutil.copytree(ep / "cache", SORTIE / "cache", dirs_exist_ok=True)
    if r.returncode == 3:
        fin(3, "budget de temps atteint : relancer pour continuer (cache conservé)")
    if r.returncode or not (SORTIE / "voice.wav").exists():
        fin(1, f"voice.py a échoué (code {r.returncode})", {"log": fin_log})
    fin(0, "ok")
except SystemExit:
    raise
except Exception as e:  # noqa: BLE001
    fin(1, f"exception : {e!r}")
