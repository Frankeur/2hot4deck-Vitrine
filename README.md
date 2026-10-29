# 2Hot4Deck

**Un jeu de cartes à collectionner sur l'univers de League of Legends, jouable sur Discord et sur le web.**

## 🎮 Essayer le jeu

1. Rejoins le serveur Discord : **[discord.gg/D64RbA6bHa](https://discord.gg/D64RbA6bHa)**
2. Dans le salon d'accueil, appuie sur **Commencer** : tu reçois ton pack de départ et tous les salons du jeu s'ouvrent.
3. Tu peux aussi jouer sur le site, [2hot4deck.com](https://2hot4deck.com), en te connectant avec ton compte Discord.

🌐 Le site : [2hot4deck.com](https://2hot4deck.com) · 💬 Le Discord : [discord.gg/D64RbA6bHa](https://discord.gg/D64RbA6bHa) · 📄 La présentation : [frankeur.github.io/2hot4deck-Vitrine](https://frankeur.github.io/2hot4deck-Vitrine/)

> Projet de fans, non affilié à Riot Games. League of Legends et tous les noms associés appartiennent à Riot Games.
> Aucune vente : tout se gagne en jouant.

---

## Le jeu en bref

On ouvre des packs, on collectionne des champions, on monte leurs niveaux et on compose une équipe de 3 cartes.
Les combats se jouent automatiquement : chaque champion attaque et lance son ultime quand sa jauge est pleine.
Tout l'enjeu est dans la composition de l'équipe, les items, les runes et le placement.

- **Plus de 120 cartes**, de N à LR : sbires, monstres de la jungle, champions, versions UR et cartes de joueurs pros
- **12 items** à forger et améliorer, **10 runes** à débloquer
- **Rôles et lignes** : tanks, combattants, assassins, tireurs, mages et supports, en première ou en deuxième ligne
- **Bonus de région** quand plusieurs champions viennent de la même région

## Les modes

| Mode | Principe |
|---|---|
| 🏰 **La tour** | 200 étages, un boss tous les 10 étages (drakes, Baron Nashor, Dragon ancestral), une tour difficile de 101 à 200 |
| 🌿 **La jungle** | Le farm : chasse rapide, clear de camps avec un Châtiment en temps réel, exploration d'une carte de buissons |
| ⚒️ **Les donjons** | Des salles qui s'enchaînent sans soin, pour gagner des composants d'items |
| 🔮 **Le raid** | De 3 à 5 joueurs contre Ryze, qui s'adapte au groupe ; il débloque les runes |
| 🐉 **Les boss de salon** | Un drake ou le Baron apparaît pour tout le serveur à heures fixes |
| 🇪🇺 **La LEC** | Un tournoi solo contre les équipes de la LEC, 9 cartes en 3 trios |
| 🏆 **Les Worlds** | Le mode phare : un tournoi à 3 joueurs (ou en solo) du Play-In à la grande finale contre des équipes de pros. Une seule défaite et c'est fini |
| ⚔️ **L'arène et les duels** | Le PvP : classement de Fer à Challenger, duels en direct entre joueurs |
| ❓ **Les mini-jeux** | Quiz « Qui est-ce ? » sur les champions et les joueurs pros |

Les tournois rapportent des **cartes de pros**, à équiper comme **coach** pour renforcer son équipe.

## Le site

Un deuxième client du même jeu, sans passer par Discord :

- connexion avec son compte Discord (OAuth2)
- packs, collection, équipe, classements et fil des belles cartes tirées
- arène de combat animée en **PixiJS**, avec une interface façon jeu
- la jungle jouable dans le navigateur
- messagerie entre joueurs
- tier list des cartes avec le meilleur item et la meilleure rune par mode, calculée par simulation

## Côté technique

- **Python 3**, **discord.py** (commandes slash, boutons, menus, vues persistantes) et **SQLite**
- **Moteur de combat** partagé entre le bot et le site (`combat.py`) : vitesse et jauge d'action, ultis, effets, boucliers, résistances, passifs, traits de boss
- **Équilibrage par simulation** : des milliers de combats simulés pour régler la difficulté des étages et des boss, et classer les cartes
- **Images générées en Python** (Pillow) : cartes, arènes de combat et petites animations
- **Site web** sans framework : serveur HTTP Python, HTML, CSS et JavaScript, PixiJS pour l'arène
- **Mises en production automatiques** : un serveur Linux récupère les changements de GitHub et ne redémarre que ce qui a changé (bot ou site). Sauvegardes quotidiennes de la base. Une branche `test` alimente un site de test séparé.
- **Notes de mise à jour** publiées automatiquement sur Discord à chaque version

## Organisation du code

| Fichier | Rôle |
|---|---|
| `bot.py` | Le bot Discord : salons, panneaux, boutons et tous les modes de jeu |
| `combat.py` | Le moteur de combat et la génération des adversaires |
| `data.py` | Toutes les données et tous les réglages : cartes, taux, récompenses, difficulté, notes de mise à jour |
| `db.py` | La sauvegarde des comptes (SQLite) |
| `cartes_img.py` | Le dessin des cartes et des scènes de combat |
| `site_web/` | Le site : serveur, logique de jeu côté web et interface |
| `serveur/` | Installation du serveur, mises à jour automatiques et sauvegardes |

## Lancer le projet chez soi

```bash
pip install -r requirements.txt
cp .env.example .env        # puis mettre le token de ton propre bot Discord
python bot.py
```

Pour le site : `cd site_web`, copier `exemple_env.txt` en `.env` avec les identifiants d'une application Discord, puis `python serveur.py`.

Les images (illustrations des champions, photos des pros, décors) ne sont pas incluses dans ce dépôt : sans elles, le jeu fonctionne avec des visuels par défaut.

## À propos de cette version

Ce dépôt est une **vitrine publique** du projet. Pour garder la surprise aux joueurs et protéger leurs données, certaines choses ont été retirées :
un contenu secret du jeu, les identifiants Discord des joueurs (remplacés par des numéros factices) et les images qui n'appartiennent pas au projet.

Projet développé en octobre 2026 par **Frankeur**. Tous droits réservés sur le code.
