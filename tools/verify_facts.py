"""Vérifie automatiquement chaque fait de la banque d'idées dans ses sources.

Pour chaque fait, les mots-clés `check` (noms, dates, nombres) doivent tous apparaître dans la page source.
Les sources où c'est le cas sont listées dans `verified`. Ce n'est pas une preuve absolue : c'est un garde-fou
contre les chiffres inventés ou mal recopiés, avant la relecture humaine.

Usage : python tools/verify_facts.py <dossier ideas>
"""
import html
import json
import re
import sys
import unicodedata
import subprocess
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
_cache: dict[str, str] = {}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"(?<=\d)[\s,.  ](?=\d{3}\b)", "", s)  # 12,262 / 12 262 → 12262
    return re.sub(r"\s+", " ", s)


def page(url: str) -> str:
    if url not in _cache:
        try:
            # curl utilise le magasin de certificats du système (le Python embarqué peut avoir des certificats périmés)
            raw = subprocess.run(["curl", "-sL", "--max-time", "30", "-A", "BureauDesFaits/1.0 (verification de faits)", url],
                                 capture_output=True, check=True).stdout.decode("utf-8", "ignore")
            _cache[url] = norm(html.unescape(re.sub(r"<[^>]+>", " ", raw)))
        except Exception as e:  # source injoignable : non vérifiée
            print(f"  ! {url} : {e}", flush=True)
            _cache[url] = ""
    return _cache[url]


files = sorted(Path(sys.argv[1]).glob("*.json"))
for n, f in enumerate(files, 1):
    idea = json.loads(f.read_text(encoding="utf-8"))
    for fact in idea["facts"]:
        terms = [norm(t) for t in fact.get("check", [])]
        if not terms:
            continue
        fact["verified"] = [u for u in fact["sources"] if all(t in page(u) for t in terms)]
    f.write_text(json.dumps(idea, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = sum(1 for x in idea["facts"] if x.get("verified"))
    print(f"{n}/{len(files)} {idea['slug']} : {ok}/{len(idea['facts'])} faits retrouvés", flush=True)
