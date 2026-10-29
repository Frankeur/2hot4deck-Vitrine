#!/bin/bash
# Copie propre des bases (même pendant que le bot tourne), une par jour, gardée 14 jours.
D=$(dirname "$0")/..; S=$HOME/sauvegardes; mkdir -p "$S"; J=$(date +%Y-%m-%d)
sqlite3 "$D/faille.db" ".backup '$S/faille_$J.db'"
[ -f "$D/site_web/site.db" ] && sqlite3 "$D/site_web/site.db" ".backup '$S/site_$J.db'"
find "$S" -name '*.db' -mtime +14 -delete
