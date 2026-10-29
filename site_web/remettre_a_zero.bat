@echo off
title 2Hot4Deck - remettre le site a zero
cd /d "%~dp0"
echo Le site va repartir d'une copie toute fraiche du jeu Discord (faille.db).
echo Tout ce qui a ete fait sur le site depuis (packs, tour, equipe...) sera perdu.
echo Ferme d'abord la fenetre du site s'il tourne.
echo.
set /p OK=Tape OUI puis Entree pour continuer : 
if /I not "%OK%"=="OUI" goto fin
if exist site.db del site.db
echo C'est fait : relance lancer_site.bat, la nouvelle copie se fera toute seule.
:fin
pause
