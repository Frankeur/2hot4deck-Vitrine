#!/bin/bash
# Récupère les changements de GitHub. Redémarre seulement ce qui a changé :
# le bot si un fichier du bot a changé, le site si un fichier du site a changé.
UTIL=${1:-ubuntu}
cd /home/$UTIL/2hot4deck || exit 0
avant=$(sudo -u $UTIL git rev-parse HEAD)
sudo -u $UTIL git pull -q --ff-only || exit 0
apres=$(sudo -u $UTIL git rev-parse HEAD)
if [ "$avant" != "$apres" ]; then
change=$(sudo -u $UTIL git diff --name-only "$avant" "$apres")
echo "Mise à jour $avant -> $apres"; echo "$change"
if echo "$change" | grep -q '^requirements.txt$'; then sudo -u $UTIL .venv/bin/pip install -q -r requirements.txt; fi
if echo "$change" | grep -qvE '^(site_web/|serveur/|.*\.md$)'; then systemctl restart 2hot4deck-bot; fi
if echo "$change" | grep -qE '^(site_web/|data\.py|combat\.py|db\.py|bot\.py|cartes_img\.py)'; then systemctl restart 2hot4deck-site; fi
fi

# Le site de test suit la branche « test » : il se met à jour de la même façon
T=/home/$UTIL/2hot4deck-test
if [ -d "$T" ]; then
  cd "$T"; a=$(sudo -u $UTIL git rev-parse HEAD); sudo -u $UTIL git pull -q --ff-only || exit 0
  [ "$a" != "$(sudo -u $UTIL git rev-parse HEAD)" ] && systemctl restart 2hot4deck-test
fi
