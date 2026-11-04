"""Voix clonée d'un épisode : texte -> voice.wav (nettoyée, 48 kHz mono) + timings.json (calage au mot).

Usage (python du venv C:\\VoiceStudio\\tts-direct\\venv) :
    python autopilot/voice.py episodes-b/<id> [--essais 4] [--seuil 0.9]

- Qwen3-TTS 0.6B Base (Apache-2.0), réglages « C » : temperature 1.05, top_p 0.95, top_k 60, repetition_penalty 1.1.
- Pour chaque phrase : N essais, Whisper réécoute chaque essai, on garde le plus fidèle au texte.
- Les phrases déjà générées sont relues depuis `cache/` (relance rapide si on corrige une seule phrase).
- Écrit `voice_report.json` : phrases dont le meilleur essai reste sous le seuil (à relire).
Le format de timings est celui de src/episodes/*.timings.json.
"""
import argparse, difflib, hashlib, json, os, re, subprocess, sys, time, unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
# Chemins surchargeables (le cloud/Kaggle les place ailleurs) : BDF_MODEL, BDF_MODEL_CUSTOM, BDF_WHISPER, BDF_REF_WAV, BDF_REF_TXT, BDF_CHAIN.
# BDF_DTYPE = bfloat16 (défaut, RTX 3050) ou float16 ; BDF_WHISPER_DEVICE = cpu (défaut) ou cuda.
_E = os.environ.get
CFG = {
    "model": _E("BDF_MODEL", r"C:\VoiceStudio\qwen3-tts-0.6b-base"),
    "model_custom": _E("BDF_MODEL_CUSTOM", r"C:\VoiceStudio\qwen3-tts-0.6b-customvoice"),
    "whisper": _E("BDF_WHISPER", r"C:\VoiceStudio\whisper-small"),
    "ref_wav": Path(_E("BDF_REF_WAV", str(HERE / "voix" / "ref.wav"))),
    "ref_txt": Path(_E("BDF_REF_TXT", str(HERE / "voix" / "ref.txt"))),
    "chain": Path(_E("BDF_CHAIN", str(HERE / "voix" / "chaine-nettoyage.txt"))),
    "temps": [1.05, 0.95, 1.0, 0.9],
    "gap": 0.14,
    "lead": 0.15,
}
REF_ID = hashlib.sha1(Path(CFG["ref_wav"]).read_bytes()).hexdigest()[:8] if Path(CFG["ref_wav"]).exists() else "none"
NUMWORDS = set("zero un une deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize vingt trente quarante cinquante soixante cent cents mille dollar dollars pour virgule et".split())


def norm(w: str) -> str:
    w = unicodedata.normalize("NFD", w.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in w if unicodedata.category(c) != "Mn"))


def content_words(s: str):
    return [phonetique(n) for n in (norm(w) for w in s.replace("…", " ").split()) if n and not n.isdigit() and n not in NUMWORDS]


# Formes qui se prononcent pareil en français : Whisper ne peut pas les départager, donc on ne les compte pas comme une erreur.
HOMOPHONES = {"ces": "ce", "ses": "se", "mes": "me", "tes": "te", "les": "le", "des": "de", "est": "et", "ai": "e"}


def phonetique(mot: str) -> str:
    """Mot sans marque de pluriel (« payeurs » = « payeur ») et homophones courants ramenés à une même forme."""
    if mot in HOMOPHONES:
        return HOMOPHONES[mot]
    return mot[:-1] if len(mot) > 3 and mot[-1] in "sx" else mot


def fidelity(target: str, heard: str) -> float:
    a, b = content_words(target), content_words(heard)
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if a else 1.0


