#!/usr/bin/env bash
# Enregistre ce qui a été ajouté (git add) et le pousse, même si le dépôt a bougé entre-temps (autre workflow, transfert depuis le PC) :
# on fusionne en gardant la version de cette exécution pour les fichiers en conflit, puis on réessaie jusqu'à 4 fois.
# Usage : bash autopilot/cloud/enregistrer.sh "message de commit"
set -u
git diff --cached --quiet && { echo "rien à enregistrer"; exit 0; }
git commit -qm "$1"
git checkout -q -- . 2>/dev/null || true   # écarte les modifications non ajoutées (restes de rendu) pour que la fusion passe
for essai in 1 2 3 4; do
  git fetch -q origin main
  if ! git merge -q -X ours origin/main -m "Fusion automatique" 2>/dev/null; then
    git merge --abort 2>/dev/null || true
    echo "fusion impossible (essai $essai), nouvel essai"; sleep 8; continue
  fi
  if git push -q origin HEAD:main; then echo "enregistré (essai $essai)"; exit 0; fi
  sleep 8
done
echo "::error::impossible d'enregistrer l'état (voir les journaux)"; exit 1
