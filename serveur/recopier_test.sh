#!/bin/bash
# Remet sur le site de test une copie fraîche des vraies données du site.
UTIL=${SUDO_USER:-ubuntu}; VRAI=/home/$UTIL/2hot4deck; TEST=/home/$UTIL/2hot4deck-test
systemctl stop 2hot4deck-test
rm -f $TEST/site_web/site.db $TEST/site_web/site.db-wal $TEST/site_web/site.db-shm
sudo -u $UTIL sqlite3 $VRAI/site_web/site.db ".backup '$TEST/site_web/site.db'"
systemctl start 2hot4deck-test; echo "Site de test remis à zéro avec les données du moment."