def trim_silence(wav, sr, thresh_db=-42.0, pad=0.08):
    """Coupe le silence au début et à la fin d'une phrase (garde 80 ms). Renvoie (audio, décalage du début en s)."""
    win = max(1, int(0.01 * sr))
    n = len(wav) // win
    if n == 0:
        return wav, 0.0
    env = 20 * np.log10(np.sqrt((wav[: n * win].reshape(n, win) ** 2).mean(axis=1)) + 1e-9)
    loud = np.where(env > thresh_db)[0]
    if len(loud) == 0:
        return wav, 0.0
    a = max(0, int((loud[0] * win) - pad * sr))
    b = min(len(wav), int((loud[-1] + 1) * win + pad * sr))
    return wav[a:b], a / sr


def align_words(sentence: str, heard_words, duration: float):
    """Associe chaque mot du texte à son horodatage Whisper (difflib), interpole les trous."""
    words = [w for w in sentence.replace("…", " ").split() if norm(w)]
    a = [norm(w) for w in words]
    b = [norm(w.word) for w in heard_words]
    times = [None] * len(a)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                times[i1 + k] = (heard_words[j1 + k].start, heard_words[j1 + k].end)
        elif tag == "replace" and j2 > j1:
            t0, t1, n = heard_words[j1].start, heard_words[j2 - 1].end, i2 - i1
            for k in range(n):
                times[i1 + k] = (t0 + (t1 - t0) * k / n, t0 + (t1 - t0) * (k + 1) / n)
    if all(t is None for t in times):  # Whisper n'a rien donné : répartition au prorata des lettres
        tot = sum(len(w) + 1.5 for w in words)
        acc = 0.0
        for i, w in enumerate(words):
            d = duration * (len(w) + 1.5) / tot
            times[i] = (acc, acc + d)
            acc += d
    for i in range(len(times)):
        if times[i] is None:
            prev = next((times[j] for j in range(i - 1, -1, -1) if times[j]), (0.0, 0.0))
            nxt = next((times[j] for j in range(i + 1, len(times)) if times[j]), (prev[1] + 0.3, prev[1] + 0.6))
            times[i] = (prev[1], max(prev[1] + 0.05, nxt[0]))
    return [(w, max(0.0, s), min(duration, max(s + 0.05, e))) for w, (s, e) in zip(words, times)]


# ─────────── nuances : un rythme et une insistance différents d'une phrase à l'autre ───────────
# Le clone de voix n'a pas de réglage d'émotion : on varie après coup, phrase par phrase (le cache reste valable).
# BDF_NUANCES = intensité (1 par défaut, 0 = voix uniforme, 1.5 = plus marqué). `vitesses` dans l'entrée = {"n": 0.9} force la vitesse de la phrase n.
def nuance(texte: str, intensite: float = 1.0) -> tuple[float, float, float]:
    """(vitesse, gain en dB, pause ajoutée après en secondes) pour une phrase, selon sa forme. Déterministe : même texte, même résultat."""
    mots = len(texte.split())
    fin = texte.rstrip()[-1:] if texte.strip() else ""
    vit, gain, pause = 1.0, 0.0, 0.0
    if mots <= 5:                      # phrase choc : on appuie, plus lent, un temps après
        vit, gain, pause = 0.90, 1.2, 0.16
    elif mots >= 16:                   # phrase longue : on déroule, plus vite
        vit, gain = 1.08, -0.5
    elif mots >= 11:
        vit = 1.03
    if fin == "?":                     # question : plus posée, laisse respirer
        vit, gain, pause = vit * 0.95, gain + 0.5, pause + 0.12
    elif fin == "!":                   # exclamation : plus énergique
        vit, gain = vit * 1.04, gain + 1.0
    elif fin == "…":                   # suspense
        vit, pause = vit * 0.93, pause + 0.2
    # petite variation propre à chaque phrase, pour que deux phrases voisines ne sonnent pas pareil
    alea = (int(hashlib.sha1(texte.encode("utf-8")).hexdigest()[:4], 16) / 0xFFFF - 0.5) * 0.06  # ±0.03
    vit += alea
    k = max(0.0, intensite)
    return (max(0.8, min(1.0 + (vit - 1.0) * k, 1.25)), max(-3.0, min(gain * k, 3.0)), max(0.0, pause * k))


