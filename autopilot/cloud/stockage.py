"""Stockage des vidéos et miniatures entre les étapes du workflow cloud.

Deux réserves au choix (variable STOCKAGE) :
  github (défaut, sans compte ni carte) : pièces jointes d'une « release » privée du dépôt (< 2 Go par fichier, pas de limite de total annoncée) ;
  r2 : Cloudflare R2 (compatible S3), 10 Go gratuits, carte bancaire probablement demandée.

Usage : python autopilot/cloud/stockage.py put <fichier> <clé>        envoie un fichier
        python autopilot/cloud/stockage.py get <clé> <fichier>        le récupère
        python autopilot/cloud/stockage.py ls [préfixe]               liste (clé, taille, date)
        python autopilot/cloud/stockage.py purge <préfixe> --jours N  supprime ce qui date de plus de N jours (--dry-run pour voir)
        python autopilot/cloud/stockage.py usage                      espace utilisé / 10 Go gratuits

Backend github : outil `gh` connecté (en Actions : GH_TOKEN) ; variables GH_REPO (ex. liliputiennn/bureau-des-faits), release « stock ».
Backend r2, variables (secrets GitHub en cloud, définies par toi en local) :
  R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET
Convention de clés : exports/<id>/<id>.mp4, exports/<id>/miniature.png, voix/<id>/voice.wav …
Nécessite `pip install boto3`.
"""
import argparse, os, sys
from datetime import datetime, timedelta, timezone

GRATUIT_OCTETS = 10 * 1024**3


def client():
    import boto3
    from botocore.config import Config
    manque = [v for v in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET") if not os.environ.get(v)]
    if manque:
        raise SystemExit("variables manquantes : " + ", ".join(manque))
    return boto3.client(
        "s3", endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto", config=Config(retries={"max_attempts": 5, "mode": "standard"}, signature_version="s3v4"),
    )


def objets(c, prefixe=""):
    """Tous les objets du seau sous `prefixe` : dicts {Key, Size, LastModified}."""
    suite = {}
    while True:
        r = c.list_objects_v2(Bucket=os.environ["R2_BUCKET"], Prefix=prefixe, **suite)
        yield from r.get("Contents", [])
        if not r.get("IsTruncated"):
            return
        suite = {"ContinuationToken": r["NextContinuationToken"]}


def a_purger(liste, jours, maintenant=None):
    """Clés plus vieilles que `jours` jours (fonction pure, testée)."""
    limite = (maintenant or datetime.now(timezone.utc)) - timedelta(days=jours)
    return [o["Key"] for o in liste if o["LastModified"] < limite]


TAG = "stock"


def _gh(*args, check=True):
    import subprocess
    exe = __import__("shutil").which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"
    repo = os.environ.get("GH_REPO")
    cmd = [exe, *args] + (["--repo", repo] if repo and args[0] in ("release",) else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode:
        raise SystemExit(f"gh {' '.join(args[:3])} : {r.stderr.strip()[:300]}")
    return r


def nom_asset(cle: str) -> str:
    """Une release n'a pas de dossiers : « exports/x/x.mp4 » devient « exports__x__x.mp4 »."""
    return cle.replace("/", "__")


def main_github(a) -> int:
    if _gh("release", "view", TAG, check=False).returncode:
        _gh("release", "create", TAG, "--title", "Stock de vidéos", "--notes", "Fichiers temporaires du workflow (purgés automatiquement).")
    if a.cmd == "put":
        import shutil, tempfile
        tmp = os.path.join(tempfile.mkdtemp(prefix="bdf-st-"), nom_asset(a.cle))
        shutil.copy(a.fichier, tmp)  # le nom de l'asset est celui du fichier : on le renomme par copie
        _gh("release", "upload", TAG, tmp, "--clobber")
        print(f"envoyé : {a.cle}")
    elif a.cmd == "get":
        d = os.path.dirname(os.path.abspath(a.fichier))
        os.makedirs(d, exist_ok=True)
        _gh("release", "download", TAG, "--pattern", nom_asset(a.cle), "--dir", d, "--clobber")
        os.replace(os.path.join(d, nom_asset(a.cle)), a.fichier)
        print(f"récupéré : {a.fichier}")
    else:
        import json
        assets = json.loads(_gh("release", "view", TAG, "--json", "assets").stdout)["assets"]
        if a.cmd == "ls":
            for x in assets:
                if x["name"].startswith(nom_asset(a.prefixe)):
                    print(f"{x['name']}	{x['size'] / 1048576:.1f} Mo	{x['updatedAt'][:16]}")
        elif a.cmd == "purge":
            liste = [{"Key": x["name"], "LastModified": datetime.fromisoformat(x["updatedAt"].replace("Z", "+00:00"))} for x in assets if x["name"].startswith(nom_asset(a.prefixe))]
            cles = a_purger(liste, a.jours)
            print(f"{len(cles)} objet(s) de plus de {a.jours} jours sous « {a.prefixe} »")
            for k in cles:
                print(("[dry-run] " if a.dry_run else "supprime ") + k)
                if not a.dry_run:
                    _gh("release", "delete-asset", TAG, k, "--yes")
        elif a.cmd == "usage":
            print(f"{sum(x['size'] for x in assets) / 1024**3:.2f} Go dans la release « {TAG} » ({len(assets)} fichiers)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("put"); p.add_argument("fichier"); p.add_argument("cle")
    p = sp.add_parser("get"); p.add_argument("cle"); p.add_argument("fichier")
    p = sp.add_parser("ls"); p.add_argument("prefixe", nargs="?", default="")
    p = sp.add_parser("purge"); p.add_argument("prefixe"); p.add_argument("--jours", type=int, required=True); p.add_argument("--dry-run", action="store_true")
    sp.add_parser("usage")
    a = ap.parse_args()
    if os.environ.get("STOCKAGE", "github") == "github":
        return main_github(a)
    c, b = client(), os.environ["R2_BUCKET"]
    if a.cmd == "put":
        c.upload_file(a.fichier, b, a.cle)
        print(f"envoyé : {a.cle}")
    elif a.cmd == "get":
        os.makedirs(os.path.dirname(os.path.abspath(a.fichier)), exist_ok=True)
        c.download_file(b, a.cle, a.fichier)
        print(f"récupéré : {a.fichier}")
    elif a.cmd == "ls":
        for o in objets(c, a.prefixe):
            print(f"{o['Key']}\t{o['Size'] / 1048576:.1f} Mo\t{o['LastModified']:%Y-%m-%d %H:%M}")
    elif a.cmd == "purge":
        cles = a_purger(list(objets(c, a.prefixe)), a.jours)
        print(f"{len(cles)} objet(s) de plus de {a.jours} jours sous « {a.prefixe} »")
        for k in cles:
            print(("[dry-run] " if a.dry_run else "supprime ") + k)
            if not a.dry_run:
                c.delete_object(Bucket=b, Key=k)
    elif a.cmd == "usage":
        total = sum(o["Size"] for o in objets(c))
        print(f"{total / 1024**3:.2f} Go utilisés sur {GRATUIT_OCTETS / 1024**3:.0f} Go gratuits ({100 * total / GRATUIT_OCTETS:.0f} %)")
        if total > 0.8 * GRATUIT_OCTETS:
            print("ATTENTION : plus de 80 % du quota gratuit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
