#!/bin/bash
# 2Hot4Deck · le site de test (test.2hot4deck.com), à lancer une fois :
#   sudo bash ~/2hot4deck/serveur/installer_test.sh
# Il tourne à part : sa propre copie du code (branche « test » de GitHub) et sa propre copie des données.
# Le vrai site et le bot ne sont jamais touchés.
set -e
UTIL=${SUDO_USER:-ubuntu}
VRAI=/home/$UTIL/2hot4deck
TEST=/home/$UTIL/2hot4deck-test
DOMAINE=$(tr -d ' \r\n' < $VRAI/serveur/domaine.txt)
PORT_TEST=8091

echo "== 1/4 Le code de test (branche « test »)"
if [ ! -d $TEST ]; then sudo -u $UTIL git clone -q -b test git@github.com:Frankeur/2hot4deck.git $TEST; fi

echo "== 2/4 Une copie des données du site (les vraies ne bougent pas)"
if [ ! -f $TEST/site_web/site.db ]; then sudo -u $UTIL sqlite3 $VRAI/site_web/site.db ".backup '$TEST/site_web/site.db'"; fi
# les réglages du site, sur un autre port ; pas de token du bot : le site de test n'envoie aucun message privé sur Discord
grep -v '^PORT=' $VRAI/site_web/.env > $TEST/site_web/.env; echo "PORT=$PORT_TEST" >> $TEST/site_web/.env
chown $UTIL:$UTIL $TEST/site_web/.env; chmod 600 $TEST/site_web/.env

echo "== 3/4 Le site de test démarre tout seul"
cat > /etc/systemd/system/2hot4deck-test.service <<UNIT
[Unit]
Description=2Hot4Deck - le site de TEST
After=network-online.target
[Service]
User=$UTIL
WorkingDirectory=$TEST/site_web
Environment=PYTHONUTF8=1
ExecStart=$VRAI/.venv/bin/python serveur.py
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload; systemctl enable --now 2hot4deck-test

echo "== 4/4 L'adresse https://test.$DOMAINE"
grep -q "^test.$DOMAINE" /etc/caddy/Caddyfile || cat >> /etc/caddy/Caddyfile <<CADDY
test.$DOMAINE {
    reverse_proxy 127.0.0.1:$PORT_TEST
}
CADDY
systemctl reload caddy
echo; echo "Le site de test : https://test.$DOMAINE"
echo "Dans le portail Discord (OAuth2 > Redirects), ajoute aussi : https://test.$DOMAINE/retour"
echo "Pour repartir des vraies données du moment : sudo bash $VRAI/serveur/recopier_test.sh"