def etirer(wav, sr: int, facteur: float):
    """Change la vitesse d'une phrase sans toucher à la hauteur (ffmpeg atempo). facteur > 1 = plus rapide."""
    import tempfile
    if abs(facteur - 1.0) < 0.005:
        return wav
    with tempfile.TemporaryDirectory(prefix="bdf-nu-") as d:
        a, b = Path(d) / "a.wav", Path(d) / "b.wav"
        sf.write(a, wav, sr)
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(a), "-af", f"atempo={facteur:.4f}", str(b)], capture_output=True)
        if r.returncode or not b.exists():
            return wav  # mieux vaut une phrase au rythme d'origine qu'un échec
        out, _ = sf.read(b, dtype="float32")
        return out if out.ndim == 1 else out[:, 0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_dir")
    ap.add_argument("--essais", type=int, default=4)
    ap.add_argument("--seuil", type=float, default=0.9)
    ap.add_argument("--episode-file", default="episode.json", help="fichier d'entrée du dossier (format long : voix-entree.json)")
    ap.add_argument("--budget-s", type=float, default=0.0, help="s'arrêter proprement (code 3) avant une nouvelle phrase une fois ce temps écoulé ; 0 = sans limite")
    ap.add_argument("--locuteur", default="", help="voix intégrée de Qwen3-TTS CustomVoice (ex. Ryan) au lieu du clone de la voix du propriétaire")
    ap.add_argument("--style", default="", help="consigne de ton pour la voix intégrée (ex. « voix de narrateur calme »)")
    args = ap.parse_args()
    ep_dir = Path(args.episode_dir).resolve()
    episode = json.loads((ep_dir / args.episode_file).read_text(encoding="utf-8"))
    phrases = episode["phrases"]
    pauses = {int(k): float(v) for k, v in (episode.get("pauses") or {}).items()}  # secondes de silence avant la phrase n (1 = première)
    vitesses = {int(k): float(v) for k, v in (episode.get("vitesses") or {}).items()}  # vitesse imposée pour la phrase n (1 = première)
    intensite = float(_E("BDF_NUANCES", "1"))
    cache = ep_dir / "cache"
    cache.mkdir(exist_ok=True)

    # truststore : l'antivirus intercepte le HTTPS (utile seulement si un téléchargement est déclenché)
    try:
        import truststore
        truststore.inject_into_ssl()
    except Exception:
        pass

    import torch
    from faster_whisper import WhisperModel
    from qwen_tts import Qwen3TTSModel

    asr = WhisperModel(CFG["whisper"], device=_E("BDF_WHISPER_DEVICE", "cpu"), compute_type="int8" if _E("BDF_WHISPER_DEVICE", "cpu") == "cpu" else "float16")
    ref_text = Path(CFG["ref_txt"]).read_text(encoding="utf-8").strip()
    model = None
    prompt = None

    def hear(wav, sr, text):
        tmp = cache / "_tmp.wav"
        sf.write(tmp, wav, sr)
        best = (-1.0, "", [])
        # Avec l'amorce du texte, puis sans : sur certaines phrases l'amorce fait halluciner Whisper (« Sous-titres … Amara.org ») alors que la voix est bonne.
        for prompt_txt in (text, None):
            segs, _ = asr.transcribe(str(tmp), language="fr", beam_size=3, word_timestamps=True, initial_prompt=prompt_txt)
            segs = list(segs)
            heard = " ".join(s.text.strip() for s in segs)
            sc = fidelity(text, heard)
            if sc > best[0]:
                best = (sc, heard, [w for s in segs for w in s.words])
            if sc >= 0.9:
                break
        return best[1], best[2]

    chunks, lines, report = [], [], []
    sr = 24000
    t_cursor = CFG["lead"]
    chunks.append(np.zeros(int(CFG["lead"] * sr), dtype=np.float32))
    t0 = time.time()
    for i, text in enumerate(phrases):
        # la voix de référence fait partie de la clé : changer `voix/ref.wav` invalide les phrases déjà générées
        extra = f"|{args.locuteur}|{args.style}" if args.locuteur else f"|ref:{REF_ID}"
        key = hashlib.sha1(f"{text}|{args.essais}|{CFG['temps']}{extra}|{Path(str(CFG['model'])).name}".encode()).hexdigest()[:12]
        wav_path, meta_path = cache / f"{i + 1:02d}-{key}.wav", cache / f"{i + 1:02d}-{key}.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if wav_path.exists() and meta_path.exists() else None
        if meta is not None:
            meta["score"] = fidelity(text, meta["entendu"])  # recalculé : la mesure a pu s'affiner depuis la mise en cache
        if meta is not None and meta["score"] >= args.seuil:  # une phrase mal lue en cache est refaite (avec le sauvetage)
            wav, sr = sf.read(wav_path)
            print(f"[{i + 1}/{len(phrases)}] cache ({meta['score']:.2f}) {text[:50]}", flush=True)
        else:
            if args.budget_s and time.time() - t0 > args.budget_s:
                print(f"BUDGET : {args.budget_s:.0f} s atteintes, arrêt avant la phrase {i + 1}/{len(phrases)} (cache conservé)", flush=True)
                sys.exit(3)
            if model is None:
                if args.locuteur:
                    model = Qwen3TTSModel.from_pretrained(CFG["model_custom"], device_map="cuda:0", dtype=getattr(torch, _E("BDF_DTYPE", "bfloat16")))
                else:
                    model = Qwen3TTSModel.from_pretrained(CFG["model"], device_map="cuda:0", dtype=getattr(torch, _E("BDF_DTYPE", "bfloat16")))
                    prompt = model.create_voice_clone_prompt(ref_audio=str(CFG["ref_wav"]), ref_text=ref_text, x_vector_only_mode=False)
            best = (-1.0, None, "", [])
            scores = []
            for temp in CFG["temps"][: args.essais]:
                if args.locuteur:
                    wavs, sr = model.generate_custom_voice(
                        text=text, language="French", speaker=args.locuteur, instruct=args.style or None,
                        temperature=temp, top_p=0.95, top_k=60, repetition_penalty=1.1,
                    )
                else:
                    wavs, sr = model.generate_voice_clone(
                        text=text, language="French", voice_clone_prompt=prompt,
                        temperature=temp, top_p=0.95, top_k=60, repetition_penalty=1.1,
                    )
                w = wavs[0].astype(np.float32)
                heard, hw = hear(w, sr, text)
                sc = fidelity(text, heard)
                scores.append(round(sc, 2))
                if sc > best[0]:
                    best = (sc, w, heard, hw)
                if sc >= 0.999:  # parfait : inutile de continuer
                    break
            if best[0] < args.seuil and not args.locuteur:
                # Sauvetage : certaines phrases ressortent illisibles à chaque essai ; sans point final (ou avec une autre température) elles passent.
                for var, temp in [(text.rstrip(" .!?…"), 1.0), (text.rstrip(" .!?…"), 0.9), (text.rstrip(" .!?…"), 1.1), (text, 0.8)]:
                    wavs, sr = model.generate_voice_clone(
                        text=var, language="French", voice_clone_prompt=prompt,
                        temperature=temp, top_p=0.95, top_k=60, repetition_penalty=1.1,
                    )
                    w = wavs[0].astype(np.float32)
                    heard, hw = hear(w, sr, text)
                    sc = fidelity(text, heard)
                    scores.append(round(sc, 2))
                    if sc > best[0]:
                        best = (sc, w, heard, hw)
                    if sc >= 0.999:
                        break
            wav = best[1]
            words = align_words(text, best[3], len(wav) / sr)
            meta = {"score": best[0], "scores": scores, "entendu": best[2], "mots": [[w, round(s, 3), round(e, 3)] for w, s, e in words]}
            sf.write(wav_path, wav, sr)
            meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            print(f"[{i + 1}/{len(phrases)}] {scores} -> {best[0]:.2f} | {text[:50]}", flush=True)
        wav, lead = trim_silence(wav.astype(np.float32), sr)
        dur = len(wav) / sr
        vit, gain_db, pause_apres = nuance(text, intensite) if intensite > 0 else (1.0, 0.0, 0.0)
        if i + 1 in vitesses:
            vit = max(0.8, min(vitesses[i + 1], 1.25))
        if abs(vit - 1.0) >= 0.005 and dur > 0:
            wav = etirer(wav, sr, vit)
        if abs(gain_db) > 0.01:
            wav = np.clip(wav * (10 ** (gain_db / 20)), -1.0, 1.0)
        ech = (len(wav) / sr) / dur if dur > 0 else 1.0  # les repères de mots suivent le changement de vitesse
        dur = len(wav) / sr
        if pauses.get(i + 1, 0) > 0 and i > 0:
            chunks.append(np.zeros(int(pauses[i + 1] * sr), dtype=np.float32))
            t_cursor += pauses[i + 1]
        lines.append({
            "start": round(t_cursor, 3), "end": round(t_cursor + dur, 3),
            "words": [
                {"w": w, "start": round(t_cursor + max(0.0, s - lead) * ech, 3), "end": round(t_cursor + min(dur, max(0.05, (e - lead) * ech)), 3)}
                for w, s, e in meta["mots"]
            ],
        })
        if meta["score"] < args.seuil:
            report.append({"phrase": i + 1, "texte": text, "score": round(meta["score"], 2), "entendu": meta["entendu"]})
        chunks += [wav.astype(np.float32), np.zeros(int((CFG["gap"] + pause_apres) * sr), dtype=np.float32)]
        t_cursor += dur + CFG["gap"] + pause_apres

    raw = np.concatenate(chunks)
    raw_path = ep_dir / "voice_raw.wav"
    sf.write(raw_path, raw, sr)
    chain = Path(CFG["chain"]).read_text(encoding="utf-8").strip()
    # Voix plus rapide (BDF_VITESSE, 1.10 par défaut = 10 % plus vite, même hauteur de voix) : on accélère le fichier final
    # et on ramène tous les repères de temps à la même échelle, les phrases en cache restent valables.
    v = max(0.8, min(float(_E("BDF_VITESSE", "1.10")), 1.4))
    rapide = f"atempo={v:.4f}," if abs(v - 1.0) > 0.001 else ""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(raw_path), "-af", f"{rapide}{chain},loudnorm=I=-16:TP=-1.5:LRA=7", "-ar", "48000", "-ac", "1", str(ep_dir / "voice.wav")],
        check=True,
    )
    if v != 1.0:
        for ln in lines:
            ln["start"], ln["end"] = round(ln["start"] / v, 3), round(ln["end"] / v, 3)
            for w in ln["words"]:
                w["start"], w["end"] = round(w["start"] / v, 3), round(w["end"] / v, 3)
    total = len(raw) / sr / v
    (ep_dir / "timings.json").write_text(json.dumps({"total": round(total, 3), "lines": lines}, ensure_ascii=False, indent=1), encoding="utf-8")
    (ep_dir / "voice_report.json").write_text(json.dumps({"seuil": args.seuil, "a_relire": report, "duree_s": round(total, 1), "calcul_s": round(time.time() - t0)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"FIN voix : {total:.1f} s d'audio en {time.time() - t0:.0f} s | à relire : {len(report)} phrase(s)", flush=True)


if __name__ == "__main__":
    main()
