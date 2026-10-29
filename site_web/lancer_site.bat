@echo off
title 2Hot4Deck - le site
cd /d "%~dp0"
set PYTHONUTF8=1
echo Le site joue avec sa propre base (site.db). Le jeu Discord n'est pas touche.
python serveur.py
pause
