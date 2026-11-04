"""Commentaire à épingler sous un long : le cadeau (messages prêts à copier), l'annonce du prochain cadeau et l'invitation à s'abonner.

L'API YouTube ne permet pas d'épingler un commentaire : le texte est préparé (`commentaire-epingle.txt` dans le stock du cloud, à côté de la vidéo),
le propriétaire le colle sous la vidéo et clique « Épingler » dans YouTube Studio (30 secondes).
Les données viennent de `publication.json` (`cadeau`: titre, messages, suite) : voir autopilot/writer/CONSIGNES.md, points 4, 5 et 12.
"""
MAX_CAR = 9000  # YouTube accepte 10 000 caractères par commentaire


def texte(pub: dict) -> str | None:
    """Le commentaire prêt à coller, ou None si la publication n'a pas de cadeau (Short, ancien épisode)."""
    c = (pub or {}).get("cadeau")
    if not isinstance(c, dict):
        return None
    msgs = [m.strip() for m in c.get("messages", []) if isinstance(m, str) and m.strip()]
    if not msgs:
        return None
    titre = str(c.get("titre") or "Messages prêts à envoyer").strip()
    L = [f"🎁 {titre} (copie-colle, change juste le prénom) :", ""]
    L += [f"{i}. {m}" for i, m in enumerate(msgs, 1)]
    suite = str(c.get("suite") or "").strip()
    if suite:
        L += ["", suite]
    q = str((pub or {}).get("question_commentaires") or "").strip()
    L += ["", "👉 " + (q or "Dis-moi en réponse lequel tu testes en premier.")]
    out = "\n".join(L)
    return out if len(out) <= MAX_CAR else out[:MAX_CAR].rsplit("\n", 1)[0]
