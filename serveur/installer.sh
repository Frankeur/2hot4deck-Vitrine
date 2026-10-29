#!/bin/bash
# 2Hot4Deck · installation sur le serveur (Ubuntu 24.04), à lancer une seule fois :
#   sudo bash ~/2hot4deck/serveur/installer.sh
# Ce script n'écrit aucun secret : les fichiers .env et les bases sont copiés à part, par toi.
set -e
UTIL=${SUDO_USER:-ubuntu}
DOSSIER=/home/$UTIL/2hot4deck
IP=$(curl -4 -s https://ifconfig.me || hostname -I | awk '{print $1}')
ADRESSE="${IP//./-}.sslip.io"          # une adresse gratuite qui pointe vers ce serveur, avec HTTPS
DOMAINE=$(tr -d ' \r\n' < $DOSSIER/serveur/domaine.txt 2>/dev/null)
[ -n "$DOMAINE" ] && ADRESSE="$DOMAINE"  # le vrai nom du site, s'il est noté dans serveur/domaine.txt

echo "== 1/6 Les logiciels (si Ubuntu fait déjà ses mises à jour, on attend qu'il ait fini)"
apt-get -o DPkg::Lock::Timeout=600 update -q
apt-get -o DPkg::Lock::Timeout=600 install -y -q python3-venv python3-pip git sqlite3 debian-keyring debian-archive-keyring apt-transport-https curl
timedatectl set-timezone Europe/Paris   # le jeu compte ses journées à l'heure de Paris

echo "== 2/6 Python et les modules du bot"
sudo -u $UTIL python3 -m venv $DOSSIER/.venv
sudo -u $UTIL $DOSSIER/.venv/bin/pip install -q -r $DOSSIER/requirements.txt

echo "== 3/6 Le bot et le site démarrent tout seuls (et redémarrent s'ils plantent)"
cat > /etc/systemd/system/2hot4deck-bot.service <<UNIT
[Unit]
Description=2Hot4Deck - le bot Discord
After=network-online.target
Wants=network-online.target
[Service]
User=$UTIL
WorkingDirectory=$DOSSIER
Environment=PYTHONUTF8=1
ExecStart=$DOSSIER/.venv/bin/python bot.py
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/2hot4deck-site.service <<UNIT
[Unit]
Description=2Hot4Deck - le site
After=network-online.target
Wants=network-online.target
[Service]
User=$UTIL
WorkingDirectory=$DOSSIER/site_web
Environment=PYTHONUTF8=1
ExecStart=$DOSSIER/.venv/bin/python serveur.py
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT

echo "== 4/6 Les mises à jour automatiques depuis GitHub (toutes les minutes)"
cat > /etc/systemd/system/2hot4deck-maj.service <<UNIT
[Unit]
Description=2Hot4Deck - récupère les changements de GitHub
[Service]
Type=oneshot
ExecStart=/bin/bash $DOSSIER/serveur/mettre_a_jour.sh $UTIL
UNIT
cat > /etc/systemd/system/2hot4deck-maj.timer <<UNIT
[Unit]
Description=2Hot4Deck - vérifie GitHub toutes les minutes
[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
[Install]
WantedBy=timers.target
UNIT

echo "== 5/6 Une sauvegarde des bases chaque nuit (on garde 14 jours)"
cat > /etc/cron.d/2hot4deck-sauvegarde <<CRON
30 4 * * * $UTIL /bin/bash $DOSSIER/serveur/sauvegarder.sh
CRON

echo "== 6/6 L'adresse du site en HTTPS : https://$ADRESSE"
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get -o DPkg::Lock::Timeout=600 update -q && apt-get -o DPkg::Lock::Timeout=600 install -y -q caddy
fi
PORT=$(grep -E '^PORT=' $DOSSIER/site_web/.env 2>/dev/null | cut -d= -f2 | tr -d ' "'); PORT=${PORT:-8081}
if [ -n "$DOMAINE" ]; then
cat > /etc/caddy/Caddyfile <<CADDY
$DOMAINE {
    reverse_proxy 127.0.0.1:$PORT
}
www.$DOMAINE {
    redir https://$DOMAINE{uri} permanent
}
${IP//./-}.sslip.io {
    reverse_proxy 127.0.0.1:$PORT
}
CADDY
else
cat > /etc/caddy/Caddyfile <<CADDY
$ADRESSE {
    reverse_proxy 127.0.0.1:$PORT
}
CADDY
fi
systemctl reload caddy || systemctl restart caddy

systemctl daemon-reload
systemctl enable --now 2hot4deck-maj.timer
if [ -f $DOSSIER/.env ] && [ -f $DOSSIER/faille.db ]; then
  systemctl enable --now 2hot4deck-bot 2hot4deck-site
  echo; echo "C'est en route ! Le site : https://$ADRESSE"
else
  systemctl enable 2hot4deck-bot 2hot4deck-site
  echo; echo "Presque fini : il manque encore tes fichiers .env et faille.db."
  echo "Copie-les, puis lance : sudo systemctl start 2hot4deck-bot 2hot4deck-site"
fi
echo "Dans le portail développeur Discord, ajoute cette adresse de retour (OAuth2 > Redirects) :"
echo "   https://$ADRESSE/retour"
