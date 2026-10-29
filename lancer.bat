@echo off
title 2Hot4Deck - bot
cd /d "%~dp0"
set RECHARGE_AUTO=1
set PYTHONUTF8=1
echo Verification des modules...
python -m pip install -q -r requirements.txt
:boucle
python bot.py
echo.
echo Le bot s'est arrete. Redemarrage dans 3 secondes... (ferme cette fenetre pour l'arreter)
timeout /t 3 /nobreak >nul
goto boucle
