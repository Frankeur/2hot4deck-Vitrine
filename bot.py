"""2Hot4Deck : jeu de collection Discord (packs, équipe, tour). Projet de fans, non affilié à Riot Games.
Lancement : python bot.py   |   Installation des salons : /installer · mise à jour des panneaux : /actualiser
(ou mentionne le bot en écrivant « installer » ou « actualiser »)."""
import asyncio
import io
import os
import random
import time

import aiohttp
import discord
from discord import app_commands

import cartes_img
import combat
import data
import db

# --- Lecture du fichier .env (TOKEN=...) --------------------------------------
if os.path.exists(".env"):
    for ligne in open(".env", encoding="utf-8"):
        if "=" in ligne and not ligne.strip().startswith("#"):
            cle, valeur = ligne.strip().split("=", 1)
            os.environ.setdefault(cle.strip(), valeur.strip())

COULEUR = 0x0AC8B9
AVERTISSEMENT = "Projet de fans, non affilié à Riot Games."


class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
        self.synchro = False
        self.proprietaires = None   # identifiants du ou des propriétaires du bot, lus au premier besoin

    async def setup_hook(self):
        for panneau in PANNEAUX.values():  # rend les boutons des salons permanents
            self.add_view(panneau["vue"]())
        self.add_view(VueBoss())
        self.add_view(PanneauTourPros())
        self.add_view(PanneauLEC())
        self.add_view(PanneauTestPerso())
        self.add_view(VueButinRaid())      # le bouton « Choisir ma rune » d'un raid gagné survit à un redémarrage           # les boutons d'un boss de salon en cours survivent à un redémarrage
        self.boss = asyncio.create_task(surveiller_boss())
        # Les cartes encadrées sont fabriquées en arrière-plan : le bot répond pendant ce temps.
        self.cartes = asyncio.create_task(asyncio.to_thread(cartes_img.preparer_tout))
        self.imports = asyncio.create_task(surveiller_import())
        self.menage = asyncio.create_task(boucle_menage())
        # 16 octobre (soir) : plus de porte pour le site, il a son propre moteur et sa propre base (site_web/jeu.py).
        if os.environ.get("RECHARGE_AUTO"):   # activé par lancer.bat
            self.surveillance = asyncio.create_task(surveiller_fichiers())

    async def on_ready(self):
        print(f"Connecté en tant que {self.user}" + (" · rechargement automatique activé" if os.environ.get("RECHARGE_AUTO") else ""))
        if self.synchro:
            return
        self.synchro = True
        # Les commandes sont enregistrées serveur par serveur : elles apparaissent tout de suite.
        for serveur in self.guilds:
            self.tree.copy_global_to(guild=serveur)
            try:
                cmds = await self.tree.sync(guild=serveur)
                print(f"  {serveur.name} : commandes {', '.join('/' + c.name for c in cmds)}")
            except discord.HTTPException as e:
                print(f"  {serveur.name} : synchronisation impossible ({e})")
        self.tree.clear_commands(guild=None)   # efface les anciennes commandes globales
        await self.tree.sync()
        print("Prêt. Tape /installer sur ton serveur, ou mentionne le bot en écrivant « installer ».")
        for serveur in self.guilds:
            await vider_tirages(serveur)
            await publier_maj(serveur)
            asyncio.create_task(synchroniser_roles(serveur))
            try:   # le panneau des Worlds suit les nouvelles phases sans attendre /installer
                await renommer_anciens_salons(serveur)
                if trouver_salon(serveur, data.SALON_TOUR_PROS):
                    await installer_tour_pros(serveur)
                if data.TOUR_PROS_OUVERTE:
                    await ouvrir_worlds(serveur)
                await installer_lec(serveur)
                await installer_test_perso(serveur)
                if data.LEC_OUVERTE:
                    await ouvrir_lec(serveur)
                await annonce_13_octobre(serveur)
                for _, nom_role, couleur in data.ROLES_NIVEAU:   # les nouveaux rôles de niveau apparaissent sans attendre /installer
                    if not discord.utils.get(serveur.roles, name=nom_role):
                        await serveur.create_role(name=nom_role, colour=discord.Colour(couleur), reason="Paliers de niveau de compte")
            except Exception as erreur:
                print(f"Panneau des Worlds non mis à jour ({erreur!r}).")

    async def on_message(self, message):
        # Secours si les commandes / n'apparaissent pas : « @LeBot installer »
        if not (message.guild and self.user in message.mentions and message.author.guild_permissions.administrator):
            return
        texte = message.content.lower()
        if "installer" in texte:
            await message.reply(await installer_salons(message.guild))
        elif "actualiser" in texte:
            n = await actualiser_panneaux(message.guild)
            remarque = await amenager(message.guild)
            await ecrire_guide(message.guild)
            await message.reply(f"{n} panneau(x) mis à jour." + remarque)

    async def on_interaction(self, i):
        # Bouton du premier pack, envoyé en message privé : debut:<id du serveur>
        if i.type == discord.InteractionType.component:
            cid = (i.data or {}).get("custom_id", "")
            if cid.startswith("debut:"):
                await premier_pack(i, int(cid.split(":")[1]))
                return
        if i.type in (discord.InteractionType.component, discord.InteractionType.modal_submit):
            await menage(i)   # les messages privés du jeu s'effacent tout seuls


async def surveiller_fichiers():
    """Arrête le bot dès qu'un fichier .py du dossier change : lancer.bat le redémarre avec la nouvelle version."""
    dossier = os.path.dirname(os.path.abspath(__file__))

    def etat():
        return {f: os.path.getmtime(os.path.join(dossier, f)) for f in os.listdir(dossier) if f.endswith(".py")}

    depart = etat()
    while True:
        await asyncio.sleep(2)
        try:
            change = etat() != depart
        except OSError:
            continue   # fichier en cours d'écriture
        if change:
            print("Fichiers modifiés : redémarrage du bot…")
            await asyncio.sleep(1.5)   # laisse le temps aux autres fichiers d'être écrits
            await bot.close()
            return


async def surveiller_import():
    """Lance pros/importer.py (données et photos des joueurs pros) à chaque fois que ce script change, sans redémarrer le bot.
    Si le script change pendant qu'il tourne, l'ancien est arrêté."""
    import subprocess, sys
    dossier = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pros")
    script, temoin = os.path.join(dossier, "importer.py"), os.path.join(dossier, "fait.txt")
    en_cours = None
    while True:
        await asyncio.sleep(5)
        try:
            if not os.path.exists(script):
                continue
            version = str(os.path.getmtime(script))
            if os.path.exists(temoin) and open(temoin).read() == version:
                continue
            if en_cours and en_cours.poll() is None:
                en_cours.terminate()
            with open(temoin, "w") as f:
                f.write(version)
            print("Import des joueurs pros : démarrage…")
            en_cours = subprocess.Popen([sys.executable, script], cwd=dossier)
        except Exception as e:
            print(f"Import des joueurs pros : {e}")


bot = Bot()


# ================================ OUTILS =====================================
async def charger(i):
    p = db.get_joueur(i.guild_id, i.user.id)
    if not p:
        await i.response.send_message("Tu n'as pas encore de compte. Va dans le salon d'accueil et appuie sur **Commencer**.", ephemeral=True)
        return None
    pseudo = getattr(i.user, "display_name", "") or ""
    if isinstance(pseudo, str) and pseudo and p["pseudo"] != pseudo:   # mémorisé pour l'afficher dans les classements
        p["pseudo"] = pseudo
        db.sauver(p)
    await maj_role_niveau(i.user, p["niveau"])
    return p


async def synchroniser_roles(guilde):
    """14 octobre : au démarrage, range les rôles de niveau (affichés à part dans la liste des membres, du plus haut au plus bas,
    juste au-dessus du rôle Joueur) et remet à jour le rôle de niveau et de rang d'arène de chaque joueur."""
    try:
        joueur = discord.utils.get(guilde.roles, name=data.ROLE_JOUEUR)
        roles = [discord.utils.get(guilde.roles, name=nom) for _, nom, _ in data.ROLES_NIVEAU]
        roles = [r for r in roles if r]
        for r in roles:
            if not r.hoist:
                await r.edit(hoist=True, reason="Rôles de niveau affichés dans la liste des membres")
        haut = guilde.me.top_role.position
        if joueur and roles and joueur.position + len(roles) < haut:
            await guilde.edit_role_positions({r: joueur.position + 1 + k for k, r in enumerate(roles)}, reason="Rôles de niveau rangés")
    except Exception as erreur:
        print(f"Rangement des rôles de niveau : {erreur!r}")
    faits = 0
    for (u, niveau, points) in db.con.execute("SELECT user_id, niveau, arene_points FROM joueurs WHERE guild_id=?", (guilde.id,)).fetchall():
        try:
            membre = guilde.get_member(u) or await guilde.fetch_member(u)
            await maj_role_niveau(membre, niveau)
            if niveau >= data.DEBLOCAGES.get("arene", 1):
                await maj_rang(membre, points)
            faits += 1
        except Exception:
            continue
        await asyncio.sleep(0.5)
    print(f"Rôles de niveau et d'arène remis à jour pour {faits} joueur(s).")


async def maj_role_niveau(membre, niveau):
    """Donne au membre le rôle Discord de son palier de niveau (un seul à la fois) et retire les précédents."""
    if not isinstance(membre, discord.Member):
        return
    voulu = next((nom for n, nom, _ in reversed(data.ROLES_NIVEAU) if niveau >= n), None)
    noms = {r[1] for r in data.ROLES_NIVEAU}
    actuels = [r for r in membre.roles if r.name in noms]
    if [r.name for r in actuels] == ([voulu] if voulu else []):
        return   # déjà à jour : aucun appel à Discord
    try:
        en_trop = [r for r in actuels if r.name != voulu]
        if en_trop:
            await membre.remove_roles(*en_trop, reason="Changement de palier de niveau")
        role = discord.utils.get(membre.guild.roles, name=voulu) if voulu else None
        if role and role not in membre.roles:
            await membre.add_roles(role, reason="Palier de niveau de compte")
    except discord.HTTPException as erreur:
        print(f"Rôle de niveau de {membre.display_name} : {erreur!r}")   # permission manquante, ou rôle du bot placé trop bas


NOMS_MODES = {"jungle": "la jungle", "donjons": "les donjons", "arene": "l'arène", "duels": "les duels"}


def noter_combat(p, mode, detail, victoire, tours, etat, possedees=None, adversaire=None):
    """Garde une trace du combat pour l'équilibrage : équipes, niveaux, dégâts de chacun, issue. Ne doit jamais gêner le jeu."""
    try:
        import json
        unites = []
        for u in etat:
            ligne = {"camp": u["camp"], "carte": u["cid"] or u["nom"], "pv": u["pv"], "pvmax": u["pvmax"], "degats": u.get("inflige", 0)}
            if u["camp"] == 0 and possedees and u["cid"] in possedees:
                ligne["niveau"], ligne["etoiles"] = possedees[u["cid"]]["niveau"], possedees[u["cid"]]["etoiles"]
            unites.append(ligne)
        donnees = {"niveau_compte": p["niveau"], "etage": p["etage"], "unites": unites}
        if adversaire:
            donnees["adversaire"] = adversaire
        db.journal_combat(p["guild_id"], p["user_id"], time.time(), mode, detail, victoire, tours, json.dumps(donnees, ensure_ascii=False, default=str))
    except Exception:
        pass


def energie_max(p):
    """Énergie maximale du joueur : elle grandit avec son niveau de compte."""
    return data.ENERGIE_MAX + data.ENERGIE_PAR_NIVEAU * (p["niveau"] - 1)


def gagner_xp_compte(p, source, fois=1):
    """Ajoute l'XP de compte d'une activité. Renvoie (lignes à afficher s'il y a montée de niveau, cartes gagnées).
    L'appelant doit sauvegarder le joueur ensuite."""
    if p["niveau"] >= data.NIVEAU_COMPTE_MAX:
        p["xp_compte"] = 0
        return [], []
    p["xp_compte"] += int(round(data.XP_COMPTE[source] * fois))
    lignes, cartes = [], []
    while p["niveau"] < data.NIVEAU_COMPTE_MAX and p["xp_compte"] >= combat.xp_compte_requis(p["niveau"]):
        p["xp_compte"] -= combat.xp_compte_requis(p["niveau"])
        p["niveau"] += 1
        n = p["niveau"]
        golds = data.NIVEAU_GOLDS[0] + data.NIVEAU_GOLDS[1] * n
        p["golds"] += golds
        avant = charges_max({**p, "niveau": n - 1})
        p["packs_niveau"] += 1
        charge = n <= data.NIVEAU_SANS_CHARGE
        if charge:
            p["charges"] += 1   # une charge de jungle à chaque niveau (elle peut dépasser le stock maximum)
        ligne = f"**Niveau {n} !** +{golds} golds" + (" · ⚡ +1 charge de jungle" if charge else "") + " · 🎁 un pack à taux triplés t'attend dans le salon des packs"
        if charges_max(p) > avant:
            ligne += f"\n⚡ Ton stock passe à **{charges_max(p)} charges de Châtiment** !"
        numero = next((k for k, (niveau, _) in enumerate(data.DEFIS) if niveau == n), None)
        if numero is not None:
            ligne += f"\n🗿 Le **donjon défi {numero + 1}** est ouvert !"
            if p["totems"] == numero:   # c'est bien son prochain défi
                message_prive(p, f"🗿 Tu passes **niveau {n}** : le **donjon défi {numero + 1}** est ouvert ! Va le tenter dans le salon des donjons (bouton **Donjon défi**). "
                                 f"Le gagner fait revenir tes charges de jungle toutes les {texte_delai(data.CHARGES_DELAI[numero + 1] * 60)} "
                                 f"et permet d'en miser {data.CHARGES_MISE[numero + 1]} sur une carte.")
        if n >= data.NIVEAU_COMPTE_MAX:
            ligne += "\n👑 Niveau maximum atteint !"
            p["xp_compte"] = 0
        prevenir_niveau(p, n)
        for cle, niveau in data.DEBLOCAGES.items():
            if niveau == n:
                ligne += f"\n🔓 Tu débloques **{NOMS_MODES[cle]}** !"
        for palier, nom_role, _ in data.ROLES_NIVEAU:
            if palier == n:
                ligne += f"\n🏅 Tu obtiens le rôle **{nom_role}** !"
        lignes.append(ligne)
    return lignes, cartes


def prevenir_niveau(p, n):
    """Annonce publique d'une montée de niveau de compte, dans le salon des tirages (sans bloquer l'action en cours)."""
    async def envoyer():
        try:
            guilde = bot.get_guild(p["guild_id"])
            salon = next((c for c in guilde.text_channels if c.name == data.SALON_TIRAGES), None) if guilde else None
            if salon:
                await salon.send(f"⭐ <@{p['user_id']}> passe **niveau {n}** ! Un pack l'attend dans le salon des packs.",
                                 allowed_mentions=discord.AllowedMentions(users=True))
        except Exception:
            pass
    try:
        asyncio.get_running_loop().create_task(envoyer())
    except RuntimeError:
        pass


def message_prive(p, texte):
    """Envoie un message privé au joueur, sans bloquer l'action en cours (rien ne se passe s'il a fermé ses messages privés)."""
    async def envoyer():
        try:
            utilisateur = bot.get_user(p["user_id"]) or await bot.fetch_user(p["user_id"])
            guilde = bot.get_guild(p["guild_id"])
            await utilisateur.send(texte + (f"\n*— {guilde.name}*" if guilde else ""))
        except Exception:
            pass
    try:
        asyncio.get_running_loop().create_task(envoyer())
    except RuntimeError:
        pass


def bonus_golds(ids, possedees):
    """Multiplicateur de golds du leader (Bilgewater) pour la tour et la jungle. Il suit le niveau du leader : plein au niveau
    BILGEWATER_NIVEAU, en proportion en dessous (12 octobre : un leader niveau 1 ne donne presque rien)."""
    chef = combat.leader(ids)
    if not chef or chef[1] != "golds":
        return 1
    niveau = (possedees.get(chef[0]) or {}).get("niveau", 1)
    return 1 + chef[2] / 100 * min(1, niveau / data.BILGEWATER_NIVEAU)


def conseils_defaite(p, possedees, ids):
    """Après une défaite : ce que le joueur a sous la main pour se renforcer tout de suite."""
    pistes = []
    faible = min((c for c in ids if c in possedees and possedees[c]["niveau"] < combat.niveau_max(c, possedees[c]["etoiles"])),
                 key=lambda c: possedees[c]["niveau"], default=None)
    if p["reserve_xp"] > 0 and faible:
        pistes.append(f"📚 Tu as **{p['reserve_xp']} XP de réserve** : verse-la sur {data.CARTES[faible]['nom']} (niv. {possedees[faible]['niveau']}) avec le bouton **Réserve d'XP**, salon de la collection.")
    if charges(p) > 0:
        pistes.append(f"⚡ Il te reste **{p['charges']} charge(s)** de jungle : une carte explorée donne beaucoup d'XP à ton équipe.")
    attente = p["packs_niveau"] + p["packs_ur"]
    if attente:
        pistes.append(f"🎁 **{attente} pack(s)** t'attendent dans le salon des packs.")
    if p["golds"] >= data.PRIX_PACK:
        pistes.append(f"💰 Tu as {p['golds']} golds : de quoi ouvrir {p['golds'] // data.PRIX_PACK} pack(s). Un doublon donne une étoile et de l'XP de réserve.")
    return pistes


def champ_compte(p, e, source, fois=1):
    """Donne l'XP de compte et ajoute à l'embed le champ de montée de niveau s'il y en a une. Renvoie les cartes gagnées."""
    lignes, cartes = gagner_xp_compte(p, source, fois)
    if lignes:
        e.add_field(name="⭐ Niveau de compte", value="\n".join(lignes)[:1024], inline=False)
    return cartes


async def verrouille(i, p, cle):
    """Répond et renvoie True si ce mode n'est pas encore débloqué pour ce joueur."""
    requis = data.DEBLOCAGES.get(cle, 1)
    if p["niveau"] >= requis:
        return False
    await i.response.send_message(
        f"🔒 **{NOMS_MODES[cle].capitalize()}** se débloque au **niveau {requis}** de compte (tu es niveau {p['niveau']}).\n"
        "Tu gagnes de l'XP de compte en jouant : chaque étage de la tour en rapporte beaucoup.", ephemeral=True)
    return True


def buff_actif(g):
    """Le buff de serveur en cours (gagné en tuant un boss de salon), ou None."""
    buff = db.monde(g)["buff"]
    return buff if buff and buff.get("fin", 0) > time.time() else None


def ligne_de(p, cid):
    """Ligne où le joueur a placé cette carte ("avant" ou "arriere") ; sans choix de sa part, celle de son rôle."""
    for morceau in (p["lignes"] or "").split(","):
        nom, _, ligne = morceau.partition(":")
        if nom == cid and ligne in ("avant", "arriere"):
            return ligne
    return data.LIGNES.get(data.CARTES[cid]["role"], "avant")


def placer(p, cid, ligne):
    """Enregistre la ligne choisie pour une carte (l'appelant sauvegarde le joueur)."""
    choix = dict(m.split(":", 1) for m in (p["lignes"] or "").split(",") if ":" in m)
    choix[cid] = ligne
    p["lignes"] = ",".join(f"{c}:{l}" for c, l in choix.items() if c in data.CARTES)


def texte_ligne(p, cid):
    role, ligne = data.CARTES[cid]["role"], ligne_de(p, cid)
    place = "🛡️ devant" if ligne == "avant" else "🏹 derrière"
    if role not in data.LIGNES:
        return place
    if data.LIGNES[role] == ligne:
        return f"{place} · ✅ {data.TEXTES_LIGNE[role]}"
    return f"{place} · pas de bonus (un {role} l'a {'devant' if data.LIGNES[role] == 'avant' else 'derrière'})"


def equipe_ids(p, possedees):
    ids = [c for c in p["equipe"].split(",") if c in possedees][:3]
    buff = buff_actif(p["guild_id"])
    runes = runes_equipees(p)
    for c in ids:
        possedees[c]["ligne"] = ligne_de(p, c)   # lu par combat.equipe_joueur
        possedees[c]["buff"] = (buff["stat"], buff["valeur"]) if buff else None
        possedees[c]["rune"] = runes.get(c)
    return ids


# -- runes --
def runes_du_compte(p):
    return [r for r in (p["runes"] or "").split(",") if r in data.RUNES]


def emplacements_runes(p):
    """14 octobre (soir) : plus de limite d'emplacements, chaque carte de l'équipe peut porter une rune (avant : une de plus par palier de la tour)."""
    return 3


def runes_equipees(p):
    """{carte: rune} : seulement des runes possédées, une rune par carte, une carte par rune, dans la limite des emplacements."""
    possedees, sortie = runes_du_compte(p), {}
    for morceau in (p["runes_equipees"] or "").split(","):
        carte, _, rune = morceau.partition(":")
        if carte in data.CARTES and rune in possedees and list(sortie.values()).count(rune) < possedees.count(rune) and len(sortie) < emplacements_runes(p):   # 14 octobre : une rune par exemplaire possédé
            sortie[carte] = rune
    return sortie


def texte_rune(rune):
    nom, emoji, palier, effet = data.RUNES[rune]
    return f"{emoji} **{nom}** · {effet}"


def ligne_carte(cid, carte):
    c = data.CARTES[cid]
    etoiles = "★" * carte["etoiles"]
    objet = f" · {data.ITEMS[carte['item'][0]][1]} {data.ITEMS[carte['item'][0]][0]}" if carte.get("item") else ""
    if carte.get("rune") in data.RUNES:
        objet += f" · {data.RUNES[carte['rune']][1]} {data.RUNES[carte['rune']][0]}"
    return f"{data.EMOJIS[c['rarete']]} **{c['nom']}** {etoiles} · niv. {carte['niveau']} · {c['role']} · {c['region']}{objet}"


DOSSIER_IMAGES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")

# ---- Atelier d'images : les animations lourdes sont calculées par un programme à part (fabrique.py), pour que le bot continue de
# répondre aux autres joueurs pendant ce temps. Si l'atelier ne répond pas, le bot fait le calcul lui-même, comme avant.
_ATELIER = {"programme": None, "verrou": None}


def _commander(nom, args):
    import pickle
    import subprocess
    import sys
    programme = _ATELIER["programme"]
    if programme is None or programme.poll() is not None:
        dossier = os.path.dirname(os.path.abspath(__file__))
        options = {"creationflags": 0x08000000 | 0x00004000} if os.name == "nt" else {}   # sans fenêtre, en priorité basse
        programme = _ATELIER["programme"] = subprocess.Popen([sys.executable, os.path.join(dossier, "fabrique.py")], cwd=dossier,
                                                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, **options)
    pickle.dump((nom, args), programme.stdin)
    programme.stdin.flush()
    etat, resultat = pickle.load(programme.stdout)
    if etat != "ok":
        raise RuntimeError(resultat)
    return resultat


async def dessiner(nom, *args):
    """Fait fabriquer une image ou une animation par l'atelier : await dessiner("duel_pro", groupes, pro, titre)."""
    if _ATELIER["verrou"] is None:
        _ATELIER["verrou"] = asyncio.Lock()
    try:
        async with _ATELIER["verrou"]:
            return await asyncio.wait_for(asyncio.to_thread(_commander, nom, args), 45)
    except Exception as erreur:
        print(f"Atelier d'images indisponible ({erreur!r}) : calcul dans le bot.")
        programme, _ATELIER["programme"] = _ATELIER["programme"], None
        try:
            if programme:
                programme.kill()
        except Exception:
            pass
        return await asyncio.to_thread(getattr(cartes_img, nom), *args)
PASTILLES = {"N": "⚪", "R": "🔵🔵", "SR": "🟣🟣🟣", "SSR": "🟡🟡🟡🟡", "UR": "💎💎💎💎💎"}


def image_carte(cid):
    """Image à montrer quand on présente une carte : la carte encadrée si elle a été fabriquée, sinon l'illustration seule."""
    encadree = f"c_{cid}.png"
    return encadree if os.path.exists(os.path.join(DOSSIER_IMAGES, encadree)) else image_locale(cid)


def banniere(cle):
    """Nom du fichier de bannière d'un salon : la version légère (.jpg) si elle existe, sinon le .png."""
    leger = f"banniere_{cle}.jpg"
    return leger if os.path.exists(os.path.join(DOSSIER_IMAGES, leger)) else f"banniere_{cle}.png"


async def reessayer(action, essais=4):
    """Lance action() (qui fabrique l'appel à Discord, fichiers compris) et recommence si la connexion a eu un raté."""
    for essai in range(essais):
        try:
            return await action()
        except (discord.Forbidden, discord.NotFound):
            raise
        except ERREURS_RESEAU:
            if essai == essais - 1:
                raise
            await asyncio.sleep(2 + 2 * essai)


def fichier_image(nom):
    """Renvoie l'image locale à joindre au message, ou None si elle n'existe pas."""
    chemin = os.path.join(DOSSIER_IMAGES, nom)
    return discord.File(chemin, filename=nom) if os.path.exists(chemin) else None


EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def image_locale(cid):
    """Nom du fichier du dossier images à utiliser pour cette carte, ou None.
    Priorité : une image à l'identifiant de la carte (ex. sbire_melee.png), sinon l'image générique de sa rareté
    pour les cartes sans illustration officielle."""
    for ext in EXTENSIONS:
        if os.path.exists(os.path.join(DOSSIER_IMAGES, cid + ext)):
            return cid + ext
    generique = f"carte_{data.CARTES[cid]['rarete']}.png"
    if not data.CARTES[cid]["image"] and os.path.exists(os.path.join(DOSSIER_IMAGES, generique)):
        return generique
    return None


def tri_cartes(possedees):
    """Ordre des listes de cartes : par rareté (LR, UR, SSR…), puis par niveau, puis par étoiles."""
    def cle(c):
        rar = 9 if c.endswith("LR") else data.RARETES.index(data.CARTES[c]["rarete"]) if data.CARTES[c]["rarete"] in data.RARETES else -1
        return (-rar, -possedees[c]["niveau"], -possedees[c].get("etoiles", 0), data.CARTES[c]["nom"])
    return cle


# ---- Filtre de rareté et pages pour les menus de champions (Discord : 25 choix au plus par menu)
def rarete_filtre(c):
    return "UR" if c.endswith("LR") else data.CARTES[c]["rarete"]


def filtres_utiles(cartes):
    return ["Toutes"] + [r for r in ("UR", "SSR", "SR", "R", "N") if any(rarete_filtre(c) == r for c in cartes)]


def page_de_cartes(cartes, filtre="Toutes", page=0, gardees=(), place=25):
    """Les cartes à mettre dans un menu : celles déjà choisies (toujours visibles), puis la page demandée des autres, filtrées par rareté.
    Renvoie (cartes visibles, nombre de pages)."""
    gardees = [c for c in gardees if c in cartes][:place]
    reste = [c for c in cartes if c not in gardees and (filtre == "Toutes" or rarete_filtre(c) == filtre)]
    n = max(1, place - len(gardees))
    pages = max(1, -(-len(reste) // n))
    page %= pages
    return gardees + reste[page * n:(page + 1) * n], pages


def boutons_filtre(vue, toutes, pages, row, rafraichir, filtre=True):
    """Ajoute à la vue les boutons 🔎 Filtre (rareté) et ▶ Page suivante, seulement s'ils servent.
    La vue garde son état dans vue.filtre et vue.page ; rafraichir(i) réaffiche le message."""
    if filtre and (len(toutes) > 25 or vue.filtre != "Toutes") and len(filtres_utiles(toutes)) > 2:
        b = discord.ui.Button(label=f"Filtre : {vue.filtre}", emoji="🔎", style=discord.ButtonStyle.primary, row=row)
        async def changer(i):
            ordre = filtres_utiles(toutes)
            vue.filtre = ordre[(ordre.index(vue.filtre) + 1) % len(ordre)] if vue.filtre in ordre else "Toutes"
            vue.page = 0
            await rafraichir(i)
        b.callback = changer
        vue.add_item(b)
    if pages > 1:
        b = discord.ui.Button(label=f"Page {vue.page % pages + 1}/{pages}", emoji="▶️", style=discord.ButtonStyle.secondary, row=row)
        async def suivante(i):
            vue.page = (vue.page + 1) % pages
            await rafraichir(i)
        b.callback = suivante
        vue.add_item(b)


def texte_actif(cid):
    """Ce que fait l'ulti d'une carte, en clair."""
    if cid in data.TEXTES_KITS:
        return data.TEXTES_KITS[cid][1]
    return data.EFFETS[data.CARTES[cid]["effet"]].capitalize() + "."


def embed_carte(cid, statut="", locale=False):
    """Fiche d'une carte. Avec locale=True, l'image vient du dossier images quand il y en a une
    (l'appelant doit alors joindre fichier_image(image_locale(cid)) au message)."""
    c = data.CARTES[cid]
    pv, atk = combat.stats(cid)
    e = discord.Embed(color=data.COULEURS[c["rarete"]],
                      description=f"# {c['nom']}\n## {PASTILLES[c['rarete']]} {c['rarete']}\n### {statut}\n{c['role'].capitalize()} · {c['region']} · {pv} PV · {atk} ATQ")
    if c["ulti"]:
        e.add_field(name=f"✨ Actif : {c['ulti']}", value=texte_actif(cid), inline=False)
        if data.TEXTES_KITS.get(cid, (None,))[0]:
            e.add_field(name="🔹 Passif", value=data.TEXTES_KITS[cid][0], inline=False)
    if data.UR_PALIERS.get(cid):
        e.add_field(name="🏆 Puissance des Worlds", value=f"+{data.UR_PALIERS[cid]} % de PV et d'ATQ (déjà compté dans ses stats).", inline=False)
    fichier = image_carte(cid) if locale else None
    if fichier:
        e.set_image(url=f"attachment://{fichier}")
    elif c["image"]:
        e.set_image(url=c["image"])
    return e


def doublons_requis(cid, etoiles):
    """Doublons qu'il faut pour passer de ce nombre d'étoiles au suivant."""
    echelle = data.ETOILE_DOUBLONS.get(data.CARTES[cid]["rarete"])
    return echelle[min(etoiles, len(echelle) - 1)] if echelle else 1


def donner(p, cid):
    """Ajoute la carte à la collection et renvoie le texte à afficher (nouvelle, doublon…). Un doublon remplit aussi la réserve d'XP."""
    g, u = p["guild_id"], p["user_id"]
    carte = db.cartes(g, u).get(cid)
    gagne_ur = ""
    if p.pop("_pack_ur", None):   # ce pack était le 50e, 100e… : un pack UR est mis de côté
        gagne_ur = f"\n💎 **Pack UR gagné !** ({data.UR_TOUS_LES} packs ouverts) Ouvre-le dans le salon des packs."
        message_prive(p, f"💎 Tu viens d'ouvrir ton {p['packs']}e pack : un **pack UR** t'attend dans le salon des packs (bouton **Pack UR**).")
    if not carte:
        db.sauver_carte(g, u, cid)
        return "🆕 Nouvelle carte !" + gagne_ur
    gain = int(data.RESERVE_XP[data.CARTES[cid]["rarete"]] * (data.JUNGLE_XP[0] + data.JUNGLE_XP[1] * min(p["etage"], 100)))
    avant = p["reserve_xp"]
    p["reserve_xp"] = min(data.RESERVE_MAX, avant + gain)
    trop, versee = avant + gain - p["reserve_xp"], None
    if trop > 0:   # réserve pleine : le surplus va tout de suite à la carte la plus haute qui n'est pas au maximum
        collection = db.cartes(g, u)
        versee = combat.recycler_xp(collection, trop)
    if avant < data.RESERVE_MAX <= p["reserve_xp"]:   # elle vient de se remplir : on prévient une fois
        message_prive(p, f"📚 Ta **réserve d'XP est pleine** ({data.RESERVE_MAX} XP) : les prochains doublons ne la rempliront plus. "
                         "Ouvre la fiche d'une carte dans le salon de la collection pour la dépenser.")
    reserve = f" · 📚 +{p['reserve_xp'] - avant} XP de réserve" if p["reserve_xp"] > avant else " · 📚 réserve d'XP pleine"
    if versee:
        reserve += f" (+{trop} XP versés à {data.CARTES[versee]['nom']})"
    reserve += gagne_ur
    if data.CARTES[cid]["rarete"] == "UR":   # les UR n'ont pas d'étoiles
        p["golds"] += data.UR_DOUBLON_GOLDS
        return f"UR déjà possédé : +{data.UR_DOUBLON_GOLDS} golds" + reserve
    if carte["etoiles"] < data.ETOILES_MAX:
        requis = doublons_requis(cid, carte["etoiles"])
        acquis = (carte.get("doublons") or 0) + 1
        if acquis < requis:   # pas encore assez de doublons pour l'étoile suivante
            db.sauver_doublons(g, u, cid, acquis)
            return f"Doublon : {acquis}/{requis} vers la {carte['etoiles'] + 1}e étoile" + reserve
        db.sauver_carte(g, u, cid, carte["niveau"], carte["xp"], carte["etoiles"] + 1)
        db.sauver_doublons(g, u, cid, 0)
        return f"Doublon : {'★' * (carte['etoiles'] + 1)} (+10 % de stats, niveau maximum +{data.ETOILE_NIVEAUX})" + reserve
    p["golds"] += data.GOLDS_DOUBLON
    return f"Doublon au maximum d'étoiles : +{data.GOLDS_DOUBLON} golds" + reserve


def duree(secondes):
    h, m = int(secondes // 3600), int(secondes % 3600 // 60)
    return f"{h} h {m:02d}" if h else f"{max(1, m)} min"


async def annoncer(guilde, joueur, cids):
    """Annonce publique des belles cartes dans le salon des tirages, visible par tout le serveur.
    13 octobre : seulement les UR et LR, et les SSR des pros (Worlds et LEC, absentes des packs normaux). Les SSR des packs ne s'annoncent plus."""
    rares = sorted({c for c in cids if data.CARTES[c]["rarete"] == "UR" or (data.CARTES[c]["rarete"] == "SSR" and not data.CARTES[c]["en_jeu"])},
                   key=lambda c: -data.RARETES.index(data.CARTES[c]["rarete"]))
    salon = next((c for c in guilde.text_channels if c.name == data.SALON_TIRAGES), None) if guilde and rares else None
    if not salon:
        return
    meilleure = data.CARTES[rares[0]]
    rang = lambda c: "LR" if c.endswith("LR") else data.CARTES[c]["rarete"]   # les cartes de Faker s'annoncent en LR
    if len(rares) == 1:
        texte = (f"# {meilleure['nom']}\n## {'🔴🔴🔴🔴🔴🔴' if rang(rares[0]) == 'LR' else PASTILLES[meilleure['rarete']]} {rang(rares[0])}\n"
                 f"{joueur.mention} vient de tirer cette carte !" + (" Une carte **LR**, la plus rare du jeu." if rang(rares[0]) == "LR" else ""))
    else:
        texte = f"## {joueur.mention} vient de tirer {len(rares)} belles cartes !\n" + "\n".join(
            f"{'🔴' if rang(c) == 'LR' else data.EMOJIS[data.CARTES[c]['rarete']]} **{data.CARTES[c]['nom']}** · {rang(c)}" for c in rares)
    e = discord.Embed(description=texte, color=data.COULEURS[meilleure["rarete"]])
    carte = image_carte(rares[0])   # la carte encadrée si elle existe, sinon l'illustration officielle
    fichier = fichier_image(carte) if carte else None
    if fichier:
        e.set_image(url=f"attachment://{carte}")
    elif meilleure["image"]:
        e.set_image(url=meilleure["image"])
    try:
        if fichier:
            await salon.send(embed=e, file=fichier)
        else:
            await salon.send(embed=e)
    except discord.HTTPException:
        pass   # le bot n'a pas le droit d'écrire dans ce salon


async def annoncer_coach(guilde, joueur, pseudo):
    """Annonce publique d'une carte de pro (coach) tirée, dans le salon des tirages, avec sa carte en image."""
    salon = next((c for c in guilde.text_channels if c.name == data.SALON_TIRAGES), None) if guilde else None
    c = data.COACHS.get(pseudo)
    if not salon or not c:
        return
    e = discord.Embed(color=0xECC86E, description=f"# 🎓 {pseudo}\n## Carte de pro · {c['poste']} · {c['nom_equipe']}\n"
                      f"{joueur.mention} vient de tirer ce **coach** ! Il donne {data.texte_bonus_coach(pseudo)}"
                      + (" partout." if c.get("partout") else " aux Worlds, à la LEC et au raid."))
    chemin = chemin_carte_pro(pseudo)
    try:
        if os.path.exists(chemin):
            e.set_image(url="attachment://coach.png")
            await salon.send(embed=e, file=discord.File(chemin, "coach.png"))
        else:
            await salon.send(embed=e)
    except discord.HTTPException:
        pass


# ============================ DÉBUT (EN MP) ==================================
def vue_debut(guild_id):
    vue = discord.ui.View(timeout=None)
    vue.add_item(discord.ui.Button(label="Ouvrir mon premier pack", emoji="🎁", style=discord.ButtonStyle.success,
                                   custom_id=f"debut:{guild_id}"))
    return vue


TEXTE_DEBUT = ("**Bienvenue sur 2Hot4Deck.**\n"
               "Ouvre des packs pour collectionner les champions, compose une équipe de 3 et grimpe la tour.\n"
               "Ton premier pack t'attend.")


async def premier_pack(i, guild_id):
    if db.get_joueur(guild_id, i.user.id):
        await i.response.edit_message(content="Tu as déjà ouvert ton premier pack. Retourne sur le serveur !", view=None)
        return
    p = db.creer_joueur(guild_id, i.user.id, data.GOLDS_DEPART, time.time())
    # Le pack de départ : un sbire et un champion SR garanti, tous deux au hasard.
    sbire, champion = random.choice(data.PAR_RARETE["N"]), random.choice(data.PAR_RARETE[data.RARETE_DEPART])
    db.sauver_carte(guild_id, i.user.id, sbire)
    db.sauver_carte(guild_id, i.user.id, champion)
    p["equipe"] = f"{champion},{sbire}"
    db.sauver(p)
    e = embed_carte(champion, f"Ton premier champion, accompagné d'un **{data.CARTES[sbire]['nom']}**.", locale=True)
    texte = (f"🎁 Tu reçois aussi **{data.GOLDS_DEPART} golds**, de quoi ouvrir {data.GOLDS_DEPART // data.PRIX_PACK} packs.\n"
             "Les salons du jeu viennent de se débloquer sur le serveur : salon des packs pour tirer des champions, salon de la tour pour combattre.")
    ouverture, pieces = embed_ouverture(champion, "🎁 Ton pack de départ s'ouvre…")
    if ouverture:
        await i.response.edit_message(view=None, embed=ouverture, attachments=pieces, content=None)
        try:
            await asyncio.sleep(DUREE_OUVERTURE)
            await editer(i, embed=e, attachments=joindre(image_carte(champion)), content=texte)
        except ERREURS_RESEAU:
            pass
    else:
        await i.response.edit_message(view=None, embed=e, attachments=joindre(image_carte(champion)), content=texte)
    await donner_role_joueur(bot.get_guild(guild_id), i.user.id)
    await annoncer(bot.get_guild(guild_id), i.user, [champion])


async def donner_role_joueur(guilde, user_id):
    """Donne le rôle qui débloque les salons du jeu. Renvoie True si c'est fait (ou déjà fait)."""
    role = discord.utils.get(guilde.roles, name=data.ROLE_JOUEUR) if guilde else None
    if not role:
        return False
    try:
        membre = guilde.get_member(user_id) or await guilde.fetch_member(user_id)
        if role not in membre.roles:
            await membre.add_roles(role, reason="A commencé le jeu")
        return True
    except discord.HTTPException:
        return False


# ================================ PANNEAUX ===================================
class ConfirmerReset(discord.ui.View):
    """Deuxième clic obligatoire avant d'effacer un compte."""
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Oui, tout effacer", emoji="⚠️", style=discord.ButtonStyle.danger)
    async def confirmer(self, i, _):
        if not data.RESET_COMPTE or i.user.id in en_duel:
            await i.response.edit_message(content="Impossible pour l'instant" + (" : termine d'abord ton duel." if i.user.id in en_duel else "."), view=None)
            return
        db.supprimer_joueur(i.guild_id, i.user.id)
        await i.response.edit_message(content="✅ Ton compte est effacé. Appuie sur **Commencer** dans le salon d'accueil pour repartir de zéro.", view=None)
        if isinstance(i.user, discord.Member):   # les rôles de rang et de niveau repartent aussi
            noms = {r[1] for r in data.ARENE_RANGS} | {r[1] for r in data.ROLES_NIVEAU}
            try:
                en_trop = [r for r in i.user.roles if r.name in noms]
                if en_trop:
                    await i.user.remove_roles(*en_trop, reason="Compte réinitialisé")
            except discord.HTTPException:
                pass

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def annuler(self, i, _):
        await i.response.edit_message(content="Annulé : ton compte n'a pas bougé.", view=None)


class PanneauProfil(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Mon profil", emoji="👤", style=discord.ButtonStyle.secondary, custom_id="f:profil")
    async def profil(self, i, _):
        p = await charger(i)
        if not p:
            return
        requis = combat.xp_compte_requis(p["niveau"])
        prochains = [f"🔓 {NOMS_MODES[c].capitalize()} au niveau {n}" for c, n in data.DEBLOCAGES.items() if n > p["niveau"]]
        cible = data.CARTES[p["cible"]]["nom"] if p["cible"] in data.CARTES else "aucun"
        e = discord.Embed(color=COULEUR, description=(
            f"# 👤 {i.user.display_name}\n## ⭐ Niveau {p['niveau']}\n{combat.barre(p['xp_compte'], requis)} {p['xp_compte']}/{requis} XP\n\n"
            f"🗼 Étage **{p['etage']}** · 🏟️ {texte_rang(p['arene_points'])}\n"
            f"💰 **{p['golds']}** golds · {texte_charges(p)}\n"
            f"⚒️ Donjons : **{donjons_restants(p)}/{data.DONJON_STOCK}** victoire(s) en réserve · 📚 Réserve d'XP : **{p['reserve_xp']}** · 🎯 SSR ciblé : **{cible}**\n"
            f"🃏 {len(db.cartes(i.guild_id, i.user.id))} cartes · {p['packs']} packs ouverts"
            + ("\n\n" + "\n".join(prochains) if prochains else "")))
        e.add_field(name="\u200b", value=texte_mes_packs(i.guild, p).replace("# 📦 Mes packs", "### 📦 Mes packs")[:1024], inline=False)
        db.sauver(p)
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="Réinitialiser mon compte", emoji="🗑️", style=discord.ButtonStyle.danger, custom_id="f:reset", row=1)
    async def reset(self, i, _):
        if not data.RESET_COMPTE:
            await i.response.send_message("La réinitialisation de compte était réservée à la bêta : elle n'est plus disponible.", ephemeral=True)
            return
        p = await charger(i)
        if not p:
            return
        await i.response.send_message(
            f"## 🗑️ Réinitialiser ton compte ?\nTu vas **tout perdre** : tes {len(db.cartes(i.guild_id, i.user.id))} cartes, tes {p['golds']} golds, "
            f"ton niveau {p['niveau']}, ton étage {p['etage']}, tes items, tes composants et ton classement.\n"
            "Tu repartiras de zéro en appuyant sur **Commencer** dans l'accueil. C'est définitif.", view=ConfirmerReset(), ephemeral=True)

    @discord.ui.button(label="Classement des niveaux", emoji="⭐", style=discord.ButtonStyle.secondary, custom_id="f:top_niveaux")
    async def top_niveaux(self, i, _):
        joueurs = sorted(db.tous_les_joueurs(i.guild_id), key=lambda q: (-q["niveau"], -q["xp_compte"]))[:10]
        lignes = [f"**{n}.** <@{q['user_id']}> · ⭐ niveau {q['niveau']} · 🗼 étage {q['etage']} · {texte_rang(q['arene_points'])}"
                  for n, q in enumerate(joueurs, 1)]
        e = discord.Embed(color=COULEUR, description="# ⭐ Classement des niveaux\n" + ("\n".join(lignes) or "Personne pour l'instant."))
        await i.response.send_message(embed=e, ephemeral=True)


class PanneauAccueil(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Commencer", emoji="🎮", style=discord.ButtonStyle.success, custom_id="f:start")
    async def start(self, i, _):
        if db.get_joueur(i.guild_id, i.user.id):
            await i.response.send_message("Tu as déjà un compte.", ephemeral=True)
            return
        await i.response.defer(ephemeral=True)
        try:
            await i.user.send(TEXTE_DEBUT, view=vue_debut(i.guild_id))
            await i.followup.send("📩 Regarde tes messages privés pour ouvrir ton premier pack.", ephemeral=True)
        except discord.Forbidden:  # messages privés fermés : on le fait ici
            await i.followup.send(TEXTE_DEBUT, view=vue_debut(i.guild_id), ephemeral=True)


# ----------------------------- Ouverture des packs ---------------------------
LUEURS = {"N": "⚪ Une faible lueur grise…", "R": "🔵 Une lueur bleue s'en échappe…",
          "SR": "🟣 Une lueur violette intense !", "SSR": "🟡⚡ UNE LUMIÈRE DORÉE AVEUGLANTE ! ⚡🟡",
          "UR": "💎⚡ UNE LUMIÈRE ÉCARLATE DÉCHIRE LE PACK ! ⚡💎"}

DUREE_OUVERTURE = 4.3   # secondes laissées à l'animation d'ouverture (images/ouverture_<rareté>.gif) avant de montrer la carte


# Pannes passagères d'Internet ou de Discord : elles ne doivent jamais laisser une animation bloquée en plein milieu.
ERREURS_RESEAU = (discord.HTTPException, OSError, asyncio.TimeoutError) + (
    (aiohttp.ClientError,) if isinstance(getattr(aiohttp, "ClientError", None), type) else ())


async def editer(i, **options):
    """Modifie le message de l'interaction, en réessayant si la connexion a eu un raté."""
    for essai in range(3):
        try:
            return await i.edit_original_response(**options)
        except discord.NotFound:
            return None   # le joueur a fermé le message
        except ERREURS_RESEAU:
            if essai == 2:
                raise
            await asyncio.sleep(1.5)
            if options.get("attachments"):   # un fichier déjà envoyé est refermé : on le rouvre pour le nouvel essai
                neufs = []
                for f in options["attachments"]:
                    if isinstance(f, discord.File) and isinstance(getattr(f.fp, "name", None), str):
                        f = discord.File(f.fp.name, filename=f.filename)   # fichier du disque : on le rouvre
                    elif isinstance(f, discord.File):
                        f.reset()                                         # image en mémoire : on la rembobine
                    neufs.append(f)
                options["attachments"] = neufs


def embed_suspense(texte, rarete=None, image=None):
    e = discord.Embed(description=f"# {texte}", color=data.COULEURS[rarete] if rarete else 0x4B5563)
    if image and os.path.exists(os.path.join(DOSSIER_IMAGES, image)):
        e.set_image(url=f"attachment://{image}")
    return e


def joindre(nom):
    """Liste de pièces jointes pour une modification de message (vide si l'image n'existe pas)."""
    f = fichier_image(nom) if nom else None
    return [f] if f else []


def embed_ouverture(cid, texte):
    """Embed et pièces jointes de l'animation d'ouverture qui précède la carte gagnée (None, [] si l'animation manque)."""
    anim = f"ouverture_{data.CARTES[cid]['rarete']}.gif" if cid in data.CARTES else ""
    if not anim or not os.path.exists(os.path.join(DOSSIER_IMAGES, anim)):
        return None, []
    return embed_suspense(texte, image=anim), joindre(anim)


def bonus_packs(g, u):
    """13 octobre (20 h) : les SSR des équipes battues aux Worlds et à la LEC tombent aussi des packs normaux (pack, pack de 10, méga tirage)."""
    return {"SSR": combat.cartes_debloquees(db.worlds_equipes(g, u), db.lec_equipes(g, u))["SSR"]}


def tirer_pack_ur(i, p, possedees):
    """Le tirage d'un pack UR (sans animation), avec les UR choisies ou boostées par le propriétaire."""
    cid = combat.tirer_ur(p, possedees, db.worlds_equipes(i.guild_id, i.user.id))
    if data.CARTES[cid]["rarete"] == "UR" and i.user.id in data.UR_CHOISIES and db.operation_unique(f"ur_choisie_{i.user.id}_{data.UR_CHOISIES[i.user.id]}"):
        cid = data.UR_CHOISIES[i.user.id]   # la prochaine UR de ce joueur est choisie par le propriétaire (une seule fois)
    boost = data.UR_BOOST.get(i.user.id)
    if boost and not db.con.execute("SELECT 1 FROM operations WHERE cle=?", (f"ur_boost_{i.user.id}_{boost[0]}",)).fetchone():
        # Chance augmentée choisie par le propriétaire : la prochaine UR est celle-ci, et chaque pack UR a boost[1] % de la donner (une seule fois).
        if (data.CARTES[cid]["rarete"] == "UR" or random.random() * 100 < boost[1]) and db.operation_unique(f"ur_boost_{i.user.id}_{boost[0]}"):
            cid = boost[0]
            p["pitie_ur"] = 0
    return cid


async def ouvrir_packs_ur_x5(i, remplacer=False):
    """14 octobre : ouvre jusqu'à 5 packs UR d'un coup, sans animation, et montre tout le butin dans un seul message."""
    p = await charger(i)
    if not p:
        return
    extra = {"embed": None, "view": None, "attachments": []} if remplacer else {"ephemeral": True}
    repondre = i.response.edit_message if remplacer else i.response.send_message
    if p["packs_ur"] <= 0:
        reste = data.UR_TOUS_LES - p["packs"] % data.UR_TOUS_LES
        return await repondre(content=f"Tu n'as pas de pack UR. Tu en gagnes un tous les {data.UR_TOUS_LES} packs ouverts : encore **{reste}**.", **extra)
    nombre = min(5, p["packs_ur"])
    possedees = set(db.cartes(i.guild_id, i.user.id))
    lignes, tirees = [], []
    for _ in range(nombre):
        p["packs_ur"] -= 1
        cid = tirer_pack_ur(i, p, possedees)
        db.journal_pack(i.guild_id, i.user.id, "ur", -1, cid + (" (garantie)" if p.pop("_garantie", False) else "") + " · x5")
        statut = donner(p, cid).split("\n")[0]
        possedees.add(cid)
        tirees.append(cid)
        lignes.append(f"{data.EMOJIS[data.CARTES[cid]['rarete']]} **{data.CARTES[cid]['nom']}** · {data.CARTES[cid]['rarete']} · {statut}")
    db.sauver(p)
    ordre = {"UR": 0, "SSR": 1, "SR": 2}
    meilleure = min(tirees, key=lambda c: ordre.get(data.CARTES[c]["rarete"], 3))
    e = discord.Embed(color=0xE0182D, description=f"# 💎 {nombre} pack{'s' if nombre > 1 else ''} UR ouvert{'s' if nombre > 1 else ''}\n" + "\n".join(lignes)[:3900])
    e.set_footer(text=f"{p['packs_ur']} pack(s) UR restant(s) · UR garanti dans {data.UR_PITIE - p['pitie_ur']} packs UR au plus")
    fichiers = joindre(image_carte(meilleure))
    if fichiers:
        e.set_thumbnail(url=f"attachment://{image_carte(meilleure)}")
    suite = EncoreUR() if p["packs_ur"] > 0 else None
    if remplacer:
        await i.response.edit_message(content=None, embed=e, view=suite, attachments=fichiers)
    else:
        await i.response.send_message(embed=e, view=suite or discord.utils.MISSING, files=fichiers, ephemeral=True)
    await annoncer(i.guild, i.user, tirees)


async def ouvrir_pack(i, gratuit=False, remplacer=False, niveau=False, ur=False):
    """Ouvre un pack avec une petite mise en scène : le pack tremble, une lueur annonce la rareté, puis la carte."""
    p = await charger(i)
    if not p:
        return
    if ur:
        if p["packs_ur"] <= 0:
            reste = data.UR_TOUS_LES - p["packs"] % data.UR_TOUS_LES
            await i.response.send_message(f"Tu n'as pas de pack UR. Tu en gagnes un tous les {data.UR_TOUS_LES} packs ouverts : encore **{reste}**.", ephemeral=True)
            return
        p["packs_ur"] -= 1
    elif niveau:
        if p["packs_niveau"] <= 0:
            await i.response.send_message("Tu n'as pas de pack de niveau à ouvrir. Tu en gagnes un à chaque niveau de compte.", ephemeral=True)
            return
        p["packs_niveau"] -= 1
    elif gratuit:
        attente = data.DELAI_GRATUIT - (time.time() - p["dernier_gratuit"])
        if attente > 0:
            await i.response.send_message(f"⏳ Prochain pack gratuit dans **{duree(attente)}**.", ephemeral=True)
            return
        p["dernier_gratuit"] = time.time()
    else:
        if p["golds"] < data.PRIX_PACK:
            await i.response.send_message(f"Il te faut {data.PRIX_PACK} golds, tu en as {p['golds']}.", ephemeral=True)
            return
        p["golds"] -= data.PRIX_PACK
    # Le tirage est fait et sauvegardé tout de suite : l'animation n'est que de l'affichage.
    cid = tirer_pack_ur(i, p, set(db.cartes(i.guild_id, i.user.id))) if ur else combat.tirer(p, gratuit=gratuit, taux=data.TAUX_NIVEAU if niveau else None, bonus=bonus_packs(i.guild_id, i.user.id))
    statut = donner(p, cid)
    db.sauver(p)
    if ur:
        db.journal_pack(i.guild_id, i.user.id, "ur", -1, cid + (" (garantie)" if p.pop("_garantie", False) else ""))
    rarete = data.CARTES[cid]["rarete"]
    suite = (EncoreUR() if ur and p["packs_ur"] > 0 else EncoreNiveau() if niveau and p["packs_niveau"] > 0
             else None if gratuit or niveau or ur else EncoreUnPack())

    anim = f"ouverture_{rarete}.gif"   # le dos de carte tremble, la lueur prend la couleur de la rareté, puis l'éclair
    if not os.path.exists(os.path.join(DOSSIER_IMAGES, anim)) and rarete == "UR":
        anim = "ouverture_SSR.gif"   # en attendant une animation propre aux UR
    animee = os.path.exists(os.path.join(DOSSIER_IMAGES, anim))
    premiere = anim if animee else "pack_ferme.png"
    debut = embed_suspense(("💎 Le pack UR s'ouvre…" if ur else "📦 Le pack s'ouvre…") if animee else "📦 Le pack tremble…", image=premiere)
    if remplacer:
        await i.response.edit_message(embed=debut, view=None, attachments=joindre(premiere))
    else:
        await i.response.send_message(embed=debut, files=joindre(premiere), ephemeral=True)
    try:
        if animee:
            await asyncio.sleep(DUREE_OUVERTURE)
        else:
            await asyncio.sleep(1.4)
            lueur = f"lueur_{rarete}.png"
            try:
                await editer(i, embed=embed_suspense(LUEURS[rarete], rarete, lueur), attachments=joindre(lueur))
            except ERREURS_RESEAU:
                pass   # tant pis pour la lueur : la carte, elle, doit s'afficher
            await asyncio.sleep(2.0 if rarete == "SSR" else 1.5)
        e = embed_carte(cid, statut, locale=True)
        e.set_footer(text=f"{p['golds']} golds · SSR garanti dans {data.PITIE - p['pitie']} packs au plus")
        if ur:
            e.set_footer(text=f"{p['packs_ur']} pack(s) UR restant(s) · UR garanti dans {data.UR_PITIE - p['pitie_ur']} packs UR au plus")
        elif niveau and p["packs_niveau"] > 0:
            e.set_footer(text=f"Encore {p['packs_niveau']} pack(s) de niveau · SSR garanti dans {data.PITIE - p['pitie']} packs au plus")
        await editer(i, embed=e, view=suite, attachments=joindre(image_carte(cid)))
    except ERREURS_RESEAU:
        pass
    await annoncer(i.guild, i.user, [cid])


class EncoreUR(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Ouvrir le suivant", emoji="💎", style=discord.ButtonStyle.danger)
    async def encore(self, i, _):
        await ouvrir_pack(i, remplacer=True, ur=True)

    @discord.ui.button(label="Ouvrir x5", emoji="💎", style=discord.ButtonStyle.primary)
    async def encore5(self, i, _):
        await ouvrir_packs_ur_x5(i, remplacer=True)


class EncoreNiveau(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Ouvrir le suivant", emoji="⭐", style=discord.ButtonStyle.success)
    async def encore(self, i, _):
        await ouvrir_pack(i, remplacer=True, niveau=True)


class EncoreUnPack(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label=f"Encore un · {data.PRIX_PACK} golds", emoji="📦", style=discord.ButtonStyle.primary)
    async def encore(self, i, _):
        await ouvrir_pack(i, remplacer=True)


def ssr_ciblables(g, u):
    """SSR qu'un joueur peut viser : ceux des packs, et (13 octobre) ceux des équipes qu'il a battues aux Worlds et à la LEC."""
    return data.PAR_RARETE["SSR"], combat.cartes_debloquees(db.worlds_equipes(g, u), db.lec_equipes(g, u))["SSR"]


RAPPEL_CIBLE_VU = set()   # (joueur, jour) : le rappel du SSR ciblé ne revient pas une fois qu'on a répondu « Ouvrir quand même »


async def rappel_cible(i, suite):
    """Avant d'ouvrir des packs sans SSR ciblé, propose d'en choisir un. Renvoie True si le rappel a été affiché (l'ouverture attend)."""
    p = db.get_joueur(i.guild_id, i.user.id)
    if not p or p["cible"] in data.CARTES or (i.user.id, aujourdhui()) in RAPPEL_CIBLE_VU:
        return False
    await i.response.send_message("## 🎯 Tu ne vises aucun SSR\nAvec un **SSR ciblé**, quand un SSR tombe, il a "
                                  f"**{data.CIBLE_CHANCE} %** de chances d'être celui que tu veux (même un SSR des Worlds ou de la LEC que tu as débloqué). "
                                  "Veux-tu en choisir un avant d'ouvrir ?", view=RappelCible(i.user.id, suite), ephemeral=True)
    return True


class RappelCible(discord.ui.View):
    def __init__(self, auteur, suite):
        super().__init__(timeout=180)
        self.auteur, self.suite = auteur, suite

    @discord.ui.button(label="Choisir un SSR", emoji="🎯", style=discord.ButtonStyle.success)
    async def choisir(self, i, _):
        p = db.get_joueur(i.guild_id, i.user.id)
        await i.response.edit_message(content="🎯 Choisis le SSR que tu veux viser, puis rouvre ton pack.", view=ChoixCible(p["cible"] if p else "", i.guild_id, i.user.id))

    @discord.ui.button(label="Ouvrir quand même", style=discord.ButtonStyle.secondary)
    async def ouvrir(self, i, _):
        RAPPEL_CIBLE_VU.add((i.user.id, aujourdhui()))   # plus de rappel aujourd'hui
        self.stop()
        await self.suite(i)


class ChoixCible(discord.ui.View):
    """Menu pour choisir le SSR visé dans les packs (une fois par jour). Deuxième menu : SSR des pros et de la LEC débloqués."""
    def __init__(self, actuelle, g=None, u=None):
        super().__init__(timeout=180)
        self.base, self.pros = ssr_ciblables(g, u) if g else (data.PAR_RARETE["SSR"], [])
        self.permis = set(self.base) | set(self.pros)
        self.actuelle, self.filtre, self.page = actuelle, "Toutes", 0
        self.construire()

    def construire(self):
        self.clear_items()
        pages = 1
        for k, (liste, texte) in enumerate(((self.base, "Un SSR des packs"), (self.pros, "Un SSR des Worlds ou de la LEC (équipes battues)"))):
            if not liste:
                continue
            visibles, n = page_de_cartes(list(liste), page=self.page, gardees=[self.actuelle])
            pages = max(pages, n)
            menu = discord.ui.Select(placeholder=texte + (f" · page {self.page % n + 1}/{n}" if n > 1 else ""), row=k, options=[discord.SelectOption(
                label=data.CARTES[c]["nom"], value=c, default=c == self.actuelle,
                description=f"{data.CARTES[c]['role'].capitalize()} · {data.CARTES[c]['region']}") for c in visibles])
            menu.callback = self.valider(menu)
            self.add_item(menu)
        boutons_filtre(self, list(self.base) + list(self.pros), pages, 2, self.rafraichir, filtre=False)

    async def rafraichir(self, i):
        self.construire()
        await i.response.edit_message(view=self)

    def valider(self, menu):
        async def clic(i):
            await self.choisir(i, menu.values[0])
        return clic

    async def choisir(self, i, choix):
        p = await charger(i)
        if not p:
            return
        if choix in self.permis:   # 14 octobre : plus de limite, on change de cible quand on veut
            if choix != p["cible"]:
                p["cible"], p["cible_jour"] = choix, aujourdhui()
                db.sauver(p)
        e = embed_carte(p["cible"], "🎯 Ton SSR ciblé", locale=True) if p["cible"] in data.CARTES else None
        await i.response.edit_message(content=f"🎯 Tu vises maintenant **{data.CARTES[p['cible']]['nom']}**. Tu peux changer quand tu veux.", embed=e, view=None,
                                      attachments=joindre(image_carte(p["cible"])))


def texte_mes_packs(guilde, p):
    """Tous les packs qu'un joueur a à ouvrir, et où (le compteur de packs)."""
    def salon(nom, defaut):
        c = trouver_salon(guilde, nom) if guilde else None
        return c.mention if c else defaut
    ici = salon("🎁・packs", "le salon des packs")
    attente = data.DELAI_GRATUIT - (time.time() - p["dernier_gratuit"])
    lignes = [f"🎁 **Pack gratuit** : " + ("**prêt !**" if attente <= 0 else f"dans {duree(attente)}") + f" · {ici}",
              f"⭐ **Packs de niveau** : **{p['packs_niveau']}** · {ici}",
              f"💎 **Packs UR** : **{p['packs_ur']}** · prochain dans {data.UR_TOUS_LES - p['packs'] % data.UR_TOUS_LES} packs ouverts · {ici}",
              f"🏆 **Packs Worlds** : **{p['packs_pro']}** · {salon(data.SALON_TOUR_PROS, 'le salon des Worlds')}"]
    if data.LEC_OUVERTE:
        lignes.append(f"🇪🇺 **Packs LEC** : **{p['packs_lec']}** · {salon(data.SALON_LEC, 'le salon de la LEC')}")
    if data.WORLDS_TICKETS:
        lignes.append(f"🎟️ **Tickets Worlds** : **{p['tickets_worlds']}/{data.WORLDS_TICKETS_MAX}**")
    total = p["packs_niveau"] + p["packs_ur"] + p["packs_pro"] + (p["packs_lec"] if data.LEC_OUVERTE else 0) + (attente <= 0)
    return f"# 📦 Mes packs\n**{total}** pack{'s' if total > 1 else ''} à ouvrir en tout.\n\n" + "\n".join(lignes)


def boutique_periode():
    return int(time.time() // data.BOUTIQUE_DELAI)


def boutique_offre(g, periode):
    """La boutique de ce serveur pour cette période : [(article, détail)]. Tirée d'une graine fixe : la même pour tout le monde."""
    rng = random.Random(f"boutique-{g}-{periode}")
    offre = []
    for cle, a in data.BOUTIQUE.items():
        present = rng.random() * 100 < a["chance"]
        detail = rng.choice(sorted(data.COMPOSANTS)) if cle == "composants" else rng.choice(sorted(data.PAR_RARETE["SSR"])) if cle == "ssr" else None
        if present and (cle != "pack_lec" or data.LEC_OUVERTE):
            offre.append((cle, detail))
    return offre


def nom_article(cle, detail):
    a = data.BOUTIQUE[cle]
    if cle == "composants":
        nom, emoji = data.COMPOSANTS[detail]
        return f"{emoji} {a['quantite']} × {nom}"
    if cle == "ssr":
        return f"{a['emoji']} {data.CARTES[detail]['nom']} (SSR)"
    return f"{a['emoji']} {a['nom']}"


def embed_boutique(g, u, p):
    periode = boutique_periode()
    achats = db.boutique_achats(g, u, periode)
    reste = data.BOUTIQUE_DELAI - (time.time() % data.BOUTIQUE_DELAI)
    lignes = []
    for cle, detail in boutique_offre(g, periode):
        a = data.BOUTIQUE[cle]
        dispo = a["limite"] - achats.get(cle, 0)
        lignes.append(f"**{nom_article(cle, detail)}** · {a['prix']} golds · " + (f"encore {dispo} pour toi" if dispo > 0 else "✅ acheté"))
    e = discord.Embed(color=0xECC86E, description=f"# 🛒 La boutique\nLa même pour tout le serveur. Renouvelée dans **{duree(reste)}**.\n\n" + "\n".join(lignes)
                      + f"\n\n💰 Tu as **{p['golds']} golds**.")
    ssr = next((d for c, d in boutique_offre(g, periode) if c == "ssr"), None)
    if ssr and image_carte(ssr):
        e.set_thumbnail(url=f"attachment://{image_carte(ssr)}")
    return e, (joindre(image_carte(ssr)) if ssr else [])


class VueBoutique(discord.ui.View):
    def __init__(self, g, u, p):
        super().__init__(timeout=600)
        self.periode = boutique_periode()
        achats = db.boutique_achats(g, u, self.periode)
        for k, (cle, detail) in enumerate(boutique_offre(g, self.periode)):
            a = data.BOUTIQUE[cle]
            fini = achats.get(cle, 0) >= a["limite"]
            bouton = discord.ui.Button(label=f"{nom_article(cle, detail).split(' ', 1)[1]} · {a['prix']} golds"[:80], emoji=a["emoji"] if cle != "composants" else data.COMPOSANTS[detail][1],
                                       style=discord.ButtonStyle.secondary if fini or p["golds"] < a["prix"] else discord.ButtonStyle.success, disabled=fini, row=k // 3)
            bouton.callback = self.acheter(cle, detail)
            self.add_item(bouton)

    def acheter(self, cle, detail):
        async def clic(i):
            p = await charger(i)
            if not p:
                return
            a, periode = data.BOUTIQUE[cle], boutique_periode()
            if periode != self.periode:
                return await i.response.edit_message(content="🛒 La boutique vient de se renouveler : rouvre-la pour voir les nouveaux articles.", embed=None, view=None, attachments=[])
            if db.boutique_achats(i.guild_id, i.user.id, periode).get(cle, 0) >= a["limite"]:
                return await i.response.send_message("Tu as déjà pris cet article dans cette boutique.", ephemeral=True)
            if p["golds"] < a["prix"]:
                return await i.response.send_message(f"Il te faut {a['prix']} golds, tu en as {p['golds']}.", ephemeral=True)
            if cle == "pack_lec" and not db.lec_equipes(i.guild_id, i.user.id):
                return await i.response.send_message("Un pack LEC ne contient que les cartes des équipes LEC que tu as battues : bats d'abord une équipe de la LEC.", ephemeral=True)
            if cle == "pack_pro" and not db.worlds_equipes(i.guild_id, i.user.id):
                return await i.response.send_message("Un pack Worlds ne contient que les cartes des équipes que tu as éliminées aux Worlds : élimine d'abord une équipe.", ephemeral=True)
            p["golds"] -= a["prix"]
            texte = ""
            if cle == "composants":
                db.ajouter_composant(i.guild_id, i.user.id, detail, a["quantite"])
                texte = f"{data.COMPOSANTS[detail][1]} +{a['quantite']} {data.COMPOSANTS[detail][0]}."
            elif cle == "ssr":
                texte = f"🌟 **{data.CARTES[detail]['nom']}** · {donner(p, detail)}"
            elif cle == "pack_lec":
                p["packs_lec"] += 1
                texte = "🇪🇺 +1 pack LEC, à ouvrir dans le salon de la LEC."
            elif cle == "pack_pro":
                p["packs_pro"] += 1
                texte = "🏆 +1 pack Worlds, à ouvrir dans le salon des Worlds."
            elif cle == "pack_ur":
                p["packs_ur"] += 1
                texte = "💎 +1 pack UR, à ouvrir ici avec le bouton Pack UR."
            db.sauver(p)
            db.boutique_acheter(i.guild_id, i.user.id, periode, cle)
            e, fichiers = embed_boutique(i.guild_id, i.user.id, p)
            e.add_field(name="✅ Acheté", value=texte[:1024], inline=False)
            await i.response.edit_message(embed=e, view=VueBoutique(i.guild_id, i.user.id, p), attachments=fichiers)
            if cle == "ssr":
                await annoncer(i.guild, i.user, [detail])
        return clic


async def mega_tirage(i):
    """Méga tirage : data.MEGA_CARTES cartes d'un coup, au moins un SSR, et un pack UR offert. Un seul message récapitulatif."""
    p = await charger(i)
    if not p:
        return
    if p["golds"] < data.MEGA_PRIX:
        return await i.response.send_message(f"Il te faut {data.MEGA_PRIX} golds pour un méga tirage, tu en as {p['golds']}.", ephemeral=True)
    p["golds"] -= data.MEGA_PRIX
    packs_ur = p["packs_ur"]
    lec = db.lec_equipes(i.guild_id, i.user.id)
    bonus = bonus_packs(i.guild_id, i.user.id)
    tirages = [combat.tirer(p, bonus=bonus) for _ in range(data.MEGA_CARTES)]
    for ur in combat.ur_lec_multi(lec, set(db.cartes(i.guild_id, i.user.id)), data.MEGA_CARTES // 10):   # UR de la LEC, très rare
        faible = min(range(len(tirages)), key=lambda k: data.RARETES.index(data.CARTES[tirages[k]]["rarete"]))
        tirages[faible] = ur
    p["packs_ur"] = packs_ur + 1   # le compteur des 50 packs ne donne rien ici (+50 garde son rythme) : le pack UR offert le remplace
    p.pop("_pack_ur", None)
    if not any(data.CARTES[c]["rarete"] in ("SSR", "UR") for c in tirages):   # le SSR garanti, au hasard parmi tous les SSR
        faible = min(range(len(tirages)), key=lambda k: data.RARETES.index(data.CARTES[tirages[k]]["rarete"]))
        tirages[faible] = random.choice(data.PAR_RARETE["SSR"])
        p["pitie"] = 0
    tirages.sort(key=lambda c: (-data.RARETES.index(data.CARTES[c]["rarete"]), data.CARTES[c]["nom"]))   # les plus rares d'abord
    statuts = [(c, donner(p, c)) for c in tirages]
    db.sauver(p)
    compte = {}
    for c in tirages:
        compte[data.CARTES[c]["rarete"]] = compte.get(data.CARTES[c]["rarete"], 0) + 1
    rares = [f"{data.EMOJIS[data.CARTES[c]['rarete']]} **{data.CARTES[c]['nom']}** · {st.split(chr(10))[0]}" for c, st in statuts if data.CARTES[c]["rarete"] in ("SSR", "UR")]
    nouvelles = sorted({data.CARTES[c]["nom"] for c, st in statuts if st.startswith("🆕") and data.CARTES[c]["rarete"] not in ("SSR", "UR")})
    doublons = sum(1 for _, st in statuts if not st.startswith("🆕"))
    meilleur = tirages[0]
    anim = f"ouverture_{'SSR' if data.CARTES[meilleur]['rarete'] == 'UR' else data.CARTES[meilleur]['rarete']}.gif"
    animee = os.path.exists(os.path.join(DOSSIER_IMAGES, anim))
    premiere = anim if animee else "pack_ferme.png"
    await i.response.send_message(embed=embed_suspense(f"🎰 Méga tirage : {data.MEGA_CARTES} cartes s'ouvrent…", image=premiere), files=joindre(premiere), ephemeral=True)
    texte = (f"# 🎰 Méga tirage · {data.MEGA_CARTES} cartes\n"
             + " · ".join(f"{data.EMOJIS[r]} {compte[r]} {r}" for r in reversed(data.RARETES) if r in compte) + "\n\n"
             + ("\n".join(rares) + "\n\n" if rares else "")
             + (f"🆕 **Nouvelles cartes** : {', '.join(nouvelles)}\n" if nouvelles else "")
             + f"♻️ **{doublons} doublon{'s' if doublons > 1 else ''}** : étoiles, réserve d'XP et golds déjà versés.\n"
             + f"💎 **+1 pack UR offert**, à ouvrir avec le bouton **Pack UR** ({p['packs_ur']} à ouvrir).")
    e = discord.Embed(description=texte[:4096], color=data.COULEURS[data.CARTES[meilleur]["rarete"]])
    carte = image_carte(meilleur)
    pieces = joindre(carte)
    if pieces:
        e.set_image(url=f"attachment://{carte}")
    e.set_footer(text=f"{p['golds']} golds · SSR garanti dans {data.PITIE - p['pitie']} packs au plus")
    try:
        await asyncio.sleep(DUREE_OUVERTURE if animee else 1.4)
        await editer(i, embed=e, attachments=pieces)
    except ERREURS_RESEAU:
        pass
    await annoncer(i.guild, i.user, tirages)


class PanneauPacks(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Pack gratuit", emoji="🎁", style=discord.ButtonStyle.success, custom_id="f:gratuit")
    async def gratuit(self, i, _):
        if await rappel_cible(i, lambda j: ouvrir_pack(j, gratuit=True)):
            return
        await ouvrir_pack(i, gratuit=True)

    @discord.ui.button(label=f"Méga tirage · {data.MEGA_PRIX} golds", emoji="🎰", style=discord.ButtonStyle.primary, custom_id="f:mega")
    async def mega(self, i, _):
        if await rappel_cible(i, mega_tirage):
            return
        await mega_tirage(i)

    @discord.ui.button(label="Packs de niveau", emoji="⭐", style=discord.ButtonStyle.success, custom_id="f:pack_niveau", row=1)
    async def pack_niveau(self, i, _):
        if await rappel_cible(i, lambda j: ouvrir_pack(j, niveau=True)):
            return
        await ouvrir_pack(i, niveau=True)

    @discord.ui.button(label="Pack UR", emoji="💎", style=discord.ButtonStyle.danger, custom_id="f:pack_ur", row=1)
    async def pack_ur(self, i, _):
        await ouvrir_pack(i, ur=True)

    @discord.ui.button(label="Pack UR x5", emoji="💎", style=discord.ButtonStyle.primary, custom_id="f:pack_ur5", row=1)
    async def pack_ur5(self, i, _):
        await ouvrir_packs_ur_x5(i)

    @discord.ui.button(label="Boutique", emoji="🛒", style=discord.ButtonStyle.success, custom_id="f:boutique", row=2)
    async def boutique(self, i, _):
        p = await charger(i)
        if p:
            e, fichiers = embed_boutique(i.guild_id, i.user.id, p)
            await i.response.send_message(embed=e, view=VueBoutique(i.guild_id, i.user.id, p), files=fichiers, ephemeral=True)

    @discord.ui.button(label="Mes packs", emoji="🧮", style=discord.ButtonStyle.secondary, custom_id="f:mes_packs", row=2)
    async def mes_packs(self, i, _):
        p = await charger(i)
        if p:
            await i.response.send_message(embed=discord.Embed(color=COULEUR, description=texte_mes_packs(i.guild, p)), ephemeral=True)

    @discord.ui.button(label="SSR ciblé", emoji="🎯", style=discord.ButtonStyle.secondary, custom_id="f:cible", row=1)
    async def cible(self, i, _):
        p = await charger(i)
        if not p:
            return
        actuel = data.CARTES[p["cible"]]["nom"] if p["cible"] in data.CARTES else None
        texte = (f"## 🎯 SSR ciblé\nChoisis le SSR que tu veux viser. Quand un SSR tombe d'un pack, il y a **{data.CIBLE_CHANCE} %** de chances que ce soit lui. "
                 "Ça ne change pas ta chance d'avoir un SSR, seulement lequel. "
                 "Tu peux aussi viser un **SSR des Worlds ou de la LEC**, parmi les équipes que tu as battues. "
                 "Tu peux changer de cible quand tu veux.\n" + (f"Tu vises actuellement **{actuel}**." if actuel else "Tu ne vises personne pour l'instant."))
        await i.response.send_message(texte, view=ChoixCible(p["cible"], i.guild_id, i.user.id), ephemeral=True)

    @discord.ui.button(label=f"10 packs · {data.PRIX_PACK_10} golds", emoji="🎉", style=discord.ButtonStyle.primary, custom_id="f:pack10")
    async def pack10(self, i, _):
        if await rappel_cible(i, lambda j: self.pack10.callback(j)):
            return
        p = await charger(i)
        if not p:
            return
        if p["golds"] < data.PRIX_PACK_10:
            await i.response.send_message(f"Il te faut {data.PRIX_PACK_10} golds, tu en as {p['golds']}.", ephemeral=True)
            return
        p["golds"] -= data.PRIX_PACK_10
        lec = db.lec_equipes(i.guild_id, i.user.id)
        bonus = bonus_packs(i.guild_id, i.user.id)
        tirages = [combat.tirer(p, bonus=bonus) for _ in range(9)]
        garanti = None if any(data.CARTES[c]["rarete"] in ("SR", "SSR", "UR") for c in tirages) else "SR"
        tirages.append(combat.tirer(p, minimum=garanti, bonus=bonus))
        for ur in combat.ur_lec_multi(lec, set(db.cartes(i.guild_id, i.user.id)), 1):   # UR de la LEC, très rare
            faible = min(range(len(tirages)), key=lambda k: data.RARETES.index(data.CARTES[tirages[k]]["rarete"]))
            tirages[faible] = ur
        tirages.sort(key=lambda c: data.RARETES.index(data.CARTES[c]["rarete"]))   # les plus rares à la fin
        lignes = [f"{data.EMOJIS[data.CARTES[c]['rarete']]} **{data.CARTES[c]['nom']}** · {donner(p, c)}" for c in tirages]
        db.sauver(p)
        meilleur = tirages[-1]
        anim = f"ouverture_{data.CARTES[meilleur]['rarete']}.gif"   # l'animation prend la couleur de la meilleure carte des dix
        animee = os.path.exists(os.path.join(DOSSIER_IMAGES, anim))
        premiere = anim if animee else "pack_ferme.png"
        await i.response.send_message(embed=embed_suspense("📦 Dix packs s'ouvrent en même temps…", image=premiere),
                                      files=joindre(premiere), ephemeral=True)
        try:
            if animee:
                await asyncio.sleep(DUREE_OUVERTURE - 0.7)
            # Les cartes se révèlent une par une, des plus communes aux plus rares.
            for n in range(1, 11):
                await asyncio.sleep(0.7 if data.CARTES[tirages[n - 1]]["rarete"] in ("N", "R") else 1.3)
                e = discord.Embed(title=f"🎉 10 packs · {n}/10", description="\n".join(lignes[:n]),
                                  color=data.COULEURS[data.CARTES[tirages[n - 1]]["rarete"]])
                pieces = []
                if n == 10:   # à la fin, la meilleure carte des dix s'affiche dans son cadre
                    carte = image_carte(meilleur)
                    pieces = joindre(carte)
                    if pieces:
                        e.set_image(url=f"attachment://{carte}")
                    elif data.CARTES[meilleur]["image"]:
                        e.set_image(url=data.CARTES[meilleur]["image"])
                    e.set_footer(text=f"{p['golds']} golds · SSR garanti dans {data.PITIE - p['pitie']} packs au plus")
                await editer(i, embed=e, attachments=pieces)
        except ERREURS_RESEAU:
            pass
        await annoncer(i.guild, i.user, tirages)

    @discord.ui.button(label="Taux", emoji="📊", style=discord.ButtonStyle.secondary, custom_id="f:taux")
    async def taux(self, i, _):
        p = db.get_joueur(i.guild_id, i.user.id)
        t = "\n".join(f"{data.EMOJIS[r]} {r} : {data.TAUX[r]} % (gratuit : {data.TAUX_GRATUIT[r]} %)" for r in data.RARETES if r in data.TAUX)
        t += f"\n\nUn SSR est garanti au bout de {data.PITIE} packs sans en obtenir."
        t += (f"\n\n💎 **Pack UR** : un pack UR gagné tous les {data.UR_TOUS_LES} packs ouverts. Il contient "
              + " · ".join(f"{data.EMOJIS[r]} {r} {v} %" for r, v in data.UR_TAUX.items()) + f". UR garanti au {data.UR_PITIE}e pack UR sans en avoir eu.")
        t += (f"\nEn plus : **{data.UR_WORLDS_CHANCE} %** de chances d'une **UR des Worlds** des équipes que tu as éliminées. "
              "Le garanti donne une des UR du pack UR : " + ", ".join(data.CARTES[c]["nom"].split(",")[0] for c in data.UR_PACK) + ".")
        t += ("\n\n🎉 **Packs de 10 et méga tirage** : très rarement, une UR de la LEC des équipes que tu as battues. "
              "Et avec le **SSR ciblé**, tu peux viser un SSR des Worlds ou de la LEC parmi les équipes battues.")
        t += f"\n🎯 Avec un **SSR ciblé**, un SSR obtenu a {data.CIBLE_CHANCE} % de chances d'être celui que tu vises."
        if p:
            t += f" Tu en es à {p['pitie']}."
        await i.response.send_message(t, ephemeral=True)


class ChoixEquipe(discord.ui.View):
    """Menu déroulant pour choisir ses 3 champions (25 par page, avec un filtre de rareté ; l'équipe actuelle reste en tête)."""
    def __init__(self, p, possedees, filtre="Toutes", page=0):
        super().__init__(timeout=180)
        self.filtre, self.page = filtre, page
        actuelle = equipe_ids(p, possedees)
        toutes = sorted([c for c in possedees if c in data.CARTES], key=tri_cartes(possedees))
        tri, pages = page_de_cartes(toutes, filtre, page, gardees=actuelle)
        options = [discord.SelectOption(
            label=data.CARTES[c]["nom"], value=c, default=c in actuelle, emoji="⭐" if c in actuelle else None,
            description=f"{data.CARTES[c]['rarete']} · niv. {possedees[c]['niveau']} · {data.CARTES[c]['role']} · {data.CARTES[c]['region']}")
            for c in tri]
        menu = discord.ui.Select(placeholder="Choisis jusqu'à 3 cartes" + (f" · {filtre}" if filtre != "Toutes" else ""),
                                 min_values=1, max_values=min(3, len(options)), options=options, row=0)
        menu.callback = self.valider
        self.menu = menu
        self.add_item(menu)
        auto = discord.ui.Button(label="Meilleure équipe", emoji="⭐", style=discord.ButtonStyle.success, row=1)
        auto.callback = self.automatique
        self.add_item(auto)
        boutons_filtre(self, toutes, pages, 1, self.rafraichir)
        for cid in actuelle[1:]:   # le leader est le premier de l'équipe : ces boutons en changent
            b = discord.ui.Button(label=f"Leader : {data.CARTES[cid]['nom']}"[:80], emoji="👑", style=discord.ButtonStyle.secondary, row=2)
            b.callback = self.nommer_leader(cid)
            self.add_item(b)
        for cid in actuelle:   # un bouton par carte pour la passer devant ou derrière
            devant = ligne_de(p, cid) == "avant"
            bonne = data.LIGNES.get(data.CARTES[cid]["role"], "avant") == ligne_de(p, cid)
            b = discord.ui.Button(label=f"{data.CARTES[cid]['nom']} : {'devant' if devant else 'derrière'}"[:80], emoji="🛡️" if devant else "🏹",
                                  style=discord.ButtonStyle.success if bonne else discord.ButtonStyle.secondary, row=3)
            b.callback = self.changer_ligne(cid)
            self.add_item(b)

    def changer_ligne(self, cid):
        async def clic(i):
            p = await charger(i)
            if not p:
                return
            possedees = db.cartes(i.guild_id, i.user.id)
            placer(p, cid, "arriere" if ligne_de(p, cid) == "avant" else "avant")
            db.sauver(p)
            e = embed_equipe(p, possedees)
            await i.response.edit_message(content=None, embed=e, view=ChoixEquipe(p, possedees), attachments=image_equipe(e, p, possedees))
        return clic

    def nommer_leader(self, cid):
        async def clic(i):
            p = await charger(i)
            if not p:
                return
            possedees = db.cartes(i.guild_id, i.user.id)
            equipe = equipe_ids(p, possedees)
            if cid in equipe:
                equipe.remove(cid)
                p["equipe"] = ",".join([cid] + equipe)
                db.sauver(p)
            e = embed_equipe(p, possedees)
            await i.response.edit_message(content=None, embed=e, view=ChoixEquipe(p, possedees), attachments=image_equipe(e, p, possedees))
        return clic

    async def rafraichir(self, i):
        p = await charger(i)
        if not p:
            return
        await i.response.edit_message(view=ChoixEquipe(p, db.cartes(i.guild_id, i.user.id), self.filtre, self.page))

    async def automatique(self, i):
        resultat = await composer_meilleure_equipe(i)
        if resultat:
            e = embed_equipe(*resultat)
            await i.response.edit_message(content=None, embed=e, view=ChoixEquipe(*resultat), attachments=image_equipe(e, *resultat))

    async def valider(self, i):
        p = await charger(i)
        if not p:
            return
        possedees = db.cartes(i.guild_id, i.user.id)
        choix = [c for c in self.menu.values if c in possedees]
        ancien = equipe_ids(p, possedees)
        if ancien and ancien[0] in choix:   # le leader reste leader s'il est toujours dans l'équipe
            choix.remove(ancien[0])
            choix.insert(0, ancien[0])
        p["equipe"] = ",".join(choix)
        db.sauver(p)
        e = embed_equipe(p, possedees)
        await i.response.edit_message(content=None, embed=e, view=ChoixEquipe(p, possedees), attachments=image_equipe(e, p, possedees))


def image_equipe(e, p, possedees):
    """Ajoute à la fiche d'équipe sa prévisualisation (cartes sur leurs deux lignes) et renvoie les fichiers à joindre.
    Sans module d'images ou en cas de souci, la fiche reste en texte et la liste est vide."""
    try:
        ids = equipe_ids(p, possedees)
        cartes = []
        for k, c in enumerate(ids):
            role, ligne = data.CARTES[c]["role"], ligne_de(p, c)
            actif = data.LIGNES.get(role) == ligne
            cartes.append((c, ligne, k == 0, data.TEXTES_LIGNE[role] if actif else "", actif))
        total = sum(combat.puissance(c, possedees[c]["niveau"], possedees[c]["etoiles"]) for c in ids)
        chef = combat.texte_leader(ids)
        tampon = cartes_img.apercu_equipe(cartes, [chef.replace("**", "") if chef else "Ce leader ne donne aucun bonus", f"Puissance {total}"])
        if tampon is None:
            return []
        e.set_image(url="attachment://equipe.jpg")
        return [discord.File(tampon, filename="equipe.jpg")]
    except Exception:
        return []


def embed_equipe(p, possedees):
    ids = equipe_ids(p, possedees)
    total = sum(combat.puissance(c, possedees[c]["niveau"], possedees[c]["etoiles"]) for c in ids)
    e = discord.Embed(title=f"⚔️ Ton équipe · puissance {total}", color=COULEUR,
                      description="\n".join(("👑 " if k == 0 else "") + ligne_carte(c, possedees[c]) + f"\n-# {texte_ligne(p, c)}"
                                            for k, c in enumerate(ids)) or "Aucune carte.")
    if ids:
        e.add_field(name="Bonus de leader", inline=False,
                    value=combat.texte_leader(ids) or f"👑 **{data.CARTES[ids[0]]['nom']}** est leader, mais les sbires et les monstres ne donnent aucun bonus.")
    e.set_footer(text="Le leader 👑 donne le bonus de sa région à toute l'équipe. Les boutons du bas placent chaque carte devant ou derrière : "
                      "sur la ligne de son rôle, elle gagne un petit bonus, et les ennemis visent plus souvent la ligne avant.")
    return e


# 14 octobre : toutes les cartes qu'on peut obtenir, packs, packs UR, Worlds, LEC et LR de Faker comprises (pas les cartes introuvables).
CARTES_A_COLLECTIONNER = sorted(c for c, v in data.CARTES.items() if v.get("ulti") and c not in ("AsheUR",) and (
    v["en_jeu"] or c in data.UR_PACK or c in data.WORLDS_LRS or any(c in l for l in data.WORLDS_CARTES) or any(c in l for l in data.LEC_CARTES)
    or c in data.LEC_UR)) + sorted(c for c, v in data.CARTES.items() if not v.get("ulti") and v["en_jeu"])


class Collection(discord.ui.View):
    """Collection du joueur : un onglet par rareté, puis une fiche détaillée par carte."""
    def __init__(self, p, possedees):
        super().__init__(timeout=600)
        self.p, self.possedees = p, possedees
        self.rarete = next((r for r in reversed(data.RARETES) if self.de_rarete(r)), "N")   # meilleure rareté possédée
        self.carte, self.filtre, self.page = None, "Toutes", 0
        self.construire()

    def total(self, r=None):
        """Nombre de cartes à collectionner : celles des packs, plus les cartes retirées que le joueur possède déjà."""
        return len([c for c in CARTES_A_COLLECTIONNER if (r is None or data.CARTES[c]["rarete"] == r)] + [c for c in self.possedees
                   if c in data.CARTES and c not in CARTES_A_COLLECTIONNER and (r is None or data.CARTES[c]["rarete"] == r)])

    def de_rarete(self, r):
        cartes = [c for c in self.possedees if c in data.CARTES and data.CARTES[c]["rarete"] == r]
        return sorted(cartes, key=tri_cartes(self.possedees))

    def construire(self):
        """Reconstruit les boutons selon l'écran affiché (liste d'une rareté, ou fiche d'une carte)."""
        self.clear_items()
        if self.carte:
            retour = discord.ui.Button(label="Retour", emoji="⬅️", style=discord.ButtonStyle.secondary)
            retour.callback = self.retour
            self.add_item(retour)
            equipe = equipe_ids(self.p, self.possedees)
            if self.carte in equipe:
                b = discord.ui.Button(label="Retirer de l'équipe", emoji="➖", style=discord.ButtonStyle.danger, disabled=len(equipe) <= 1)
            else:
                b = discord.ui.Button(label="Mettre dans l'équipe", emoji="➕", style=discord.ButtonStyle.success, disabled=len(equipe) >= 3)
            b.callback = self.basculer_equipe
            self.add_item(b)
            mienne = self.possedees[self.carte]
            plein = mienne["niveau"] >= combat.niveau_max(self.carte, mienne["etoiles"])
            reserve = db.get_joueur(self.p["guild_id"], self.p["user_id"])["reserve_xp"]
            for libelle, niveaux in (("Réserve : +1 niveau", 1), ("Réserve : +5 niveaux", 5), ("Réserve : au maximum", 999)):
                r = discord.ui.Button(label=libelle, emoji="📚", style=discord.ButtonStyle.primary, row=1, disabled=plein or reserve <= 0)
                r.callback = self.verser_reserve(niveaux)
                self.add_item(r)
            return
        for r in reversed(data.RARETES):
            b = discord.ui.Button(label=f"{r} · {len(self.de_rarete(r))}/{self.total(r)}", emoji=data.EMOJIS[r], row=0,
                                  style=discord.ButtonStyle.primary if r == self.rarete else discord.ButtonStyle.secondary)
            b.callback = self.onglet(r)
            self.add_item(b)
        cartes, pages = page_de_cartes(self.de_rarete(self.rarete), page=self.page)
        if cartes:
            menu = discord.ui.Select(placeholder="Voir la fiche d'une carte…", row=1, options=[discord.SelectOption(
                label=data.CARTES[c]["nom"], value=c, emoji=data.EMOJIS[self.rarete],
                description=f"Niv. {self.possedees[c]['niveau']} · {data.CARTES[c]['role']} · {data.CARTES[c]['region']}") for c in cartes])
            menu.callback = self.choisir
            self.menu = menu
            self.add_item(menu)
        boutons_filtre(self, self.de_rarete(self.rarete), pages, 2, self.afficher, filtre=False)

    def embed(self):
        if self.carte:
            return self.fiche()
        total = len([c for c in self.possedees if c in data.CARTES])
        cartes = self.de_rarete(self.rarete)
        equipe = equipe_ids(self.p, self.possedees)
        lignes = [f"**{data.CARTES[c]['nom']}** {'★' * self.possedees[c]['etoiles']} · niv. {self.possedees[c]['niveau']} · "
                  f"{data.CARTES[c]['role']} · {data.CARTES[c]['region']}{' · ⚔️ équipe' if c in equipe else ''}"
                  f"{'' if data.CARTES[c]['en_jeu'] else ' · 🔒 hors packs'}" for c in cartes]
        manquantes = self.total(self.rarete) - len(cartes)
        e = discord.Embed(color=data.COULEURS[self.rarete], description=(
            f"# 🃏 Collection · {total}/{self.total()}\n## {PASTILLES[self.rarete]} {self.rarete} · {len(cartes)}/{self.total(self.rarete)}\n"
            + ("\n".join(lignes) or "*Aucune carte de cette rareté pour l'instant.*")
            + (f"\n\n❔ {manquantes} carte(s) encore à découvrir" if manquantes else "\n\n✅ Rareté complète !")))
        e.set_footer(text=f"{self.p['golds']} golds · {self.p['packs']} packs ouverts")
        return e

    def fiche(self):
        cid, c, mienne = self.carte, data.CARTES[self.carte], self.possedees[self.carte]
        pv, atk = combat.stats(cid, mienne["niveau"], mienne["etoiles"])
        maxi = combat.niveau_max(cid, mienne["etoiles"])
        if mienne["niveau"] >= maxi:
            xp = f"Niveau maximum ({maxi})" + (f" · une étoile de plus le porte à {maxi + data.ETOILE_NIVEAUX}" if mienne["etoiles"] < data.ETOILES_MAX and c["rarete"] != "UR" else "")
        else:
            xp = f"{combat.barre(mienne['xp'], combat.xp_requis(mienne['niveau']))} {mienne['xp']}/{combat.xp_requis(mienne['niveau'])} XP"
        etoiles = "sans étoiles" if c["rarete"] == "UR" else "★" * mienne["etoiles"] + "☆" * (data.ETOILES_MAX - mienne["etoiles"])
        if c["rarete"] != "UR" and mienne["etoiles"] < data.ETOILES_MAX and doublons_requis(cid, mienne["etoiles"]) > 1:
            etoiles += f" · {mienne.get('doublons') or 0}/{doublons_requis(cid, mienne['etoiles'])} doublons vers la suivante"
        e = discord.Embed(color=data.COULEURS[c["rarete"]], description=(
            f"# {c['nom']}\n## {PASTILLES[c['rarete']]} {c['rarete']} · {etoiles}\n"
            f"### Niveau {mienne['niveau']}/{maxi}\n{xp}\n📚 Réserve d'XP : **{db.get_joueur(self.p['guild_id'], self.p['user_id'])['reserve_xp']}** / {data.RESERVE_MAX}"))
        e.add_field(name="Stats", value=f"❤️ {pv} PV\n⚔️ {atk} ATQ ({c['type']})\n💨 {c['vitesse']} vitesse\n🛡️ {c['res'][0]} rés. physique\n🔮 {c['res'][1]} rés. magique\n"
                                        f"💪 Puissance {combat.puissance(cid, mienne['niveau'], mienne['etoiles'])}")
        e.add_field(name="Profil", value=f"{c['role'].capitalize()}\n{c['region']}" + ("\n⚔️ Dans ton équipe" if cid in equipe_ids(self.p, self.possedees) else "")
                    + ("" if c["en_jeu"] else "\n🔒 Retirée des packs"))
        if c["ulti"]:
            e.add_field(name=f"✨ Actif : {c['ulti']}", value=f"{texte_actif(cid)}\n*Se charge en {c['cout']} actions.*", inline=False)
            if data.TEXTES_KITS.get(cid, (None,))[0]:
                e.add_field(name="🔹 Passif", value=data.TEXTES_KITS[cid][0], inline=False)
        if c["region"] in data.LEADERS:
            stat, valeur = data.LEADERS[c["region"]]
            e.add_field(name="👑 Bonus de leader", value=f"+{valeur} % {data.NOMS_STATS[stat]} pour toute l'équipe", inline=False)
        if mienne.get("item"):
            e.add_field(name="🎒 Item équipé", value=combat.texte_item(*mienne["item"]), inline=False)
        rune = runes_equipees(self.p).get(cid)
        if rune:
            e.add_field(name="🔮 Rune équipée", value=texte_rune(rune), inline=False)
        fichier = image_carte(cid)
        if fichier:
            e.set_image(url=f"attachment://{fichier}")
        elif c["image"]:
            e.set_image(url=c["image"])
        return e

    async def afficher(self, i):
        self.construire()
        await i.response.edit_message(embed=self.embed(), view=self, attachments=joindre(image_carte(self.carte)) if self.carte else [])

    def onglet(self, r):
        async def clic(i):
            self.rarete, self.page = r, 0
            await self.afficher(i)
        return clic

    async def choisir(self, i):
        if self.menu.values and self.menu.values[0] in self.possedees:
            self.carte = self.menu.values[0]
        await self.afficher(i)

    async def retour(self, i):
        self.carte = None
        await self.afficher(i)

    def verser_reserve(self, niveaux):
        """Dépense la réserve d'XP sur la carte affichée, pour gagner au plus ce nombre de niveaux (tout ce qu'il reste si la réserve ne suffit pas)."""
        async def clic(i):
            p = db.get_joueur(i.guild_id, i.user.id)
            carte = db.cartes(i.guild_id, i.user.id).get(self.carte)
            if p and carte:
                plafond = combat.niveau_max(self.carte, carte["etoiles"])
                cible, besoin, n = min(plafond, carte["niveau"] + niveaux), -carte["xp"], carte["niveau"]
                while n < cible:
                    besoin += combat.xp_requis(n)
                    n += 1
                verse = max(0, min(besoin, p["reserve_xp"]))
                if verse:
                    combat.gagner_xp(self.carte, carte, verse)
                    db.sauver_carte(i.guild_id, i.user.id, self.carte, carte["niveau"], carte["xp"], carte["etoiles"])
                    p["reserve_xp"] -= verse
                    db.sauver(p)
                self.p, self.possedees = p, db.cartes(i.guild_id, i.user.id)
            await self.afficher(i)
        return clic

    async def basculer_equipe(self, i):
        p = db.get_joueur(i.guild_id, i.user.id)
        equipe = equipe_ids(p, self.possedees)
        if self.carte in equipe:
            if len(equipe) > 1:
                equipe.remove(self.carte)
        elif len(equipe) < 3:
            equipe.append(self.carte)   # ajoutée en dernier : le leader ne change pas
        p["equipe"] = ",".join(equipe)
        db.sauver(p)
        self.p = p
        await self.afficher(i)


# ------------------------------- Items ---------------------------------------
def texte_composants(sac):
    """Liste lisible des composants possédés."""
    lignes = [f"{emoji} {nom} ×{sac[cle]}" for cle, (nom, emoji) in data.COMPOSANTS.items() if sac.get(cle)]
    return " · ".join(lignes) or "Aucun pour l'instant : va en chercher dans les donjons."


class Items(discord.ui.View):
    """La forge et le sac d'items : fabriquer un item avec des composants, puis l'équiper sur un champion."""
    def __init__(self, p, guild_id, user_id):
        super().__init__(timeout=300)
        self.g, self.u, self.item, self.recette, self.message = guild_id, user_id, None, None, ""
        self.filtre, self.page = "Toutes", 0
        self.recharger()

    def recharger(self):
        self.sac = db.items(self.g, self.u)
        self.composants = db.composants(self.g, self.u)
        self.cartes = db.cartes(self.g, self.u)
        self.construire()

    def exemplaires(self, x):
        """14 octobre : les exemplaires d'un item (« x », « x~2 »…), du moins avancé au plus avancé."""
        return sorted([k for k in self.sac if k.split("~")[0] == x], key=lambda k: self.sac[k]["niveau"])

    def cible(self, x):
        """L'exemplaire que la forge travaille : le moins avancé qui n'est pas au maximum, sinon un nouvel exemplaire."""
        pas_fini = [k for k in self.exemplaires(x) if self.sac[k]["niveau"] < data.ITEM_NIVEAU_MAX]
        if pas_fini:
            return pas_fini[0]
        if x not in self.sac:
            return x
        n = 2
        while f"{x}~{n}" in self.sac:
            n += 1
        return f"{x}~{n}"

    def niveau_vise(self, x):
        return self.sac.get(self.cible(x), {}).get("niveau", 0) + 1

    def faisable(self, x):
        n = self.niveau_vise(x)
        return n <= data.ITEM_NIVEAU_MAX and all(self.composants.get(c, 0) >= q for c, q in combat.cout_recette(x, n).items())

    def texte_cout(self, x):
        n = self.niveau_vise(x)
        if n > data.ITEM_NIVEAU_MAX:
            return "Niveau maximum"
        return " + ".join(f"{q} {data.COMPOSANTS[c][0]} ({self.composants.get(c, 0)})" for c, q in combat.cout_recette(x, n).items())

    def construire(self):
        self.clear_items()
        if self.recette:
            b = discord.ui.Button(label=("Fabriquer un autre exemplaire" if self.exemplaires(self.recette) else "Fabriquer") if self.niveau_vise(self.recette) == 1 else "Améliorer", emoji="⚒️",
                                  style=discord.ButtonStyle.success, disabled=not self.faisable(self.recette))
            b.callback = self.fabriquer
            self.add_item(b)
        elif self.item:
            joueur = db.get_joueur(self.g, self.u)
            equipe = [c for c in joueur["equipe"].split(",") if c in self.cartes][:3] if joueur else []   # les cartes de l'équipe d'abord
            toutes = equipe + [c for c in sorted([c for c in self.cartes if c in data.CARTES], key=tri_cartes(self.cartes)) if c not in equipe]
            tri, pages = page_de_cartes(toutes, self.filtre, self.page, gardees=equipe)
            menu = discord.ui.Select(placeholder=f"Sur qui équiper {data.ITEMS[self.item.split('~')[0]][0]} ?", row=0, options=[discord.SelectOption(
                label=data.CARTES[c]["nom"], value=c, description=(f"Porte déjà : {data.ITEMS[self.cartes[c]['item'][0]][0]}" if self.cartes[c].get("item")
                                                                  else f"{data.CARTES[c]['rarete']} · niv. {self.cartes[c]['niveau']}") + (" · dans ton équipe" if c in equipe else "")) for c in tri])
            menu.callback = self.equiper
            self.menu = menu
            self.add_item(menu)
            boutons_filtre(self, toutes, pages, 2, self.rafraichir_filtre)
            if self.sac[self.item]["carte"]:
                retirer = discord.ui.Button(label="Retirer l'item", emoji="↩️", style=discord.ButtonStyle.secondary, row=1)
                retirer.callback = self.retirer
                self.add_item(retirer)
        else:
            forge = discord.ui.Select(placeholder="⚒️ Fabriquer ou améliorer un item", row=0, options=[discord.SelectOption(
                label=f"{data.ITEMS[x][0]} → " + (f"exemplaire {len(self.exemplaires(x)) + 1}" if self.niveau_vise(x) == 1 and self.exemplaires(x) else f"niv. {self.niveau_vise(x)}") + (" ✅" if self.faisable(x) else ""),
                value=x, emoji=data.ITEMS[x][1], description=self.texte_cout(x)[:100]) for x in data.ITEMS])
            forge.callback = self.choisir_recette
            self.forge = forge
            self.add_item(forge)
            possedes = sorted([x for x in self.sac if x.split("~")[0] in data.ITEMS])[:25]
            if possedes:
                menu = discord.ui.Select(placeholder="🎒 Équiper ou déplacer un item", row=1, options=[discord.SelectOption(
                    label=f"{data.ITEMS[x.split('~')[0]][0]}" + (f" #{x.split('~')[1]}" if "~" in x else "") + f" niv. {self.sac[x]['niveau']}", value=x, emoji=data.ITEMS[x.split("~")[0]][1],
                    description=(f"Sur {data.CARTES[self.sac[x]['carte']]['nom']}" if self.sac[x]["carte"] in data.CARTES else "Non équipé")) for x in possedes])
                menu.callback = self.selection
                self.menu = menu
                self.add_item(menu)
        if self.recette or self.item:
            retour = discord.ui.Button(label="Retour", emoji="◀️", style=discord.ButtonStyle.secondary, row=1)
            retour.callback = self.retour
            self.add_item(retour)

    def embed(self):
        e = discord.Embed(color=COULEUR)
        texte = "# ⚒️ Forge et items\n" + (f"{self.message}\n\n" if self.message else "")
        if self.recette:
            x, n = self.recette, self.niveau_vise(self.recette)
            if n > data.ITEM_NIVEAU_MAX:
                texte += combat.texte_item(x, data.ITEM_NIVEAU_MAX) + "\nCet item est déjà au niveau maximum.\n"
            else:
                texte += f"## {('Fabriquer un autre exemplaire' if self.exemplaires(x) else 'Fabriquer') if n == 1 else 'Améliorer'}\n{combat.texte_item(x, n)}\n\n**Il te faut :**\n" + "\n".join(
                    f"{'✅' if self.composants.get(c, 0) >= q else '❌'} {data.COMPOSANTS[c][1]} {q} × {data.COMPOSANTS[c][0]} · tu en as {self.composants.get(c, 0)}"
                    for c, q in combat.cout_recette(x, n).items()) + "\n"
                ou = [f"{d[1]} {d[0]}" for d in data.DONJONS if any(c in d[2] for c in data.RECETTES[x])]
                texte += f"\n-# On les trouve dans : {', '.join(ou)}.\n"
        else:
            texte += f"## Tes composants\n{texte_composants(self.composants)}\n"
            if self.sac:
                texte += "## Tes items\n" + "\n".join(
                    combat.texte_item(x.split("~")[0], o["niveau"]) + (f" → **{data.CARTES[o['carte']]['nom']}**" if o["carte"] in data.CARTES else " → *non équipé*")
                    for x, o in sorted(self.sac.items()) if x.split("~")[0] in data.ITEMS)
            else:
                texte += "\nTu n'as encore aucun item. Choisis une recette dans le menu : un ✅ signale celles que tu peux fabriquer."
        e.description = texte
        e.set_footer(text="Les composants se gagnent dans les donjons. Refabriquer un item l'améliore ; une fois au niveau maximum, tu en fabriques un autre exemplaire pour un autre champion. Un item par champion.")
        return e

    async def afficher(self, i):
        await i.response.edit_message(embed=self.embed(), view=self)

    async def rafraichir_filtre(self, i):
        self.construire()
        await self.afficher(i)

    async def choisir_recette(self, i):
        if self.forge.values and self.forge.values[0] in data.ITEMS:
            self.recette, self.message = self.forge.values[0], ""
        self.construire()
        await self.afficher(i)

    async def fabriquer(self, i):
        x = self.recette
        self.sac, self.composants = db.items(self.g, self.u), db.composants(self.g, self.u)   # relus : pas de double clic gagnant
        if self.faisable(x):
            n = self.niveau_vise(x)
            for c, q in combat.cout_recette(x, n).items():
                db.ajouter_composant(self.g, self.u, c, -q)
            k = self.cible(x)
            db.sauver_item(self.g, self.u, k, n, self.sac.get(k, {}).get("carte", ""))
            self.message = f"✅ **{data.ITEMS[x][0]}** est {('fabriqué' + (f' (exemplaire {k.split(chr(126))[1]})' if '~' in k else '')) if n == 1 else f'amélioré au niveau {n}'} !" + (" Équipe-le avec le menu du bas." if n == 1 else "")
        self.recette = None
        self.recharger()
        await self.afficher(i)

    async def selection(self, i):
        if self.menu.values and self.menu.values[0] in self.sac:
            self.item, self.message = self.menu.values[0], ""
        self.construire()
        await self.afficher(i)

    async def equiper(self, i):
        carte = self.menu.values[0] if self.menu.values else None
        if carte in db.cartes(self.g, self.u) and self.item in db.items(self.g, self.u):
            db.sauver_item(self.g, self.u, self.item, self.sac[self.item]["niveau"], carte)
            self.message = f"✅ **{data.ITEMS[self.item.split('~')[0]][0]}** est équipé sur **{data.CARTES[carte]['nom']}**."
        self.item = None
        self.recharger()
        await self.afficher(i)

    async def retirer(self, i):
        db.sauver_item(self.g, self.u, self.item, self.sac[self.item]["niveau"], "")
        self.message = f"↩️ **{data.ITEMS[self.item.split('~')[0]][0]}** est retourné dans ton sac."
        self.item = None
        self.recharger()
        await self.afficher(i)

    async def retour(self, i):
        self.item = self.recette = None
        self.construire()
        await self.afficher(i)


class VueReserve(discord.ui.View):
    """La réserve d'XP : on choisit une carte, puis combien de niveaux lui donner."""
    def __init__(self, p, possedees):
        super().__init__(timeout=600)
        self.p, self.possedees, self.carte, self.note = p, possedees, None, ""
        self.filtre, self.page = "Toutes", 0
        self.construire()

    def montables(self):
        equipe = equipe_ids(self.p, self.possedees)
        libres = [c for c in self.possedees if c in data.CARTES and self.possedees[c]["niveau"] < combat.niveau_max(c, self.possedees[c]["etoiles"])]
        return sorted(libres, key=lambda c: (c not in equipe, -data.RARETES.index(data.CARTES[c]["rarete"]), -self.possedees[c]["niveau"]))

    def construire(self):
        self.clear_items()
        toutes = self.montables()
        if not toutes or self.p["reserve_xp"] <= 0:
            return
        equipe = equipe_ids(self.p, self.possedees)
        cartes, pages = page_de_cartes(toutes, self.filtre, self.page, gardees=[self.carte] if self.carte else [])
        menu = discord.ui.Select(placeholder="Sur quelle carte verser ta réserve ?", row=0, options=[discord.SelectOption(
            label=data.CARTES[c]["nom"], value=c, emoji=data.EMOJIS[data.CARTES[c]["rarete"]], default=c == self.carte,
            description=f"Niv. {self.possedees[c]['niveau']}/{combat.niveau_max(c, self.possedees[c]['etoiles'])}" + (" · dans ton équipe" if c in equipe else "")) for c in cartes])
        menu.callback = self.choisir(menu)
        self.add_item(menu)
        if self.carte in cartes:
            for libelle, niveaux in (("+1 niveau", 1), ("+5 niveaux", 5), ("Au maximum", 999)):
                b = discord.ui.Button(label=libelle, emoji="📚", style=discord.ButtonStyle.primary, row=1)
                b.callback = self.verser(niveaux)
                self.add_item(b)
        boutons_filtre(self, toutes, pages, 2, self.rafraichir)

    async def rafraichir(self, i):
        self.construire()
        await i.response.edit_message(embed=self.embed(), view=self)

    def embed(self):
        texte = (f"# 📚 Ta réserve d'XP\n## {self.p['reserve_xp']} / {data.RESERVE_MAX} XP\n"
                 "Chaque **doublon** tiré dans un pack la remplit. Verse-la sur la carte de ton choix : c'est le moyen le plus rapide de monter un champion que tu viens de tirer.")
        if self.carte in self.possedees:
            c = self.possedees[self.carte]
            texte += f"\n\n**{data.CARTES[self.carte]['nom']}** · niveau {c['niveau']}/{combat.niveau_max(self.carte, c['etoiles'])} · prochain niveau : {combat.xp_requis(c['niveau']) - c['xp']} XP"
        if self.note:
            texte += f"\n\n{self.note}"
        e = discord.Embed(color=COULEUR, description=texte)
        if self.p["reserve_xp"] <= 0:
            e.set_footer(text="Ta réserve est vide. Ouvre des packs : chaque doublon la remplit.")
        elif not self.montables():
            e.set_footer(text="Toutes tes cartes sont à leur niveau maximum. Une étoile de plus relève ce maximum de 10 niveaux.")
        else:
            e.set_footer(text="Choisis une carte dans le menu, puis le nombre de niveaux à lui donner.")
        return e

    def choisir(self, menu):
        async def clic(i):
            self.carte, self.note = menu.values[0], ""
            self.construire()
            await i.response.edit_message(embed=self.embed(), view=self)
        return clic

    def verser(self, niveaux):
        async def clic(i):
            p = db.get_joueur(i.guild_id, i.user.id)
            carte = db.cartes(i.guild_id, i.user.id).get(self.carte)
            if p and carte:
                avant = carte["niveau"]
                cible, besoin, n = min(combat.niveau_max(self.carte, carte["etoiles"]), avant + niveaux), -carte["xp"], avant
                while n < cible:
                    besoin += combat.xp_requis(n)
                    n += 1
                verse = max(0, min(besoin, p["reserve_xp"]))
                if verse:
                    combat.gagner_xp(self.carte, carte, verse)
                    db.sauver_carte(i.guild_id, i.user.id, self.carte, carte["niveau"], carte["xp"], carte["etoiles"])
                    p["reserve_xp"] -= verse
                    db.sauver(p)
                self.note = f"✅ {verse} XP versés : **{data.CARTES[self.carte]['nom']}** passe du niveau {avant} au niveau {carte['niveau']}."
                self.p, self.possedees = p, db.cartes(i.guild_id, i.user.id)
            self.construire()
            await i.response.edit_message(embed=self.embed(), view=self)
        return clic


class PanneauCollection(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ma collection", emoji="🃏", style=discord.ButtonStyle.primary, custom_id="f:collection")
    async def collection(self, i, _):
        p = await charger(i)
        if not p:
            return
        vue = Collection(p, db.cartes(i.guild_id, i.user.id))
        await i.response.send_message(embed=vue.embed(), view=vue, ephemeral=True)

    @discord.ui.button(label="Mon équipe", emoji="⚔️", style=discord.ButtonStyle.primary, custom_id="f:equipe")
    async def equipe(self, i, _):
        p = await charger(i)
        if not p:
            return
        possedees = db.cartes(i.guild_id, i.user.id)
        e = embed_equipe(p, possedees)
        await i.response.send_message(embed=e, view=ChoixEquipe(p, possedees), files=image_equipe(e, p, possedees), ephemeral=True)

    @discord.ui.button(label="Mes items", emoji="🎒", style=discord.ButtonStyle.primary, custom_id="f:items")
    async def items(self, i, _):
        p = await charger(i)
        if not p:
            return
        vue = Items(p, i.guild_id, i.user.id)
        await i.response.send_message(embed=vue.embed(), view=vue, ephemeral=True)

    @discord.ui.button(label="Mes runes", emoji="🔮", style=discord.ButtonStyle.primary, custom_id="f:runes")
    async def runes(self, i, _):
        if not await proposer_rune(i):
            await ouvrir_runes(i)

    @discord.ui.button(label="Réserve d'XP", emoji="📚", style=discord.ButtonStyle.success, custom_id="f:reserve", row=1)
    async def reserve(self, i, _):
        p = await charger(i)
        if not p:
            return
        vue = VueReserve(p, db.cartes(i.guild_id, i.user.id))
        await i.response.send_message(embed=vue.embed(), view=vue, ephemeral=True)

    @discord.ui.button(label="Classement", emoji="🏆", style=discord.ButtonStyle.secondary, custom_id="f:top")
    async def classement(self, i, _):
        lignes = [f"**{n}.** <@{p['user_id']}> · étage {p['etage']} · {p['nb']} cartes"
                  for n, p in enumerate(db.classement(i.guild_id), 1)]
        e = discord.Embed(title="🏆 Classement", description="\n".join(lignes) or "Personne pour l'instant.", color=COULEUR)
        await i.response.send_message(embed=e, ephemeral=True)


def ligne_unite(u):
    """Une ligne d'affichage pour une unité : barre de vie, nom, PV et jauge d'ulti."""
    if u["pv"] <= 0:
        return f"{combat.barre_pv(0, 1, 6)} 💀 ~~{u['nom']}~~"
    jauge = f" · {'◆' * min(u['jauge'], u['cout'])}{'◇' * max(0, u['cout'] - u['jauge'])}" if u["cout"] else ""
    bouclier = f" 🛡️{u['bouclier']}" if u.get("bouclier") else ""
    return f"{combat.barre_pv(u['pv'], u['pvmax'], 6)} **{u['nom']}** {max(0, u['pv'])}/{u['pvmax']}{bouclier}{jauge}"


class EmbedScene(discord.Embed):
    """Un embed qui peut porter en plus l'image de la scène de combat (discord.Embed n'accepte pas d'attribut en plus)."""
    scene = None


def illustrer(e, cid_image=None, cid_vignette=None, recompense=None):
    """Illustre un embed de combat et renvoie les fichiers à joindre. Par ordre de priorité : la carte gagnée (recompense),
    la scène de combat préparée par embed_combat, sinon la grande image d'une carte et la vignette d'une autre."""
    if recompense and recompense in data.CARTES:
        carte = image_carte(recompense)
        fichier = fichier_image(carte) if carte else None
        if fichier:
            e.set_image(url=f"attachment://{carte}")
            return [fichier]
    scene = getattr(e, "scene", None)
    if scene is not None:
        e.set_image(url="attachment://combat.jpg")
        return [discord.File(scene, filename="combat.jpg")]
    noms = []
    for cid, poser in ((cid_image, e.set_image), (cid_vignette, e.set_thumbnail)):
        if not cid or cid not in data.CARTES:
            continue
        fichier = image_locale(cid)
        if fichier:
            poser(url=f"attachment://{fichier}")
            if fichier not in noms:
                noms.append(fichier)
        elif data.CARTES[cid]["image"]:
            poser(url=data.CARTES[cid]["image"])
    return [f for f in (fichier_image(n) for n in noms) if f]


def embed_combat(titre, sous_titre, etat, lignes, couleur=COULEUR, fond="combat"):
    e = EmbedScene(description=f"# {titre}\n## {sous_titre}\n" + "\n".join(lignes), color=couleur)
    try:   # la scène en image (cartes face à face, barres de vie) ; sans elle, on retombe sur l'affichage en texte
        e.scene = cartes_img.scene(etat, "Ton équipe", titre, lignes, fond=fond)
    except Exception:
        e.scene = None
    if e.scene is None:
        e.add_field(name="Ton équipe", value="\n".join(ligne_unite(u) for u in etat if u["camp"] == 0), inline=False)
        e.add_field(name="Ennemis", value="\n".join(ligne_unite(u) for u in etat if u["camp"] == 1), inline=False)
    return e


def ennemi_illustre(etat):
    """Premier ennemi encore debout qui possède une illustration (pour la vignette)."""
    vivants = [u for u in etat if u["camp"] == 1 and u["pv"] > 0 and u["cid"]] or [u for u in etat if u["camp"] == 1 and u["cid"]]
    return vivants[0]["cid"] if vivants else None


def regrouper(tours, maximum=5):
    """Regroupe les tours en quelques étapes d'animation pour qu'un long combat ne dure pas une éternité."""
    taille = -(-len(tours) // maximum)   # division arrondie au supérieur
    return [tours[k:k + taille] for k in range(0, len(tours), taille)]


async def combattre(i, remplacer=False, rapide=False):
    """Combat de l'étage suivant. Le résultat est calculé et sauvegardé tout de suite ; l'animation n'est que de l'affichage."""
    p = await charger(i)
    if not p:
        return
    offre = offre_item(p)
    if offre:   # le butin du Héraut attend d'être choisi : on le propose avant d'aller plus haut
        if remplacer:
            await i.response.edit_message(content=None, embed=embed_offre(offre), view=ChoixItem(offre), attachments=[])
        else:
            await i.response.send_message(embed=embed_offre(offre), view=ChoixItem(offre), ephemeral=True)
        return
    possedees = db.cartes(i.guild_id, i.user.id)
    ids = equipe_ids(p, possedees)
    if not ids:
        await i.response.send_message("Ton équipe est vide. Compose-la dans le salon de la collection.", ephemeral=True)
        return
    if p["etage"] >= data.TOUR_MAX:
        await i.response.send_message(f"🏆 Tu as vaincu les {data.TOUR_MAX} étages de la tour. Il n'y a plus rien au-dessus… pour l'instant.", ephemeral=True)
        return
    etage = p["etage"] + 1
    equipe, adversaires = combat.equipe_joueur(ids, possedees), combat.ennemis(etage)
    depart = combat.photo(equipe + adversaires)
    victoire, tours = combat.simuler_detail(equipe, adversaires, hemorragie=etage > 100)   # tour difficile : soins réduits
    noter_combat(p, "tour", etage, victoire, len(tours), tours[-1]["etat"], possedees)
    titre = f"{'👹 Boss · ' if combat.est_boss(etage) else '⚔️ '}Étage {etage}" + (" · tour difficile" if etage > 100 else "")

    recompenses, carte_pack, nom_pack, statut_pack, cartes_niveau, gagnee = None, None, "", "", [], None
    if victoire:
        golds = int((data.TOUR_GOLDS[0] + data.TOUR_GOLDS[1] * etage) * bonus_golds(ids, possedees))
        xp = data.TOUR_XP[0] + data.TOUR_XP[1] * etage
        p["etage"] = etage
        p["golds"] += golds
        # Packs de palier : taux doublés tous les 5 étages, boss compris. Gagnés une seule fois, comme l'étage.
        if etage == data.TOUR_SSR_GARANTI:
            carte_pack, nom_pack = combat.tirer(p, taux={"SSR": 100}), "🎁 Pack du boss : SSR garanti !"
        elif combat.est_boss(etage):
            carte_pack, nom_pack = combat.tirer(p, taux=data.TAUX_BOSS), "🎁 Pack du boss (taux doublés)"
        elif etage % data.TOUR_PACK_SR == 0:
            carte_pack, nom_pack = combat.tirer(p, taux=data.TAUX_BOSS), "🎁 Pack de palier (taux doublés)"
        if carte_pack:
            statut_pack = donner(p, carte_pack)
        montees = []
        for cid in ids:
            n = combat.gagner_xp(cid, possedees[cid], xp)
            db.sauver_carte(i.guild_id, i.user.id, cid, possedees[cid]["niveau"], possedees[cid]["xp"], possedees[cid]["etoiles"])
            if n:
                montees.append(f"{data.CARTES[cid]['nom']} niv. {possedees[cid]['niveau']}")
        db.sauver(p)
        recompenses = f"💰 +{golds} golds · ✨ +{xp} XP par carte" + (f"\n⬆️ {', '.join(montees)}" if montees else "")

    vedette = max(ids, key=lambda c: combat.puissance(c, possedees[c]["niveau"], possedees[c]["etoiles"]))   # carte mise en avant

    # Écran final
    moments = [l for t in tours for l in t["journal"] if not l.startswith("💫")]
    final = embed_combat(titre, f"{'🏆 Victoire' if victoire else '💀 Défaite'} en {len(tours)} tours", tours[-1]["etat"], moments[-6:],
                         0x2F855A if victoire else 0xC53030)
    vue = Suite()
    if victoire:
        final.add_field(name="Récompenses", value=recompenses, inline=False)
        # L'XP de compte d'un étage grandit avec la hauteur, et un boss compte bien plus : la tour suit le coût des niveaux.
        part = 1.0
        if etage >= data.TOUR_XP_COMPTE[2]:   # avant cet étage, l'XP de compte reste fixe
            part = data.TOUR_XP_COMPTE[0] ** (min(etage, 100) - data.TOUR_XP_COMPTE[2]) * (data.TOUR_XP_COMPTE[1] if combat.est_boss(etage) else 1)
        final.add_field(name="XP de compte", value=f"⭐ +{int(round(data.XP_COMPTE['tour'] * part))}", inline=True)
        cartes_niveau = champ_compte(p, final, "tour", part)
        if carte_pack:
            c = data.CARTES[carte_pack]
            final.add_field(name=nom_pack, value=f"{data.EMOJIS[c['rarete']]} **{c['nom']}** · {c['rarete']} · {statut_pack}", inline=False)
        db.sauver(p)
        if etage == data.ITEM_ETAGE and p["items_choisis"] < 1:
            final.add_field(name="🎁 Le butin du Héraut", inline=False, value="Tu as gagné **un item au choix parmi trois**. Appuie sur **Étage suivant** pour le choisir.")
        final.set_footer(text=f"{p['golds']} golds · prochain étage : {etage + 1}")
        dernier_ulti = [c for t in tours for c in t["ultis"] if c]
        gagnee = carte_pack or (cartes_niveau[0] if cartes_niveau else None)   # la carte montrée : pack de palier, sinon pack de niveau
        fichiers_fin = illustrer(final, dernier_ulti[-1] if dernier_ulti else vedette, recompense=gagnee)
    else:
        mieux = combat.meilleure_equipe(possedees)
        if combat.puissance_equipe(mieux, possedees) > combat.puissance_equipe(ids, possedees):
            oubliees = [data.CARTES[c]["nom"] for c in mieux if c not in ids]
            final.add_field(name="💡 Tu as plus fort dans ta collection", inline=False,
                            value=f"**{', '.join(oubliees)}** ne {'sont' if len(oubliees) > 1 else 'est'} pas dans ton équipe. Le bouton ci-dessous compose ta meilleure équipe.")
            vue = Revanche(proposer=True)
        else:
            final.set_footer(text="Renforce ton équipe : ouvre des packs ou récupère le butin de ton expédition pour gagner de l'XP.")
            pistes = conseils_defaite(p, possedees, ids)
            if pistes:
                final.add_field(name="💡 Ce que tu peux faire maintenant", value="\n".join(pistes)[:1024], inline=False)
            vue = Revanche()
        fichiers_fin = illustrer(final, None, ennemi_illustre(tours[-1]["etat"]))

    await animer_combat(i, titre, depart, tours, final, vue, fichiers_fin, vedette, remplacer, rapide, pack=gagnee)
    if carte_pack or cartes_niveau:
        await annoncer(i.guild, i.user, ([carte_pack] if carte_pack else []) + cartes_niveau)


async def animer_combat(i, titre, depart, tours, final, vue, fichiers_fin, vedette, remplacer=False, rapide=False, pack=None):
    """Affiche un combat déjà calculé : face-à-face, déroulé en quelques étapes, puis l'écran final.
    La grande image montre ta carte vedette, puis le champion qui vient de lancer son ulti ; la vignette montre l'ennemi."""
    options = {"view": vue} if vue else {}
    ouverture, pieces = embed_ouverture(pack, "🎁 Tu as gagné un pack ! Il s'ouvre…") if pack else (None, [])
    if rapide and ouverture:   # même sans animation de combat, un pack gagné s'ouvre avec la sienne
        if remplacer:
            await i.response.edit_message(embed=ouverture, view=None, attachments=pieces)
        else:
            await i.response.send_message(embed=ouverture, files=pieces, ephemeral=True)
        try:
            await asyncio.sleep(DUREE_OUVERTURE)
            await editer(i, embed=final, view=vue, attachments=fichiers_fin)
        except ERREURS_RESEAU:
            pass
        return
    if rapide:
        if remplacer:
            await i.response.edit_message(embed=final, view=vue, attachments=fichiers_fin)
        else:
            await i.response.send_message(embed=final, files=fichiers_fin, ephemeral=True, **options)
        return
    debut = embed_combat(titre, "Le combat commence…", depart, [])
    fichiers = illustrer(debut, vedette, ennemi_illustre(depart))
    if remplacer:
        await i.response.edit_message(embed=debut, view=None, attachments=fichiers)
    else:
        await i.response.send_message(embed=debut, files=fichiers, ephemeral=True)
    try:
        en_scene = vedette
        for groupe in regrouper(tours):
            await asyncio.sleep(1.3)
            premier, dernier = groupe[0]["numero"], groupe[-1]["numero"]
            lignes = [l for t in groupe for l in t["journal"]][-5:]
            inflige, subi = sum(t["degats"][0] for t in groupe), sum(t["degats"][1] for t in groupe)
            lignes.append(f"🗡️ Ton équipe inflige **{inflige}** dégâts et en subit **{subi}**.")
            sous_titre = f"Tour {premier}" if premier == dernier else f"Tours {premier} à {dernier}"
            ultis = [c for t in groupe for c in t["ultis"] if c]
            if ultis:
                en_scene = ultis[-1]
            etape = embed_combat(titre, sous_titre, groupe[-1]["etat"], lignes)
            await editer(i, embed=etape, attachments=illustrer(etape, en_scene, ennemi_illustre(groupe[-1]["etat"])))
        await asyncio.sleep(1.3)
        if ouverture:
            await editer(i, embed=ouverture, attachments=pieces)
            await asyncio.sleep(DUREE_OUVERTURE)
        await editer(i, embed=final, view=vue, attachments=fichiers_fin)
    except ERREURS_RESEAU:
        pass


def offre_item(p):
    """Prépare, une seule fois par compte, le choix d'un item parmi trois offert pour avoir vaincu le Héraut (étage 20)."""
    if p["etage"] >= data.ITEM_ETAGE and p["items_choisis"] < 1 and not p["items_offre"]:
        sac = db.items(p["guild_id"], p["user_id"])
        libres = [x for x in data.ITEMS if x not in sac] or list(data.ITEMS)
        p["items_offre"] = ",".join(random.sample(libres, min(3, len(libres))))
        db.sauver(p)
    return [x for x in p["items_offre"].split(",") if x in data.ITEMS]


def embed_offre(offre):
    lignes = [f"{data.ITEMS[x][1]} **{data.ITEMS[x][0]}** · {data.ITEMS[x][4].format(data.ITEMS[x][3][0])}" for x in offre]
    return discord.Embed(color=0xD69E2E, description="# 🎁 Le butin du Héraut\nTu as vaincu le Héraut de la Faille : choisis **un item** parmi ces trois. "
                         "Tu l'équiperas ensuite sur le champion de ton choix, et tu pourras l'améliorer plus tard à la forge.\n\n" + "\n".join(lignes))


class ChoixItem(discord.ui.View):
    """Le choix d'un item parmi trois, puis du champion qui le porte."""
    def __init__(self, offre):
        super().__init__(timeout=600)
        for x in offre:
            b = discord.ui.Button(label=data.ITEMS[x][0][:80], emoji=data.ITEMS[x][1], style=discord.ButtonStyle.success)
            b.callback = self.prendre(x)
            self.add_item(b)

    def prendre(self, x):
        async def clic(i):
            p = await charger(i)
            if not p:
                return
            if x not in p["items_offre"].split(","):
                await i.response.edit_message(content="Tu as déjà choisi ton item.", embed=None, view=None, attachments=[])
                return
            sac = db.items(i.guild_id, i.user.id)
            niveau = min(data.ITEM_NIVEAU_MAX, sac.get(x, {}).get("niveau", 0) + 1)
            db.sauver_item(i.guild_id, i.user.id, x, niveau, sac.get(x, {}).get("carte", ""))
            p["items_offre"], p["items_choisis"] = "", p["items_choisis"] + 1
            db.sauver(p)
            possedees = db.cartes(i.guild_id, i.user.id)
            e = discord.Embed(color=0x2F855A, description=f"# {data.ITEMS[x][1]} {data.ITEMS[x][0]} obtenu !\n"
                              f"{data.ITEMS[x][4].format(data.ITEMS[x][3][niveau - 1])} · niveau {niveau}\n\nSur quel champion veux-tu l'équiper ? "
                              "Tu pourras le déplacer plus tard à la forge (salon des donjons).")
            await i.response.edit_message(embed=e, view=PorteurItem(x, niveau, equipe_ids(p, possedees), possedees), attachments=[])
        return clic


class PorteurItem(discord.ui.View):
    def __init__(self, item, niveau, ids, possedees):
        super().__init__(timeout=600)
        self.item, self.niveau = item, niveau
        tri = ids + [c for c in sorted(possedees, key=tri_cartes(possedees)) if c not in ids]
        for cid in tri[:5]:
            b = discord.ui.Button(label=data.CARTES[cid]["nom"][:80], style=discord.ButtonStyle.primary if cid in ids else discord.ButtonStyle.secondary)
            b.callback = self.poser(cid)
            self.add_item(b)

    def poser(self, cid):
        async def clic(i):
            db.sauver_item(i.guild_id, i.user.id, self.item, self.niveau, cid)
            await i.response.edit_message(embed=discord.Embed(color=0x2F855A, description=f"✅ **{data.ITEMS[self.item][0]}** est équipé sur "
                                          f"**{data.CARTES[cid]['nom']}**. Retourne à la tour pour continuer."), view=None)
        return clic


AUTO_MAX = 30   # étages enchaînés au plus par montée automatique


async def monter_auto(i, remplacer=False):
    """Montée automatique : enchaîne les étages sans animation jusqu'à la première défaite, et s'arrête avant chaque boss."""
    p = await charger(i)
    if not p:
        return
    repondre = i.response.edit_message if remplacer else i.response.send_message
    extra = {"embed": None, "view": None, "attachments": []} if remplacer else {"ephemeral": True}
    offre = offre_item(p)
    if offre:
        if remplacer:
            await i.response.edit_message(content=None, embed=embed_offre(offre), view=ChoixItem(offre), attachments=[])
        else:
            await i.response.send_message(embed=embed_offre(offre), view=ChoixItem(offre), ephemeral=True)
        return
    possedees = db.cartes(i.guild_id, i.user.id)
    ids = equipe_ids(p, possedees)
    if not ids:
        return await repondre(content="Ton équipe est vide. Compose-la dans le salon de la collection.", **extra)
    if p["etage"] >= data.TOUR_MAX:
        return await repondre(content=f"🏆 Tu as vaincu les {data.TOUR_MAX} étages de la tour.", **extra)
    if combat.est_boss(p["etage"] + 1):
        return await repondre(content=f"👹 L'étage {p['etage'] + 1} est un **boss** : la montée automatique s'arrête toujours avant. "
                                      "Vérifie ton équipe, puis affronte-le avec **Combattre**.", **extra)
    depart, golds_total, xp_total, packs, montees, niveaux, cartes = p["etage"], 0, 0, [], {}, [], []
    arret, defaite = "", None
    while True:
        etage = p["etage"] + 1
        if etage > data.TOUR_MAX:
            arret = "🏆 Tu es au sommet de la tour."
            break
        if combat.est_boss(etage):
            arret = f"👹 Arrêt avant le **boss de l'étage {etage}** : vérifie ton équipe, puis affronte-le avec **Combattre**."
            break
        if etage - depart > AUTO_MAX:
            arret = f"⏸️ {AUTO_MAX} étages d'un coup : relance la montée pour continuer."
            break
        if offre_item(p):
            arret = "🎁 Un item t'attend : appuie sur **Étage suivant** pour le choisir."
            break
        victoire, tours = combat.simuler_detail(combat.equipe_joueur(ids, possedees), combat.ennemis(etage), hemorragie=etage > 100)
        noter_combat(p, "tour", etage, victoire, len(tours), tours[-1]["etat"], possedees)
        if not victoire:
            defaite = (etage, tours)
            break
        golds = int((data.TOUR_GOLDS[0] + data.TOUR_GOLDS[1] * etage) * bonus_golds(ids, possedees))
        xp = data.TOUR_XP[0] + data.TOUR_XP[1] * etage
        p["etage"] = etage
        p["golds"] += golds
        golds_total, xp_total = golds_total + golds, xp_total + xp
        if etage % data.TOUR_PACK_SR == 0:   # pack de palier (les boss ne sont jamais joués en automatique)
            cid = combat.tirer(p, taux=data.TAUX_BOSS)
            c = data.CARTES[cid]
            packs.append((cid, f"Étage {etage} · {data.EMOJIS[c['rarete']]} **{c['nom']}** · {donner(p, cid)}"))
            cartes.append(cid)
        for cid in ids:
            if combat.gagner_xp(cid, possedees[cid], xp):
                montees[cid] = possedees[cid]["niveau"]
            db.sauver_carte(i.guild_id, i.user.id, cid, possedees[cid]["niveau"], possedees[cid]["xp"], possedees[cid]["etoiles"])
        part = 1.0
        if etage >= data.TOUR_XP_COMPTE[2]:
            part = data.TOUR_XP_COMPTE[0] ** (min(etage, 100) - data.TOUR_XP_COMPTE[2])
        lignes, _ = gagner_xp_compte(p, "tour", part)
        niveaux += lignes
        db.sauver(p)
    gagnes = p["etage"] - depart
    texte = f"# ⏩ Montée automatique\n## {'Étage ' + str(depart + 1) + ' → ' + str(p['etage']) if gagnes else 'Aucun étage gagné'}"
    if gagnes:
        texte += f" · {gagnes} étage{'s' if gagnes > 1 else ''}\n💰 **+{golds_total} golds** · ✨ **+{xp_total} XP** par carte"
        if montees:
            texte += "\n⬆️ " + ", ".join(f"{data.CARTES[c]['nom']} niv. {n}" for c, n in montees.items())
    e = discord.Embed(color=0xC53030 if defaite else 0x2F855A, description=texte)
    if packs:
        e.add_field(name=f"🎁 Packs de palier ({len(packs)})", value="\n".join(t for _, t in packs)[:1024], inline=False)
    if niveaux:
        e.add_field(name="⭐ Niveau de compte", value="\n".join(l.split("\n")[0] for l in niveaux)[:1024], inline=False)
    vue = Suite()
    if defaite:
        etage, tours = defaite
        ennemis = [u for u in tours[-1]["etat"] if u["camp"] == 1]
        reste = 100 * sum(u["pv"] for u in ennemis) // max(1, sum(u["pvmax"] for u in ennemis))
        e.add_field(name=f"💀 Défaite à l'étage {etage}", inline=False,
                    value=f"Combat de {len(tours)} tours ; il restait **{reste} %** de PV aux ennemis.\n" + "\n".join(conseils_defaite(p, possedees, ids)))
        vue = Revanche()
    else:
        e.add_field(name="Arrêt", value=arret, inline=False)
    e.set_footer(text=f"{p['golds']} golds · prochain étage : {p['etage'] + 1}")
    meilleur = max(cartes, key=lambda c: data.RARETES.index(data.CARTES[c]["rarete"]), default=None)
    image = image_carte(meilleur) if meilleur else None
    if image:
        e.set_thumbnail(url=f"attachment://{image}")
    if remplacer:
        await i.response.edit_message(content=None, embed=e, view=vue, attachments=joindre(image))
    else:
        await i.response.send_message(embed=e, view=vue, files=joindre(image), ephemeral=True)
    if cartes:
        await annoncer(i.guild, i.user, cartes)


class Suite(discord.ui.View):
    """Boutons affichés après une victoire."""
    def __init__(self):
        super().__init__(timeout=600)

    @discord.ui.button(label="Étage suivant", emoji="⚔️", style=discord.ButtonStyle.danger)
    async def suivant(self, i, _):
        await combattre(i, remplacer=True)

    @discord.ui.button(label="Suivant, sans animation", emoji="⏩", style=discord.ButtonStyle.secondary)
    async def rapide(self, i, _):
        await combattre(i, remplacer=True, rapide=True)

    @discord.ui.button(label="Monter en automatique", emoji="🚀", style=discord.ButtonStyle.primary)
    async def auto(self, i, _):
        await monter_auto(i, remplacer=True)


async def composer_meilleure_equipe(i):
    """Place les trois cartes les plus puissantes dans l'équipe. Renvoie (joueur, cartes possédées) ou None."""
    p = await charger(i)
    if not p:
        return None
    possedees = db.cartes(i.guild_id, i.user.id)
    p["equipe"] = ",".join(combat.meilleure_equipe(possedees))
    db.sauver(p)
    return p, possedees


class Revanche(discord.ui.View):
    """Boutons affichés après une défaite."""
    def __init__(self, proposer=False):
        super().__init__(timeout=600)
        if not proposer:
            self.remove_item(self.meilleure)

    @discord.ui.button(label="Meilleure équipe et retenter", emoji="⭐", style=discord.ButtonStyle.success)
    async def meilleure(self, i, _):
        p = db.get_joueur(i.guild_id, i.user.id)
        if p:
            possedees = db.cartes(i.guild_id, i.user.id)
            p["equipe"] = ",".join(combat.meilleure_equipe(possedees))
            db.sauver(p)
        await combattre(i, remplacer=True)

    @discord.ui.button(label="Retenter", emoji="🔁", style=discord.ButtonStyle.secondary)
    async def retenter(self, i, _):
        await combattre(i, remplacer=True)


class PanneauTour(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Combattre", emoji="⚔️", style=discord.ButtonStyle.danger, custom_id="f:combat")
    async def combat(self, i, _):
        await combattre(i)

    @discord.ui.button(label="Monter en automatique", emoji="🚀", style=discord.ButtonStyle.primary, custom_id="f:tour_auto")
    async def auto(self, i, _):
        await monter_auto(i)

    @discord.ui.button(label="Entraînement", emoji="🎯", style=discord.ButtonStyle.secondary, custom_id="f:tour_entrainement")
    async def entrainement(self, i, _):
        p = await charger(i)
        if not p:
            return
        if p["etage"] < 1:
            return await i.response.send_message("L'entraînement s'ouvre dès que tu as vaincu le premier étage de la tour.", ephemeral=True)
        await i.response.send_modal(ChoixEtage(p["etage"]))

    @discord.ui.button(label="Voir l'étage", emoji="👁️", style=discord.ButtonStyle.secondary, custom_id="f:etage")
    async def etage(self, i, _):
        p = await charger(i)
        if not p:
            return
        if p["etage"] >= data.TOUR_MAX:
            await i.response.send_message(f"🏆 Tu as vaincu les {data.TOUR_MAX} étages de la tour.", ephemeral=True)
            return
        n = p["etage"] + 1
        adv = combat.ennemis(n)
        possedees = db.cartes(i.guild_id, i.user.id)
        ids = equipe_ids(p, possedees)
        equipe = combat.equipe_joueur(ids, possedees)
        e = discord.Embed(color=COULEUR, description=f"# {'👹 Boss · ' if combat.est_boss(n) else '⚔️ '}Étage {n}\n## Aperçu avant le combat")
        e.add_field(name="Ton équipe", value="\n".join(f"**{u['nom']}** · ❤️ {u['pv']} · ⚔️ {u['atk']}" for u in equipe) or "Aucune carte.", inline=False)
        e.add_field(name="Ennemis", value="\n".join(f"**{u['nom']}** · ❤️ {u['pv']} · ⚔️ {u['atk']}" for u in adv), inline=False)
        force_toi, force_eux = sum(u["pv"] // 5 + u["atk"] * 2 for u in equipe), sum(u["pv"] // 5 + u["atk"] * 2 for u in adv)
        avis = "🟢 Tu as l'avantage." if force_toi > force_eux * 1.2 else "🔴 Ça s'annonce difficile." if force_toi < force_eux * 0.8 else "🟡 Combat serré."
        e.add_field(name="Rapport de force", value=f"Toi {force_toi} · Eux {force_eux}\n{avis}", inline=False)
        if combat.est_boss(n):
            e.add_field(name="👹 Ce boss", value=combat.texte_boss(n), inline=False)
        if n > 100:
            e.add_field(name="🩸 Hémorragie", value=f"Dans la tour difficile, tous les soins sont réduits à {data.HEMORRAGIE} % (les boucliers ne changent pas).", inline=False)
            e.set_footer(text="Les boss ne peuvent être ni étourdis, ni aveuglés, ni exécutés. En battre un offre "
                              + ("un pack avec un SSR garanti." if n == data.TOUR_SSR_GARANTI else "un pack à taux doublés."))
        await i.response.send_message(embed=e, ephemeral=True)


def ouvrir_coffre_hextech(p, cartes):
    """Le coffre hextech, très rare dans la jungle : des composants, un pack à taux doublés, ou (plus rare encore) un pack Worlds.
    cartes : liste où ajouter une carte tirée, pour l'annonce. Renvoie la ligne du journal."""
    genre = random.choices(list(data.COFFRE_HEXTECH_BUTIN), weights=list(data.COFFRE_HEXTECH_BUTIN.values()))[0]
    if genre == "pack_pro":
        p["packs_pro"] += 1
        return ("🧰 **Coffre hextech !** Il contient **un pack Worlds** 🏆. Ouvre-le dans le salon des Worlds"
                + ("." if db.worlds_equipes(p["guild_id"], p["user_id"]) else " dès que tu auras éliminé une première équipe."))
    if genre == "pack":
        trouvee = combat.tirer(p, taux=data.TAUX_BOSS)
        cartes.append(trouvee)
        c = data.CARTES[trouvee]
        return f"🧰 **Coffre hextech !** Un pack à taux doublés : {data.EMOJIS[c['rarete']]} **{c['nom']}** · {donner(p, trouvee)}"
    gagnes = {}
    for _ in range(data.COFFRE_HEXTECH_COMPOSANTS):
        c = random.choice(list(data.COMPOSANTS))
        gagnes[c] = gagnes.get(c, 0) + 1
    for c, q in gagnes.items():
        db.ajouter_composant(p["guild_id"], p["user_id"], c, q)
    return "🧰 **Coffre hextech !** Des composants : " + " · ".join(f"{data.COMPOSANTS[c][1]} {data.COMPOSANTS[c][0]} ×{q}" for c, q in gagnes.items())


# ---------------------------- Entraînement -----------------------------------
async def entrainement(i, etage, remplacer=False):
    """Rejoue un étage de la tour déjà vaincu, autant de fois qu'on veut, sans rien gagner ni perdre : pour essayer ses champions."""
    p = await charger(i)
    if not p:
        return
    repondre = i.response.edit_message if remplacer else i.response.send_message
    extra = {"embed": None, "view": None, "attachments": []} if remplacer else {"ephemeral": True}
    possedees = db.cartes(i.guild_id, i.user.id)
    ids = equipe_ids(p, possedees)
    if not ids:
        return await repondre(content="Ton équipe est vide. Compose-la dans le salon de la collection.", **extra)
    if p["etage"] < 1:
        return await repondre(content="L'entraînement s'ouvre dès que tu as vaincu le premier étage de la tour.", **extra)
    if not 1 <= etage <= p["etage"]:
        return await repondre(content=f"Choisis un étage que tu as déjà vaincu : de 1 à {p['etage']}.", **extra)
    equipe, adversaires = combat.equipe_joueur(ids, possedees), combat.ennemis(etage)
    victoire, tours = combat.simuler_detail(equipe, adversaires, hemorragie=etage > 100)
    etat = tours[-1]["etat"]
    moments = [l for t in tours for l in t["journal"] if not l.startswith("💫")]
    e = embed_combat(f"🎯 Entraînement · étage {etage}" + (" (boss)" if combat.est_boss(etage) else ""),
                     f"{'🏆 Victoire' if victoire else '💀 Défaite'} en {len(tours)} tours", etat, moments[-4:], 0x2F855A if victoire else 0xC53030)
    miens = [u for u in etat if u["camp"] == 0]
    total = sum(u.get("inflige", 0) for u in miens) or 1
    e.add_field(name="Dégâts de tes champions", inline=False, value="\n".join(
        f"**{u['nom']}** · {u.get('inflige', 0)} ({100 * u.get('inflige', 0) // total} %)" for u in sorted(miens, key=lambda u: -u.get("inflige", 0))))
    e.set_footer(text=f"Entraînement : aucun gain, aucune perte, autant de fois que tu veux · étages ouverts : 1 à {p['etage']}")
    fichiers = illustrer(e, None, ennemi_illustre(etat))
    vue = VueEntrainement(etage, p["etage"])
    if remplacer:
        await i.response.edit_message(content=None, embed=e, view=vue, attachments=fichiers)
    else:
        await i.response.send_message(embed=e, view=vue, files=fichiers, ephemeral=True)


class ChoixEtage(discord.ui.Modal, title="Entraînement"):
    etage = discord.ui.TextInput(label="Étage de la tour à rejouer", placeholder="Un étage que tu as déjà vaincu", min_length=1, max_length=3)

    def __init__(self, maximum, remplacer=False):
        super().__init__()
        self.remplacer = remplacer
        self.etage.label = f"Étage à rejouer (de 1 à {maximum})"[:45]
        self.etage.default = str(maximum)

    async def on_submit(self, i):
        texte = self.etage.value.strip()
        if not texte.isdigit():
            return await i.response.send_message("Écris un numéro d'étage, par exemple 40.", ephemeral=True)
        await entrainement(i, int(texte), remplacer=self.remplacer)


class VueEntrainement(discord.ui.View):
    def __init__(self, etage, maximum):
        super().__init__(timeout=900)
        self.etage, self.maximum = etage, maximum

    @discord.ui.button(label="Rejouer cet étage", emoji="🔁", style=discord.ButtonStyle.success)
    async def rejouer(self, i, _):
        await entrainement(i, self.etage, remplacer=True)

    @discord.ui.button(label="Changer d'étage", emoji="🎯", style=discord.ButtonStyle.secondary)
    async def changer(self, i, _):
        await i.response.send_modal(ChoixEtage(self.maximum, remplacer=True))


# ------------------------------- Jungle --------------------------------------
def charges_max(p):
    """Stock maximum de charges de Châtiment : il grandit avec le niveau de compte."""
    return [nombre for niveau, nombre in data.CHARGES_PALIERS if p["niveau"] >= niveau][-1]


def delai_charge(p):
    """Secondes pour regagner une charge : de moins en moins avec les donjons défi gagnés."""
    return data.CHARGES_DELAI[min(p["totems"], len(data.CHARGES_DELAI) - 1)] * 60


def mise_max(p):
    """Charges jouables sur une seule carte : débloqué par les donjons défi."""
    return data.CHARGES_MISE[min(p["totems"], len(data.CHARGES_MISE) - 1)]


def charges(p):
    """Met à jour et renvoie les charges de Châtiment du joueur : elles reviennent toutes seules avec le temps."""
    maxi, delai = charges_max(p), delai_charge(p)
    if p["charges_moment"] <= 0:
        p["charges_moment"] = time.time()
    if p["charges"] < maxi:
        gagne = int((time.time() - p["charges_moment"]) // delai)
        if gagne > 0:
            p["charges"] = min(maxi, p["charges"] + gagne)
            p["charges_moment"] += gagne * delai
    else:
        p["charges_moment"] = time.time()
    return p["charges"]


def depenser_charges(p, nombre):
    if p["charges"] >= charges_max(p):
        p["charges_moment"] = time.time()   # la recharge démarre quand le stock n'est plus plein
    p["charges"] -= nombre


def texte_charges(p):
    c, maxi = charges(p), charges_max(p)
    if c >= maxi:
        return f"⚡ {c}/{maxi} charges"
    return f"⚡ {c}/{maxi} charges · +1 dans {duree(max(0, delai_charge(p) - (time.time() - p['charges_moment'])))}"


def delai_energie(p):
    return data.ENERGIE_DELAI


def texte_delai(secondes):
    h, m = int(secondes // 3600), int(secondes % 3600 // 60)
    return f"{h} h" + (f" {m:02d}" if m else "")


def energie(p):
    """Met à jour et renvoie l'énergie du joueur : elle remonte toute seule avec le temps."""
    maxi, delai = energie_max(p), delai_energie(p)
    if p["energie"] < maxi:
        gagne = int((time.time() - p["energie_moment"]) // delai)
        if gagne > 0:
            p["energie"] = min(maxi, p["energie"] + gagne)
            p["energie_moment"] += gagne * delai
    return p["energie"]


def texte_energie(p):
    e, maxi = energie(p), energie_max(p)
    if e >= maxi:
        return f"⚡ {e}/{maxi}"
    return f"⚡ {e}/{maxi} · +1 dans {duree(max(0, delai_energie(p) - (time.time() - p['energie_moment'])))}"


def chasses_groupees(p):
    """Tailles de chasse groupée déjà débloquées par le joueur (5, 10…)."""
    return [fois for fois, camps in data.JUNGLE_MULTI if p["chasses"] >= camps]


async def chasser(i, difficulte, remplacer=False, fois=1):
    """Un combat dans la jungle : le farm d'XP et de golds. Coûte 1 énergie par chasse, seulement en cas de victoire.
    fois : chasse groupée (5 ou 10 d'un coup), débloquée après assez de camps nettoyés."""
    p = await charger(i)
    if not p:
        return
    if await verrouille(i, p, "jungle"):
        return
    nom, minimum, _, mult = data.JUNGLE[difficulte]
    repondre = i.response.edit_message if remplacer else i.response.send_message
    extra = {"embed": None, "view": None, "attachments": []} if remplacer else {"ephemeral": True}
    if p["etage"] < minimum:
        await repondre(content=f"🔒 La jungle **{nom}** se débloque à l'étage {minimum} de la tour (tu es à l'étage {p['etage']}).", **extra)
        return
    if fois > 1 and fois not in chasses_groupees(p):
        camps = dict(data.JUNGLE_MULTI).get(fois, 0)
        await repondre(content=f"🔒 La chasse ×{fois} se débloque après {camps} camps nettoyés (tu en es à {p['chasses']}).", **extra)
        return
    if energie(p) <= 0:
        db.sauver(p)
        await repondre(content=f"Tu n'as plus d'énergie. {texte_energie(p)}\nEn attendant : la tour ne coûte rien, et ton expédition continue de rapporter.", **extra)
        return
    if energie(p) < fois:
        db.sauver(p)
        await repondre(content=f"Il te faut {fois} ⚡ pour une chasse ×{fois}. {texte_energie(p)}", **extra)
        return
    possedees = db.cartes(i.guild_id, i.user.id)
    ids = equipe_ids(p, possedees)
    if not ids:
        await repondre(content="Ton équipe est vide. Compose-la dans le salon de la collection.", **extra)
        return
    niveau = combat.niveau_jungle(p["etage"], difficulte)
    victoire, tours = combat.simuler_detail(combat.equipe_joueur(ids, possedees), combat.monstres(niveau))
    noter_combat(p, "jungle", niveau, victoire, len(tours), tours[-1]["etat"], possedees)
    moments = [l for t in tours for l in t["journal"] if not l.startswith("💫")]
    e = embed_combat("🌿 Jungle" + (f" ×{fois}" if fois > 1 else ""), f"{'🏆 Victoire' if victoire else '💀 Défaite'} en {len(tours)} tours", tours[-1]["etat"], moments[-4:],
                     0x2F855A if victoire else 0xC53030)
    trouvee, cartes_niveau = None, []
    if victoire:
        if p["energie"] >= energie_max(p):
            p["energie_moment"] = time.time()   # la recharge démarre quand la barre n'est plus pleine
        p["energie"] -= fois
        p["chasses"] += fois
        xp = int((data.JUNGLE_XP[0] + data.JUNGLE_XP[1] * p["etage"]) * mult) * fois
        golds = int((data.JUNGLE_GOLDS[0] + data.JUNGLE_GOLDS[1] * p["etage"]) * mult) * fois
        p["golds"] += golds
        montees = []
        for cid in ids:
            if combat.gagner_xp(cid, possedees[cid], xp):
                montees.append(f"{data.CARTES[cid]['nom']} niv. {possedees[cid]['niveau']}")
            db.sauver_carte(i.guild_id, i.user.id, cid, possedees[cid]["niveau"], possedees[cid]["xp"], possedees[cid]["etoiles"])
        butin = f"✨ +{xp} XP par carte · 💰 +{golds} golds" + (f"\n⬆️ {', '.join(montees)}" if montees else "")
        for taille, camps in data.JUNGLE_MULTI:   # annonce d'un déblocage, ou rappel du prochain palier
            if camps and p["chasses"] - fois < camps <= p["chasses"]:
                butin += f"\n🔓 **{camps} camps nettoyés** : tu débloques la chasse **×{taille}** !"
        e.add_field(name="Butin", inline=False, value=butin)
        cartes_niveau = champ_compte(p, e, "jungle", fois)
        trouvees = [combat.tirer(p, gratuit=True) for _ in range(fois) if random.random() * 100 < data.JUNGLE_CHANCE_PACK]
        if trouvees:
            trouvee = max(trouvees, key=lambda c: data.RARETES.index(data.CARTES[c]["rarete"]))   # la plus rare est mise en avant
            cartes_niveau = [c for c in trouvees if c is not trouvee] + cartes_niveau
            e.add_field(name="🎁 Un pack traînait dans les buissons !" if len(trouvees) == 1 else f"🎁 {len(trouvees)} packs traînaient dans les buissons !",
                        inline=False, value="\n".join(f"{data.EMOJIS[data.CARTES[c]['rarete']]} **{data.CARTES[c]['nom']}** · "
                                                      f"{data.CARTES[c]['rarete']} · {donner(p, c)}" for c in trouvees)[:1024])
    else:
        e.add_field(name="Les monstres ont gagné", value="Aucune énergie dépensée. Renforce ton équipe ou change de composition.", inline=False)
    db.sauver(p)
    e.set_footer(text=f"{texte_energie(p)} · {p['golds']} golds")
    gagnee = trouvee or (cartes_niveau[0] if cartes_niveau else None)
    fichiers = illustrer(e, None, ennemi_illustre(tours[-1]["etat"]), recompense=gagnee)
    ouverture, pieces = embed_ouverture(gagnee, "🎁 Tu as gagné un pack ! Il s'ouvre…") if gagnee else (None, [])
    if ouverture:
        if remplacer:
            await i.response.edit_message(content=None, embed=ouverture, view=None, attachments=pieces)
        else:
            await i.response.send_message(embed=ouverture, files=pieces, ephemeral=True)
        try:
            await asyncio.sleep(DUREE_OUVERTURE)
            await editer(i, embed=e, view=EncoreJungle(difficulte, p), attachments=fichiers)
        except ERREURS_RESEAU:
            pass
    elif remplacer:
        await i.response.edit_message(content=None, embed=e, view=EncoreJungle(difficulte, p), attachments=fichiers)
    else:
        await i.response.send_message(embed=e, view=EncoreJungle(difficulte, p), files=fichiers, ephemeral=True)
    if trouvee or cartes_niveau:
        await annoncer(i.guild, i.user, ([trouvee] if trouvee else []) + cartes_niveau)


# --------------------------- Exploration de la jungle -------------------------
class Exploration(discord.ui.View):
    """Une carte de 16 buissons, payée d'avance en charges de Châtiment (mise). Fouiller est gratuit et donne tout de suite son butin.
    Chaque buisson fouillé indique le nombre de ganks cachés autour de lui (comme au démineur). Au 2e gank, la carte est finie."""
    COTE = 4

    def __init__(self, p, ids, mise=1):
        super().__init__(timeout=900)
        self.g, self.u, self.ids, self.etage = p["guild_id"], p["user_id"], ids, min(p["etage"], 100)   # le butin ne suit pas la tour difficile
        self.mise, self.mult = mise, data.JUNGLE_BUTIN * mise
        self.xp, self.golds, self.fini, self.pris, self.pourcent = 0, 0, False, None, 100
        self.bonus = max([b for c, b in data.EXPLO_BONUS if p["chasses"] >= c] or [0])
        buff = buff_actif(p["guild_id"])
        if buff and buff["stat"] == "jungle":   # buff du Baron Nashor
            self.bonus += buff["valeur"]
        self.journal = ["Choisis un buisson à fouiller."]
        self.nouvelle_carte(p)
        self.dessiner()

    def nouvelle_carte(self, p):
        """Tire une carte : le contenu des 16 buissons."""
        contenu = [cle for cle, nombre in data.EXPLO_CASES for _ in range(nombre)]
        contenu += ["vide"] * (self.COTE ** 2 - len(contenu))
        if "vide" in contenu and random.random() * 100 < data.COFFRE_HEXTECH_CHANCE:   # très rare : un coffre hextech caché sur la carte
            contenu[contenu.index("vide")] = "coffre"
        random.shuffle(contenu)
        self.cases = contenu[:self.COTE ** 2]
        self.prix = [0] * len(self.cases)
        self.payes = {}
        self.vues, self.reperes, self.vies = set(), set(), data.EXPLO_VIES
        self.carte_xp, self.carte_golds = 0, 0   # butin ramassé sur cette carte, pour le bonus de clear complet

    # -- la carte --
    def voisins(self, k):
        x, y = k % self.COTE, k // self.COTE
        return [yy * self.COTE + xx for xx in range(x - 1, x + 2) for yy in range(y - 1, y + 2)
                if 0 <= xx < self.COTE and 0 <= yy < self.COTE and (xx, yy) != (x, y)]

    def ganks_autour(self, k):
        """Ganks encore cachés autour d'un buisson (ceux déjà tombés ne comptent plus)."""
        return sum(1 for v in self.voisins(k) if self.cases[v] == "gank" and v not in self.vues)

    def bouger_ganks(self):
        """Après chaque fouille, chaque gank caché se glisse dans un buisson voisin encore caché. Les chiffres affichés suivent."""
        caches = [k for k in range(len(self.cases)) if self.cases[k] == "gank" and k not in self.vues]
        random.shuffle(caches)
        for k in caches:
            libres = [v for v in self.voisins(k) if v not in self.vues and self.cases[v] != "gank"]
            if not libres:
                continue
            v = random.choice(libres)
            self.cases[k], self.cases[v] = self.cases[v], self.cases[k]
            self.prix[k], self.prix[v] = self.prix[v], self.prix[k]
            if k in self.reperes:   # un gank repéré par une balise reste suivi
                self.reperes.discard(k)
                self.reperes.add(v)

    def suite(self, p):
        """Après une fouille : retour à la base au 2e gank, bonus de clear complet, puis déplacement des ganks."""
        caches = [k for k in range(len(self.cases)) if k not in self.vues]
        if self.vies <= 0:
            self.terminer(f"💀 **{data.EXPLO_VIES} ganks : ton équipe rentre à la base.** Le butin ramassé est gardé.")
        elif all(self.cases[k] == "gank" for k in caches):   # il ne reste que des ganks : clear complet
            xp, golds = int(self.carte_xp * data.EXPLO_CLEAR / 100), int(self.carte_golds * data.EXPLO_CLEAR / 100)
            if xp:
                possedees = db.cartes(self.g, self.u)
                for cid in self.ids:
                    if cid in possedees:
                        combat.gagner_xp(cid, possedees[cid], xp)
                        db.sauver_carte(self.g, self.u, cid, possedees[cid]["niveau"], possedees[cid]["xp"], possedees[cid]["etoiles"])
            p["golds"] += golds
            self.xp, self.golds = self.xp + xp, self.golds + golds
            self.terminer(f"🏆 **Clear complet !** Il ne restait que des ganks : +{data.EXPLO_CLEAR} % du butin de la carte (✨ +{xp} XP par carte · 💰 +{golds} golds).")
        elif len(self.vues) >= 2:   # ils restent immobiles après le tout premier buisson, pour laisser un premier indice fiable
            self.bouger_ganks()

    def dessiner(self):
        self.clear_items()
        for k, cle in enumerate(self.cases):
            if k in self.vues:
                bouton = discord.ui.Button(label=str(self.ganks_autour(k)), emoji=data.EXPLO_EMOJIS[cle], disabled=True, row=k // self.COTE,
                                           style=discord.ButtonStyle.danger if cle == "gank" else discord.ButtonStyle.secondary)
            else:
                repere = k in self.reperes
                bouton = discord.ui.Button(emoji="⚠️" if repere else "🌿", row=k // self.COTE, disabled=self.fini,
                                           style=discord.ButtonStyle.danger if repere else discord.ButtonStyle.success)
                bouton.callback = self.fouiller(k)
            self.add_item(bouton)
        if not self.fini:
            sortie = discord.ui.Button(label="Rentrer à la base", emoji="🏠", style=discord.ButtonStyle.primary, row=4)
            sortie.callback = self.rentrer
            self.add_item(sortie)
        else:
            encore = discord.ui.Button(label="Nouvelle carte", emoji="🗺️", style=discord.ButtonStyle.primary, row=4)
            encore.callback = self.recommencer
            self.add_item(encore)

    def embed(self, p):
        restants = self.COTE ** 2 - len(self.vues)
        e = discord.Embed(color=0x2F855A if self.vies else 0xC53030, description=(
            f"# 🗺️ Exploration de la jungle\n## Ganks : {'⚔️' * (data.EXPLO_VIES - self.vies)}{'▫️' * self.vies} · {texte_charges(p)}\n"
            + (f"**Mise : {self.mise} charges, butin ×{self.mise}.**\n" if self.mise > 1 else "")
            + "\n".join(self.journal[-3:])))
        e.add_field(name="Butin de cette carte", value=f"✨ +{self.xp} XP par carte · 💰 +{self.golds} golds", inline=False)
        e.set_footer(text=f"Le chiffre d'un buisson fouillé = le nombre de ganks ⚔️ encore cachés autour de lui (un gank découvert ne compte plus) · {restants} buisson(s) restant(s)"
                          + (f" · butin +{self.bonus} %" if self.bonus else "") + "\n"
                          f"Dès ton 2e buisson, les ganks se déplacent d'une case après chaque fouille : les chiffres changent · au {data.EXPLO_VIES}e gank, ton équipe rentre et la carte est finie · "
                          f"s'il ne reste que des ganks : clear complet, +{data.EXPLO_CLEAR} % de butin\n"
                          "Fouiller ne coûte rien : la carte est payée par ta charge · "
                          "🐺 camp · 🔵🔴 gros monstre (Châtiment) · 💰 trésor · 🍯 fruit (efface un gank) · 🍃 rien · ton premier buisson n'est jamais un gank")
        return e

    # -- butin, versé tout de suite --
    def verser(self, p, chasses_xp=0.0, chasses_golds=0.0):
        plus = 1 + self.bonus / 100
        xp = int((data.JUNGLE_XP[0] + data.JUNGLE_XP[1] * self.etage) * chasses_xp * plus)
        golds = int((data.JUNGLE_GOLDS[0] + data.JUNGLE_GOLDS[1] * self.etage) * chasses_golds * plus * bonus_golds(self.ids, db.cartes(self.g, self.u)))
        montees = []
        if xp:
            possedees = db.cartes(self.g, self.u)
            for cid in self.ids:
                if cid in possedees:
                    if combat.gagner_xp(cid, possedees[cid], xp):
                        montees.append(f"{data.CARTES[cid]['nom']} niv. {possedees[cid]['niveau']}")
                    db.sauver_carte(self.g, self.u, cid, possedees[cid]["niveau"], possedees[cid]["xp"], possedees[cid]["etoiles"])
        p["golds"] += golds
        self.xp, self.golds = self.xp + xp, self.golds + golds
        self.carte_xp, self.carte_golds = self.carte_xp + xp, self.carte_golds + golds
        texte = " · ".join(t for t in (f"✨ +{xp} XP par carte" if xp else "", f"💰 +{golds} golds" if golds else "") if t)
        return texte + (f" · ⬆️ {', '.join(montees)}" if montees else "")

    def fouiller(self, k):
        async def clic(i):
            p = await charger(i)
            if not p:
                return
            if self.fini or k in self.vues:
                await i.response.edit_message(embed=self.embed(p), view=self)
                return
            if not self.vues and self.cases[k] == "gank":   # premier buisson d'une carte : jamais un gank, il est échangé avec un autre
                autres = [v for v in range(len(self.cases)) if self.cases[v] != "gank"]
                v = random.choice(autres)
                self.cases[k], self.cases[v] = self.cases[v], self.cases[k]
                self.prix[k], self.prix[v] = self.prix[v], self.prix[k]
            cle = self.cases[k]
            cout = self.mult
            self.vues.add(k)
            self.reperes.discard(k)
            cartes = []
            prix = ""
            lignes, cartes_niveau = gagner_xp_compte(p, "jungle", self.mise) if cle in ("camp", "tresor", "bleu", "rouge") else ([], [])
            if cle == "camp":
                p["chasses"] += 1
                nom = random.choice(data.JUNGLE_MONSTRES[:4])
                self.journal.append(f"🐺 **{nom}** {prix} : camp nettoyé. {self.verser(p, data.EXPLO_CAMP * cout, data.EXPLO_CAMP * cout)}")
                for _ in range(self.mise):
                    if random.random() * 100 < data.JUNGLE_CHANCE_PACK:
                        trouvee = combat.tirer(p, gratuit=True)
                        cartes.append(trouvee)
                        c = data.CARTES[trouvee]
                        self.journal.append(f"🎁 Un pack traînait dans le buisson : {data.EMOJIS[c['rarete']]} **{c['nom']}** · {donner(p, trouvee)}")
            elif cle == "tresor":
                self.journal.append(f"💰 **Un trésor oublié !** {prix} {self.verser(p, 0, data.EXPLO_TRESOR * cout)}")
            elif cle == "gank":
                self.vies -= 1
                self.journal.append("⚔️ **Gank !** Un jungler ennemi t'attendait." + (f" Encore {self.vies} et ton équipe rentre à la base." if self.vies else ""))
            elif cle == "fruit":
                gagne = self.vies < data.EXPLO_VIES
                self.vies = min(data.EXPLO_VIES, self.vies + 1)
                self.journal.append("🍯 **Fruit de miel** : " + ("un gank est effacé." if gagne else "aucun gank à effacer."))
            elif cle == "balise":
                caches = [c for c in range(len(self.cases)) if self.cases[c] == "gank" and c not in self.vues and c not in self.reperes]
                trouves = random.sample(caches, min(2, len(caches)))
                self.reperes.update(trouves)
                self.journal.append(f"👁️ **Balise de vision** : {len(trouves)} gank(s) repéré(s), marqué(s) ⚠️ sur la carte." if trouves
                                    else "👁️ **Balise de vision** : plus aucun gank caché.")
            elif cle == "coffre":
                self.journal.append(ouvrir_coffre_hextech(p, cartes))
            elif cle == "vide":
                self.journal.append("🍃 Rien dans ce buisson.")
            for ligne in lignes:
                self.journal.append("⭐ " + ligne.replace("\n", " · "))
            if cle in ("bleu", "rouge"):   # gros monstre : place au Châtiment
                p["chasses"] += 1
                db.sauver(p)
                await self.chatiment(i, cle, cout)
                if cartes_niveau:
                    await annoncer(i.guild, i.user, cartes_niveau)
                return
            self.suite(p)
            db.sauver(p)
            self.dessiner()
            await i.response.edit_message(embed=self.embed(p), view=self)
            if cartes or cartes_niveau:
                await annoncer(i.guild, i.user, cartes + cartes_niveau)
        return clic

    def terminer(self, texte):
        self.fini = True
        self.journal.append(texte)
        self.dessiner()

    async def rentrer(self, i):
        p = await charger(i)
        if not p:
            return
        self.terminer("🏠 Ton équipe rentre à la base, butin en poche.")
        await i.response.edit_message(embed=self.embed(p), view=self)

    async def recommencer(self, i):
        await ouvrir_exploration(i, remplacer=True)

    # -- Châtiment sur un gros monstre --
    def embed_chatiment(self, nom):
        plein = max(0, round(self.pourcent / 5))
        return discord.Embed(color=0xD69E2E, description=f"# ⚡ Châtiment !\n## {nom} · {self.pourcent} % de PV\n{'🟥' * plein}{'⬛' * (20 - plein)}\n\n"
                             f"Appuie sur **Châtiment** quand il lui reste **moins de {data.CLEAR_FENETRE} %** de PV. Trop tôt, c'est raté. Un seul essai.")

    async def appuyer(self, i):
        if self.pris is None:
            self.pris = self.pourcent
        await i.response.defer()

    async def chatiment(self, i, cle, cout=None):
        cout = cout or self.mult
        nom = "Sentinelle bleue" if cle == "bleu" else "Roncier rouge"
        paliers, rythme = data.EXPLO_CHATIMENT[cle]
        self.pris, self.pourcent = None, paliers[0]
        self.clear_items()
        bouton = discord.ui.Button(label="Châtiment", emoji="⚡", style=discord.ButtonStyle.danger)
        bouton.callback = self.appuyer
        self.add_item(bouton)
        await i.response.edit_message(embed=self.embed_chatiment(nom), view=self)
        try:
            for pourcent in paliers[1:]:
                await asyncio.sleep(rythme)
                if self.pris is not None:
                    break
                self.pourcent = pourcent
                await editer(i, embed=self.embed_chatiment(nom), view=self)
            if self.pris is None:
                await asyncio.sleep(rythme)
        except ERREURS_RESEAU:
            pass
        reussi = self.pris is not None and self.pris <= data.CLEAR_FENETRE
        p = db.get_joueur(self.g, self.u)
        part = (data.EXPLO_GROS[0] if reussi else data.EXPLO_GROS[1]) * cout
        butin = self.verser(p, part, part)
        if reussi:
            self.journal.append(f"⚡ **Châtiment réussi sur {nom}** (à {self.pris} % de PV) ! {butin}")
        elif self.pris is None:
            self.journal.append(f"{data.EXPLO_EMOJIS[cle]} **{nom}** vaincu sans Châtiment : petit butin. {butin}")
        else:
            self.journal.append(f"{data.EXPLO_EMOJIS[cle]} **{nom}** : Châtiment trop tôt (à {self.pris} % de PV), petit butin. {butin}")
        self.suite(p)
        db.sauver(p)
        self.dessiner()
        try:
            await editer(i, embed=self.embed(p), view=self)
        except ERREURS_RESEAU:
            pass


def butin_clear_complet(p, mise=1):
    """Butin d'un clear complet parfait (tous les camps, Châtiments réussis, trésors, bonus de clear) : (XP par carte, golds)."""
    nombre = dict(data.EXPLO_CASES)
    gros = nombre.get("bleu", 0) + nombre.get("rouge", 0)
    chasses_xp = nombre.get("camp", 0) * data.EXPLO_CAMP + gros * data.EXPLO_GROS[0]
    chasses_golds = chasses_xp + nombre.get("tresor", 0) * data.EXPLO_TRESOR
    plus = (1 + data.EXPLO_CLEAR / 100) * data.JUNGLE_BUTIN * mise
    etage = min(p["etage"], 100)
    return (int((data.JUNGLE_XP[0] + data.JUNGLE_XP[1] * etage) * chasses_xp * plus),
            int((data.JUNGLE_GOLDS[0] + data.JUNGLE_GOLDS[1] * etage) * chasses_golds * plus))


class ChoixMise(discord.ui.View):
    """Combien de charges jouer sur cette carte (débloqué par les donjons défi)."""
    def __init__(self, maximum, rapide):
        super().__init__(timeout=300)
        self.rapide = rapide
        for n in range(1, maximum + 1):
            b = discord.ui.Button(label=f"{n} charge{'s' if n > 1 else ''} · butin ×{n}", emoji="⚡",
                                  style=discord.ButtonStyle.success if n == 1 else discord.ButtonStyle.danger)
            b.callback = self.choisir(n)
            self.add_item(b)

    def choisir(self, n):
        async def clic(i):
            await (clear_rapide if self.rapide else ouvrir_exploration)(i, remplacer=True, mise=n)
        return clic


async def entree_jungle(i, remplacer, mise, rapide):
    """Vérifications communes à l'exploration et au clear rapide. Renvoie (joueur, équipe, mise) ou None si la réponse est déjà partie."""
    p = await charger(i)
    if not p:
        return None
    if await verrouille(i, p, "jungle"):
        return None
    repondre = i.response.edit_message if remplacer else i.response.send_message
    extra = {"embed": None, "view": None, "attachments": []} if remplacer else {"ephemeral": True}
    c = charges(p)
    db.sauver(p)
    if c <= 0:
        await repondre(content=f"Tu n'as plus de charge de Châtiment. {texte_charges(p)}\nEn attendant : la tour et les donjons ne coûtent rien.", **extra)
        return None
    ids = equipe_ids(p, db.cartes(i.guild_id, i.user.id))
    if not ids:
        await repondre(content="Ton équipe est vide. Compose-la dans le salon de la collection.", **extra)
        return None
    maximum = min(c, mise_max(p))
    if mise is None and maximum > 1:
        xp, golds = butin_clear_complet(p)
        part = data.CLEAR_RAPIDE / 100 if rapide else 1
        await repondre(content=f"## ⚡ Combien de charges sur cette carte ?\n{texte_charges(p)}\n"
                       f"Une charge rapporte jusqu'à ✨ {int(xp * part)} XP par carte et 💰 {int(golds * part)} golds. Miser plus multiplie le butin"
                       + ("." if rapide else f", mais **tout est perdu si tu sors au {data.EXPLO_VIES}e gank** trop tôt."),
                       **{**extra, "view": ChoixMise(maximum, rapide)})
        return None
    return p, ids, max(1, min(mise or 1, maximum))


async def ouvrir_exploration(i, remplacer=False, mise=None):
    pret = await entree_jungle(i, remplacer, mise, False)
    if not pret:
        return
    p, ids, mise = pret
    depenser_charges(p, mise)
    db.sauver(p)
    vue = Exploration(p, ids, mise)
    if remplacer:
        await i.response.edit_message(content=None, embed=vue.embed(p), view=vue, attachments=[])
    else:
        await i.response.send_message(embed=vue.embed(p), view=vue, ephemeral=True)


async def clear_rapide(i, remplacer=False, mise=None):
    """Dépense des charges sans jouer : une part du butin d'un clear complet, tout de suite."""
    pret = await entree_jungle(i, remplacer, mise, True)
    if not pret:
        return
    p, ids, mise = pret
    depenser_charges(p, mise)
    bonus = max([b for c, b in data.EXPLO_BONUS if p["chasses"] >= c] or [0])
    buff = buff_actif(p["guild_id"])
    if buff and buff["stat"] == "jungle":
        bonus += buff["valeur"]
    xp, golds = butin_clear_complet(p, mise)
    part = data.CLEAR_RAPIDE / 100 * (1 + bonus / 100)
    possedees, montees = db.cartes(i.guild_id, i.user.id), []
    xp, golds = int(xp * part), int(golds * part * bonus_golds(ids, possedees))
    for cid in ids:
        if cid in possedees:
            if combat.gagner_xp(cid, possedees[cid], xp):
                montees.append(f"{data.CARTES[cid]['nom']} niv. {possedees[cid]['niveau']}")
            db.sauver_carte(i.guild_id, i.user.id, cid, possedees[cid]["niveau"], possedees[cid]["xp"], possedees[cid]["etoiles"])
    p["golds"] += golds
    p["chasses"] += 4 * mise
    e = discord.Embed(color=0x2F855A, description=f"# ⏩ Clear rapide\n✨ **+{xp} XP** par carte · 💰 **+{golds} golds**"
                      + (f"\n⬆️ {', '.join(montees)}" if montees else "")
                      + f"\n\n{mise} charge{'s' if mise > 1 else ''} dépensée{'s' if mise > 1 else ''}. C'est {data.CLEAR_RAPIDE} % d'un clear complet : explorer toi-même rapporte jusqu'au double.")
    champ_compte(p, e, "jungle", 5 * mise)
    db.sauver(p)
    e.set_footer(text=texte_charges(p))
    repondre = i.response.edit_message if remplacer else i.response.send_message
    await repondre(content=None, embed=e, **({"view": None, "attachments": []} if remplacer else {"ephemeral": True}))


# ------------------------------- Donjons -------------------------------------
def donjons_restants(p):
    """Met à jour et renvoie la réserve de victoires de donjon : une revient toutes les DONJON_DELAI secondes, jusqu'à DONJON_STOCK."""
    maxi, delai = data.DONJON_STOCK, data.DONJON_DELAI
    if p.get("donjon_moment", 0) <= 0:
        p["donjon_moment"] = time.time()
    if p["donjon_stock"] < maxi:
        gagne = int((time.time() - p["donjon_moment"]) // delai)
        if gagne > 0:
            p["donjon_stock"] = min(maxi, p["donjon_stock"] + gagne)
            p["donjon_moment"] += gagne * delai
    else:
        p["donjon_moment"] = time.time()
    return p["donjon_stock"]


def texte_donjons(p):
    """« 3/5 victoires de donjon · prochaine dans 2 h 10 »."""
    n = donjons_restants(p)
    texte = f"{n}/{data.DONJON_STOCK} victoire{'s' if n > 1 else ''} de donjon en réserve"
    if n < data.DONJON_STOCK:
        texte += f" · prochaine dans {texte_delai(max(60, data.DONJON_DELAI - (time.time() - p['donjon_moment'])))}"
    return texte


async def explorer(i, numero, remplacer=False):
    """Un combat de donjon contre des champions gardiens. Une victoire rapporte des composants et consomme un essai du jour."""
    p = await charger(i)
    if not p:
        return
    if await verrouille(i, p, "donjons"):
        return
    nom, emoji, butin = data.DONJONS[numero]
    repondre = i.response.edit_message if remplacer else i.response.send_message
    extra = {"embed": None, "view": None, "attachments": []} if remplacer else {"ephemeral": True}
    if donjons_restants(p) <= 0:
        await repondre(content=f"Ta réserve de victoires de donjon est vide. {texte_donjons(p).split(' · ')[-1].capitalize()}. En attendant, la forge reste ouverte.", **extra)
        return
    possedees = db.cartes(i.guild_id, i.user.id)
    ids = equipe_ids(p, possedees)
    if not ids:
        await repondre(content="Ton équipe est vide. Compose-la dans le salon de la collection.", **extra)
        return
    victoire, tours = combat.simuler_detail(combat.equipe_joueur(ids, possedees), combat.gardiens_donjon(numero, p["etage"]), hemorragie=True)
    noter_combat(p, "donjon", numero, victoire, len(tours), tours[-1]["etat"], possedees)
    moments = [l for t in tours for l in t["journal"] if not l.startswith("💫")]
    e = embed_combat(f"{emoji} {nom}", f"{'🏆 Victoire' if victoire else '💀 Défaite'} en {len(tours)} tours", tours[-1]["etat"], moments[-4:],
                     0x2F855A if victoire else 0xC53030)
    cartes_niveau = []
    if victoire:
        if p["donjon_stock"] >= data.DONJON_STOCK:
            p["donjon_moment"] = time.time()   # la recharge démarre quand la réserve n'est plus pleine
        p["donjon_stock"] -= 1
        db.sauver(p)
        gagnes = {}
        for _ in range(data.DONJON_BUTIN + p["etage"] // data.DONJON_PALIER):
            c = random.choice(butin)
            gagnes[c] = gagnes.get(c, 0) + 1
        for c, q in gagnes.items():
            db.ajouter_composant(i.guild_id, i.user.id, c, q)
        e.add_field(name="Butin", inline=False, value=" · ".join(f"{data.COMPOSANTS[c][1]} **{data.COMPOSANTS[c][0]}** ×{q}" for c, q in gagnes.items()))
        cartes_niveau = champ_compte(p, e, "donjon")
        db.sauver(p)
    else:
        e.add_field(name="Les gardiens ont tenu", value="L'essai n'est pas décompté. Renforce ton équipe dans la jungle, ou change de composition.", inline=False)
    e.set_footer(text=f"{texte_donjons(p)} · 🩸 Hémorragie : soins réduits à {data.HEMORRAGIE} %")
    fichiers = illustrer(e, None, ennemi_illustre(tours[-1]["etat"]))
    vue = EncoreDonjon(numero) if donjons_restants(p) > 0 else None
    if remplacer:
        await i.response.edit_message(content=None, embed=e, view=vue, attachments=fichiers)
    elif vue:
        await i.response.send_message(embed=e, view=vue, files=fichiers, ephemeral=True)
    else:
        await i.response.send_message(embed=e, files=fichiers, ephemeral=True)
    if cartes_niveau:
        await annoncer(i.guild, i.user, cartes_niveau)


# ----------------------- Donjon de Noxus : la descente -------------------------
def cles(p):
    """Met à jour et renvoie les clés de donjon du joueur : il en gagne une toutes les quelques heures, jusqu'à un plafond."""
    if p["cles_moment"] <= 0:
        p["cles_moment"] = time.time()
    if p["cles"] < data.CLES_MAX:
        gagne = int((time.time() - p["cles_moment"]) // data.CLES_DELAI)
        if gagne > 0:
            p["cles"] = min(data.CLES_MAX, p["cles"] + gagne)
            p["cles_moment"] += gagne * data.CLES_DELAI
    else:
        p["cles_moment"] = time.time()
    return p["cles"]


def texte_cles(p):
    n = cles(p)
    if n >= data.CLES_MAX:
        return f"🗝️ {n}/{data.CLES_MAX} clés"
    return f"🗝️ {n}/{data.CLES_MAX} clés · +1 dans {duree(max(0, data.CLES_DELAI - (time.time() - p['cles_moment'])))}"


def indices_code(code, essai):
    """Réponse de la serrure : (sceaux bien placés, sceaux présents mais mal placés)."""
    bien = sum(a == b for a, b in zip(code, essai))
    return bien, len(set(code) & set(essai)) - bien


class Noxus(discord.ui.View):
    """Une descente dans l'Armurerie de Noxus : trouver le code de la serrure (chaque essai raté fait venir une vague de gardes),
    puis vaincre Darius et Swain, et ouvrir le coffre. L'équipe garde ses PV du début à la fin.
    Entrer est gratuit ; les clés ne servent qu'à ouvrir le coffre."""
    PLAN = ["darius", "boss"]

    def __init__(self, p, ids, possedees, numero=0):
        super().__init__(timeout=900)
        self.numero, self.d, self.nom, self.icone = numero, data.DESCENTES[numero], data.DONJONS[numero][0], data.DONJONS[numero][1]
        self.sceaux, self.fond = self.d["sceaux"], self.d["fond"]
        self.g, self.u, self.ids, self.possedees, self.etage = p["guild_id"], p["user_id"], ids, possedees, p["etage"]
        self.equipe = combat.equipe_joueur(ids, possedees)
        self.etape, self.fini = 0, False
        self.code = random.sample(self.sceaux, data.NOXUS["code"])
        self.essais, self.saisie, self.ecran, self.ouvert = [], [], None, False

    def etat(self, adversaires=()):
        return combat.photo(self.equipe + list(adversaires))

    def butin(self):
        return max(1, round((data.DONJON_BUTIN + self.etage // 10) * data.NOXUS["butin_base"]))

    def pied(self, e):
        e.set_footer(text=f"Coffre : {self.butin()} composant(s) par clé · tes PV ne remontent jamais pendant la descente · 🩸 Hémorragie : soins réduits à {data.HEMORRAGIE} % · "
                          "entrer est gratuit, une défaite ne coûte rien")
        return e

    async def afficher(self, i, e):
        await i.response.edit_message(content=None, embed=self.pied(e), view=self, attachments=illustrer(e))

    def bouton(self, nom, emoji, action, style=discord.ButtonStyle.danger):
        b = discord.ui.Button(label=nom, emoji=emoji, style=style)
        b.callback = action
        self.add_item(b)

    async def perdu(self, i, e, raison):
        """Fin de la descente sur un échec : aucune clé dépensée, on peut recommencer."""
        self.fini = True
        self.clear_items()
        self.bouton("Recommencer la descente", "⚔️", self.recommencer)
        e.add_field(name="La descente s'arrête ici", value=raison + "\nTu n'as dépensé aucune clé.", inline=False)
        await i.response.edit_message(content=None, embed=e, view=self, attachments=illustrer(e))

    async def combat(self, i, salle, titre, raison=None):
        """Joue une salle de combat. Renvoie (victoire, derniers moments) ; en cas de défaite, la descente est terminée et affichée."""
        p = db.get_joueur(self.g, self.u)
        adversaires = combat.salle_donjon(self.numero, salle, self.etage)
        victoire, tours = combat.simuler_detail(self.equipe, adversaires, hemorragie=True)
        noter_combat(p, self.d["cle"], salle, victoire, len(tours), tours[-1]["etat"], self.possedees)
        moments = [l for t in tours for l in t["journal"] if not l.startswith("💫")]
        if not victoire:
            e = embed_combat(titre, f"💀 Défaite en {len(tours)} tours", tours[-1]["etat"], moments[-3:], 0xC53030, fond=self.fond)
            await self.perdu(i, e, raison or "Change de composition ou reviens plus fort : les gardiens ont la force de ton étage de la tour.")
        return victoire, moments[-2:]

    async def recommencer(self, i):
        await entrer_noxus(i, remplacer=True, numero=self.numero)

    # -- la serrure --
    def texte_serrure(self):
        n = len(self.code)
        lignes = [f"`{k + 1}.` {' '.join(essai)}  →  🟢 **{bien}** bien placé{'s' if bien > 1 else ''} · 🟡 **{mal}** mal placé{'s' if mal > 1 else ''}"
                  for k, (essai, bien, mal) in enumerate(self.essais)]
        saisie = " ".join(self.saisie + ["▫️"] * (n - len(self.saisie)))
        return (f"### 🔐 La serrure · {self.nom}\nLe code : **{n} sceaux différents** parmi {' '.join(self.sceaux)}, dans le bon ordre.\n"
                "🟢 = bon sceau au bon endroit · 🟡 = bon sceau au mauvais endroit\n"
                "Chaque essai raté alerte **une vague de gardes**.\n\n"
                + ("\n".join(lignes) + "\n\n" if lignes else "") + f"**Ton essai :** {saisie}")[:1024]

    def boutons_serrure(self):
        self.clear_items()
        for sceau in self.sceaux:
            b = discord.ui.Button(emoji=sceau, style=discord.ButtonStyle.secondary, disabled=sceau in self.saisie, row=0)
            b.callback = self.poser(sceau)
            self.add_item(b)
        b = discord.ui.Button(label="Effacer", emoji="↩️", style=discord.ButtonStyle.secondary, disabled=not self.saisie, row=1)
        b.callback = self.effacer
        self.add_item(b)

    async def demarrer(self, i):
        await self.serrure(i, f"🔐 Trouve le code pour atteindre {self.d['gardien'][0]}")

    async def serrure(self, i, resultat, lignes=()):
        self.saisie = []
        self.boutons_serrure()
        e = embed_combat(f"🔐 {self.nom} · la serrure", resultat, self.etat(), list(lignes), 0x9B2C2C, fond=self.fond)
        e.add_field(name="​", value=self.texte_serrure(), inline=False)
        self.ecran = e
        await self.afficher(i, e)

    async def rafraichir(self, i):
        """Met à jour l'essai en cours sans renvoyer l'image."""
        self.boutons_serrure()
        e = self.ecran
        e.set_field_at(len(e.fields) - 1, name="​", value=self.texte_serrure(), inline=False)
        await i.response.edit_message(embed=e, view=self)

    async def effacer(self, i):
        if self.fini or self.ouvert:
            return await i.response.defer()
        self.saisie = []
        await self.rafraichir(i)

    def poser(self, sceau):
        async def clic(i):
            if self.fini or self.ouvert or sceau in self.saisie or len(self.saisie) >= len(self.code):
                return await i.response.defer()
            self.saisie.append(sceau)
            if len(self.saisie) < len(self.code):
                return await self.rafraichir(i)
            essai = list(self.saisie)
            bien, mal = indices_code(self.code, essai)
            self.essais.append((essai, bien, mal))
            if bien == len(self.code):
                n, self.ouvert = len(self.essais), True
                return await self.suivant(i, f"🔓 Code trouvé en {n} essai{'s' if n > 1 else ''} !")
            victoire, moments = await self.combat(i, "garde", f"{self.icone} {self.nom} · vague de gardes n°{len(self.essais)}",
                                                  f"Les gardes t'ont submergé. Le code était {' '.join(self.code)} : il change à chaque descente.")
            if victoire:
                await self.serrure(i, f"❌ Mauvais code · 🟢 {bien} · 🟡 {mal} · vague de gardes repoussée", moments)
        return clic

    # -- les deux gardiens --
    async def suivant(self, i, resultat, lignes=()):
        """Présente le combat suivant : ton équipe telle qu'elle est, face à ce qui l'attend."""
        self.clear_items()
        if self.etape >= len(self.PLAN):
            return await self.coffre(i)
        if self.PLAN[self.etape] == "darius":
            g = self.d["gardien"]
            texte = f"### {g[4]} {g[0]} te barre la route\n{g[5]}\nIl faut le vaincre pour passer."
            self.bouton(f"Affronter {g[0]}", g[4], self.darius)
        else:
            g = self.d["boss"]
            texte = f"### {g[4]} La dernière salle\n{g[5]} Derrière, le coffre."
            self.bouton(f"Affronter {g[0]}", g[4], self.boss)
        titre, apercu = f"{g[4]} {self.nom} · {g[0]}", combat.salle_donjon(self.numero, self.PLAN[self.etape], self.etage)
        e = embed_combat(titre, resultat, self.etat(apercu), list(lignes), 0x9B2C2C, fond=self.fond)
        e.add_field(name="​", value=texte[:1024], inline=False)
        await self.afficher(i, e)

    async def darius(self, i):
        if self.fini or not self.ouvert or self.etape != 0:
            return await i.response.defer()
        self.etape = 1
        victoire, moments = await self.combat(i, "darius", f"{self.d['gardien'][4]} {self.nom} · {self.d['gardien'][1]}")
        if victoire:
            await self.suivant(i, f"🏆 {self.d['gardien'][0]} est vaincu", moments)

    async def boss(self, i):
        if self.fini or self.etape != 1:
            return await i.response.defer()
        self.etape = 2
        victoire, moments = await self.combat(i, "boss", f"{self.d['boss'][4]} {self.nom} · {self.d['boss'][1]}")
        if victoire:
            await self.suivant(i, f"🏆 {self.d['boss'][0]} est vaincu", moments)

    # -- le coffre --
    async def coffre(self, i):
        p = db.get_joueur(self.g, self.u)
        n = cles(p)
        db.sauver(p)
        self.clear_items()
        e = embed_combat(f"🧰 {self.nom} · le coffre", f"🏆 {self.d['boss'][0]} est vaincu", self.etat(), [], 0xD69E2E, fond=self.fond)
        texte = (f"### 🧰 Le coffre\nIl contient **{self.butin()} composant(s)** par clé. {texte_cles(p)}.\n"
                 + ("Combien de clés utilises-tu ?" if n else "Tu n'as aucune clé pour l'instant : le coffre reste fermé. Reviens quand tu en auras une, la descente sera à refaire."))
        for k in sorted({1, 2, 3, n}):
            if 1 <= k <= n:
                b = discord.ui.Button(label=f"Ouvrir avec {k} clé{'s' if k > 1 else ''}", emoji="🗝️", style=discord.ButtonStyle.success)
                b.callback = self.ouvrir(k)
                self.add_item(b)
        e.add_field(name="\u200b", value=texte, inline=False)
        self.fini = not n
        await self.afficher(i, e)

    def ouvrir(self, nombre):
        async def clic(i):
            p = await charger(i)
            if not p:
                return
            if self.fini or cles(p) < nombre:
                await i.response.edit_message(view=None)
                return
            self.fini = True
            if p["cles"] >= data.CLES_MAX:
                p["cles_moment"] = time.time()
            p["cles"] -= nombre
            gagnes = {}
            for _ in range(self.butin() * nombre):
                c = random.choice(data.DONJONS[self.numero][2])
                gagnes[c] = gagnes.get(c, 0) + 1
            for c, q in gagnes.items():
                db.ajouter_composant(self.g, self.u, c, q)
            e = discord.Embed(color=0xD69E2E, description=f"# 🧰 Coffre ouvert avec {nombre} clé{'s' if nombre > 1 else ''} !\n"
                              + " · ".join(f"{data.COMPOSANTS[c][1]} **{data.COMPOSANTS[c][0]}** ×{q}" for c, q in gagnes.items()))
            cartes = champ_compte(p, e, "donjon", nombre)
            db.sauver(p)
            e.set_footer(text=f"{texte_cles(p)} · fabrique tes items à la forge")
            self.clear_items()
            self.bouton("Nouvelle descente", "⚔️", self.recommencer)
            await i.response.edit_message(embed=e, view=self, attachments=[])
            if cartes:
                await annoncer(i.guild, i.user, cartes)
        return clic


async def entrer_noxus(i, remplacer=False, numero=0):
    p = await charger(i)
    if not p:
        return
    if await verrouille(i, p, "donjons"):
        return
    possedees = db.cartes(i.guild_id, i.user.id)
    ids = equipe_ids(p, possedees)
    cles(p)
    db.sauver(p)
    if not ids:
        if remplacer:
            await i.response.edit_message(content="Ton équipe est vide. Compose-la dans le salon de la collection.", embed=None, view=None, attachments=[])
        else:
            await i.response.send_message("Ton équipe est vide. Compose-la dans le salon de la collection.", ephemeral=True)
        return
    vue = Noxus(p, ids, possedees, numero)
    if not remplacer:   # le premier écran arrive par une modification : on ouvre d'abord un message
        await i.response.send_message(f"{data.DONJONS[numero][1]} Ton équipe entre : {data.DONJONS[numero][0]}… {texte_cles(p)}"
                                      + ("" if p["cles"] else "\n⚠️ Tu n'as aucune clé : tu peux t'entraîner, mais tu ne pourras pas ouvrir le coffre."), ephemeral=True)
        i = RelaisMessage(i)
    await vue.demarrer(i)


class RelaisMessage:
    """Fait passer la suite d'une interaction déjà répondue pour une modification de son message (même interface que i.response.edit_message)."""
    def __init__(self, i):
        self._i, self.response, self.guild, self.user, self.guild_id = i, self, i.guild, i.user, i.guild_id

    async def edit_message(self, **options):
        await editer(self._i, **options)


def defi_ouvert(p):
    """Vrai si le prochain donjon défi est accessible au niveau de compte du joueur."""
    return p["totems"] < len(data.DEFIS) and p["niveau"] >= data.DEFIS[p["totems"]][0]


def embed_defis(p):
    """Présentation des donjons défi : ceux déjà vaincus, le prochain, et ce qu'ils rapportent."""
    lignes = []
    for n, (niveau, etage) in enumerate(data.DEFIS):
        etat = "✅" if n < p["totems"] else "⚔️" if n == p["totems"] and p["niveau"] >= niveau else "🔒"
        final = " (défi final)" if n == len(data.DEFIS) - 1 else ""
        lignes.append(f"{etat} **Défi {n + 1}**{final} · niveau de compte {niveau} · force de l'étage {etage} → "
                      f"une charge toutes les **{texte_delai(data.CHARGES_DELAI[n + 1] * 60)}**, mise de **{data.CHARGES_MISE[n + 1]}** charge(s) par carte")
    e = discord.Embed(color=0x9B2C2C, description="# 🗿 Donjons défi\nTrois champions redoutables à vaincre **une seule fois**. "
                      "Un défi s'ouvre tous les 10 niveaux de compte ; les essais sont gratuits et illimités. Chaque victoire donne un **totem** permanent : "
                      "tes charges de Châtiment reviennent plus vite, et tu peux en miser davantage sur une seule carte de jungle.\n\n"
                      + "\n".join(lignes))
    e.set_footer(text=f"Aujourd'hui : une charge toutes les {texte_delai(delai_charge(p))}, mise de {mise_max(p)} · tu es niveau {p['niveau']}, étage {p['etage']}")
    return e


class VueDefi(discord.ui.View):
    def __init__(self, p):
        super().__init__(timeout=600)
        if defi_ouvert(p):
            b = discord.ui.Button(label=f"Affronter le défi {p['totems'] + 1}", emoji="⚔️", style=discord.ButtonStyle.danger)
            b.callback = self.clic
            self.add_item(b)

    async def clic(self, i):
        await defier(i)


async def defier(i):
    """Un combat de donjon défi : gratuit, sans limite d'essais, et le totem ne se gagne qu'une fois."""
    p = await charger(i)
    if not p:
        return
    if await verrouille(i, p, "donjons"):
        return
    if not defi_ouvert(p):
        await i.response.edit_message(embed=embed_defis(p), view=None, attachments=[])
        return
    possedees = db.cartes(i.guild_id, i.user.id)
    ids = equipe_ids(p, possedees)
    if not ids:
        await i.response.edit_message(content="Ton équipe est vide. Compose-la dans le salon de la collection.", embed=None, view=None, attachments=[])
        return
    numero = p["totems"]
    _, etage = data.DEFIS[numero]
    victoire, tours = combat.simuler_detail(combat.equipe_joueur(ids, possedees), combat.champions_ennemis(etage, random))
    noter_combat(p, "defi", numero + 1, victoire, len(tours), tours[-1]["etat"], possedees)
    moments = [l for t in tours for l in t["journal"] if not l.startswith("💫")]
    e = embed_combat(f"🗿 Donjon défi {numero + 1}", f"{'🏆 Victoire' if victoire else '💀 Défaite'} en {len(tours)} tours", tours[-1]["etat"],
                     moments[-4:], 0x2F855A if victoire else 0xC53030)
    cartes_niveau = []
    if victoire:
        charges(p)   # les charges déjà dues sont comptées à l'ancien rythme avant de changer de délai
        p["totems"] = numero + 1
        e.add_field(name="🗿 Totem obtenu !", inline=False,
                    value=f"Une charge de Châtiment revient maintenant toutes les **{texte_delai(delai_charge(p))}**, "
                          f"et tu peux en miser **{mise_max(p)}** sur une seule carte de jungle.")
        cartes_niveau = champ_compte(p, e, "donjon")
        if defi_ouvert(p):
            e.add_field(name="🗿 Défi suivant", value=f"Le **défi {p['totems'] + 1}** est déjà ouvert à ton niveau.", inline=False)
        db.sauver(p)
    else:
        e.add_field(name="Le défi a tenu", inline=False,
                    value=f"Ces gardiens ont la force de l'étage {etage} de la tour (tu es à l'étage {p['etage']}). Reviens plus fort : l'essai est gratuit.")
        db.sauver(p)
    fichiers = illustrer(e, None, ennemi_illustre(tours[-1]["etat"]))
    await i.response.edit_message(content=None, embed=e, view=VueDefi(p), attachments=fichiers)
    if cartes_niveau:
        await annoncer(i.guild, i.user, cartes_niveau)


class EncoreDonjon(discord.ui.View):
    def __init__(self, numero):
        super().__init__(timeout=600)
        b = discord.ui.Button(label=f"Encore · {data.DONJONS[numero][0]}"[:80], emoji=data.DONJONS[numero][1], style=discord.ButtonStyle.success)

        async def clic(i):
            await explorer(i, numero, remplacer=True)
        b.callback = clic
        self.add_item(b)


class PanneauDonjons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for numero, (nom, emoji, _) in enumerate(data.DONJONS):
            b = discord.ui.Button(label=nom, emoji=emoji, style=discord.ButtonStyle.danger, custom_id=f"f:donjon_{numero}", row=0)
            b.callback = self.entrer(numero)
            self.add_item(b)

    @staticmethod
    def entrer(numero):
        async def clic(i):
            await explorer(i, numero)
        return clic

    @discord.ui.button(label="La forge", emoji="⚒️", style=discord.ButtonStyle.primary, custom_id="f:forge", row=1)
    async def forge(self, i, _):
        p = await charger(i)
        if not p:
            return
        vue = Items(p, i.guild_id, i.user.id)
        await i.response.send_message(embed=vue.embed(), view=vue, ephemeral=True)

    @discord.ui.button(label="Donjon défi", emoji="🗿", style=discord.ButtonStyle.danger, custom_id="f:defi", row=1)
    async def defi(self, i, _):
        p = await charger(i)
        if not p:
            return
        if await verrouille(i, p, "donjons"):
            return
        await i.response.send_message(embed=embed_defis(p), view=VueDefi(p), ephemeral=True)

    @discord.ui.button(label="Recettes", emoji="📜", style=discord.ButtonStyle.secondary, custom_id="f:recettes", row=1)
    async def recettes(self, i, _):
        lignes = [f"{d[1]} **{d[0]}** : " + ", ".join(f"{data.COMPOSANTS[c][1]} {data.COMPOSANTS[c][0]}" for c in d[2]) for d in data.DONJONS]
        lignes.append("")
        for x, (a, b) in data.RECETTES.items():
            nom, emoji, _, valeurs, texte = data.ITEMS[x]
            lignes.append(f"{emoji} **{nom}** = {data.COMPOSANTS[a][0]} + {data.COMPOSANTS[b][0]} · {texte.format('/'.join(str(v) for v in valeurs))}")
        q = data.RECETTE_QUANTITES
        e = discord.Embed(color=COULEUR, description="# 📜 Donjons et recettes\n" + "\n".join(lignes))
        e.set_footer(text=f"Il faut {q[0]} exemplaires de chaque composant pour le niveau 1, {q[1]} pour le niveau 2, {q[2]} pour le niveau 3.")
        await i.response.send_message(embed=e, ephemeral=True)


class EncoreJungle(discord.ui.View):
    def __init__(self, difficulte, p=None):
        super().__init__(timeout=600)
        for fois in [1] + (chasses_groupees(p) if p else []):
            b = discord.ui.Button(label=f"Encore{'' if fois == 1 else f' ×{fois}'} ({fois} ⚡)", emoji="🌿",
                                  style=discord.ButtonStyle.success if fois == 1 else discord.ButtonStyle.primary)
            b.callback = self.rappel(difficulte, fois)
            self.add_item(b)

    @staticmethod
    def rappel(difficulte, fois):
        async def clic(i):
            await chasser(i, difficulte, remplacer=True, fois=fois)
        return clic


class PanneauJungle(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Explorer la jungle", emoji="🗺️", style=discord.ButtonStyle.danger, custom_id="f:clear")
    async def clear(self, i, _):
        await ouvrir_exploration(i)

    @discord.ui.button(label="Clear rapide", emoji="⏩", style=discord.ButtonStyle.primary, custom_id="f:clear_rapide")
    async def rapide(self, i, _):
        await clear_rapide(i)

    @discord.ui.button(label="Mes charges", emoji="⚡", style=discord.ButtonStyle.secondary, custom_id="f:energie")
    async def mes_charges(self, i, _):
        p = await charger(i)
        if not p:
            return
        xp, golds = butin_clear_complet(p)
        bonus = max([b for c, b in data.EXPLO_BONUS if p["chasses"] >= c] or [0])
        prochain = next((f"niveau {niveau} : {nombre} charges" for niveau, nombre in data.CHARGES_PALIERS if niveau > p["niveau"]), None)
        e = discord.Embed(color=COULEUR, description=f"# {texte_charges(p)}\n"
                          f"Une charge = une carte complète. Un clear complet rapporte jusqu'à **✨ {xp} XP par carte** et **💰 {golds} golds** à ton étage ; "
                          f"le clear rapide en donne {data.CLEAR_RAPIDE} % sans jouer. Plus tu montes dans la tour, plus la jungle rapporte.\n\n"
                          f"⏱️ Une charge toutes les **{texte_delai(delai_charge(p))}** · mise maximum : **{mise_max(p)}** charge(s) par carte (les donjons défi améliorent les deux).\n"
                          + (f"📈 Prochain palier de stock : {prochain}.\n" if prochain else "")
                          + f"🏕️ **{p['chasses']} camps nettoyés.** " + " · ".join(
                              f"{camps} camps : +{b} % de butin {'✅' if p['chasses'] >= camps else ''}" for camps, b in data.EXPLO_BONUS)
                          + (f"\nTon bonus actuel : **+{bonus} %**." if bonus else ""))
        db.sauver(p)
        await i.response.send_message(embed=e, ephemeral=True)


def contenu_coffre(p):
    """Renvoie (golds, XP par carte, secondes accumulées) du farm passif."""
    secondes = min(time.time() - p["dernier_coffre"], data.COFFRE_HEURES * 3600)
    heures = secondes / 3600
    etage = min(p["etage"], 100)
    return (int(heures * (data.COFFRE_GOLDS[0] + data.COFFRE_GOLDS[1] * etage)),
            int(heures * (data.COFFRE_XP[0] + data.COFFRE_XP[1] * etage)), secondes)


class PanneauCoffre(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Récupérer le butin", emoji="🧭", style=discord.ButtonStyle.success, custom_id="f:coffre")
    async def recuperer(self, i, _):
        p = await charger(i)
        if not p:
            return
        golds, xp, secondes = contenu_coffre(p)
        if golds < 1:
            await i.response.send_message("Ton expédition vient de partir : elle n'a encore rien rapporté. Reviens dans quelques minutes.", ephemeral=True)
            return
        possedees = db.cartes(i.guild_id, i.user.id)
        montees = []
        for cid in equipe_ids(p, possedees):
            n = combat.gagner_xp(cid, possedees[cid], xp)
            db.sauver_carte(i.guild_id, i.user.id, cid, possedees[cid]["niveau"], possedees[cid]["xp"], possedees[cid]["etoiles"])
            if n:
                montees.append(f"{data.CARTES[cid]['nom']} niv. {possedees[cid]['niveau']}")
        p["golds"] += golds
        p["dernier_coffre"] = time.time()
        tirages = [combat.tirer(p) for _ in range(int(secondes // (data.COFFRE_PACK_HEURES * 3600)))]
        tirages.sort(key=lambda c: data.RARETES.index(data.CARTES[c]["rarete"]))   # la plus rare à la fin
        lignes = [f"{data.EMOJIS[data.CARTES[c]['rarete']]} **{data.CARTES[c]['nom']}** · {donner(p, c)}" for c in tirages]
        db.sauver(p)
        plein = " (durée maximale atteinte)" if secondes >= data.COFFRE_HEURES * 3600 else ""
        texte = (f"# 🧭 Retour d'expédition\nElle a duré {duree(secondes)}{plein}.\n## 💰 +{golds} golds · ✨ +{xp} XP par carte"
                 + (f"\n⬆️ {', '.join(montees)}" if montees else ""))
        if tirages:
            texte += f"\n\n### 🎁 {len(tirages)} pack{'s' if len(tirages) > 1 else ''} rapporté{'s' if len(tirages) > 1 else ''}\n" + "\n".join(lignes)
        else:
            reste = data.COFFRE_PACK_HEURES * 3600 - secondes
            texte += f"\n\n🎁 Pas encore de pack : il en revient un toutes les {data.COFFRE_PACK_HEURES} heures (il manquait {duree(reste)})."
        e = discord.Embed(color=data.COULEURS[data.CARTES[tirages[-1]]["rarete"]] if tirages else COULEUR, description=texte[:4000])
        e.set_footer(text=f"Tu as {p['golds']} golds · un pack par tranche de {data.COFFRE_PACK_HEURES} h, {data.COFFRE_HEURES} h au maximum")
        if not tirages:
            await i.response.send_message(embed=e, ephemeral=True)
            return
        meilleur = tirages[-1]
        image = image_carte(meilleur)
        if image:
            e.set_image(url=f"attachment://{image}")
        anim, fichiers_anim = embed_ouverture(meilleur, f"🧭 Ton expédition rapporte {len(tirages)} pack{'s' if len(tirages) > 1 else ''}…")
        if anim:
            await i.response.send_message(embed=anim, files=fichiers_anim, ephemeral=True)
            await asyncio.sleep(DUREE_OUVERTURE)
            try:
                await editer(i, embed=e, attachments=joindre(image))
            except ERREURS_RESEAU:
                pass
        else:
            await i.response.send_message(embed=e, files=joindre(image), ephemeral=True)
        await annoncer(i.guild, i.user, tirages)


# ============================ MINI-JEUX : LE PACK ==============================
def palier_essais(essais):
    """Qualité du pack selon l'essai où l'on trouve : 1er = taux doublés, 2e = taux améliorés, ensuite = normal."""
    return min(essais - 1, len(data.MINI_PACKS) - 1)


def bareme_essais():
    return "1er essai : **pack à taux doublés** · 2e : **pack à taux améliorés** · ensuite : **pack normal**"


async def offrir_pack_jeu(i, p, palier, e, fichiers, bravo):
    """Tire le pack gagné à un mini-jeu, joue l'animation du coffre, puis montre le résultat du jeu avec la carte gagnée."""
    nom, taux = data.MINI_PACKS[palier]
    cid = combat.tirer(p, taux=taux)
    statut = donner(p, cid)
    db.sauver(p)
    c = data.CARTES[cid]
    carte = discord.Embed(color=data.COULEURS[c["rarete"]], description=f"# 🎁 Ton {nom}\n## {c['nom']} · {c['rarete']}\n{statut}")
    image = image_carte(cid)
    pieces = list(fichiers)
    if image:
        if not any(getattr(f, "filename", None) == image for f in pieces):
            pieces += joindre(image)
        carte.set_image(url=f"attachment://{image}")
    anim, fichiers_anim = embed_ouverture(cid, f"{bravo} Ton {nom} s'ouvre…")
    if anim:
        await i.response.edit_message(embed=anim, view=None, attachments=fichiers_anim)
        await asyncio.sleep(DUREE_OUVERTURE)
        try:
            await editer(i, embeds=[e, carte], view=None, attachments=pieces)
        except ERREURS_RESEAU:
            pass
    else:
        await i.response.edit_message(embeds=[e, carte], view=None, attachments=pieces)
    await annoncer(i.guild, i.user, [cid])


# ========================= QUI EST CE CHAMPION ? ==============================
def champion_du_jour(jour=None):
    """Le champion mystère du jour : le même pour tout le monde, tiré d'après la date."""
    jour = jour or aujourdhui()
    champions = sorted(c for c in data.CARTES if data.CARTES[c]["ulti"] and data.CARTES[c]["rarete"] != "UR")
    import datetime
    numero = datetime.date.fromisoformat(jour).toordinal()
    ordre = champions[:]   # un ordre mélangé par cycle : chaque champion passe une fois avant qu'un autre revienne
    random.Random(f"quiz-{numero // len(champions)}").shuffle(ordre)
    return ordre[numero % len(champions)]


def simplifier(texte):
    """Minuscules, sans accents ni espaces ni ponctuation : « Maître Yi » et « maitre yi » se valent."""
    import unicodedata
    sans = unicodedata.normalize("NFD", texte or "")
    return "".join(ch for ch in sans.lower() if ch.isalnum() and unicodedata.category(ch) != "Mn")


def duree_quiz(q):
    s = max(0, int(q["fin"] - q["debut"]))
    return f"{s} s" if s < 60 else f"{s // 60} min {s % 60:02d}" if s < 3600 else f"{s // 3600} h {s % 3600 // 60:02d}"


def embed_quiz(q, cid):
    """Écran d'une partie en cours ou terminée, et ses pièces jointes."""
    essais_max = len(data.QUIZ_ZOOMS)
    if q["fini"]:
        c = data.CARTES[cid]
        if q["trouve"]:
            titre = f"# ✅ C'était {c['nom']} !\nTrouvé en **{q['essais']} essai{'s' if q['essais'] > 1 else ''}** ({duree_quiz(q)}) · **{data.MINI_PACKS[palier_essais(q['essais'])][0]}**"
        else:
            titre = f"# ❌ C'était {c['nom']}\nPas trouvé cette fois · +{data.MINI_CONSOLATION} golds de consolation"
        e = discord.Embed(color=0x2F855A if q["trouve"] else 0xC53030, description=titre + "\n\nReviens demain pour un nouveau champion. Garde la réponse pour toi : les autres cherchent encore !")
        carte = image_carte(cid)
        fichiers = joindre(carte)
        if fichiers:
            e.set_image(url=f"attachment://{carte}")
        return e, fichiers
    numero = q["essais"] + 1
    texte = (f"# ❓ Qui est ce champion ?\n## Essai {numero}/{essais_max} · à gagner : {data.MINI_PACKS[palier_essais(q['essais'] + 1)][0]}\n"
             "Appuie sur **Répondre** et écris son nom. À chaque erreur, l'image se dévoile un peu plus.")
    if q["essais"] >= 2:
        c = data.CARTES[cid]
        texte += f"\n\n💡 **Indice** : {c['role']} · {c['region']}"
    e = discord.Embed(color=COULEUR, description=texte)
    fichiers = []
    try:
        tampon = cartes_img.mystere(cid, q["essais"], q["jour"])
        if tampon:
            e.set_image(url="attachment://mystere.jpg")
            fichiers = [discord.File(tampon, filename="mystere.jpg")]
    except Exception:
        pass
    if not fichiers:   # pas d'image possible : on donne des indices en texte
        c = data.CARTES[cid]
        indices = [f"Rareté : {c['rarete']}", f"Rôle : {c['role']}", f"Région : {c['region']}", f"Son actif : {c['ulti']}", f"Son nom commence par {c['nom'][0]}"]
        e.add_field(name="Indices", value="\n".join(indices[:q["essais"] + 1]))
    return e, fichiers


class ReponseQuiz(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Qui est ce champion ?")
        self.nom = discord.ui.TextInput(label="Son nom", placeholder="Écris le nom du champion", max_length=40)
        self.add_item(self.nom)

    async def on_submit(self, i):
        p = await charger(i)
        if not p:
            return
        cid = champion_du_jour()
        q = db.quiz(i.guild_id, i.user.id, aujourdhui(), i.user.display_name)
        if q["fini"]:
            e, fichiers = embed_quiz(q, cid)
            await i.response.edit_message(embed=e, view=None, attachments=fichiers)
            return
        q["essais"] += 1
        q["pseudo"] = i.user.display_name
        juste = simplifier(self.nom.value) in (simplifier(data.CARTES[cid]["nom"]), simplifier(cid))
        if juste or q["essais"] >= len(data.QUIZ_ZOOMS):
            q["fini"], q["trouve"], q["fin"] = 1, int(juste), time.time()
            if not juste:
                p["golds"] += data.MINI_CONSOLATION
            db.sauver(p)
            db.sauver_quiz(q)
            if juste:
                e, fichiers = embed_quiz(q, cid)
                return await offrir_pack_jeu(i, p, palier_essais(q["essais"]), e, fichiers, "✅ Bien joué !")
        db.sauver_quiz(q)
        e, fichiers = embed_quiz(q, cid)
        if not q["fini"]:
            e.description += f"\n\n❌ Ce n'est pas **{self.nom.value[:40]}**."
        await i.response.edit_message(embed=e, view=None if q["fini"] else VueQuiz(), attachments=fichiers)


class VueQuiz(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=900)

    @discord.ui.button(label="Répondre", emoji="✍️", style=discord.ButtonStyle.success)
    async def repondre(self, i, _):
        await i.response.send_modal(ReponseQuiz())


class PanneauQuiz(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Jouer", emoji="❓", style=discord.ButtonStyle.success, custom_id="f:quiz")
    async def jouer(self, i, _):
        p = await charger(i)
        if not p:
            return
        cid = champion_du_jour()
        q = db.quiz(i.guild_id, i.user.id, aujourdhui(), i.user.display_name)
        e, fichiers = embed_quiz(q, cid)
        if q["fini"]:
            await i.response.send_message(embed=e, files=fichiers, ephemeral=True)
        else:
            await i.response.send_message(embed=e, view=VueQuiz(), files=fichiers, ephemeral=True)

    @discord.ui.button(label="Classement du jour", emoji="🏅", style=discord.ButtonStyle.secondary, custom_id="f:quiz_top")
    async def classement(self, i, _):
        liste = db.classement_quiz(i.guild_id, aujourdhui())
        medailles = ["🥇", "🥈", "🥉"]
        lignes = [f"{medailles[k] if k < 3 else f'**{k + 1}.**'} {q['pseudo'] or 'Un joueur'} · {q['essais']} essai{'s' if q['essais'] > 1 else ''} · {duree_quiz(q)}"
                  for k, q in enumerate(liste[:20])]
        e = discord.Embed(color=COULEUR, description="# 🏅 Classement du jour\n" + ("\n".join(lignes) or "Personne n'a encore trouvé le champion du jour."))
        e.set_footer(text="Le moins d'essais d'abord, puis le plus rapide entre le premier coup d'œil et la bonne réponse. Nouveau champion chaque jour à minuit.")
        await i.response.send_message(embed=e, ephemeral=True)


# ============================== QUIZ DES PROS =================================
DOSSIER_PROS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pros")
POSTES = [("top", "Top"), ("jungle", "Jungle"), ("mid", "Mid"), ("adc", "ADC"), ("support", "Support")]
_PROS = {"version": None, "joueurs": {}, "equipes": {}, "visages": [], "effectifs": []}


def pros():
    """Les données des joueurs pros (pros/pros.json, fabriqué par pros/importer.py), relues quand le fichier change."""
    import json
    chemin = os.path.join(DOSSIER_PROS, "pros.json")
    try:
        version = os.path.getmtime(chemin)
    except OSError:
        return _PROS
    if version == _PROS["version"]:
        return _PROS
    try:
        joueurs = json.load(open(chemin, encoding="utf-8"))["joueurs"]
    except Exception:
        return _PROS
    equipes, total = {}, {}
    for page, j in joueurs.items():
        total[page] = sum(c[4] for c in j["carriere"])
        for annee, ligue, equipe, role, matchs in j["carriere"]:
            e = equipes.setdefault(f"{equipe}|{annee}", {"equipe": equipe, "annee": annee, "ligue": ligue, "roles": {}})
            e["roles"].setdefault(role, []).append((matchs, page))
    effectifs = []
    for cle, e in equipes.items():
        for role in e["roles"]:
            e["roles"][role].sort(reverse=True)
        if all(e["roles"].get(r) and e["roles"][r][0][0] >= 10 for r, _ in POSTES):
            effectifs.append((sum(total[e["roles"][r][0][1]] for r, _ in POSTES), cle))
    effectifs.sort(reverse=True)
    garde = sorted(cle for _, cle in effectifs[:max(1, int(len(effectifs) * data.PROS_EQUIPE_PART))])
    visages = sorted(p for p, j in joueurs.items() if j.get("photo") and total[p] >= data.PROS_VISAGE_MATCHS
                     and os.path.exists(os.path.join(DOSSIER_PROS, "photos", j["photo"])))
    _PROS.update(version=version, joueurs=joueurs, equipes=equipes, visages=visages, effectifs=garde)
    return _PROS


def tirage_du_jour(liste, graine, jour=None):
    """Un élément de la liste par jour, le même pour tout le monde ; chaque élément passe une fois avant qu'un autre revienne."""
    import datetime
    if not liste:
        return None
    numero = datetime.date.fromisoformat(jour or aujourdhui()).toordinal()
    ordre = list(liste)
    random.Random(f"{graine}-{numero // len(ordre)}").shuffle(ordre)
    return ordre[numero % len(ordre)]


def photo_pro(page):
    detouree = os.path.join(DOSSIER_PROS, "detoures", page.split(" (")[0] + ".png")   # photo sans fond, fournie à la main : elle passe d'abord
    if os.path.exists(detouree):
        return detouree
    j = pros()["joueurs"].get(page) or {}
    chemin = os.path.join(DOSSIER_PROS, "photos", j["photo"]) if j.get("photo") else None
    return chemin if chemin and os.path.exists(chemin) else None


def resume_carriere(j, masquer=False):
    """Carrière d'un pro, une ligne par équipe : « LPL · EDward Gaming (2021–2023) »."""
    parcours = []
    for annee, ligue, equipe, role, matchs in j["carriere"]:
        if parcours and parcours[-1][1] == equipe and annee - parcours[-1][3] <= 1:
            parcours[-1][3] = annee
        else:
            parcours.append([ligue, equipe, annee, annee])
    return "\n".join(f"{l} · {e} ({a}{'' if a == b else f'–{b}'})" for l, e, a, b in parcours[-12:])


PAS_PRET = "Le quiz des pros n'est pas encore prêt : les données sont en cours de récupération. Réessaie dans quelques minutes."


# -- Qui est ce pro ? --
def embed_visage(q, page):
    j = pros()["joueurs"][page]
    golds, essais_max = data.PROS_VISAGE_GOLDS, len(data.PROS_VISAGE_GOLDS)
    roles = {}
    for c in j["carriere"]:
        roles[c[3]] = roles.get(c[3], 0) + c[4]
    poste = dict(POSTES)[max(roles, key=roles.get)]
    ligues = " · ".join(sorted({c[1] for c in j["carriere"]}))
    if q["fini"]:
        if q["trouve"]:
            titre = f"# ✅ C'était {j['nom']} !\nTrouvé en **{q['essais']} essai{'s' if q['essais'] > 1 else ''}** ({duree_quiz(q)}) · **{data.MINI_PACKS[palier_essais(q['essais'])][0]}**"
        else:
            titre = f"# ❌ C'était {j['nom']}\nPas trouvé cette fois · +{data.MINI_CONSOLATION} golds de consolation"
        e = discord.Embed(color=0x2F855A if q["trouve"] else 0xC53030, description=f"{titre}\n\n**{poste}** · {ligues}\n{resume_carriere(j)}\n\nReviens demain pour un nouveau pro. Garde la réponse pour toi !")
    else:
        texte = (f"# 🎤 Qui est ce pro ?\n## Essai {q['essais'] + 1}/{essais_max} · à gagner : {data.MINI_PACKS[palier_essais(q['essais'] + 1)][0]}\n"
                 "Appuie sur **Répondre** et écris son pseudo. Un indice de plus à chaque erreur.")
        if q["essais"] >= 1:
            texte += f"\n\n💡 **Poste** : {poste} · **Ligue(s)** : {ligues}"
        if q["essais"] >= 2:
            texte += f"\n💡 **Parcours** :\n{resume_carriere(j)}"
        if q["essais"] >= 3:
            texte += f"\n💡 Son pseudo commence par **{j['nom'][0].upper()}** et fait {len(j['nom'])} caractères."
        e = discord.Embed(color=COULEUR, description=texte[:4000])
    e.set_footer(text="Données et photo : Leaguepedia (lol.fandom.com)")
    fichiers, chemin = [], photo_pro(page)
    if chemin:
        e.set_image(url="attachment://pro.jpg")
        fichiers = [discord.File(chemin, filename="pro.jpg")]
    return e, fichiers


class ReponseVisage(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Qui est ce pro ?")
        self.nom = discord.ui.TextInput(label="Son pseudo", placeholder="Écris son pseudo de joueur", max_length=40)
        self.add_item(self.nom)

    async def on_submit(self, i):
        p = await charger(i)
        if not p:
            return
        page = tirage_du_jour(pros()["visages"], "visage")
        if not page:
            return await i.response.send_message(PAS_PRET, ephemeral=True)
        q = db.jeu_jour(i.guild_id, i.user.id, aujourdhui(), "visage", i.user.display_name)
        if not q["fini"]:
            j = pros()["joueurs"][page]
            q["essais"] += 1
            q["pseudo"] = i.user.display_name
            juste = simplifier(self.nom.value) in (simplifier(j["nom"]), simplifier(page))
            if juste or q["essais"] >= len(data.PROS_VISAGE_GOLDS):
                q["fini"], q["trouve"], q["fin"] = 1, int(juste), time.time()
                if not juste:
                    p["golds"] += data.MINI_CONSOLATION
                db.sauver(p)
                db.sauver_jeu_jour(q)
                if juste:
                    e, fichiers = embed_visage(q, page)
                    return await offrir_pack_jeu(i, p, palier_essais(q["essais"]), e, fichiers, "✅ Bien joué !")
            db.sauver_jeu_jour(q)
        e, fichiers = embed_visage(q, page)
        if not q["fini"]:
            e.description += f"\n\n❌ Ce n'est pas **{self.nom.value[:40]}**."
        await i.response.edit_message(embed=e, view=None if q["fini"] else VueVisage(), attachments=fichiers)


class VueVisage(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=900)

    @discord.ui.button(label="Répondre", emoji="✍️", style=discord.ButtonStyle.success)
    async def repondre(self, i, _):
        await i.response.send_modal(ReponseVisage())


# -- L'effectif du jour --
def palier_effectif(nombre):
    """Qualité du pack selon le nombre de joueurs trouvés : 5 = taux doublés, 3 ou 4 = taux améliorés, 1 ou 2 = normal, 0 = pas de pack."""
    return None if nombre <= 0 else 0 if nombre >= len(POSTES) else 1 if nombre >= 3 else 2


def gain_effectif(nombre):
    palier = palier_effectif(nombre)
    return f"+{data.MINI_CONSOLATION} golds de consolation" if palier is None else data.MINI_PACKS[palier][0]


def acceptes(e, role):
    """Les joueurs acceptés à un poste : le titulaire, et ceux qui ont joué au moins un quart de ses matchs."""
    liste = e["roles"][role]
    return [page for matchs, page in liste if matchs * 4 >= liste[0][0]]


def embed_effectif(q, cle):
    P = pros()
    e, J = P["equipes"][cle], P["joueurs"]
    trouves = q["donnees"].get("trouves", {})
    titre = f"{e['equipe']} · {e['annee']} ({e['ligue']})"
    lignes = []
    for role, nom in POSTES:
        if role in trouves:
            lignes.append(f"🟢 **{nom}** : {J[trouves[role]]['nom']}")
        elif q["fini"]:
            lignes.append(f"🔴 **{nom}** : {' / '.join(J[x]['nom'] for x in acceptes(e, role))}")
        else:
            lignes.append(f"⬜ **{nom}** : ?")
    if q["fini"]:
        n = len(trouves)
        tete = f"# {'✅' if n == len(POSTES) else '🧩'} {titre}\n**{n}/{len(POSTES)}** trouvés en {q['essais']} essai{'s' if q['essais'] > 1 else ''} · **{gain_effectif(n)}**"
        fin = "\n\nReviens demain pour une nouvelle équipe. Garde les réponses pour toi !"
    else:
        tete = (f"# 🧩 Donne l'effectif\n## {titre}\nEssai {q['essais'] + 1}/{data.PROS_EQUIPE_ESSAIS} \n"
                "Les 5 : **pack à taux doublés** · 3 ou 4 : **pack à taux améliorés** · 1 ou 2 : **pack normal**")
        fin = "\n\nAppuie sur **Répondre** et écris les pseudos. Un poste trouvé reste acquis ; tu peux en laisser vides."
    emb = discord.Embed(color=(0x2F855A if len(trouves) == len(POSTES) else 0xC53030) if q["fini"] else COULEUR,
                        description=tete + "\n\n" + "\n".join(lignes) + (("\n\n" + q["donnees"]["note"]) if q["donnees"].get("note") and not q["fini"] else "") + fin)
    emb.set_footer(text="Titulaires sur l'année entière (saison et playoffs) · Données et photos : Leaguepedia (lol.fandom.com)")
    fichiers = []
    if q["fini"]:
        try:
            portraits = [(photo_pro(trouves.get(r) or e["roles"][r][0][1]), J[trouves.get(r) or e["roles"][r][0][1]]["nom"], nom, r in trouves) for r, nom in POSTES]
            emb.set_image(url="attachment://effectif.jpg")
            fichiers = [discord.File(cartes_img.effectif(portraits, titre), filename="effectif.jpg")]
        except Exception:
            emb.set_image(url=None)
            fichiers = []
    return emb, fichiers


class ReponseEffectif(discord.ui.Modal):
    def __init__(self, trouves, joueurs):
        super().__init__(title="Donne l'effectif")
        self.champs = {}
        for role, nom in POSTES:
            fait = role in trouves
            champ = discord.ui.TextInput(label=nom + (" (trouvé)" if fait else ""), required=False, max_length=40,
                                         default=joueurs[trouves[role]]["nom"] if fait else None, placeholder=None if fait else "Pseudo du joueur")
            self.champs[role] = champ
            self.add_item(champ)

    async def on_submit(self, i):
        p = await charger(i)
        if not p:
            return
        P = pros()
        cle = tirage_du_jour(P["effectifs"], "effectif")
        if not cle:
            return await i.response.send_message(PAS_PRET, ephemeral=True)
        e = P["equipes"][cle]
        q = db.jeu_jour(i.guild_id, i.user.id, aujourdhui(), "effectif", i.user.display_name)
        if not q["fini"]:
            trouves = q["donnees"].setdefault("trouves", {})
            notes = []
            for role, nom in POSTES:
                saisie = simplifier(self.champs[role].value)
                if role in trouves or not saisie:
                    continue
                bon = next((x for x in acceptes(e, role) if saisie in (simplifier(P["joueurs"][x]["nom"]), simplifier(x))), None)
                if bon:
                    trouves[role] = bon
                elif any(saisie in (simplifier(P["joueurs"][x]["nom"]), simplifier(x)) for r, _ in POSTES for _, x in e["roles"][r]):
                    notes.append(f"🟡 **{self.champs[role].value[:30]}** a bien joué dans cette équipe, mais pas (ou trop peu) au poste {nom}.")
                else:
                    notes.append(f"❌ **{self.champs[role].value[:30]}** n'est pas le {nom}.")
            q["essais"] += 1
            q["pseudo"], q["trouve"], q["donnees"]["note"] = i.user.display_name, len(trouves), "\n".join(notes)[:900]
            if len(trouves) == len(POSTES) or q["essais"] >= data.PROS_EQUIPE_ESSAIS:
                q["fini"], q["fin"] = 1, time.time()
                palier = palier_effectif(len(trouves))
                if palier is None:
                    p["golds"] += data.MINI_CONSOLATION
                db.sauver(p)
                db.sauver_jeu_jour(q)
                if palier is not None:
                    emb, fichiers = embed_effectif(q, cle)
                    return await offrir_pack_jeu(i, p, palier, emb, fichiers, f"🧩 {len(trouves)}/{len(POSTES)} !")
            db.sauver_jeu_jour(q)
        emb, fichiers = embed_effectif(q, cle)
        await i.response.edit_message(embed=emb, view=None if q["fini"] else VueEffectif(), attachments=fichiers)


class VueEffectif(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=900)

    @discord.ui.button(label="Répondre", emoji="✍️", style=discord.ButtonStyle.success)
    async def repondre(self, i, _):
        q = db.jeu_jour(i.guild_id, i.user.id, aujourdhui(), "effectif", i.user.display_name)
        await i.response.send_modal(ReponseEffectif(q["donnees"].get("trouves", {}), pros()["joueurs"]))


class PanneauPros(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Qui est ce pro ?", emoji="🎤", style=discord.ButtonStyle.success, custom_id="f:pros_visage")
    async def visage(self, i, _):
        p = await charger(i)
        if not p:
            return
        page = tirage_du_jour(pros()["visages"], "visage")
        if not page:
            return await i.response.send_message(PAS_PRET, ephemeral=True)
        q = db.jeu_jour(i.guild_id, i.user.id, aujourdhui(), "visage", i.user.display_name)
        e, fichiers = embed_visage(q, page)
        await i.response.send_message(embed=e, files=fichiers, ephemeral=True, **({} if q["fini"] else {"view": VueVisage()}))

    @discord.ui.button(label="L'effectif du jour", emoji="🧩", style=discord.ButtonStyle.success, custom_id="f:pros_effectif")
    async def effectif(self, i, _):
        p = await charger(i)
        if not p:
            return
        cle = tirage_du_jour(pros()["effectifs"], "effectif")
        if not cle:
            return await i.response.send_message(PAS_PRET, ephemeral=True)
        q = db.jeu_jour(i.guild_id, i.user.id, aujourdhui(), "effectif", i.user.display_name)
        e, fichiers = embed_effectif(q, cle)
        await i.response.send_message(embed=e, files=fichiers, ephemeral=True, **({} if q["fini"] else {"view": VueEffectif()}))

    @discord.ui.button(label="Classements du jour", emoji="🏅", style=discord.ButtonStyle.secondary, custom_id="f:pros_top")
    async def classement(self, i, _):
        medailles = ["🥇", "🥈", "🥉"]
        e = discord.Embed(color=COULEUR, description="# 🏅 Quiz des pros · classements du jour")
        for jeu, nom in (("visage", "🎤 Qui est ce pro ?"), ("effectif", "🧩 L'effectif du jour")):
            liste = db.classement_jeu_jour(i.guild_id, aujourdhui(), jeu)
            lignes = [f"{medailles[k] if k < 3 else f'**{k + 1}.**'} {q['pseudo'] or 'Un joueur'} · "
                      + (f"{q['trouve']}/{len(POSTES)} · " if jeu == "effectif" else "") + f"{q['essais']} essai{'s' if q['essais'] > 1 else ''} · {duree_quiz(q)}"
                      for k, q in enumerate(liste[:10])]
            e.add_field(name=nom, value="\n".join(lignes)[:1024] or "Personne pour l'instant.", inline=False)
        e.set_footer(text="Nouvelles questions chaque jour à minuit.")
        await i.response.send_message(embed=e, ephemeral=True)


# ================================ RUNES =======================================
class VueRunes(discord.ui.View):
    """Équiper ses runes : un menu par carte de l'équipe. Une rune par carte, une carte par rune, dans la limite des emplacements."""
    def __init__(self, p, possedees):
        super().__init__(timeout=600)
        self.g, self.u = p["guild_id"], p["user_id"]
        self.construire(p, possedees)

    def construire(self, p, possedees):
        self.clear_items()
        ids, miennes, portees = equipe_ids(p, possedees), runes_du_compte(p), runes_equipees(p)
        if not miennes or not emplacements_runes(p):
            return
        for rang, cid in enumerate(ids):
            options = [discord.SelectOption(label="Aucune rune", value="-", default=cid not in portees)]
            options += [discord.SelectOption(label=data.RUNES[r][0] + (f" ×{miennes.count(r)}" if miennes.count(r) > 1 else ""), value=r, emoji=data.RUNES[r][1],
                                             default=portees.get(cid) == r, description=data.RUNES[r][3][:100]) for r in dict.fromkeys(miennes)]
            menu = discord.ui.Select(placeholder=f"Rune de {data.CARTES[cid]['nom']}", options=options, row=rang)
            menu.callback = self.choisir(cid, menu)
            self.add_item(menu)

    def embed(self, p, possedees, note=""):
        miennes, portees, places = runes_du_compte(p), runes_equipees(p), emplacements_runes(p)
        lignes = []
        for palier, etage in enumerate(data.RUNE_ETAGES):
            du_palier = [r for r in data.RUNES if data.RUNES[r][2] == palier]
            lignes.append(f"**{data.RAID_NOMS[palier]}** (étage {etage}) · " + " ".join(
                f"{data.RUNES[r][1]}" if r in miennes else "▫️" for r in du_palier) + f" · {sum(r in miennes for r in du_palier)}/{len(du_palier)}")
        e = discord.Embed(color=0x6B46C1, description=f"# 🔮 Tes runes\n**{len(portees)}/{places}** carte(s) de ton équipe portent une rune. "
                          "Chaque carte de l'équipe peut en porter une."
                          + "\nLes runes se gagnent en battant **Ryze** dans le salon du raid.\n\n" + "\n".join(lignes) + (f"\n\n{note}" if note else ""))
        if miennes:
            e.add_field(name="Tes runes", value="\n".join(texte_rune(r) + (f" ×{miennes.count(r)}" if miennes.count(r) > 1 else "")
                                                         + (" → *" + ", ".join(data.CARTES[k]["nom"] for k, v in portees.items() if v == r) + "*" if r in portees.values() else "")
                                                         for r in dict.fromkeys(miennes))[:1024], inline=False)
        if not places:
            e.set_footer(text=f"Atteins l'étage {data.RUNE_ETAGES[0]} de la tour pour ton premier emplacement (tu es à l'étage {p['etage']}).")
        elif not miennes:
            e.set_footer(text="Tu n'as pas encore de rune : va battre Ryze dans le salon du raid.")
        else:
            e.set_footer(text="Choisis la rune de chaque carte de ton équipe dans les menus. Chaque exemplaire d'une rune se porte sur une carte : regagne-la contre Ryze pour l'équiper ailleurs aussi.")
        return e

    def choisir(self, cid, menu):
        async def clic(i):
            p = db.get_joueur(i.guild_id, i.user.id)
            possedees = db.cartes(i.guild_id, i.user.id)
            portees, rune, note = runes_equipees(p), menu.values[0], ""
            portees.pop(cid, None)
            if rune != "-":
                autres = [k for k, v in portees.items() if v == rune]
                while autres and len(autres) >= runes_du_compte(p).count(rune):   # plus d'exemplaire libre : la rune change de carte
                    portees.pop(autres.pop(0))
                if len(portees) >= emplacements_runes(p):
                    note = f"⚠️ Tu n'as que **{emplacements_runes(p)}** emplacement(s) de rune : retire d'abord une rune d'une autre carte."
                else:
                    portees[cid] = rune
            p["runes_equipees"] = ",".join(f"{k}:{v}" for k, v in portees.items())
            db.sauver(p)
            self.construire(p, possedees)
            await i.response.edit_message(embed=self.embed(p, possedees, note), view=self)
        return clic


async def ouvrir_runes(i):
    p = await charger(i)
    if not p:
        return
    possedees = db.cartes(i.guild_id, i.user.id)
    vue = VueRunes(p, possedees)
    await i.response.send_message(embed=vue.embed(p, possedees), view=vue, ephemeral=True)


# ============================ RAID CONTRE RYZE ================================
RAIDS = {}   # (serveur, difficulté) -> groupe en cours de formation : {"joueurs": {id: pseudo}, "chef": id, "message": message}


def raid_ouvert(p, difficulte):
    return p["etage"] >= data.RUNE_ETAGES[difficulte]


def runes_a_gagner(p, difficulte):
    return [r for r in data.RUNES if data.RUNES[r][2] == difficulte]   # 14 octobre : on peut regagner une rune déjà possédée (un exemplaire de plus)


def embed_groupe(difficulte, groupe):
    mini, maxi = data.RAID_JOUEURS
    noms = "\n".join(f"{'👑' if u == groupe['chef'] else '•'} {nom}" for u, nom in groupe["joueurs"].items())
    e = discord.Embed(color=0x6B46C1, description=f"# 🔮 Raid · {data.RAID_NOMS[difficulte]}\n## {len(groupe['joueurs'])}/{maxi} joueurs\n{noms}\n\n"
                      f"Il faut **{mini} joueurs au moins** pour lancer. Chacun amène son équipe de 3 ; Ryze s'adapte au groupe.\n"
                      f"Entrée : étage **{data.RUNE_ETAGES[difficulte]}** de la tour, une récompense par jour. Si tu as déjà battu Ryze aujourd'hui, tu peux revenir **aider** sans récompense.")
    e.set_footer(text=f"Le chef de groupe (👑) lance le combat. Le groupe se ferme tout seul après 15 minutes. 🩸 Hémorragie : soins réduits à {data.HEMORRAGIE} % pendant le raid.")
    return e


class VueGroupe(discord.ui.View):
    def __init__(self, guilde, difficulte):
        super().__init__(timeout=900)
        self.cle, self.difficulte = (guilde, difficulte), difficulte

    async def on_timeout(self):
        groupe = RAIDS.pop(self.cle, None)
        if groupe and groupe.get("message"):
            try:
                await groupe["message"].edit(content="⌛ Le groupe de raid s'est dissous.", embed=None, view=None)
            except Exception:
                pass

    async def refuser(self, i, texte):
        await i.response.send_message(texte, ephemeral=True)

    @discord.ui.button(label="Rejoindre", emoji="⚔️", style=discord.ButtonStyle.success)
    async def rejoindre(self, i, _):
        groupe = RAIDS.get(self.cle)
        p = await charger(i)
        if not p:
            return
        if not groupe:
            return await self.refuser(i, "Ce groupe n'existe plus.")
        raison = raison_refus(p, self.difficulte, i)
        if raison:
            return await self.refuser(i, raison)
        if i.user.id not in groupe["joueurs"] and len(groupe["joueurs"]) >= data.RAID_JOUEURS[1]:
            return await self.refuser(i, "Le groupe est complet.")
        groupe["joueurs"][i.user.id] = i.user.display_name
        groupe["moment"] = time.time()
        await i.response.edit_message(embed=embed_groupe(self.difficulte, groupe), view=self)

    @discord.ui.button(label="Quitter", emoji="🚪", style=discord.ButtonStyle.secondary)
    async def quitter(self, i, _):
        groupe = RAIDS.get(self.cle)
        if not groupe or i.user.id not in groupe["joueurs"]:
            return await self.refuser(i, "Tu n'es pas dans ce groupe.")
        groupe["joueurs"].pop(i.user.id)
        if not groupe["joueurs"]:
            RAIDS.pop(self.cle, None)
            self.stop()
            return await i.response.edit_message(content="Le groupe de raid s'est dissous.", embed=None, view=None)
        if groupe["chef"] == i.user.id:
            groupe["chef"] = next(iter(groupe["joueurs"]))
        await i.response.edit_message(embed=embed_groupe(self.difficulte, groupe), view=self)

    @discord.ui.button(label="Lancer le raid", emoji="🔮", style=discord.ButtonStyle.danger)
    async def lancer(self, i, _):
        groupe = RAIDS.get(self.cle)
        if not groupe:
            return await self.refuser(i, "Ce groupe n'existe plus.")
        if i.user.id != groupe["chef"]:
            return await self.refuser(i, "Seul le chef de groupe (👑) peut lancer le raid.")
        if len(groupe["joueurs"]) < data.RAID_JOUEURS[0]:
            return await self.refuser(i, f"Il faut au moins {data.RAID_JOUEURS[0]} joueurs (vous êtes {len(groupe['joueurs'])}).")
        RAIDS.pop(self.cle, None)
        self.stop()
        await jouer_raid(i, self.difficulte, groupe)


def raison_refus(p, difficulte, i):
    """Pourquoi ce joueur ne peut pas entrer dans ce raid (None s'il peut)."""
    if not raid_ouvert(p, difficulte):
        return f"🔒 {data.RAID_NOMS[difficulte]} s'ouvre à l'étage **{data.RUNE_ETAGES[difficulte]}** de la tour (tu es à l'étage {p['etage']})."
    if not equipe_ids(p, db.cartes(i.guild_id, i.user.id)):
        return "Ton équipe est vide. Compose-la dans le salon de la collection."
    return None


async def jouer_raid(i, difficulte, groupe):
    """Le combat : toutes les équipes du groupe contre Ryze, en un seul affrontement."""
    await i.response.edit_message(content=f"🔮 **{data.RAID_NOMS[difficulte]}** : le groupe entre dans la salle des runes…", embed=None, view=None)
    allies, parts = [], {}
    for u, nom in groupe["joueurs"].items():
        p = db.get_joueur(i.guild_id, u)
        possedees = db.cartes(i.guild_id, u)
        ids = equipe_ids(p, possedees) if p else []
        if not ids:
            continue
        equipe = combat.equipe_joueur(ids, possedees, coach_plein=True)   # au raid, le coach donne tout son bonus
        parts[u] = {"nom": nom, "unites": equipe, "aide": p["raid_jour"] == aujourdhui()}   # aide : a déjà battu Ryze aujourd'hui, revient sans récompense
        allies += equipe
    if len(parts) < data.RAID_JOUEURS[0]:
        return await editer(i, content="Le raid est annulé : il n'y a plus assez de joueurs prêts dans le groupe.")
    boss = combat.ryze(difficulte, allies)
    victoire, tours = combat.simuler_detail(allies, boss, hemorragie=True)
    reste = max(0, boss[0]["pv"]) / boss[0]["pvmax"]
    compte = False   # seule une victoire consomme le raid du jour : une défaite se retente autant de fois qu'on veut
    moments = [l for t in tours for l in t["journal"] if l.startswith(("🔮", "💀", "✨", "😤", "😇"))]
    total = sum(x["inflige"] for x in allies) or 1
    lignes = []
    for u, part in sorted(parts.items(), key=lambda kv: -sum(x["inflige"] for x in kv[1]["unites"])):
        degats, debout = sum(x["inflige"] for x in part["unites"]), sum(1 for x in part["unites"] if x["pv"] > 0)
        lignes.append(f"{'🤝 ' if part['aide'] else ''}**{part['nom']}** · {degats} dégâts ({100 * degats // total} %) · {debout}/{len(part['unites'])} debout")
    # L'écran du raid : une rangée par joueur face à Ryze, animé (coups, secousses, Surcharge) puis figé sur le résultat.
    def scene(etat):
        cote, rang, groupes = [x for x in etat if x["camp"] == 0], 0, []
        for part in parts.values():
            groupes.append((part["nom"], cote[rang:rang + len(part["unites"])]))
            rang += len(part["unites"])
        return groupes, next(x for x in etat if x["camp"] == 1)
    titre_image = f"Raid · {data.RAID_NOMS[difficulte]}"
    choisis = sorted({round(k * (len(tours) - 1) / 5) for k in range(6)})   # six instants du combat au plus
    depart = [dict(x, pv=x["pvmax"], inflige=0) for x in tours[0]["etat"]]
    etapes = [scene(depart) + ((),)]
    for k in choisis:
        forts = [l for l in tours[k]["journal"] if l.startswith(("🔮", "💀", "✨", "😤", "😇"))]
        etapes.append(scene(tours[k]["etat"]) + (forts[-1:],))
    try:
        film, duree = await dessiner("raid_anime", etapes, titre_image)
        fixe = await dessiner("raid", *scene(tours[-1]["etat"]), titre_image)
    except Exception:
        film, duree, fixe = None, 0, None
    if film:
        attente = discord.Embed(color=0x6B46C1, description=f"# 🔮 {data.RAID_NOMS[difficulte]}\nLe combat fait rage…")
        attente.set_image(url="attachment://raid.gif")
        if await editer(i, content=" ".join(f"<@{u}>" for u in parts), embed=attente, attachments=[discord.File(film, "raid.gif")]):
            await asyncio.sleep(duree + 1)
    plein = round(20 * reste)
    e = discord.Embed(color=0x2F855A if victoire else 0xC53030, description=(
        f"# 🔮 {data.RAID_NOMS[difficulte]} · {'🏆 Ryze est vaincu !' if victoire else '💀 Ryze a tenu bon'}\n"
        f"## Ryze : {max(0, boss[0]['pv'])} / {boss[0]['pvmax']} PV\n{'🟪' * plein}{'⬛' * (20 - plein)}\nCombat de {len(tours)} tours.\n\n" + "\n".join(lignes)))
    if moments:
        e.add_field(name="Moments forts", value="\n".join(moments[-6:])[:1024], inline=False)
    if fixe:
        e.set_image(url="attachment://raid.jpg")
    else:
        e.set_thumbnail(url="https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Ryze_0.jpg")
    mentions, gagnants = " ".join(f"<@{u}>" for u in parts), 0
    for u in parts:
        p = db.get_joueur(i.guild_id, u)
        if parts[u]["aide"]:   # venu aider : ni rune, ni XP, et sa victoire du jour ne change pas
            noter_combat(p, "raid", difficulte + 1, victoire, len(tours), tours[-1]["etat"], db.cartes(i.guild_id, u))
            continue
        if victoire or compte:
            p["raid_jour"] = aujourdhui()
        if victoire and runes_a_gagner(p, difficulte):
            p["rune_a_choisir"] = difficulte + 1
            gagnants += 1
        if victoire:
            gagner_xp_compte(p, "donjon", 4)
            p["golds"] += data.GOLDS_RAID
        db.sauver(p)
        noter_combat(p, "raid", difficulte + 1, victoire, len(tours), tours[-1]["etat"], db.cartes(i.guild_id, u))
    if victoire:
        e.add_field(name="🎁 Récompense", inline=False, value=f"💰 **+{data.GOLDS_RAID} golds** pour chacun, et chaque participant choisit **une rune** de ce palier avec le bouton ci-dessous."
                    + ("" if gagnants == len(parts) else " Ceux qui avaient déjà battu Ryze aujourd'hui ont aidé pour la gloire (🤝)."))
    elif compte:
        e.add_field(name="Défaite", inline=False, value="Le raid du jour est consommé pour tout le groupe. Montez vos cartes, équipez vos items et réessayez demain.")
    else:
        e.add_field(name="Défaite", inline=False, value="Une défaite **ne consomme pas** le raid du jour. Changez de composition et relancez quand vous voulez.")
    await editer(i, content=mentions, embed=e, view=VueButinRaid() if victoire and gagnants else None,
                 attachments=[discord.File(fixe, "raid.jpg")] if fixe else [])


class ChoixRune(discord.ui.View):
    def __init__(self, p, difficulte):
        super().__init__(timeout=600)
        for r in runes_a_gagner(p, difficulte):
            b = discord.ui.Button(label=data.RUNES[r][0], emoji=data.RUNES[r][1], style=discord.ButtonStyle.primary)
            b.callback = self.prendre(r)
            self.add_item(b)

    def prendre(self, rune):
        async def clic(i):
            p = db.get_joueur(i.guild_id, i.user.id)
            if not p or not p["rune_a_choisir"] or data.RUNES[rune][2] != p["rune_a_choisir"] - 1:
                return await i.response.edit_message(content="Tu n'as pas de rune à choisir.", embed=None, view=None)
            p["runes"] = ",".join(runes_du_compte(p) + [rune])
            p["rune_a_choisir"] = 0
            db.sauver(p)
            await i.response.edit_message(content=f"🔮 Rune obtenue : {texte_rune(rune)}\nÉquipe-la avec **Mes runes**, dans le salon de la collection.", embed=None, view=None)
        return clic


async def proposer_rune(i):
    """Ouvre le choix de rune d'un joueur qui en a une en attente. Renvoie False s'il n'en a pas."""
    p = db.get_joueur(i.guild_id, i.user.id)
    if not p or not p["rune_a_choisir"]:
        return False
    difficulte = p["rune_a_choisir"] - 1
    if not runes_a_gagner(p, difficulte):
        p["rune_a_choisir"] = 0
        db.sauver(p)
        return False
    e = discord.Embed(color=0x6B46C1, description=f"# 🔮 Choisis ta rune · {data.RAID_NOMS[difficulte]}\n" + "\n".join(texte_rune(r) for r in runes_a_gagner(p, difficulte)))
    await i.response.send_message(embed=e, view=ChoixRune(p, difficulte), ephemeral=True)
    return True


class VueButinRaid(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Choisir ma rune", emoji="🔮", style=discord.ButtonStyle.success, custom_id="f:raid_rune")
    async def choisir(self, i, _):
        if not await proposer_rune(i):
            await i.response.send_message("Tu n'as pas de rune à choisir ici.", ephemeral=True)


class PanneauRaid(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for difficulte, nom in enumerate(data.RAID_NOMS):
            b = discord.ui.Button(label=f"{nom} · étage {data.RUNE_ETAGES[difficulte]}", emoji="🔮", style=discord.ButtonStyle.danger, custom_id=f"f:raid_{difficulte}", row=0)
            b.callback = self.ouvrir(difficulte)
            self.add_item(b)

    @staticmethod
    def ouvrir(difficulte):
        async def clic(i):
            p = await charger(i)
            if not p:
                return
            raison = raison_refus(p, difficulte, i)
            if raison:
                return await i.response.send_message(raison, ephemeral=True)
            cle = (i.guild_id, difficulte)
            ancien = RAIDS.get(cle)
            if ancien:
                # Un groupe dont le message n'a jamais été posté (coupure réseau) ou trop vieux ne bloque plus le raid.
                perime = time.time() - ancien.get("moment", 0) > 960 or (not ancien.get("message") and time.time() - ancien.get("moment", 0) > 30)
                if not perime:
                    return await i.response.send_message("Un groupe se forme déjà pour ce raid : clique sur **Rejoindre** sous son message, plus bas dans ce salon.", ephemeral=True)
                RAIDS.pop(cle, None)
            groupe = {"joueurs": {i.user.id: i.user.display_name}, "chef": i.user.id, "message": None, "moment": time.time()}
            RAIDS[cle] = groupe
            try:
                await i.response.send_message(content=f"🔮 **{i.user.display_name}** forme un groupe pour **{data.RAID_NOMS[difficulte]}** !",
                                              embed=embed_groupe(difficulte, groupe), view=VueGroupe(i.guild_id, difficulte))
            except Exception:
                RAIDS.pop(cle, None)
                raise
            try:
                groupe["message"] = await i.original_response()
            except Exception:
                pass
        return clic

    @discord.ui.button(label="Mes runes", emoji="📖", style=discord.ButtonStyle.primary, custom_id="f:raid_runes", row=1)
    async def runes(self, i, _):
        if not await proposer_rune(i):
            await ouvrir_runes(i)

    @discord.ui.button(label="Comment ça marche", emoji="❔", style=discord.ButtonStyle.secondary, custom_id="f:raid_info", row=1)
    async def info(self, i, _):
        lignes = []
        for palier, etage in enumerate(data.RUNE_ETAGES):
            lignes.append(f"\n**{data.RAID_NOMS[palier]}** · étage {etage} de la tour · {palier + 1} carte{'s' if palier else ''} avec rune")
            lignes += [texte_rune(r) for r in data.RUNES if data.RUNES[r][2] == palier]
        e = discord.Embed(color=0x6B46C1, description="# 🔮 Le raid et les runes\n"
                          f"De {data.RAID_JOUEURS[0]} à {data.RAID_JOUEURS[1]} joueurs unissent leurs équipes contre **Ryze**. Il s'adapte au groupe, enferme un champion dans sa "
                          f"**Prison runique** toutes les {data.RAID_RYZE['prison']} actions, frappe tout le monde avec sa **Surcharge** et **entre en rage** sous {data.RAID_RYZE['enrage_seuil']} % de PV.\n"
                          f"**{data.RAID_NOMS[2]}** est à part : rage dès {data.RAID_DIFFICULTE[2]['rage']} % de PV, et un **Flux runique** qui vise régulièrement la carte qui lui fait le plus mal.\n"
                          "Une victoire donne à chacun **une rune au choix** du palier. Une récompense par jour et par joueur : une défaite ne consomme rien, et après ta victoire tu peux revenir aider les autres, sans récompense.\n" + "\n".join(lignes))
        await i.response.send_message(embed=e, ephemeral=True)


# ============================== BOSS DE SALON =================================
def barre_boss(etat):
    plein = max(0, min(20, round(20 * etat["pv"] / etat["pvmax"])))
    return "🟥" * plein + "⬛" * (20 - plein)


def embed_boss(m, fin=None):
    """Le message public du boss : barre de vie commune, derniers coups, meilleurs dégâts. fin : texte de conclusion."""
    etat = m["boss"]
    coups = sorted(m["coups"].values(), key=lambda c: -c["degats"])
    pourcent = max(0, round(100 * etat["pv"] / etat["pvmax"]))
    if fin:
        texte = f"# 🐉 {etat['nom']}\n{fin}"
    else:
        texte = (f"# 🐉 {etat['nom']} est apparu !\n## {max(0, etat['pv'])} / {etat['pvmax']} PV · {pourcent} %\n{barre_boss(etat)}\n"
                 f"Il s'enfuit <t:{int(etat['fin'])}:R>. S'il meurt, tout le serveur gagne **{etat['texte']}** pendant {data.BOSS_BUFF_HEURES} heures.")
    e = discord.Embed(color=0xC53030 if not fin else 0x2F855A if etat["pv"] <= 0 else 0x4B5563, description=texte)
    if etat.get("journal"):
        e.add_field(name="Derniers coups", value="\n".join(etat["journal"][-4:])[:1024], inline=False)
    if coups:
        e.add_field(name=f"Dégâts · {len(coups)} participant(s)", inline=False,
                    value="\n".join(f"**{k + 1}.** {c['pseudo']} · {c['degats']}" for k, c in enumerate(coups[:8]))[:1024])
    if not fin:
        e.set_footer(text=f"{data.BOSS_ATTAQUES} attaques par joueur ({data.BOSS_PAUSE} s entre deux) · sous {data.BOSS_SEUIL} % de PV, un Châtiment chacun · "
                          "le coup fatal vole le boss : un pack à taux doublés")
    if etat.get("image"):
        e.set_image(url=f"attachment://{etat['image']}")
    return e


class VueBoss(discord.ui.View):
    """Les deux boutons du boss, sous son message public. Permanents : ils survivent à un redémarrage du bot."""
    def __init__(self):
        super().__init__(timeout=None)

    async def frapper(self, i, chatiment):
        p = await charger(i)
        if not p:
            return
        possedees = db.cartes(i.guild_id, i.user.id)
        ids = equipe_ids(p, possedees)
        # À partir d'ici, rien n'attend Discord jusqu'à la sauvegarde : deux joueurs ne peuvent pas se marcher dessus.
        m = db.monde(i.guild_id)
        etat = m["boss"]
        if not etat or etat["pv"] <= 0 or etat.get("message") != i.message.id:
            await i.response.send_message("Ce boss n'est plus là.", ephemeral=True)
            return
        if not ids:
            await i.response.send_message("Ton équipe est vide. Compose-la dans le salon de la collection.", ephemeral=True)
            return
        cle = str(i.user.id)
        moi = m["coups"].setdefault(cle, {"pseudo": i.user.display_name, "attaques": 0, "dernier": 0, "degats": 0, "chatiment": 0})
        moi["pseudo"] = i.user.display_name
        maintenant = time.time()
        if chatiment:
            if etat["pv"] > etat["pvmax"] * data.BOSS_SEUIL / 100:
                await i.response.send_message(f"Trop tôt : le Châtiment se débloque sous {data.BOSS_SEUIL} % de PV.", ephemeral=True)
                return
            if moi["chatiment"]:
                await i.response.send_message("Tu as déjà utilisé ton Châtiment sur ce boss.", ephemeral=True)
                return
            moi["chatiment"] = 1
            degats = int(etat["pvmax"] * data.BOSS_CHATIMENT / 100)
            ligne = f"⚡ **{i.user.display_name}** lance son Châtiment : {degats} dégâts !"
        else:
            if moi["attaques"] >= data.BOSS_ATTAQUES:
                await i.response.send_message(f"Tu as déjà fait tes {data.BOSS_ATTAQUES} attaques." + (" Il te reste ton Châtiment." if not moi["chatiment"] else ""), ephemeral=True)
                return
            attente = data.BOSS_PAUSE - (maintenant - moi["dernier"])
            if attente > 0:
                await i.response.send_message(f"Ton équipe reprend son souffle : encore {int(attente) + 1} s.", ephemeral=True)
                return
            moi["attaques"] += 1
            moi["dernier"] = maintenant
            force = combat.puissance_equipe(ids, possedees) / max(1, etat["reference"])
            degats = int(1000 * max(0.6, min(1.6, force)) * random.uniform(0.85, 1.15))
            ligne = f"⚔️ **{i.user.display_name}** attaque ({moi['attaques']}/{data.BOSS_ATTAQUES}) : {degats} dégâts."
        degats = min(degats, etat["pv"])
        etat["pv"] -= degats
        moi["degats"] += degats
        etat.setdefault("journal", []).append(ligne)
        etat["journal"] = etat["journal"][-6:]
        if etat["pv"] <= 0:
            fin, cartes = conclure_boss(i.guild_id, m, tueur=i.user.id, pseudo=i.user.display_name, vol=chatiment)
            await i.response.edit_message(embed=embed_boss(m, fin), view=None)
            if cartes:
                await annoncer(i.guild, i.user, cartes)
            return
        db.sauver_monde(i.guild_id, m)
        await i.response.edit_message(embed=embed_boss(m), view=self)

    @discord.ui.button(label="Attaquer", emoji="⚔️", style=discord.ButtonStyle.danger, custom_id="f:boss_atk")
    async def attaquer(self, i, _):
        await self.frapper(i, False)

    @discord.ui.button(label="Châtiment", emoji="⚡", style=discord.ButtonStyle.primary, custom_id="f:boss_smite")
    async def chatiment(self, i, _):
        await self.frapper(i, True)


def conclure_boss(g, m, tueur=None, pseudo="", vol=False):
    """Fin d'un boss : récompenses des participants, pack du tueur, buff du serveur s'il est mort. Renvoie (texte de fin, cartes du tueur)."""
    etat, coups = m["boss"], m["coups"]
    mort = etat["pv"] <= 0
    meilleur = max([c["degats"] for c in coups.values()] or [1]) or 1
    cartes = []
    for cle, c in coups.items():
        p = db.get_joueur(g, int(cle))
        if not p or c["degats"] <= 0:
            continue
        camps = data.BOSS_BUTIN * (0.5 + 0.5 * c["degats"] / meilleur) * (1.0 if mort else 0.5)
        xp = int((data.JUNGLE_XP[0] + data.JUNGLE_XP[1] * p["etage"]) * camps)
        p["golds"] += int((data.JUNGLE_GOLDS[0] + data.JUNGLE_GOLDS[1] * p["etage"]) * camps) + (20 if mort else 5)
        possedees = db.cartes(g, int(cle))
        for cid in [x for x in p["equipe"].split(",") if x in possedees][:3]:
            combat.gagner_xp(cid, possedees[cid], xp)
            db.sauver_carte(g, int(cle), cid, possedees[cid]["niveau"], possedees[cid]["xp"], possedees[cid]["etoiles"])
        if mort and tueur == int(cle):
            carte = combat.tirer(p, taux=data.TAUX_BOSS)
            cartes.append(carte)
            c["pack"] = f"{data.EMOJIS[data.CARTES[carte]['rarete']]} **{data.CARTES[carte]['nom']}** · {donner(p, carte)}"
        db.sauver(p)
    if mort:
        m["buff"] = {"cle": etat["cle"], "nom": etat["nom"], "stat": etat["stat"], "valeur": etat["valeur"], "texte": etat["texte"],
                     "fin": time.time() + data.BOSS_BUFF_HEURES * 3600}
        pack = coups.get(str(tueur), {}).get("pack", "")
        fin = (f"## 💀 Vaincu !\n{'⚡ **' + pseudo + '** vole le boss au Châtiment' if vol else '⚔️ **' + pseudo + '** porte le coup fatal'} "
               f"et gagne un pack à taux doublés : {pack}\n\n"
               f"🎉 **Tout le serveur gagne {etat['texte']}** pendant {data.BOSS_BUFF_HEURES} heures.\n"
               "Tous les participants reçoivent des golds et de l'XP pour leurs cartes, selon leurs dégâts.")
    else:
        fin = (f"## 💨 Il s'est enfui avec {max(0, round(100 * etat['pv'] / etat['pvmax']))} % de ses PV.\n"
               "Pas de buff cette fois. Les participants reçoivent une petite part du butin.") if coups else "## 💨 Personne n'est venu : il est reparti."
    m["boss"]["termine"] = True
    dernier = dict(m["boss"])
    m["boss"], m["coups"] = None, {}
    db.sauver_monde(g, m)
    m["boss"], m["coups"] = dernier, coups   # gardés en mémoire pour l'affichage final
    return fin, cartes


async def apparaitre(guilde, cle=None):
    """Fait apparaître un boss dans le salon des boss du serveur. Renvoie un texte de résultat."""
    salon = trouver_salon(guilde, data.SALON_BOSS)
    if not salon:
        return "Le salon des boss n'existe pas encore : lance `/installer`."
    m = db.monde(guilde.id)
    if m["boss"]:
        return "Un boss est déjà là."
    m["numero"] += 1
    if cle is None:
        drakes = [b for b in data.BOSS_MONDE if b[0] != "nashor"]
        cle = "nashor" if m["numero"] % data.BOSS_NASHOR == 0 else random.choice(drakes)[0]
    choix = next((b for b in data.BOSS_MONDE if b[0] == cle), data.BOSS_MONDE[0])
    joueurs = db.tous_les_joueurs(guilde.id)
    forces = []
    for j in joueurs:
        possedees = db.cartes(guilde.id, j["user_id"])
        ids = [c for c in j["equipe"].split(",") if c in possedees][:3]
        if ids:
            forces.append(combat.puissance_equipe(ids, possedees))
    forces.sort()
    reference = forces[len(forces) // 2] if forces else 1
    cible = max(2, round(len(forces) * 0.5))   # nombre de joueurs attendus : la moitié des inscrits, deux au minimum
    pvmax = int(1000 * cible * data.BOSS_ATTAQUES * (1.5 if cle == "nashor" else 1.0))
    chemin = cartes_img._image_boss(choix[1])
    image = ("boss" + os.path.splitext(chemin)[1]) if chemin else None
    m["boss"] = {"cle": choix[0], "nom": choix[1], "stat": choix[2], "valeur": choix[3], "texte": choix[4], "pv": pvmax, "pvmax": pvmax,
                 "fin": time.time() + data.BOSS_DUREE, "reference": reference, "journal": [], "image": image, "salon": salon.id, "message": 0}
    m["coups"] = {}
    role = discord.utils.get(guilde.roles, name=data.ROLE_BOSS)
    try:
        message = await reessayer(lambda: salon.send(
            content=(role.mention + " " if role else "") + f"**{choix[1]}** vient d'apparaître !", embed=embed_boss(m), view=VueBoss(),
            files=[discord.File(chemin, filename=image)] if chemin else [],
            allowed_mentions=discord.AllowedMentions(roles=True)))
    except ERREURS_RESEAU as erreur:
        return f"Je n'ai pas pu poster le boss ({type(erreur).__name__}). Vérifie que j'ai le droit d'écrire dans {salon.mention}."
    m["boss"]["message"] = message.id
    db.sauver_monde(guilde.id, m)
    return f"{choix[1]} est apparu dans {salon.mention}."


async def surveiller_boss():
    """Fait apparaître les boss aux heures prévues et renvoie ceux dont le temps est écoulé."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            maintenant = time.localtime()
            creneau = time.strftime("%Y-%m-%d-", maintenant) + str(maintenant.tm_hour)
            for guilde in bot.guilds:
                m = db.monde(guilde.id)
                etat = m["boss"]
                if etat and etat["fin"] < time.time():   # temps écoulé : il s'enfuit
                    fin, _ = conclure_boss(guilde.id, m)
                    try:
                        salon = guilde.get_channel(etat.get("salon", 0))
                        if salon and etat.get("message"):
                            message = await salon.fetch_message(etat["message"])
                            await message.edit(content=None, embed=embed_boss(m, fin), view=None)
                    except ERREURS_RESEAU:
                        pass
                elif not etat and maintenant.tm_hour in data.BOSS_HEURES and maintenant.tm_min < 5 and m["creneau"] != creneau:
                    m["creneau"] = creneau
                    db.sauver_monde(guilde.id, m)
                    await apparaitre(guilde)
        except Exception as erreur:   # la surveillance ne doit jamais s'arrêter
            print(f"Boss de salon : {type(erreur).__name__} : {erreur}")
        await asyncio.sleep(20)


class PanneauBoss(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Me prévenir", emoji="🔔", style=discord.ButtonStyle.success, custom_id="f:boss_role")
    async def prevenir(self, i, _):
        role = discord.utils.get(i.guild.roles, name=data.ROLE_BOSS)
        if not role:
            await i.response.send_message(f"Le rôle {data.ROLE_BOSS} n'existe pas encore : un admin doit lancer `/installer`.", ephemeral=True)
            return
        try:
            if role in i.user.roles:
                await i.user.remove_roles(role, reason="Ne veut plus être prévenu des boss")
                await i.response.send_message("🔕 Tu ne seras plus mentionné à l'apparition d'un boss.", ephemeral=True)
            else:
                await i.user.add_roles(role, reason="Veut être prévenu des boss")
                await i.response.send_message(f"🔔 Tu as le rôle **{data.ROLE_BOSS}** : tu seras mentionné à chaque apparition. Reclique pour l'enlever.", ephemeral=True)
        except discord.HTTPException:
            await i.response.send_message("Je n'ai pas pu changer ton rôle : il me manque la permission **Gérer les rôles**, ou mon rôle est placé trop bas.", ephemeral=True)

    @discord.ui.button(label="Buff et horaires", emoji="🐉", style=discord.ButtonStyle.secondary, custom_id="f:boss_info")
    async def infos(self, i, _):
        m = db.monde(i.guild_id)
        buff = buff_actif(i.guild_id)
        lignes = [f"**Buff du serveur** : {buff['texte']} ({buff['nom']}), encore <t:{int(buff['fin'])}:R>." if buff else "**Buff du serveur** : aucun pour l'instant.",
                  "**Apparitions** : tous les jours à " + ", ".join(f"{h} h" for h in data.BOSS_HEURES) + ".",
                  "**Boss en cours** : " + (f"{m['boss']['nom']}, juste au-dessus !" if m["boss"] else "aucun."), "",
                  "**Les buffs possibles**"] + [f"• {nom} : {texte}" for _, nom, _, _, texte in data.BOSS_MONDE]
        await i.response.send_message(embed=discord.Embed(color=COULEUR, description="# 🐉 Boss de salon\n" + "\n".join(lignes)), ephemeral=True)


# ================================= ARÈNE =====================================
def aujourdhui():
    return time.strftime("%Y-%m-%d")


def debut_du_jour():
    """Instant de minuit ce matin, à l'heure de l'ordinateur qui fait tourner le bot."""
    return time.mktime(time.strptime(aujourdhui(), "%Y-%m-%d"))


async def prevenir_defenseur(guilde, q, nom_attaquant, perce, variation):
    """Envoie au défenseur un message privé que lui seul voit. Au plus un message toutes les 10 minutes :
    le reste se retrouve dans « Mon historique »."""
    if not q["arene_notif"] or time.time() - q["arene_message"] < data.ARENE_DELAI_MESSAGE:
        return
    e = discord.Embed(color=0xC53030 if perce else 0x2F855A, description=(
        f"## 🏟️ Arène · {guilde.name if guilde else '2Hot4Deck'}\n"
        + (f"💥 **{nom_attaquant}** a percé ta défense." if perce else f"🛡️ Ta défense a repoussé **{nom_attaquant}**.")
        + f"\n{'+' if variation > 0 else ''}{variation} pts → {texte_rang(q['arene_points'])}"))
    e.set_footer(text="Détail dans « Mon historique », salon de l'arène. Le bouton « Notifications » coupe ces messages.")
    try:
        utilisateur = await bot.fetch_user(q["user_id"])
        await utilisateur.send(embed=e)
        q["arene_message"] = time.time()
        db.sauver(q)
    except discord.HTTPException:
        pass   # messages privés fermés : il verra l'alerte dans l'arène


def combats_restants(p):
    faits = p["arene_combats"] if p["arene_jour"] == aujourdhui() else 0
    return max(0, data.ARENE_COMBATS_PAR_JOUR - faits)


def texte_rang(points):
    _, nom, emoji = combat.rang_arene(points)
    return f"{emoji} {nom} · {points} pts"


async def maj_rang(membre, points):
    """Donne au membre le rôle Discord de son rang d'arène et retire les autres rôles de rang."""
    if not isinstance(membre, discord.Member):
        return
    _, nom, _ = combat.rang_arene(points)
    noms = {r[1] for r in data.ARENE_RANGS}
    voulu = discord.utils.get(membre.guild.roles, name=nom)
    try:
        en_trop = [r for r in membre.roles if r.name in noms and r.name != nom]
        if en_trop:
            await membre.remove_roles(*en_trop, reason="Changement de rang d'arène")
        if voulu and voulu not in membre.roles:
            await membre.add_roles(voulu, reason="Rang d'arène")
    except discord.HTTPException:
        pass   # permission manquante, ou rôle du bot placé trop bas


def equipe_defense(q, possedees):
    """Équipe de défense d'un joueur : celle qu'il a enregistrée, sinon son équipe du moment."""
    ids = [c for c in q["defense"].split(",") if c in possedees][:3]
    buff = buff_actif(q["guild_id"])
    for c in ids:
        possedees[c]["ligne"] = ligne_de(q, c)
        possedees[c]["buff"] = (buff["stat"], buff["valeur"]) if buff else None
    return ids or equipe_ids(q, possedees)


async def combat_arene(i, adversaire_id=None, facteur=None):
    """Combat d'arène contre l'équipe de défense d'un joueur (adversaire_id) ou contre un reflet (facteur)."""
    p = await charger(i)
    if not p:
        return
    if combats_restants(p) <= 0:
        await i.response.edit_message(content="Tu as utilisé tous tes combats d'arène pour aujourd'hui. Reviens demain !", embed=None, view=None, attachments=[])
        return
    possedees = db.cartes(i.guild_id, i.user.id)
    ids = equipe_ids(p, possedees)
    if not ids:
        await i.response.edit_message(content="Ton équipe est vide. Compose-la dans le salon de la collection.", embed=None, view=None, attachments=[])
        return
    equipe = combat.equipe_joueur(ids, possedees)
    q = db.get_joueur(i.guild_id, adversaire_id) if adversaire_id else None
    if q and db.combats_contre(i.guild_id, i.user.id, adversaire_id, debut_du_jour()) >= data.ARENE_MAX_CONTRE_UN_JOUEUR:
        await i.response.edit_message(content=f"Tu as déjà affronté ce joueur {data.ARENE_MAX_CONTRE_UN_JOUEUR} fois aujourd'hui. Choisis-en un autre.",
                                      embed=None, view=None, attachments=[])
        return
    if q:
        cartes_q = db.cartes(i.guild_id, adversaire_id)
        adversaires = combat.equipe_joueur(equipe_defense(q, cartes_q), cartes_q, camp=1)
        nom = q["pseudo"] or "un joueur"
        gain = data.ARENE_GAIN + max(0, min(10, (q["arene_points"] - p["arene_points"]) // 20))
        perte = data.ARENE_PERTE
    else:
        facteur = facteur if facteur in data.ARENE_REFLETS else 1.0
        adversaires = combat.reflets(equipe, facteur)
        nom = "ton reflet"
        gain, perte = data.ARENE_REFLETS[facteur]
    if not adversaires:
        await i.response.edit_message(content="Cet adversaire n'a plus d'équipe.", embed=None, view=None, attachments=[])
        return

    depart = combat.photo(equipe + adversaires)
    victoire, tours = combat.simuler_detail(equipe, adversaires)
    noter_combat(p, "arene", nom, victoire, len(tours), tours[-1]["etat"], possedees, adversaire_id if q else None)
    avant = p["arene_points"]
    rang_avant = combat.rang_arene(avant)[0]
    p["arene_points"] = max(0, avant + (gain if victoire else -perte))
    p["arene_victoires" if victoire else "arene_defaites"] += 1
    p["arene_combats"] = (p["arene_combats"] if p["arene_jour"] == aujourdhui() else 0) + 1
    p["arene_jour"] = aujourdhui()
    db.sauver(p)
    variation_defense = 0
    if q:   # le défenseur gagne ou perd quelques points lui aussi
        avant_q = q["arene_points"]
        protege = db.defenses_perdues(i.guild_id, adversaire_id, debut_du_jour()) >= data.ARENE_PERTES_DEFENSE_PAR_JOUR
        perte_defense = 0 if protege else data.ARENE_DEFENSE_PERDUE   # plafond de pertes quotidien du défenseur
        q["arene_points"] = max(0, avant_q + (-perte_defense if victoire else data.ARENE_DEFENSE_TENUE))
        variation_defense = q["arene_points"] - avant_q
        db.sauver(q)
    db.noter_combat(i.guild_id, i.user.id, adversaire_id if q else 0, p["pseudo"] or "Un joueur", nom,
                    victoire, p["arene_points"] - avant, variation_defense)

    rang_apres, nom_rang, emoji_rang = combat.rang_arene(p["arene_points"])
    variation = p["arene_points"] - avant
    titre = f"🏟️ Arène · contre {nom}"
    moments = [l for t in tours for l in t["journal"] if not l.startswith("💫")]
    final = embed_combat(titre, f"{'🏆 Victoire' if victoire else '💀 Défaite'} en {len(tours)} tours", tours[-1]["etat"], moments[-6:],
                         0x2F855A if victoire else 0xC53030)
    promo = f"\n🎉 **Tu montes {nom_rang} !**" if rang_apres > rang_avant else f"\n📉 Tu redescends {nom_rang}." if rang_apres < rang_avant else ""
    final.add_field(name="Classement", value=f"{'+' if variation >= 0 else ''}{variation} points → {texte_rang(p['arene_points'])}{promo}", inline=False)
    cartes_niveau = champ_compte(p, final, "arene_victoire" if victoire else "arene_defaite")
    db.sauver(p)
    final.set_footer(text=f"Combats restants aujourd'hui : {combats_restants(p)}")
    vedette = max(ids, key=lambda c: combat.puissance(c, possedees[c]["niveau"], possedees[c]["etoiles"]))
    dernier_ulti = [c for t in tours for c in t["ultis"] if c]
    fichiers_fin = illustrer(final, (dernier_ulti[-1] if dernier_ulti else vedette) if victoire else None,
                             None if victoire else ennemi_illustre(tours[-1]["etat"]))
    await animer_combat(i, titre, depart, tours, final, None, fichiers_fin, vedette, remplacer=True)

    await maj_rang(i.user, p["arene_points"])
    if q:
        await prevenir_defenseur(i.guild, q, p["pseudo"] or "Un joueur", victoire, variation_defense)
    if q and i.guild:
        try:
            await maj_rang(await i.guild.fetch_member(adversaire_id), q["arene_points"])
        except discord.HTTPException:
            pass
    # Les combats restent privés (bouton « Mon historique »). Seules les montées de rang sont annoncées à tous.
    if rang_apres > rang_avant:
        try:
            await i.channel.send(f"🎉 **{p['pseudo'] or 'Un joueur'}** monte **{emoji_rang} {nom_rang}** !",
                                 allowed_mentions=discord.AllowedMentions.none())
        except (discord.HTTPException, AttributeError):
            pass


class ChoixAdversaire(discord.ui.View):
    """Jusqu'à trois adversaires : les joueurs les plus proches au classement, complétés par des reflets d'entraînement."""
    def __init__(self, p, autres):
        super().__init__(timeout=300)
        mon_rang = combat.rang_arene(p["arene_points"])[0]   # seulement des joueurs à un rang d'écart au plus
        autres = [q for q in autres if abs(combat.rang_arene(q["arene_points"])[0] - mon_rang) <= 1]
        proches = sorted(autres, key=lambda q: abs(q["arene_points"] - p["arene_points"]))[:3]
        for q in proches:
            epuise = db.combats_contre(p["guild_id"], p["user_id"], q["user_id"], debut_du_jour()) >= data.ARENE_MAX_CONTRE_UN_JOUEUR
            b = discord.ui.Button(label=(f"{q['pseudo'] or 'Joueur'} · {texte_rang(q['arene_points'])}" + (" · déjà affronté" if epuise else ""))[:80],
                                  emoji="⚔️", style=discord.ButtonStyle.danger, disabled=epuise)
            b.callback = self.contre_joueur(q["user_id"])
            self.add_item(b)
        for facteur in list(data.ARENE_REFLETS)[:3 - len(proches)]:
            gain, _ = data.ARENE_REFLETS[facteur]
            b = discord.ui.Button(label=f"Reflet à {round(facteur * 100)} % · +{gain} pts", emoji="🪞", style=discord.ButtonStyle.secondary)
            b.callback = self.contre_reflet(facteur)
            self.add_item(b)

    @staticmethod
    def contre_joueur(user_id):
        async def clic(i):
            await combat_arene(i, adversaire_id=user_id)
        return clic

    @staticmethod
    def contre_reflet(facteur):
        async def clic(i):
            await combat_arene(i, facteur=facteur)
        return clic


# ============================ DUEL EN DIRECT =================================
en_duel = set()   # identifiants des joueurs en plein duel


class Duel(discord.ui.View):
    """Duel tour par tour entre deux joueurs, visible par tout le salon. Sans limite et sans points de classement.
    L'ordre de jeu dépend de la vitesse : chaque champion joue quand sa jauge d'action est pleine."""
    DELAI = 90   # secondes pour jouer une action, sinon forfait

    def __init__(self, membres, equipes, guild_id=0, classe=False):
        super().__init__(timeout=self.DELAI)
        self.guild_id, self.classe = guild_id, classe
        self.membres = membres                      # {camp: membre Discord}
        self.tous = equipes[0] + equipes[1]
        for u in equipes[random.randint(0, 1)]:
            u["action"] += 1   # à vitesse égale, le camp qui passe devant est tiré au sort
        self.manche = 0   # nombre d'actions jouées
        self.journal, self.actif, self.message, self.fini = [], None, None, False
        self.avancer()

    def vivants(self, camp):
        return [u for u in self.tous if u["camp"] == camp and u["pv"] > 0]

    def avancer(self):
        """Passe à la prochaine unité dont la jauge d'action est pleine (les plus rapides jouent plus souvent)."""
        while self.gagnant() is None:
            u = combat.suivant(self.tous)
            self.manche += 1
            if not combat.commencer_action(u, self.tous, self.journal):
                continue
            self.actif = u
            if self.gagnant() is None:
                self.construire()
            return

    def gagnant(self):
        """Camp vainqueur si l'une des deux équipes est à terre, sinon None."""
        for camp in (0, 1):
            if not self.vivants(camp):
                return 1 - camp
        return None

    def construire(self):
        self.clear_items()
        u = self.actif
        for cible in combat.cibles_possibles(u, self.tous):
            b = discord.ui.Button(label=f"Attaquer {cible['nom']}"[:80], emoji="🗡️", style=discord.ButtonStyle.secondary, row=0)
            b.callback = self.choix(False, cible)
            self.add_item(b)
        if u["cout"] and u["jauge"] >= u["cout"]:
            if combat.ulti_cible(u):
                for cible in combat.cibles_possibles(u, self.tous):
                    b = discord.ui.Button(label=f"{u['ulti']} → {cible['nom']}"[:80], emoji="✨", style=discord.ButtonStyle.primary, row=1)
                    b.callback = self.choix(True, cible)
                    self.add_item(b)
            else:
                b = discord.ui.Button(label=u["ulti"][:80], emoji="✨", style=discord.ButtonStyle.primary, row=1)
                b.callback = self.choix(True, None)
                self.add_item(b)
        if u["kit"] == "Soraka":   # son passif : soigner un allié au lieu d'attaquer, ou passer
            for allie in [a for a in self.vivants(u["camp"]) if a is not u and a["pv"] < a["pvmax"]][:2]:
                b = discord.ui.Button(label=f"Soigner {allie['nom']}"[:80], emoji="💚", style=discord.ButtonStyle.success, row=2)
                b.callback = self.choix(False, allie, "soin")
                self.add_item(b)
            b = discord.ui.Button(label="Passer", emoji="⏭️", style=discord.ButtonStyle.secondary, row=2)
            b.callback = self.choix(False, None, "passer")
            self.add_item(b)
        abandon = discord.ui.Button(label="Abandonner", emoji="🏳️", style=discord.ButtonStyle.danger, row=3)
        abandon.callback = self.abandonner
        self.add_item(abandon)

    def embed(self, titre=None, couleur=COULEUR):
        u = self.actif
        if titre is None:
            titre = f"Action {self.manche} · au tour de {self.membres[u['camp']].display_name}\n### ▶️ {u['nom']} doit agir"
        genre = "🏆 Duel classé" if self.classe else "🤝 Duel amical"
        e = EmbedScene(color=couleur, description=f"# {genre}\n## {titre}\n" + "\n".join(self.journal[-5:]))
        try:
            e.scene = cartes_img.scene(combat.photo(self.tous), self.membres[0].display_name, self.membres[1].display_name, self.journal[-2:],
                                       None if self.fini else self.tous.index(u))
        except Exception:
            e.scene = None
        for camp in (0, 1):
            if e.scene is not None:
                break
            lignes = [("▶️ " if x is u and not self.fini else "") + ligne_unite(x) for x in self.tous if x["camp"] == camp]
            e.add_field(name=f"Équipe de {self.membres[camp].display_name}", value="\n".join(lignes), inline=False)
        if not self.fini:
            e.add_field(name="Prochains à jouer", inline=False,
                        value=" → ".join(("🔵 " if x["camp"] == 0 else "🔴 ") + x["nom"] for x in combat.prochains(self.tous, 5)))
            e.set_footer(text=f"🔵 {self.membres[0].display_name} · 🔴 {self.membres[1].display_name} · l'ordre dépend de la vitesse")
        return e

    async def interaction_check(self, i):
        if i.user.id != self.membres[self.actif["camp"]].id:
            message = "Ce n'est pas ton tour." if i.user.id in (self.membres[0].id, self.membres[1].id) else "Tu es spectateur de ce duel."
            await i.response.send_message(message, ephemeral=True)
            return False
        return True

    def choix(self, ulti, cible, special=None):
        async def clic(i):
            if self.fini or (cible is not None and cible["pv"] <= 0):
                return
            combat.jouer_action(self.actif, self.tous, ulti, cible, self.journal, special)
            self.avancer()
            vainqueur = self.gagnant()
            if vainqueur is not None:
                await self.terminer(vainqueur, i, f"🏆 Victoire de {self.membres[vainqueur].display_name} en {self.manche} actions")
                return
            e = self.embed()
            await i.response.edit_message(content=f"Au tour de {self.membres[self.actif['camp']].mention}", embed=e, view=self,
                                          attachments=illustrer(e, self.actif["cid"]))
        return clic

    async def abandonner(self, i):
        camp = self.actif["camp"]
        self.journal.append(f"🏳️ {self.membres[camp].display_name} abandonne.")
        await self.terminer(1 - camp, i, f"🏆 Victoire de {self.membres[1 - camp].display_name} par abandon")

    async def terminer(self, gagnant, i=None, titre=""):
        self.fini = True
        self.stop()
        en_duel.difference_update({self.membres[0].id, self.membres[1].id})
        perdant = 1 - gagnant
        # Classement : seuls les duels classés déplacent des points. Le lanceur du défi est le camp 0.
        variations, montee, montees_compte = {0: 0, 1: 0}, None, {0: [], 1: []}
        joueurs = {c: db.get_joueur(self.guild_id, self.membres[c].id) for c in (0, 1)}
        if joueurs[0]:   # noté du point de vue du lanceur du défi (camp 0)
            noter_combat(joueurs[0], "duel classé" if self.classe else "duel amical", titre or "", gagnant == 0, self.manche,
                         combat.photo(self.tous), None, self.membres[1].id)
        if self.classe and all(joueurs.values()):
            for camp, delta in ((gagnant, data.DUEL_GAIN), (perdant, -data.DUEL_PERTE)):
                q = joueurs[camp]
                avant = q["arene_points"]
                q["arene_points"] = max(0, avant + delta)
                q["arene_victoires" if camp == gagnant else "arene_defaites"] += 1
                variations[camp] = q["arene_points"] - avant
                montees_compte[camp] = gagner_xp_compte(q, "duel_victoire" if camp == gagnant else "duel_defaite")[0]
                db.sauver(q)
                if combat.rang_arene(q["arene_points"])[0] > combat.rang_arene(avant)[0]:
                    montee = camp
        if all(joueurs.values()):
            db.noter_combat(self.guild_id, self.membres[0].id, self.membres[1].id, self.membres[0].display_name,
                            self.membres[1].display_name, gagnant == 0, variations[0], variations[1], mode="duel", classe=self.classe)
        e = self.embed(titre, 0x2F855A)
        vedettes = self.vivants(gagnant) or [u for u in self.tous if u["camp"] == gagnant]
        fichiers = illustrer(e, vedettes[0]["cid"])
        if self.classe and all(joueurs.values()):
            e.add_field(name="Classement", inline=False, value="\n".join(
                f"**{self.membres[c].display_name}** : {'+' if variations[c] > 0 else ''}{variations[c]} pts → {texte_rang(joueurs[c]['arene_points'])}"
                for c in (gagnant, perdant)))
        else:
            e.set_footer(text="Duel amical : aucun point en jeu. Vous pouvez en relancer un tout de suite.")
        for c in (0, 1):
            if montees_compte[c]:
                e.add_field(name=f"⭐ {self.membres[c].display_name}", value="\n".join(montees_compte[c])[:1024], inline=False)
        contenu = f"🏆 {self.membres[gagnant].mention} remporte le duel contre {self.membres[perdant].mention} !"
        if montee is not None:
            _, nom_rang, emoji_rang = combat.rang_arene(joueurs[montee]["arene_points"])
            contenu += f"\n🎉 **{self.membres[montee].display_name}** monte **{emoji_rang} {nom_rang}** !"
        try:
            if i:
                await i.response.edit_message(content=contenu, embed=e, view=None, attachments=fichiers)
            elif self.message:
                await self.message.edit(content=contenu, embed=e, view=None, attachments=fichiers)
        except discord.HTTPException:
            pass
        if self.classe and all(joueurs.values()):
            for c in (0, 1):
                await maj_rang(self.membres[c], joueurs[c]["arene_points"])

    async def on_timeout(self):
        if self.fini:
            return
        camp = self.actif["camp"]
        self.journal.append(f"⏱️ {self.membres[camp].display_name} n'a pas joué à temps.")
        await self.terminer(1 - camp, None, f"🏆 Victoire de {self.membres[1 - camp].display_name} par forfait")


def duels_classes_restants(guild_id, user_id):
    return max(0, data.DUELS_CLASSES_PAR_JOUR - db.duels_classes(guild_id, user_id, debut_du_jour()))


def duel_classe_possible(guild_id, a, b):
    """Un duel compte pour le classement si les deux joueurs ont encore un duel classé aujourd'hui
    et ne se sont pas déjà affrontés en classé dans la journée."""
    return (duels_classes_restants(guild_id, a) > 0 and duels_classes_restants(guild_id, b) > 0
            and db.duel_classe_entre(guild_id, a, b, debut_du_jour()) == 0)


class Defi(discord.ui.View):
    """Invitation à un duel : seul le joueur défié peut répondre."""
    def __init__(self, lanceur, cible):
        super().__init__(timeout=120)
        self.lanceur, self.cible, self.message = lanceur, cible, None

    async def interaction_check(self, i):
        if i.user.id != self.cible.id:
            await i.response.send_message("Ce défi ne t'est pas adressé.", ephemeral=True)
            return False
        return True

    def liberer(self):
        en_duel.difference_update({self.lanceur.id, self.cible.id})
        self.stop()

    @discord.ui.button(label="Accepter", emoji="⚔️", style=discord.ButtonStyle.success)
    async def accepter(self, i, _):
        equipes = {}
        for camp, membre in ((0, self.lanceur), (1, self.cible)):
            p = db.get_joueur(i.guild_id, membre.id)
            possedees = db.cartes(i.guild_id, membre.id)
            ids = equipe_ids(p, possedees) if p else []
            if not ids:
                self.liberer()
                await i.response.edit_message(content=f"Duel annulé : {membre.display_name} n'a pas d'équipe.", view=None)
                return
            equipes[camp] = combat.equipe_joueur(ids, possedees, camp=camp)
        self.stop()
        duel = Duel({0: self.lanceur, 1: self.cible}, equipes, i.guild_id, duel_classe_possible(i.guild_id, self.lanceur.id, self.cible.id))
        e = duel.embed()
        await i.response.edit_message(content=f"Au tour de {duel.membres[duel.actif['camp']].mention}", embed=e, view=duel,
                                      attachments=illustrer(e, duel.actif["cid"]))
        duel.message = i.message

    @discord.ui.button(label="Refuser", emoji="✖️", style=discord.ButtonStyle.secondary)
    async def refuser(self, i, _):
        self.liberer()
        await i.response.edit_message(content=f"{self.cible.display_name} a refusé le duel de {self.lanceur.display_name}.", view=None)

    async def on_timeout(self):
        self.liberer()
        try:
            if self.message:
                await self.message.edit(content=f"Le défi de {self.lanceur.display_name} est resté sans réponse.", view=None)
        except discord.HTTPException:
            pass


class ChoixDuel(discord.ui.View):
    """Menu pour choisir le joueur à défier."""
    def __init__(self):
        super().__init__(timeout=120)
        self.menu = discord.ui.UserSelect(placeholder="Qui veux-tu défier ?", min_values=1, max_values=1)
        self.menu.callback = self.defier
        self.add_item(self.menu)

    async def defier(self, i):
        cible = self.menu.values[0]
        erreur = None
        if cible.id == i.user.id:
            erreur = "Tu ne peux pas te défier toi-même."
        elif getattr(cible, "bot", False):
            erreur = "Les bots ne se battent pas en duel."
        elif not db.get_joueur(i.guild_id, cible.id):
            erreur = f"{cible.display_name} n'a pas encore de compte."
        elif i.user.id in en_duel or cible.id in en_duel:
            erreur = "L'un de vous deux est déjà en duel ou a un défi en attente."
        if erreur:
            await i.response.edit_message(content=erreur, view=None)
            return
        en_duel.update({i.user.id, cible.id})
        defi = Defi(i.user, cible)
        await i.response.edit_message(content=f"Défi envoyé à {cible.display_name}.", view=None)
        try:
            genre = "**duel classé**" if duel_classe_possible(i.guild_id, i.user.id, cible.id) else "duel amical (sans points)"
            defi.message = await i.channel.send(
                f"⚔️ {cible.mention}, **{i.user.display_name}** te défie en {genre} ! Tu as 2 minutes pour répondre.", view=defi)
        except discord.HTTPException:
            defi.liberer()


def embed_classement_arene(guild_id):
    """Classement commun à l'arène et aux duels."""
    lignes = [f"**{n}.** {texte_rang(q['arene_points'])} · **{q['pseudo'] or 'Joueur'}** · {q['arene_victoires']} V / {q['arene_defaites']} D"
              for n, q in enumerate(db.classement_arene(guild_id), 1)]
    return discord.Embed(color=COULEUR, description="# 🏆 Classement\n" + ("\n".join(lignes) or "Personne n'a encore combattu."))


class PanneauDuels(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Défier un joueur", emoji="🤺", style=discord.ButtonStyle.success, custom_id="f:duel")
    async def duel(self, i, _):
        p = await charger(i)
        if not p:
            return
        if await verrouille(i, p, "duels"):
            return
        if not equipe_ids(p, db.cartes(i.guild_id, i.user.id)):
            await i.response.send_message("Ton équipe est vide. Compose-la dans le salon de la collection.", ephemeral=True)
            return
        restants = duels_classes_restants(i.guild_id, i.user.id)
        await i.response.send_message(
            f"## 🤺 Duel en direct\nChoisis un joueur. S'il accepte, vous jouez tour par tour dans ce salon, devant tout le monde.\n"
            f"Duels classés restants aujourd'hui : **{restants}**. Ensuite, les duels sont amicaux et illimités.", view=ChoixDuel(), ephemeral=True)

    @discord.ui.button(label="Mes duels", emoji="📖", style=discord.ButtonStyle.primary, custom_id="f:mes_duels")
    async def mes_duels(self, i, _):
        p = await charger(i)
        if not p:
            return
        duels = [c for c in db.historique_arene(i.guild_id, i.user.id, 40) if c["mode"] == "duel"][:15]
        lignes = []
        for c in duels:
            moi_lanceur = c["attaquant"] == i.user.id
            gagne = bool(c["victoire"]) == moi_lanceur
            autre = c["nom_defenseur"] if moi_lanceur else c["nom_attaquant"]
            pts = c["points_attaquant"] if moi_lanceur else c["points_defenseur"]
            detail = f"{'+' if pts > 0 else ''}{pts} pts" if c["classe"] else "amical"
            lignes.append(f"{'🏆 Gagné' if gagne else '💀 Perdu'} contre **{autre}** · {detail} · <t:{int(c['moment'])}:R>")
        e = discord.Embed(color=COULEUR, description=(
            f"# 📖 Tes duels\n## {texte_rang(p['arene_points'])}\nDuels classés restants aujourd'hui : **{duels_classes_restants(i.guild_id, i.user.id)}**\n\n"
            + ("\n".join(lignes) or "Aucun duel pour l'instant.")))
        e.set_footer(text="Toi seul vois cet historique.")
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="Classement", emoji="🏆", style=discord.ButtonStyle.secondary, custom_id="f:top_duel")
    async def classement(self, i, _):
        await i.response.send_message(embed=embed_classement_arene(i.guild_id), ephemeral=True)

    @discord.ui.button(label="Règles", emoji="📜", style=discord.ButtonStyle.secondary, custom_id="f:regles_duel")
    async def regles(self, i, _):
        e = discord.Embed(color=COULEUR, description=(
            "# 📜 Règles du duel\n"
            "**L'ordre de jeu.** Il dépend de la vitesse : chaque champion a une jauge d'action, et joue dès qu'elle est pleine. Un champion rapide joue plus souvent, et tu peux donc jouer plusieurs fois de suite. La ligne **Prochains à jouer** montre ce qui arrive.\n"
            "**Les actions.** Attaquer une cible, ou lancer l'ulti quand la jauge est pleine. Chaque champion a son passif et son actif : ils sont décrits sur sa fiche, dans la collection.\n"
            "**Les tanks protègent.** Tant qu'un tank adverse est debout, les attaques ciblées doivent passer par lui.\n"
            f"**Le temps.** {Duel.DELAI} secondes par action, sinon forfait.\n\n"
            f"**Le classement** est le même que celui de l'arène. Les {data.DUELS_CLASSES_PAR_JOUR} premiers duels de ta journée sont classés "
            f"(un seul par adversaire) : +{data.DUEL_GAIN} pts pour le vainqueur, -{data.DUEL_PERTE} pts pour le perdant. "
            "Au-delà, les duels sont amicaux et illimités."))
        await i.response.send_message(embed=e, ephemeral=True)


class PanneauArene(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Chercher un adversaire", emoji="⚔️", style=discord.ButtonStyle.danger, custom_id="f:arene")
    async def chercher(self, i, _):
        p = await charger(i)
        if not p:
            return
        if await verrouille(i, p, "arene"):
            return
        if combats_restants(p) <= 0:
            await i.response.send_message("Tu as utilisé tous tes combats d'arène pour aujourd'hui. Reviens demain !", ephemeral=True)
            return
        autres = db.autres_joueurs(i.guild_id, i.user.id)
        subies = db.attaques_non_vues(i.guild_id, i.user.id, p["arene_vu"])
        alerte = f"\n\n🔔 **{subies} attaque(s) subie(s)** depuis ta dernière visite : regarde « Mon historique »." if subies else ""
        e = discord.Embed(color=COULEUR, description=(
            f"# 🏟️ Arène\n## {texte_rang(p['arene_points'])}\nCombats restants aujourd'hui : **{combats_restants(p)}**\n\n"
            "Choisis ton adversaire. Tu affrontes son **équipe de défense**, jouée par le bot."
            + ("\nLes reflets sont des copies de ton équipe : ils servent d'entraînement quand il manque des joueurs." if len(autres) < 3 else "") + alerte))
        await i.response.send_message(embed=e, view=ChoixAdversaire(p, autres), ephemeral=True)
        await maj_rang(i.user, p["arene_points"])

    @discord.ui.button(label="Ma défense", emoji="🛡️", style=discord.ButtonStyle.primary, custom_id="f:defense")
    async def defense(self, i, _):
        p = await charger(i)
        if not p:
            return
        possedees = db.cartes(i.guild_id, i.user.id)
        p["defense"] = ",".join(equipe_ids(p, possedees))
        db.sauver(p)
        e = embed_equipe(p, possedees)
        e.title = "🛡️ Équipe de défense enregistrée"
        e.set_footer(text="C'est ton équipe actuelle. Elle défendra à ta place, même si tu changes d'équipe ensuite. Reclique ici pour la mettre à jour.")
        await i.response.send_message(embed=e, files=image_equipe(e, p, possedees), ephemeral=True)

    @discord.ui.button(label="Mon historique", emoji="📖", style=discord.ButtonStyle.primary, custom_id="f:historique")
    async def historique(self, i, _):
        p = await charger(i)
        if not p:
            return
        lignes = []
        for c in [c for c in db.historique_arene(i.guild_id, i.user.id, 40) if c["mode"] == "arene"][:15]:
            quand = f"<t:{int(c['moment'])}:R>"
            nouveau = " 🆕" if c["defenseur"] == i.user.id and c["moment"] > p["arene_vu"] else ""
            if c["attaquant"] == i.user.id:
                pts = f"{'+' if c['points_attaquant'] >= 0 else ''}{c['points_attaquant']} pts"
                lignes.append(f"{'⚔️ Tu as battu' if c['victoire'] else '💀 Tu as perdu contre'} **{c['nom_defenseur']}** · {pts} · {quand}")
            else:
                pts = f"{'+' if c['points_defenseur'] > 0 else ''}{c['points_defenseur']} pts"
                lignes.append(f"{'🛡️💥 **' + c['nom_attaquant'] + '** a percé ta défense' if c['victoire'] else '🛡️ Ta défense a repoussé **' + c['nom_attaquant'] + '**'} · {pts} · {quand}{nouveau}")
        e = discord.Embed(color=COULEUR, description=(
            f"# 📖 Ton historique d'arène\n## {texte_rang(p['arene_points'])} · {p['arene_victoires']} V / {p['arene_defaites']} D\n"
            + ("\n".join(lignes) or "Aucun combat pour l'instant.")))
        e.set_footer(text="Toi seul vois cet historique.")
        p["arene_vu"] = time.time()
        db.sauver(p)
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="Notifications", emoji="🔔", style=discord.ButtonStyle.secondary, custom_id="f:notif")
    async def notifications(self, i, _):
        p = await charger(i)
        if not p:
            return
        p["arene_notif"] = 0 if p["arene_notif"] else 1
        db.sauver(p)
        await i.response.send_message(
            "🔔 Notifications activées : le bot t'envoie un message privé quand ta défense est attaquée." if p["arene_notif"]
            else "🔕 Notifications coupées. Tes attaques subies restent visibles dans « Mon historique ».", ephemeral=True)

    @discord.ui.button(label="Classement", emoji="🏆", style=discord.ButtonStyle.secondary, custom_id="f:top_arene")
    async def classement(self, i, _):
        await i.response.send_message(embed=embed_classement_arene(i.guild_id), ephemeral=True)

    @discord.ui.button(label="Rangs", emoji="📜", style=discord.ButtonStyle.secondary, custom_id="f:rangs")
    async def rangs(self, i, _):
        lignes = [f"{emoji} **{nom}** · {points} pts" for points, nom, emoji, _ in data.ARENE_RANGS]
        e = discord.Embed(color=COULEUR, description=(
            "# 📜 Les rangs\n" + "\n".join(lignes) +
            f"\n\n**Victoire** contre un joueur : +{data.ARENE_GAIN} pts, jusqu'à +{data.ARENE_GAIN + 10} s'il est mieux classé. **Défaite** : -{data.ARENE_PERTE} pts."
            f"\n**En défense** : +{data.ARENE_DEFENSE_TENUE} pts si ton équipe résiste, -{data.ARENE_DEFENSE_PERDUE} pts si elle tombe."
            f"\n{data.ARENE_COMBATS_PAR_JOUR} combats par jour, dont {data.ARENE_MAX_CONTRE_UN_JOUEUR} au plus contre le même joueur."
            f"\nUn défenseur ne perd des points que sur ses {data.ARENE_PERTES_DEFENSE_PAR_JOUR} premières défenses percées de la journée."
            "\nTon rang te donne le rôle Discord du même nom."))
        await i.response.send_message(embed=e, ephemeral=True)


# clé -> salon créé par /installer, bannière, texte du panneau, sujet du salon et boutons
# ============================== TOUR DES PROS =================================
# En construction : le salon est privé et seul le mode test existe. Le propriétaire y joue les trois places d'un groupe avec une copie
# des équipes de trois joueurs (data.TOUR_PROS_TEST). Rien n'est enregistré : ni essais, ni récompenses, ni progression.
MOMENTS_FORTS = ("🔮", "💀", "✨", "😤", "😇", "👑", "🦖", "👻", "⚡")


async def proprietaire_du_jeu(i):
    return await est_proprietaire(i) or (i.guild is not None and i.user.id == i.guild.owner_id)


async def avatar_de(guilde, user_id):
    """La photo de profil Discord d'un membre, en octets (None si on ne peut pas la charger)."""
    try:
        membre = guilde.get_member(user_id) or await guilde.fetch_member(user_id)
        return membre.display_name, await membre.display_avatar.with_size(128).read()
    except Exception:
        return None, None


# Les tournois de pros : les Worlds, et la LEC (même moteur, autres équipes, peu d'animation).
CIRCUITS = {
    "worlds": {"nom": "Worlds", "emoji": "🏆", "couleur": 0xECC86E, "paliers": lambda: data.TOUR_PROS, "repos": lambda: data.WORLDS_REPOS,
               "anime": True, "reposer": lambda g, u, ids, fin: db.worlds_reposer(g, u, ids, fin), "au_repos": lambda g, u: db.worlds_au_repos(g, u)},
    "lec": {"nom": "LEC", "emoji": "🇪🇺", "couleur": 0x00B4D8, "paliers": lambda: data.LEC_PALIERS, "repos": lambda: data.LEC_REPOS,
            "anime": False, "apercu": True, "reposer": lambda g, u, ids, fin: db.lec_reposer(g, u, ids, fin), "au_repos": lambda g, u: db.lec_au_repos(g, u)},
}


# Joueurs dont le prochain tournoi des Worlds (ticket rendu après le bug de 21h41) ne rapporte des packs qu'à partir de cette équipe (4 = HLE).
REPRISE_HLE = 4   # 13 octobre (22 h) : un groupe bloqué contre HLE peut reprendre directement à HLE, une fois


def jeton_reprise(g, u):
    return db.con.execute("SELECT 1 FROM operations WHERE cle=?", (f"jeton_reprise_hle_{g}_{u}",)).fetchone() is not None


REPRISES_WORLDS = {100000000000000002: 4, 100000000000000004: 4, 100000000000000003: 4}   # Joueur A, Joueur B, Joueur C

DELAI_EFFACEMENT = 5 * 60   # un tournoi (Worlds, LEC) terminé disparaît du salon au bout de 5 minutes


def effacer_plus_tard(message, delai=DELAI_EFFACEMENT):
    """Supprime un message de tournoi quelques minutes après la fin, pour garder les salons propres."""
    if not message:
        return
    async def effacer():
        await asyncio.sleep(delai)
        try:
            await message.delete()
        except Exception:
            pass
    try:
        asyncio.get_running_loop().create_task(effacer())
    except RuntimeError:
        pass


class EssaiPros(discord.ui.View):
    """Un tournoi des Worlds : trois joueurs, chacun avec les 3 cartes qu'il a inscrites. Les équipes s'enchaînent (Karmine Corp jusqu'à
    Faker) ; avant chaque match, chaque joueur envoie une de ses 3 cartes, au choix. Le tournoi s'arrête à la première défaite, ou une
    fois Faker battu. Les cartes inscrites se reposent ensuite (data.WORLDS_REPOS)."""

    def __init__(self, auteur, numero, places, guilde=None, circuit="worlds"):
        super().__init__(timeout=1800)
        self.circuit, self.cle = CIRCUITS[circuit], circuit
        self.paliers = self.circuit["paliers"]()
        self.auteur, self.numero, self.palier, self.guilde = auteur, numero, self.paliers[numero], guilde
        self.places = places          # [{"nom", "avatar", "possedees", "ids": ses 3 cartes, "user": qui la joue, "reel": vrai joueur ou place de test}]
        self.match, self.score, self.fini = 0, [], False
        self.choix = [None] * len(places)
        self.message, self.occupe = None, False
        self.poser_choix()

    @property
    def test(self):
        return not any(p.get("reel") for p in self.places)

    async def interaction_check(self, i):
        if i.user.id not in {p["user"] for p in self.places}:
            await i.response.send_message("Ce tournoi n'est pas le tien.", ephemeral=True)
            return False
        return True

    def reposer(self):
        """Met au repos les cartes inscrites des vrais joueurs (rien en mode test)."""
        for place in self.places:
            if place.get("reel") and self.guilde:
                if self.circuit["repos"]():   # LEC solo : plus de repos
                    self.circuit["reposer"](self.guilde, place["user"], place["ids"], time.time() + self.circuit["repos"]())

    def recompenser(self):
        """L'équipe du palier vient d'être éliminée : elle est débloquée pour toujours, et chacun touche ses packs Worlds. Une fois par jour,
        seul le meilleur palier compte : on ne touche que la différence avec ce qu'on a déjà eu aujourd'hui. Renvoie le texte à afficher."""
        if self.test or not self.guilde:
            return "*Mode test : aucun pack, aucune équipe débloquée.*"
        if self.cle == "lec":
            return self.recompenser_lec()
        palier, lignes, vus = self.numero + 1, [], set()
        for place in self.places:
            if place["user"] in vus:   # Worlds solo : les trois places sont au même joueur, il n'est récompensé qu'une fois
                continue
            vus.add(place["user"])
            p = db.get_joueur(self.guilde, place["user"])
            if not p:
                continue
            nouvelle = db.worlds_eliminer(self.guilde, place["user"], self.numero)
            gain = data.WORLDS_PACKS_PAR_PALIER   # chaque tournoi rapporte ses packs (le ticket limite les tournois) : total palier × 2
            if self.numero < place.get("reprise", 0):   # tournoi « rendu » : pas de packs avant l'équipe déjà atteinte
                gain = 0
            p["worlds_jour"], p["worlds_palier"] = aujourdhui(), max(palier, p["worlds_palier"] if p["worlds_jour"] == aujourdhui() else 0)
            p["packs_pro"] += gain
            p["golds"] += data.GOLDS_WORLDS_EQUIPE
            db.sauver(p)
            if gain:
                db.journal_pack(self.guilde, place["user"], "pro", gain, f"Worlds · {self.palier['equipe']}")
            lignes.append(f"**{place['nom'].split(' · trio')[0]}** : " + (f"**+{gain} packs Worlds** ({p['packs_pro']} à ouvrir)" if gain else "pas de packs (ticket rendu : déjà récompensé jusqu'à BLG)") + f" · 💰 +{data.GOLDS_WORLDS_EQUIPE}"
                          + (f" · 🔓 les cartes de {self.palier['equipe'] if self.numero < len(data.TOUR_PROS) - 1 else 'Faker'} entrent dans tes packs Worlds" if nouvelle else ""))
        return "\n".join(lignes)

    def recompenser_lec(self):
        """LEC : chaque tournoi rapporte ses packs (1, 2, 4, 6 puis 12 au total selon la dernière équipe battue), sans limite par jour.
        Atteindre la finale donne data.LEC_TICKETS_FINALE tickets Worlds, la gagner data.LEC_TICKETS_VICTOIRE de plus (data.WORLDS_TICKETS_MAX au plus)."""
        k, lignes = self.numero, []
        gain = data.LEC_PACKS[k] - (data.LEC_PACKS[k - 1] if k else 0)
        finale = k == len(self.paliers) - 2
        a_gagner = data.LEC_TICKETS_FINALE if finale else data.LEC_TICKETS_VICTOIRE if k == len(self.paliers) - 1 else 0
        vus = set()
        for place in self.places:
            if place["user"] in vus:   # LEC solo : les trois places sont au même joueur, il n'est récompensé qu'une fois
                continue
            vus.add(place["user"])
            p = db.get_joueur(self.guilde, place["user"])
            if not p:
                continue
            nouvelle = db.lec_eliminer(self.guilde, place["user"], k)
            p["packs_lec"] += gain
            db.journal_pack(self.guilde, place["user"], "lec", gain, f"LEC · {self.palier['equipe']}")
            p["golds"] += data.GOLDS_LEC_EQUIPE
            ticket = min(a_gagner, max(0, data.WORLDS_TICKETS_MAX - p["tickets_worlds"]))
            if ticket:
                p["tickets_worlds"] += ticket
            db.sauver(p)
            lignes.append(f"**{place['nom'].split(' · trio')[0]}** : **+{gain} pack{'s' if gain > 1 else ''} LEC** ({p['packs_lec']} à ouvrir) · 💰 +{data.GOLDS_LEC_EQUIPE}"
                          + (f" · 🎟️ +{ticket} ticket{'s' if ticket > 1 else ''} Worlds ({p['tickets_worlds']}/{data.WORLDS_TICKETS_MAX})" if ticket else " · 🎟️ tickets Worlds déjà au maximum" if a_gagner else "")
                          + (f" · 🔓 les cartes de {self.palier['equipe']} entrent dans tes packs LEC" if nouvelle else ""))
        return "\n".join(lignes)

    def couronner(self):
        """Faker est battu : chacun gagne un titre de champion du monde, et le serveur est prévenu."""
        if self.test or not self.guilde:
            return
        if self.cle == "lec":
            for u in {place["user"] for place in self.places}:
                p = db.get_joueur(self.guilde, u)
                if p:
                    p["lec_titres"] += 1
                    db.sauver(p)
            return
        joueurs = list(dict.fromkeys(place["user"] for place in self.places))   # Worlds solo : un seul titre
        for u in joueurs:
            p = db.get_joueur(self.guilde, u)
            if p:
                p["worlds_titres"] += 1
                db.sauver(p)
        asyncio.create_task(annoncer_champions(self.message.guild if self.message else None, joueurs))

    def terminer(self):
        if not self.fini:
            self.fini = True
            self.reposer()
            effacer_plus_tard(self.message)
        self.stop()

    async def on_timeout(self):
        self.terminer()
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    @property
    def pro(self):
        return self.palier["pros"][self.match]

    def titre(self):
        return f"{self.circuit['nom']} · {self.palier['phase']} · {self.palier['equipe']}"

    def nom_match(self):
        total = len(self.palier["pros"])
        return "Match unique" if total == 1 else f"Match {self.match + 1} sur {total}"

    def pied(self):
        return ("Mode test : rien n'est enregistré, aucune carte ne se repose. " + (texte_coach(self.guilde, self.numero) if self.cle == "worlds" else "Pas de coach de test en LEC.") if self.test
                else (f"Tournoi : à la fin (défaite, abandon ou victoire finale), vos 3 cartes inscrites se reposent {self.circuit['repos']() // 3600} h." if self.circuit["repos"]()
                      else f'LEC solo : {data.LEC_ESSAIS} tournoi{"s" if data.LEC_ESSAIS > 1 else ""} par jour, pas de repos des cartes.' if self.cle == "lec"
                      else "Worlds solo : un 🎟️ ticket, 9 cartes en 3 trios, pas de repos des cartes." if solo(self.places)
                      else "Worlds : un 🎟️ ticket par joueur et par tournoi, pas de repos des cartes."))

    def poser_choix(self):
        """Un menu par joueur (ses 3 cartes inscrites), puis le bouton de lancement."""
        self.clear_items()
        for k, place in enumerate(self.places):
            libres = [c for c in place["ids"] if c not in place.setdefault("jouees", [])] or list(place["ids"])   # une carte ne joue qu'une fois par équipe
            if self.choix[k] not in libres:   # pré-sélection : une carte libre est déjà choisie, le menu ne sert qu'à changer d'avis
                self.choix[k] = libres[0]
            menu = discord.ui.Select(placeholder=f"{place['nom']} : qui envoies-tu ?", row=k, options=[
                discord.SelectOption(label=data.CARTES[c]["nom"], value=c, default=self.choix[k] == c, description=resume_carte_worlds(place["possedees"], c))
                for c in libres])
            menu.callback = self.choisir(k, menu)
            self.add_item(menu)
        lancer = discord.ui.Button(label="Lancer le match", emoji="⚔️", style=discord.ButtonStyle.success, row=3, disabled=None in self.choix)
        lancer.callback = self.combattre
        self.add_item(lancer)
        quitter = discord.ui.Button(label="Abandonner le tournoi", style=discord.ButtonStyle.secondary, row=3)
        quitter.callback = self.abandonner
        self.add_item(quitter)

    def choisir(self, k, menu):
        async def clic(i):
            if i.user.id != self.places[k]["user"]:
                return await i.response.send_message(f"Ce menu est celui de {self.places[k]['nom']}.", ephemeral=True)
            self.choix[k] = menu.values[0]
            self.poser_choix()
            await i.response.edit_message(view=self)
        return clic

    async def abandonner(self, i):
        if i.user.id != self.auteur:
            return await i.response.send_message("Seul le chef de groupe peut abandonner le tournoi.", ephemeral=True)
        self.terminer()
        await i.response.edit_message(content="Tournoi abandonné." + ("" if self.test or not self.circuit["repos"]() else f" Les cartes inscrites se reposent {self.circuit['repos']() // 3600} h."),
                                      embed=None, view=None, attachments=[])

    def embed_pro(self):
        pseudo, poste, champions = self.pro
        lignes = []
        for c in champions:
            passif, actif = data.TEXTES_KITS.get(data.CARTES[c].get("base", c), (None, None))
            lignes.append(f"**{data.CARTES[c]['nom']}** · {data.CARTES[c]['role']}\n" + (f"Passif : {passif}\n" if passif else "") + (f"Actif : {actif}" if actif else ""))
        e = discord.Embed(color=self.circuit["couleur"], description=f"# {self.nom_match()} · {pseudo}\n{poste} · {self.palier['equipe']}\n\n" + "\n\n".join(lignes)
                          + "\n\nChaque joueur envoie **une de ses 3 cartes inscrites**. Une carte ne joue **qu'une fois par équipe** : "
                          "celle que tu envoies maintenant est bloquée pour les autres pros de cette équipe, et revient contre l'équipe suivante."
                          + (f" Éliminer {self.palier['equipe']} porte ce tournoi à **{(self.numero + 1) * data.WORLDS_PACKS_PAR_PALIER} packs Worlds**."
                             if self.cle == "worlds" else f"\n\n{self.circuit['emoji']} **{self.circuit['nom']}** · {self.palier['phase']} ({self.numero + 1}/{len(self.paliers)}) · "
                             f"battre {self.palier['equipe']} : **{data.LEC_PACKS[self.numero]} packs LEC** au total" + (f" et {data.LEC_TICKETS_FINALE} 🎟️ tickets Worlds" if self.numero == len(self.paliers) - 2 else f" et {data.LEC_TICKETS_VICTOIRE} 🎟️ ticket Worlds de plus" if self.numero == len(self.paliers) - 1 else "") + "."))
        e.set_footer(text=self.pied())
        return e

    async def intro(self):
        """L'entrée de l'équipe du palier en cours dans son arène, puis son effectif, un pro à la fois."""
        if not self.circuit["anime"]:   # LEC : pas d'entrée d'équipe, on enchaîne
            return
        palier = self.palier
        if palier.get("da") == "faker":   # Faker : le titre « The Unkillable Demon King », puis lui, avec le chut ; il est seul, pas d'effectif
            etapes = (("entree_faker", "equipe.gif", (palier["pros"][0][0], "Grande finale")),)
        else:
            etapes = None
        for nom, fichier, args in etapes or (
                ("entree_equipe", "equipe.gif", (palier["equipe"], palier["phase"], palier.get("logo"), palier.get("entree"),
                                                 palier.get("couleur", (236, 200, 110)), palier.get("clarte", 1.0))),
                ("presentation_pros", "effectif.gif", (palier["equipe"], [(pseudo.split(" (")[0], poste, photo_pro(pseudo)) for pseudo, poste, _ in palier["pros"]],
                                                       palier.get("fond"), palier.get("clarte", 1.0), palier.get("couleur", (236, 200, 110))))):
            try:
                film, duree = await dessiner(nom, *args)
            except Exception:
                film, duree = None, 0
            if film:
                e = discord.Embed(color=0xECC86E)
                e.set_image(url=f"attachment://{fichier}")
                try:
                    await self.message.edit(content=None, embed=e, view=None, attachments=[discord.File(film, fichier)])
                    await asyncio.sleep(duree + 0.5)
                except ERREURS_RESEAU:
                    pass

    async def reveler(self):
        """Fait entrer le pro du match en cours (animation), puis laisse les menus de choix sous son image."""
        pseudo, poste, champions = self.pro
        self.choix = [None] * len(self.places)
        self.poser_choix()
        e = self.embed_pro()
        try:
            if not (self.circuit["anime"] or self.circuit.get("apercu")):   # LEC : pas d'entrée d'équipe, mais l'aperçu du pro reste
                raise RuntimeError("pas d'animation")
            film, _ = await dessiner("entree_pro", {"nom": pseudo.split(" (")[0], "detail": f"{poste} · {self.palier['equipe']}", "photo": photo_pro(pseudo), "fond": self.palier.get("fond"), "clarte": self.palier.get("clarte", 1.0), "couleur": self.palier.get("couleur", (236, 190, 90)), "da": self.palier.get("da")},
                                              self.nom_match(), [{"cid": c, "nom": data.CARTES[c]["nom"]} for c in champions])
        except Exception:
            film = None
        if film:
            e.set_image(url="attachment://pro.gif")
        for essai in range(3):   # 13 octobre : une coupure réseau ne doit plus bloquer le tournoi (on réessaie, sans l'animation au dernier essai)
            avec_film = film and essai < 2
            if film and not avec_film:
                e.set_image(url=None)
            try:
                if avec_film and hasattr(film, "seek"):
                    film.seek(0)
                await self.message.edit(content=None, embed=e, view=self, attachments=[discord.File(film, "pro.gif")] if avec_film else [])
                return
            except ERREURS_RESEAU:
                await asyncio.sleep(2)

    def scene(self, etat, lignes=()):
        """Ce que l'image attend : une rangée par place avec le champion envoyé, et les trois champions du pro."""
        notres, eux = [x for x in etat if x["camp"] == 0], [x for x in etat if x["camp"] == 1]
        return [(place["nom"], [dict(notres[k], etat="joue")], place["avatar"]) for k, place in enumerate(self.places)], eux, tuple(lignes)

    async def combattre(self, i):
        if self.occupe or None in self.choix:
            return await i.response.defer()
        self.occupe = True
        await i.response.edit_message(view=None)
        pseudo, poste, champions = self.pro
        nous = combat.equipe_melee([(self.choix[k], place["possedees"]) for k, place in enumerate(self.places)])   # vrai joueur : son coach renforce sa carte
        coach = coach_de_test(self.guilde, self.numero) if self.test and self.cle == "worlds" else None
        if coach:
            combat.appliquer_coach(nous, *coach)
        force = self.palier["force"]
        if any(p.get("perso") for p in self.places):   # salon de test personnel : forces d'équipes réglées à part
            force = getattr(data, "TEST_PERSO_FORCES", {}).get(self.numero, force)
        bonus = self.palier.get("bonus", {}).get(pseudo, 1.0)
        if any(p.get("perso") for p in self.places):
            bonus = getattr(data, "TEST_PERSO_BONUS", {}).get(self.numero, {}).get(pseudo, bonus)
        eux = combat.equipe_pro(champions, force, bonus, nouveaux_kits=self.cle == "worlds" and self.palier["equipe"] in data.PROS_NOUVEAUX_KITS and self.numero < len(self.paliers) - 1)
        victoire, tours = combat.simuler_detail(nous, eux, hemorragie=True)
        pro = {"nom": pseudo.split(" (")[0], "detail": f"{poste} · {self.palier['equipe']}", "photo": photo_pro(pseudo), "fond": self.palier.get("fond"), "clarte": self.palier.get("clarte", 1.0), "couleur": self.palier.get("couleur", (236, 190, 90)), "da": self.palier.get("da")}
        sous_titre = self.nom_match()
        depart = [dict(x, pv=x["pvmax"], inflige=0) for x in tours[0]["etat"]]
        etapes = [self.scene(depart)]
        for k in sorted({round(n * (len(tours) - 1) / 4) for n in range(5)}):
            forts = [l for l in tours[k]["journal"] if l.startswith(MOMENTS_FORTS)]
            etapes.append(self.scene(tours[k]["etat"], forts[-1:]))
        try:
            film, duree = await dessiner("duel_anime", etapes, pro, self.titre(), sous_titre, tuple(self.score))
            groupes, unites, _ = self.scene(tours[-1]["etat"])
            fixe = await dessiner("duel_pro", groupes, dict(pro, unites=unites), self.titre(), sous_titre, tuple(self.score + [victoire]))
        except Exception:
            film, duree, fixe = None, 0, None
        if film:
            attente = discord.Embed(color=0xECC86E, description=f"# ⚔️ {pro['nom']} · {sous_titre}\nLe match est lancé…")
            attente.set_image(url="attachment://match.gif")
            try:
                await self.message.edit(embed=attente, view=None, attachments=[discord.File(film, "match.gif")])
                await asyncio.sleep(duree + 1)
            except ERREURS_RESEAU:
                pass
        self.score.append(victoire)
        for k, place in enumerate(self.places):   # la carte envoyée est bloquée jusqu'à la fin de cette équipe
            place.setdefault("jouees", []).append(self.choix[k])
        total = sum(x["inflige"] for x in nous) or 1
        lignes = [f"**{place['nom']}** · {nous[k]['nom']} : {nous[k]['inflige']} dégâts ({100 * nous[k]['inflige'] // total} %)" + ("" if nous[k]["pv"] > 0 else " · K.O.")
                  for k, place in enumerate(self.places)]
        moments = [l for t in tours for l in t["journal"] if l.startswith(MOMENTS_FORTS)]
        self.clear_items()
        if victoire:
            self.match += 1
            equipe_finie = self.match >= len(self.palier["pros"])
            dernier = equipe_finie and self.numero + 1 >= len(self.paliers)
            texte = f"# 🏆 {pro['nom']} est battu !\nCombat de {len(tours)} tours.\n\n" + "\n".join(lignes)
            butin = self.recompenser() if equipe_finie else ""
            if dernier and self.cle != "worlds":
                texte += f"\n\n## {self.circuit['emoji']} Vous remportez la {self.circuit['nom']} !\n" + butin
                self.couronner()
                self.terminer()
            elif dernier:
                texte += "\n\n## 👑 Vous êtes champions du monde !\nLe tournoi est gagné, du Play-In à la grande finale.\n" + butin
                self.couronner()
                self.terminer()
            elif equipe_finie:
                suivante = self.paliers[self.numero + 1]
                texte += f"\n\n## 🎉 {self.palier['phase']} remporté : {self.palier['equipe']} est éliminée !\n" + butin + f"\nProchaine étape : **{suivante['phase']}**."
                suite = discord.ui.Button(label="Équipe suivante", emoji="➡️", style=discord.ButtonStyle.success)
                suite.callback = self.vers_equipe(self.numero + 1)
                self.add_item(suite)
            else:
                texte += "\n\nUn autre joueur de l'équipe s'avance…"
                suite = discord.ui.Button(label="Pro suivant", emoji="➡️", style=discord.ButtonStyle.success)
                suite.callback = self.vers_pro(self.numero, self.match)
                self.add_item(suite)
        else:
            texte = (f"# 💀 {pro['nom']} l'emporte\nCombat de {len(tours)} tours. **Le tournoi s'arrête ici**, en {self.palier['phase']}.\n"
                     + (f"Dernière équipe éliminée : **{self.paliers[self.numero - 1]['equipe']}**. " if self.numero else "Aucune équipe éliminée. ")
                     + "Les packs déjà gagnés sont acquis.\n\n" + "\n".join(lignes)
                     + ("" if self.test or not self.circuit["repos"]() else f"\n\nVos 3 cartes inscrites se reposent **{self.circuit['repos']() // 3600} h**. Vous pouvez relancer un tournoi avec d'autres cartes."))
            self.terminer()
        e = discord.Embed(color=0x2F855A if victoire else 0xC53030, description=texte)
        if moments:
            e.add_field(name="Moments forts", value="\n".join(moments[-5:])[:1024], inline=False)
        e.set_footer(text=self.pied())
        if fixe:
            e.set_image(url="attachment://match.jpg")
        self.occupe = False
        for essai in range(3):   # 13 octobre : une coupure réseau ne doit plus laisser le tournoi sans bouton (on réessaie, sans image au dernier essai)
            avec_image = fixe and essai < 2
            if fixe and not avec_image:
                e.set_image(url=None)
            try:
                if avec_image and hasattr(fixe, "seek"):
                    fixe.seek(0)
                await self.message.edit(embed=e, view=self if self.children else None, attachments=[discord.File(fixe, "match.jpg")] if avec_image else [])
                break
            except ERREURS_RESEAU:
                await asyncio.sleep(2)

    def vers_pro(self, numero, match):
        """Bouton « Pro suivant » : ne compte qu'une fois, même si plusieurs joueurs cliquent en même temps."""
        async def clic(i):
            if (self.numero, self.match) != (numero, match) or self.occupe:
                return await i.response.defer()
            self.occupe = True
            await i.response.edit_message(view=None)
            self.occupe = False
            await self.reveler()
        return clic

    def vers_equipe(self, numero):
        """Bouton « Équipe suivante » : ne compte qu'une fois (deux clics en même temps faisaient sauter une équipe)."""
        async def clic(i):
            if self.numero + 1 != numero or self.occupe:
                return await i.response.defer()
            self.occupe = True
            self.numero = numero
            await i.response.edit_message(view=None)
            self.occupe = False
            self.palier, self.match, self.score = self.paliers[self.numero], 0, []
            for place in self.places:
                place["jouees"] = []
            await self.intro()
            await self.reveler()
        return clic

    async def suivant(self, i):
        await i.response.edit_message(view=None)
        await self.reveler()

    async def equipe_suivante(self, i):
        await i.response.edit_message(view=None)
        self.numero += 1
        self.palier, self.match, self.score = self.paliers[self.numero], 0, []
        for place in self.places:   # nouvelle équipe : les trois cartes de chacun sont de nouveau disponibles
            place["jouees"] = []
        await self.intro()
        await self.reveler()


def resume_carte_worlds(possedees, c):
    carte = possedees[c]
    return (f"Niveau {carte['niveau']} · {carte['etoiles']}★ · {data.CARTES[c]['rarete']} · {data.CARTES[c]['role']}"
            + (f" · {data.ITEMS[carte['item'][0]][0]}" if carte.get("item") else "")
            + (f" · {data.RUNES[carte['rune']][0]}" if carte.get("rune") in data.RUNES else ""))[:100]


class InscriptionWorlds(discord.ui.View):
    """Avant le tournoi : chaque joueur inscrit 3 de ses cartes disponibles (pas au repos)."""

    def __init__(self, auteur, numero, places, guilde, circuit="worlds"):
        super().__init__(timeout=900)
        self.auteur, self.numero, self.places, self.guilde, self.message, self.parti = auteur, numero, places, guilde, None, False
        self.circuit, self.cle = CIRCUITS[circuit], circuit
        self.departs = self.departs_possibles() if numero == 0 else []   # équipes où l'on peut commencer directement
        self.depart = 0
        self.offert = numero == 0 and self.cle == "worlds" and depart_blg_offert() and any(p.get("reel") for p in places)
        if self.offert:   # 14 octobre : le prochain groupe des Worlds part directement de BLG (une seule fois)
            if data.WORLDS_DEPART not in self.departs:
                self.departs = sorted(self.departs + [data.WORLDS_DEPART])
            self.depart = data.WORLDS_DEPART
        self.filtre, self.page = "Toutes", 0
        for place in places:   # l'équipe active du joueur passe en tête de sa liste
            j = db.get_joueur(guilde, place["user"]) if guilde and place.get("reel") else None
            actives = [c for c in (j["equipe"].split(",") if j and j["equipe"] else []) if c in place["dispo"]]
            place["actives"] = actives
            place["dispo"] = actives + [c for c in place["dispo"] if c not in actives]
        self.poser()

    def departs_possibles(self):
        """Une équipe battue data.DEPART_VICTOIRES fois par TOUS les vrais joueurs permet de commencer directement à elle
        (on touche alors les récompenses des équipes d'avant). LEC : seulement à data.LEC_DEPART (Team Vitality)."""
        users = {p["user"] for p in self.places if p.get("reel")}
        if not users or not self.guilde:
            return []
        table = "lec_equipes" if self.cle == "lec" else "worlds_equipes"
        def victoires(u, k):
            r = db.con.execute(f"SELECT victoires FROM {table} WHERE guild_id=? AND user_id=? AND equipe=?", (self.guilde, u, k)).fetchone()
            return r[0] if r else 0
        candidats = [data.LEC_DEPART] if self.cle == "lec" else list(data.WORLDS_DEPARTS)   # Vitality (LEC) ; BLG, et Gen.G depuis le 28 octobre (Worlds)
        departs = [k for k in candidats if all(victoires(u, k) >= data.DEPART_MINIMUM for u in users)]
        if self.cle == "worlds" and REPRISE_HLE not in departs and all(jeton_reprise(self.guilde, u) for u in users):   # tournoi bloqué : reprise à HLE
            departs.append(REPRISE_HLE)
        return sorted(departs)

    def prise_ailleurs(self, k, c):
        """LEC solo : une carte déjà inscrite dans un autre trio du même joueur ne peut pas être reprise."""
        return any(c in autre["ids"] for j, autre in enumerate(self.places) if j != k and autre["user"] == self.places[k]["user"])

    def poser(self):
        self.clear_items()
        pages, toutes = 1, []
        for k, place in enumerate(self.places):
            libres = [c for c in place["dispo"] if not self.prise_ailleurs(k, c)]
            toutes += [c for c in libres if c not in toutes]
            visibles, n = page_de_cartes(libres, self.filtre, self.page, gardees=place["ids"])
            pages = max(pages, n)
            if not visibles:
                self.add_item(discord.ui.Select(placeholder=f"{place['nom']} : aucune carte {self.filtre} libre ici", row=k, disabled=True,
                                                options=[discord.SelectOption(label="-", value="-")]))
                continue
            menu = discord.ui.Select(placeholder=f"{place['nom']} : inscris 3 cartes" + (f" · {self.filtre}" if self.filtre != "Toutes" else ""),
                                     row=k, min_values=1, max_values=min(3, len(visibles)), options=[
                discord.SelectOption(label=data.CARTES[c]["nom"], value=c, default=c in place["ids"], emoji="⭐" if c in place.get("actives", []) else None,
                                     description=resume_carte_worlds(place["possedees"], c)) for c in visibles])
            menu.callback = self.inscrire(k, menu)
            self.add_item(menu)
        if self.departs:   # 14 octobre : un bouton qui bascule entre le début et le départ direct (BLG ou Vitality)
            paliers = self.circuit["paliers"]()
            ordre = [0] + self.departs
            suivant = ordre[(ordre.index(self.depart) + 1) % len(ordre)] if self.depart in ordre else 0
            bouton = discord.ui.Button(label=(f"Départ {paliers[self.depart]['equipe']} ✅" if self.depart else f"Départ {paliers[suivant]['equipe']}")[:80],
                                       emoji="⏩", style=discord.ButtonStyle.primary if self.depart else discord.ButtonStyle.secondary, row=4)
            bouton.callback = self.basculer_depart(suivant)
            self.add_item(bouton)
        pret = all(len(p["ids"]) == 3 for p in self.places)
        lancer = discord.ui.Button(label="Commencer le tournoi", emoji="🏆", style=discord.ButtonStyle.success, row=3, disabled=not pret)
        lancer.callback = self.commencer
        self.add_item(lancer)
        quitter = discord.ui.Button(label="Annuler", style=discord.ButtonStyle.secondary, row=3)
        quitter.callback = self.annuler
        self.add_item(quitter)
        boutons_filtre(self, toutes, pages, 3, self.rafraichir_filtre)

    async def rafraichir_filtre(self, i):
        self.poser()
        await i.response.edit_message(embed=self.embed(), view=self)

    def embed(self):
        test = not any(p.get("reel") for p in self.places)
        lignes = [f"**{p['nom']}** : " + (" · ".join(data.CARTES[c]["nom"] for c in p["ids"]) if p["ids"] else "*pas encore inscrit*")
                  + (f" · 🎟️ {texte_tickets(self.guilde, p['user'])}" if self.cle == "worlds" and data.WORLDS_TICKETS and p.get("reel") else "") for p in self.places]
        depart = self.circuit["paliers"]()[self.depart or self.numero]
        e = discord.Embed(color=self.circuit["couleur"], description=f"# {self.circuit['emoji']} {self.circuit['nom']} · inscription au tournoi\n"
                          + ("" if self.cle == "lec" else "Chaque joueur inscrit **3 cartes**. Elles feront tout le tournoi : contre chaque équipe, il en envoie une par pro, "
                             "donc **chacune joue une fois par équipe**. À toi de choisir laquelle affronte quel pro.\n")
                          + f"Le tournoi commence par : **{depart['phase']}** ({depart['equipe']}), et s'arrête à la première défaite ou après la finale.\n"
                          + ("🎁 **Départ direct à BLG offert** à votre groupe (une seule fois) : le tournoi commence contre BLG, "
                             "les récompenses des équipes d'avant sont données au départ.\n" if getattr(self, "offert", False) else
                             f"⏩ **Départ direct possible** : vous avez tous déjà battu "
                             + " / ".join(self.circuit["paliers"]()[k]["equipe"] for k in self.departs)
                             + ". Le chef de groupe peut partir de là avec le bouton ⏩ ; les récompenses des équipes sautées sont données au départ.\n" if self.departs else "")
                          + ("" if test or not self.circuit["repos"]() else f"À la fin, les 3 cartes inscrites **se reposent {self.circuit['repos']() // 3600} h** ({self.circuit['nom']} seulement).\n")
                          + ("**LEC solo** : tu inscris 3 trios, soit **9 cartes différentes**. Contre chaque pro, tu envoies un trio.\n" if self.cle == "lec" else
                             "**Worlds solo** : tu inscris 3 trios, soit **9 cartes différentes**. Contre chaque pro, tu envoies une carte de chaque trio. "
                             "Un seul 🎟️ ticket.\n" if solo(self.places) else "")
                          + "\n" + "\n".join(lignes))
        e.set_footer(text="Mode test : rien n'est enregistré, aucune carte ne se repose." if test else
                     "Une carte prise dans un trio disparaît des autres. Lance le tournoi quand tes 3 trios sont prêts." if self.cle == "lec" or solo(self.places) else
                     "Le chef de groupe lance le tournoi quand tout le monde est inscrit.")
        return e

    async def interaction_check(self, i):
        if i.user.id not in {p["user"] for p in self.places}:
            await i.response.send_message("Ce tournoi n'est pas le tien.", ephemeral=True)
            return False
        return True

    def inscrire(self, k, menu):
        async def clic(i):
            if i.user.id != self.places[k]["user"]:
                return await i.response.send_message(f"Ce menu est celui de {self.places[k]['nom']}.", ephemeral=True)
            self.places[k]["ids"] = list(menu.values)
            self.poser()
            await i.response.edit_message(embed=self.embed(), view=self)
        return clic

    async def annuler(self, i):
        if i.user.id != self.auteur:
            return await i.response.send_message("Seul le chef de groupe peut annuler.", ephemeral=True)
        self.stop()
        await i.response.edit_message(content="Inscription annulée : aucune carte ne se repose.", embed=None, view=None, attachments=[])
        effacer_plus_tard(self.message, 60)

    async def commencer(self, i):
        if i.user.id != self.auteur:
            return await i.response.send_message("Seul le chef de groupe peut lancer le tournoi.", ephemeral=True)
        if self.parti or not all(len(p["ids"]) == 3 for p in self.places):
            return await i.response.defer()
        if (self.cle == "lec" or solo(self.places)) and len({c for p in self.places for c in p["ids"]}) < sum(len(p["ids"]) for p in self.places):
            return await i.response.send_message("Une même carte ne peut pas être dans deux trios : il faut **9 cartes différentes**.", ephemeral=True)
        if self.cle == "lec":   # LEC solo : un essai du jour est consommé au départ du tournoi
            for u in {pl["user"] for pl in self.places if pl.get("reel")}:
                p = db.get_joueur(self.guilde, u)
                if not p or lec_essais_restants(p) <= 0:
                    return await i.response.send_message("Tu as déjà joué ta LEC du jour. Reviens demain !" if data.LEC_ESSAIS == 1 else f"Tu as déjà joué tes {data.LEC_ESSAIS} LEC du jour. Reviens demain !", ephemeral=True)
                if p["lec_jour"] != aujourdhui():
                    p["lec_jour"], p["lec_essais"] = aujourdhui(), 0
                p["lec_essais"] += 1
                db.sauver(p)
        if self.cle == "worlds" and data.WORLDS_TICKETS:   # un ticket par joueur, pris au départ du tournoi
            uniques = {place["user"]: place for place in self.places if place.get("reel")}   # Worlds solo : un seul ticket
            reels = [(place, db.get_joueur(self.guilde, u)) for u, place in uniques.items()]
            manque = [place["nom"].split(" · trio")[0] for place, p in reels if not p or p["tickets_worlds"] <= 0]
            if manque:
                return await i.response.send_message(f"Il manque un 🎟️ ticket Worlds à : **{', '.join(manque)}**.", ephemeral=True)
            for _, p in reels:
                p["tickets_worlds"] -= 1
                db.sauver(p)
            for place in self.places:   # ticket rendu après le bug de 21h41 : ce tournoi-là ne rapporte des packs qu'après BLG
                if place.get("reel") and place["user"] in REPRISES_WORLDS and db.operation_unique(f"reprise_worlds_{place['user']}_2026_10_12"):
                    place["reprise"] = REPRISES_WORLDS[place["user"]]
        self.parti = True
        self.stop()
        await i.response.edit_message(content=f"{self.circuit['emoji']} **{self.circuit['nom']}** · le tournoi commence…"
                                      + ((" Un 🎟️ ticket Worlds a été utilisé (" if solo(self.places) else " Un 🎟️ ticket Worlds a été utilisé par chaque joueur (")
                                         + ", ".join(f"{pl['nom'].split(' · trio')[0]} : {texte_tickets(self.guilde, pl['user'])}" for pl in {x["user"]: x for x in self.places if x.get("reel")}.values()) + ")."
                                         if self.cle == "worlds" and data.WORLDS_TICKETS and any(pl.get("reel") for pl in self.places) else ""),
                                      embed=None, view=None, attachments=[])
        tournoi = EssaiPros(self.auteur, self.numero, self.places, self.guilde, self.cle)
        tournoi.message = self.message
        tournoi.reposer()   # les cartes sont engagées dès le départ : un tournoi interrompu les laisse au repos
        if self.cle == "worlds" and self.depart == REPRISE_HLE and all(jeton_reprise(self.guilde, pl["user"]) for pl in self.places if pl.get("reel")):
            for pl in self.places:   # reprise après un tournoi bloqué : pas de packs pour les équipes d'avant (déjà gagnés), le jeton est utilisé
                if pl.get("reel"):
                    pl["reprise"] = REPRISE_HLE
                    db.con.execute("DELETE FROM operations WHERE cle=?", (f"jeton_reprise_hle_{self.guilde}_{pl['user']}",))
            db.con.commit()
        if self.offert and self.depart == data.WORLDS_DEPART:
            db.operation_unique(CLE_DEPART_BLG_OFFERT)   # le départ BLG offert est utilisé
            db.con.commit()
        if self.depart:   # départ direct : les équipes d'avant comptent comme battues, avec leurs récompenses
            for k in range(self.depart):
                tournoi.numero, tournoi.palier = k, tournoi.paliers[k]
                tournoi.recompenser()
            tournoi.numero, tournoi.palier, tournoi.match, tournoi.score = self.depart, tournoi.paliers[self.depart], 0, []
            tournoi.poser_choix()
            try:
                await self.message.edit(content=f"⏩ **Départ direct à {tournoi.palier['equipe']}** : les récompenses des {self.depart} équipes d'avant "
                                                f"ont été données ({'packs LEC' if self.cle == 'lec' else 'packs Worlds'} et golds).")
            except ERREURS_RESEAU:
                pass
        await tournoi.intro()
        await tournoi.reveler()

    def basculer_depart(self, k):
        async def clic(i):
            if i.user.id != self.auteur:
                return await i.response.send_message("Seul le chef de groupe choisit le départ.", ephemeral=True)
            self.depart = k
            self.poser()
            await i.response.edit_message(embed=self.embed(), view=self)
        return clic

    async def on_timeout(self):
        if self.message and not self.parti:
            try:
                await self.message.edit(content="⌛ Inscription expirée.", embed=None, view=None)
                effacer_plus_tard(self.message, 60)
            except Exception:
                pass


CLE_DEPART_BLG_OFFERT = "depart_blg_offert_2026_10_14"


def depart_blg_offert():
    """14 octobre : le propriétaire offre un départ direct à BLG au prochain groupe qui lance les Worlds (tant qu'il n'est pas utilisé)."""
    return not db.con.execute("SELECT 1 FROM operations WHERE cle=?", (CLE_DEPART_BLG_OFFERT,)).fetchone()


async def message_durable(i):
    """Le message de la réponse, modifiable sans limite de temps. Celui que renvoie original_response() passe par le jeton de
    l'interaction, qui expire au bout de 15 minutes : un tournoi plus long restait bloqué (bouton « Pro suivant » sans effet)."""
    m = await i.original_response()
    try:
        return i.channel.get_partial_message(m.id) if i.channel else m
    except Exception:
        return m


async def ouvrir_inscription(i, numero, places, repondre=None, circuit="worlds"):
    vue = InscriptionWorlds(i.user.id, numero, places, i.guild_id, circuit)
    await (repondre or i.response.send_message)(embed=vue.embed(), view=vue)
    vue.message = await message_durable(i)


COACH_TEST = {}   # serveur -> statistique du coach de test ("pv" par défaut, None = sans coach). Oublié au redémarrage.
COACHS_NOMS = {"pv": "PV (coach Top)", "atk": "attaque (coach ADC)", "vitesse": "vitesse (coach Jungle)", "ulti": "dégâts d'ulti (coach Mid)", "soin": "soins et boucliers (coach Support)"}


def coach_de_test(guilde, numero):
    """Le coach simulé en mode test : celui de l'équipe d'avant (aucun contre Karmine Corp). Renvoie (statistique, valeur) ou None."""
    stat = COACH_TEST.get(guilde, "pv")
    if not stat or numero < 1:
        return None
    return stat, getattr(data, "TEST_COACH_VALEUR", None) or data.WORLDS_COACHS[min(numero, len(data.WORLDS_COACHS)) - 1]   # 14 octobre : valeur fixe si réglée


def texte_coach(guilde, numero):
    coach = coach_de_test(guilde, numero)
    if not coach:
        return "Coach de test : aucun."
    valeur = coach[1] * (data.WORLDS_COACH_ULTI if coach[0] == "ulti" else 1)
    return f"Coach de test : +{round(valeur * 100)} % de {COACHS_NOMS[coach[0]]} pour toute l'équipe."


ROLE_CHAMPION = "👑 Champion du monde"


async def annoncer_champions(guilde, joueurs):
    """Un tournoi est gagné : chaque joueur reçoit le grade de champion du monde, et le serveur est prévenu dans le salon des tirages
    (sans dire qui attendait en grande finale)."""
    if not guilde:
        return
    try:   # le grade : créé s'il manque. Sans le droit de gérer les rôles, tant pis : l'annonce part quand même
        role = discord.utils.get(guilde.roles, name=ROLE_CHAMPION) or await guilde.create_role(
            name=ROLE_CHAMPION, colour=discord.Colour(0xECC86E), hoist=True, reason="Grade des vainqueurs des Worlds")
        for u in joueurs:
            membre = guilde.get_member(u) or await guilde.fetch_member(u)
            if role not in membre.roles:
                await membre.add_roles(role, reason="A gagné les Worlds")
    except Exception as erreur:
        print(f"Grade de champion du monde : {erreur!r}")
    salon = next((c for c in guilde.text_channels if c.name == data.SALON_TIRAGES), None)
    if not salon:
        return
    noms = [f"<@{u}>" for u in joueurs]
    liste = noms[0] if len(noms) == 1 else ", ".join(noms[:-1]) + " et " + noms[-1]
    e = discord.Embed(color=0xECC86E, description=f"# 👑 {'Champion' if len(noms) == 1 else 'Champions'} du monde !\n"
                      f"{liste} {'est devenu **champion' if len(noms) == 1 else 'sont devenus **champions'} du monde** : "
                      "ils ont gagné les **Worlds**, du Play-In à la grande finale, sans une seule défaite.\n"
                      f"Ils portent désormais le grade **{ROLE_CHAMPION}**.")
    fichier = fichier_image("banniere_worlds.jpg")
    if fichier:
        e.set_image(url="attachment://banniere_worlds.jpg")
    try:
        await salon.send(content=" ".join(noms), embed=e, **({"file": fichier} if fichier else {}))
    except discord.HTTPException:
        pass


EQUIPE_TEST = {}   # serveur -> "ur" (par défaut : UR niveau 100 équipées) ou "copies" (cartes des trois joueurs). Oublié au redémarrage.


async def lancer_essai_pros(i, numero=0, circuit="worlds"):
    """Mode test : le propriétaire joue seul les trois places d'un tournoi, à partir de l'équipe choisie. Rien n'est enregistré."""
    if not await proprietaire_du_jeu(i):
        return await i.response.send_message(f"Ce mode est en construction : seul le propriétaire du jeu peut le tester.", ephemeral=True)
    places = []
    if EQUIPE_TEST.get(i.guild_id, "ur") == "ur":   # par défaut : les UR au niveau 100, équipées
        nom, avatar = await avatar_de(i.guild, i.user.id)
        for k in range(3):
            cartes_ur = {c: {"niveau": 100, "etoiles": 0, "xp": 0, "ligne": None, "buff": None, "item": (item, data.ITEM_NIVEAU_MAX), "rune": rune}
                         for c, (item, rune) in data.TOUR_PROS_TEST_UR.items()}
            places.append({"nom": f"Place {k + 1}", "avatar": avatar, "possedees": cartes_ur, "dispo": list(data.TOUR_PROS_TEST_UR), "ids": [], "user": i.user.id, "reel": False})
    for u in ([] if places else data.TOUR_PROS_TEST):
        p, possedees = db.get_joueur(i.guild_id, u), db.cartes(i.guild_id, u)
        if not p:
            continue
        for ancienne, (nouvelle, niveau, etoiles) in data.TOUR_PROS_TEST_REMPLACE.get(u, {}).items():   # cartes prêtées pour le test
            if nouvelle in data.CARTES and nouvelle not in possedees:
                possedees[nouvelle] = {"xp": 0, "niveau": niveau, "etoiles": etoiles, "ligne": None, "buff": None, "rune": None}
        for carte, niveau in getattr(data, "TOUR_PROS_TEST_NIVEAU", {}).get(u, {}).items():   # niveau forcé pour le test
            if carte in possedees:
                possedees[carte] = dict(possedees[carte], niveau=niveau)
        dispo = cartes_inscriptibles(possedees, set())
        if len(dispo) < 3:
            continue
        nom, avatar = await avatar_de(i.guild, u)
        places.append({"nom": nom or f"Joueur {len(places) + 1}", "avatar": avatar, "possedees": possedees, "dispo": dispo, "ids": [], "user": i.user.id, "reel": False})
    if len(places) < 3:
        return await i.response.send_message("Il me faut trois joueurs avec au moins 3 cartes pour le mode test (voir TOUR_PROS_TEST dans data.py).", ephemeral=True)
    await ouvrir_inscription(i, numero, places, circuit=circuit)


async def places_test_perso(i):
    """Les trois places du salon de test : les cartes copiées de trois joueurs, plus des UR prêtées au hasard. Renvoie (places, lignes)."""
    places, lignes = [], []
    for u in data.TEST_PERSO_JOUEURS:
        p, possedees = db.get_joueur(i.guild_id, u), db.cartes(i.guild_id, u)
        if not p:
            continue
        neuves = [c for c in data.TEST_PERSO_UR if c in data.CARTES and c not in possedees]
        pretees = random.sample(neuves, min(data.TEST_PERSO_UR_NOMBRE, len(neuves)))
        for c in pretees:   # UR prêtées pour ce test seulement : niveau 100, sans item ni rune
            possedees[c] = {"xp": 0, "niveau": 100, "etoiles": 0, "ligne": None, "buff": None, "rune": None}
        dispo = cartes_inscriptibles(possedees, set())
        if len(dispo) < 3:
            continue
        nom, avatar = await avatar_de(i.guild, u)
        nom = nom or p.get("pseudo") or f"Joueur {len(places) + 1}"
        places.append({"nom": nom, "avatar": avatar, "possedees": possedees, "dispo": dispo, "ids": [], "user": i.user.id, "reel": False, "perso": True})
        lignes.append(f"**{nom}** : " + ", ".join(data.CARTES[c]["nom"] for c in pretees))
    return places, lignes


async def lancer_test_perso(i, depart=None):
    """Salon de test du propriétaire : Worlds de test à partir de l'équipe data.TEST_PERSO_DEPART (ou depart : 14 octobre, bouton Faker),
    avec les cartes copiées de trois joueurs et 3 UR prêtées au hasard à chacun (tier S ou A). Rien n'est enregistré."""
    if i.user.id != data.TEST_PERSO_PROPRIO and not await proprietaire_du_jeu(i):
        return await i.response.send_message("Ce salon de test est réservé au propriétaire du jeu.", ephemeral=True)
    places, lignes = await places_test_perso(i)
    if len(places) < 3:
        return await i.response.send_message("Il me faut les trois joueurs du test avec au moins 3 cartes chacun.", ephemeral=True)
    if depart is not None:   # 14 octobre, bouton Tester Faker : les meilleures cartes du serveur, pour pouvoir passer Faker et voir la suite
        lignes = cartes_du_serveur_pour_test(i.guild_id, places)
    await ouvrir_inscription(i, data.TEST_PERSO_DEPART if depart is None else depart, places)
    try:
        await i.followup.send(("🧪 **Meilleures cartes du serveur** (item et rune de leur propriétaire) :\n" if depart is not None else
                               "🧪 **UR prêtées pour ce test** (niveau 100, sans item) :\n") + "\n".join(lignes[:15])
                              + "\n-# Rien n'est enregistré.", ephemeral=True)
    except ERREURS_RESEAU:
        pass


def meilleures_cartes_serveur(g, nombre=25):
    """Test : les cartes les plus fortes que les joueurs du serveur possèdent vraiment, en comptant item et rune
    (combat.force_reelle). Une seule copie par carte : la plus forte. Renvoie ({carte: sa fiche}, lignes à afficher)."""
    meilleures = {}
    for j in db.tous_les_joueurs(g):
        runes = runes_equipees(j)
        for cid, fiche in db.cartes(g, j["user_id"]).items():
            fiche["rune"] = runes.get(cid)
            if cid not in data.CARTES or not data.CARTES[cid].get("ulti"):
                continue
            f = combat.force_reelle(cid, fiche)
            if cid not in meilleures or f > meilleures[cid][0]:
                propre = {k: v for k, v in fiche.items() if k != "_collection"}
                meilleures[cid] = (f, propre, j.get("pseudo") or str(j["user_id"]))
    top = sorted(meilleures.items(), key=lambda x: -x[1][0])[:nombre]
    lignes = []
    for cid, (f, fiche, pseudo) in top:
        item = fiche.get("item")
        lignes.append(f"**{data.CARTES[cid]['nom']}** · niv. {fiche['niveau']}" + (f" · {data.ITEMS[item[0]][1]} {data.ITEMS[item[0]][0]} niv. {item[1]}" if item and item[0] in data.ITEMS else "")
                      + (f" · rune {data.RUNES[fiche['rune']][0]}" if fiche.get("rune") in data.RUNES else "") + f" · de {pseudo} · force {int(f)}")
    return {cid: fiche for cid, (f, fiche, pseudo) in top}, lignes


def cartes_du_serveur_pour_test(g, places):
    """Donne à chaque place de test les meilleures cartes du serveur (sa propre copie), en gardant le coach du joueur copié."""
    pool, lignes = meilleures_cartes_serveur(g)
    for place in places:
        coll = db.Cartes({c: dict(v) for c, v in pool.items()})
        coll.coach = getattr(place["possedees"], "coach", "")
        place["possedees"], place["dispo"], place["ids"] = coll, cartes_inscriptibles(coll, set()), []
    return lignes


class PanneauTestPerso(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label=f"Lancer un test · {data.TOUR_PROS[data.TEST_PERSO_DEPART]['equipe']}", emoji="🧪", style=discord.ButtonStyle.success, custom_id="f:testperso_go")
    async def go(self, i, _):
        await lancer_test_perso(i)

    @discord.ui.button(label="Tester Faker", emoji="👑", style=discord.ButtonStyle.danger, custom_id="f:testperso_faker")
    async def faker(self, i, _):
        await lancer_test_perso(i, len(data.TOUR_PROS) - 1)

    @discord.ui.button(label="Changer de coach de test", emoji="🎓", style=discord.ButtonStyle.secondary, custom_id="f:testperso_coach")
    async def coach(self, i, _):
        if i.user.id != data.TEST_PERSO_PROPRIO and not await proprietaire_du_jeu(i):
            return await i.response.send_message("Réservé au propriétaire du jeu.", ephemeral=True)
        ordre = ["pv", "atk", "vitesse", "ulti", "soin", None]
        actuel = COACH_TEST.get(i.guild_id, "pv")
        COACH_TEST[i.guild_id] = ordre[(ordre.index(actuel) + 1) % len(ordre)] if actuel in ordre else "pv"
        stat = COACH_TEST[i.guild_id]
        await i.response.send_message("🎓 Coach de test : " + (f"**{COACHS_NOMS[stat]}**." if stat else "**aucun**."), ephemeral=True)


def embed_test_perso(guilde):
    noms = []
    for u in data.TEST_PERSO_JOUEURS:
        p = db.get_joueur(guilde.id, u)
        noms.append(p["pseudo"] if p and p.get("pseudo") else str(u))
    urs = ", ".join(data.CARTES[c]["nom"] for c in data.TEST_PERSO_UR if c in data.CARTES)
    return discord.Embed(color=0x6B5BD6, description="# 🧪 Test des Worlds\n"
                         f"Un tournoi de test qui commence à **{data.TOUR_PROS[data.TEST_PERSO_DEPART]['equipe']}**, avec les vraies cartes de "
                         f"**{noms[0]}** (en haut), **{noms[1]}** (au milieu) et **{noms[2]}** (en bas).\n\n"
                         f"Chaque place reçoit en plus **{data.TEST_PERSO_UR_NOMBRE} UR prêtées au hasard** (tier S ou A, niveau 100, sans item), "
                         "tirées de nouveau à chaque lancement :\n" + urs + ".\n\n"
                         "-# Rien n'est enregistré : pas de packs, pas de repos, aucun compte n'est modifié. Coach de test : PV par défaut."
                         + "".join(f"\n-# Réglage de test : {data.TOUR_PROS[k]['equipe']} à la force {str(f).replace('.', ',')} (au lieu de {str(data.TOUR_PROS[k]['force']).replace('.', ',')})." for k, f in sorted(getattr(data, "TEST_PERSO_FORCES", {}).items()))
                         + "".join(f"\n-# Réglage de test : {p} ({data.TOUR_PROS[k]['equipe']}) à {str(v).replace('.', ',')} (au lieu de {str(data.TOUR_PROS[k]['bonus'][p]).replace('.', ',')})." for k, d in sorted(getattr(data, "TEST_PERSO_BONUS", {}).items()) for p, v in d.items()))


async def installer_test_perso(guilde):
    """Crée le salon de test personnel (visible par le propriétaire et le bot seulement), sinon remet son panneau à jour."""
    if guilde.get_member(data.TEST_PERSO_PROPRIO) is None:
        try:
            await guilde.fetch_member(data.TEST_PERSO_PROPRIO)
        except discord.HTTPException:
            return   # pas sur ce serveur
    salon = trouver_salon(guilde, data.TEST_PERSO_SALON)
    if salon:
        async for message in salon.history(limit=30, oldest_first=True):
            if message.author == guilde.me and message.components:
                await message.edit(embed=embed_test_perso(guilde), view=PanneauTestPerso())
                return
        await salon.send(embed=embed_test_perso(guilde), view=PanneauTestPerso())
        return
    membre = guilde.get_member(data.TEST_PERSO_PROPRIO) or await guilde.fetch_member(data.TEST_PERSO_PROPRIO)
    nom_categorie = next(c for c, cles in data.CATEGORIES if "raid" in cles)
    categorie = discord.utils.get(guilde.categories, name=nom_categorie) or await guilde.create_category(nom_categorie)
    droits = {guilde.default_role: discord.PermissionOverwrite(view_channel=False),
              guilde.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, attach_files=True),
              membre: discord.PermissionOverwrite(view_channel=True)}
    salon = await guilde.create_text_channel(data.TEST_PERSO_SALON, category=categorie, overwrites=droits,
                                             topic="Salon de test privé : Worlds de test, rien n'est enregistré.")
    await salon.send(embed=embed_test_perso(guilde), view=PanneauTestPerso())


def cartes_inscriptibles(possedees, au_repos):
    """Les cartes qu'un joueur peut inscrire aux Worlds : ses champions pas au repos, les plus forts d'abord (le menu les montre 25 par page)."""
    cartes = [c for c in possedees if c in data.CARTES and data.CARTES[c].get("ulti") and c not in au_repos]
    return sorted(cartes, key=tri_cartes(possedees))


# ---- Le vrai mode : un groupe de trois joueurs (comme le raid). Tant que le salon est privé, seul le propriétaire peut le voir.
GROUPES_WORLDS = {}   # serveur -> {"joueurs": {id: pseudo}, "chef": id}


def cle_groupe(guilde, circuit):
    """Un groupe en formation par serveur et par circuit (Worlds et LEC à part)."""
    return guilde if circuit == "worlds" else (guilde, circuit)


class VueGroupeWorlds(discord.ui.View):
    def __init__(self, guilde, circuit="worlds"):
        super().__init__(timeout=900)
        self.circuit, self.cle = CIRCUITS[circuit], circuit
        self.guilde, self.message = cle_groupe(guilde, circuit), None

    def embed(self):
        groupe = GROUPES_WORLDS.get(self.guilde) or {"joueurs": {}, "chef": None}
        g = self.guilde if isinstance(self.guilde, int) else self.guilde[0]
        noms = "\n".join(f"{'👑' if u == groupe['chef'] else '•'} {nom}" + (f" · 🎟️ {texte_tickets(g, u)}" if self.cle == "worlds" and data.WORLDS_TICKETS else "")
                          for u, nom in groupe["joueurs"].items())
        e = discord.Embed(color=self.circuit["couleur"], description=f"# {self.circuit['emoji']} {self.circuit['nom']} · un groupe se forme\n## {len(groupe['joueurs'])}/3 joueurs\n{noms}\n\n"
                          f"Il faut **3 joueurs**, chacun avec au moins 3 cartes" + ("" if not self.circuit["repos"]() else " qui ne sont pas au repos")
                          + (" et un 🎟️ ticket Worlds" if self.cle == "worlds" and data.WORLDS_TICKETS else "") + ". Chacun inscrira ensuite 3 cartes pour tout le tournoi.")
        e.set_footer(text="Le chef de groupe (👑) lance l'inscription quand vous êtes trois. Le groupe se ferme tout seul après 15 minutes.")
        return e

    async def on_timeout(self):
        if GROUPES_WORLDS.pop(self.guilde, None) and self.message:
            try:
                await self.message.edit(content="⌛ Le groupe s'est dissous.", embed=None, view=None)
                effacer_plus_tard(self.message, 60)
            except Exception:
                pass

    @discord.ui.button(label="Rejoindre", emoji="✋", style=discord.ButtonStyle.success)
    async def rejoindre(self, i, _):
        groupe = GROUPES_WORLDS.get(self.guilde)
        if not groupe:
            return await i.response.edit_message(content="Ce groupe n'existe plus.", embed=None, view=None)
        if i.user.id in groupe["joueurs"]:
            return await i.response.send_message("Tu es déjà dans le groupe.", ephemeral=True)
        if len(groupe["joueurs"]) >= 3:
            return await i.response.send_message("Le groupe est complet.", ephemeral=True)
        raison = refus_worlds(i.guild_id, i.user.id, self.cle)
        if raison:
            return await i.response.send_message(raison, ephemeral=True)
        groupe["joueurs"][i.user.id] = i.user.display_name
        await i.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Quitter", style=discord.ButtonStyle.secondary)
    async def quitter(self, i, _):
        groupe = GROUPES_WORLDS.get(self.guilde)
        if not groupe or i.user.id not in groupe["joueurs"]:
            return await i.response.send_message("Tu n'es pas dans ce groupe.", ephemeral=True)
        del groupe["joueurs"][i.user.id]
        if not groupe["joueurs"]:
            GROUPES_WORLDS.pop(self.guilde, None)
            self.stop()
            return await i.response.edit_message(content="Le groupe s'est dissous.", embed=None, view=None)
        if groupe["chef"] == i.user.id:
            groupe["chef"] = next(iter(groupe["joueurs"]))
        await i.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Passer à l'inscription", emoji="🏆", style=discord.ButtonStyle.danger)
    async def lancer(self, i, _):
        groupe = GROUPES_WORLDS.get(self.guilde)
        if not groupe:
            return await i.response.edit_message(content="Ce groupe n'existe plus.", embed=None, view=None)
        if i.user.id != groupe["chef"]:
            return await i.response.send_message("Seul le chef de groupe (👑) peut lancer.", ephemeral=True)
        if len(groupe["joueurs"]) < 3:
            return await i.response.send_message(f"Il faut 3 joueurs (vous êtes {len(groupe['joueurs'])}).", ephemeral=True)
        places = []
        for u, nom in groupe["joueurs"].items():
            raison = refus_worlds(i.guild_id, u, self.cle)
            if raison:
                return await i.response.send_message(f"**{nom}** ne peut pas participer : {raison[0].lower()}{raison[1:]}", ephemeral=True)
            possedees = db.cartes(i.guild_id, u)
            _, avatar = await avatar_de(i.guild, u)
            places.append({"nom": nom, "avatar": avatar, "possedees": possedees, "dispo": cartes_inscriptibles(possedees, set(self.circuit["au_repos"](i.guild_id, u))),
                           "ids": [], "user": u, "reel": True})
        GROUPES_WORLDS.pop(self.guilde, None)
        self.stop()
        await ouvrir_inscription(i, 0, places, repondre=i.response.edit_message, circuit=self.cle)


def texte_tickets(g, u):
    p = db.get_joueur(g, u)
    return f"{p['tickets_worlds']}/{data.WORLDS_TICKETS_MAX}" if p else "?"


def lec_essais_restants(p):
    return data.LEC_ESSAIS - (p["lec_essais"] if p["lec_jour"] == aujourdhui() else 0)


async def lancer_lec_solo(i):
    """LEC solo : le joueur occupe les trois places, avec 3 trios de cartes différentes (9 cartes)."""
    raison = refus_worlds(i.guild_id, i.user.id, "lec")
    if raison:
        return await i.response.send_message(raison, ephemeral=True)
    possedees = db.cartes(i.guild_id, i.user.id)
    dispo = cartes_inscriptibles(possedees, set())
    if len(dispo) < 9:
        return await i.response.send_message(f"Il te faut au moins **9 champions** pour la LEC solo (tu en as {len(dispo)}).", ephemeral=True)
    _, avatar = await avatar_de(i.guild, i.user.id)
    nom = i.user.display_name
    places = [{"nom": f"{nom} · trio {k + 1}", "avatar": avatar, "possedees": possedees, "dispo": dispo, "ids": [], "user": i.user.id, "reel": True} for k in range(3)]
    await ouvrir_inscription(i, 0, places, circuit="lec")


async def lancer_worlds_solo(i):
    """26 octobre : Worlds solo. Le joueur occupe les trois places, avec 3 trios de cartes différentes (9 cartes). Même difficulté
    qu'à trois, un seul ticket, les mêmes packs qu'un joueur de groupe."""
    raison = refus_worlds(i.guild_id, i.user.id)
    if raison:
        return await i.response.send_message(raison, ephemeral=True)
    possedees = db.cartes(i.guild_id, i.user.id)
    dispo = cartes_inscriptibles(possedees, set(db.worlds_au_repos(i.guild_id, i.user.id)))
    if len(dispo) < 9:
        return await i.response.send_message(f"Il te faut au moins **9 champions** pour les Worlds en solo (tu en as {len(dispo)}). "
                                             "Tu peux aussi **former un groupe** de 3 joueurs.", ephemeral=True)
    _, avatar = await avatar_de(i.guild, i.user.id)
    nom = i.user.display_name
    places = [{"nom": f"{nom} · trio {k + 1}", "avatar": avatar, "possedees": possedees, "dispo": list(dispo), "ids": [], "user": i.user.id, "reel": True} for k in range(3)]
    await ouvrir_inscription(i, 0, places, circuit="worlds")


def solo(places):
    """Vrai si toutes les places sont au même joueur (LEC solo, Worlds solo)."""
    return len(places) > 1 and len({p["user"] for p in places}) == 1


def refus_worlds(g, u, circuit="worlds"):
    """Pourquoi ce joueur ne peut pas entrer dans un tournoi (None s'il peut)."""
    p = db.get_joueur(g, u)
    if not p:
        return "Tu n'as pas encore de compte. Va dans le salon d'accueil et appuie sur **Commencer**."
    if circuit == "lec" and lec_essais_restants(p) <= 0:
        return "Tu as déjà joué ta **LEC** du jour. Reviens demain !" if data.LEC_ESSAIS == 1 else f"Tu as déjà joué tes **{data.LEC_ESSAIS} LEC** du jour. Reviens demain !"
    if circuit == "worlds" and data.WORLDS_TICKETS and p["tickets_worlds"] <= 0:
        return f"Il te faut un **🎟️ ticket Worlds**. On en gagne {data.LEC_TICKETS_FINALE} en atteignant la finale de la LEC, et {data.LEC_TICKETS_VICTOIRE} de plus en la gagnant ({data.WORLDS_TICKETS_MAX} au plus)."
    repos = CIRCUITS[circuit]["au_repos"](g, u)
    if len(cartes_inscriptibles(db.cartes(g, u), set(repos))) < 3:
        fin = min(repos.values()) if repos else 0
        return f"Il te faut au moins **3 cartes qui ne sont pas au repos** pour entrer {'aux Worlds' if circuit == 'worlds' else 'en ' + CIRCUITS[circuit]['nom']}." + (f" La prochaine se réveille dans {duree(max(0, fin - time.time()))}." if repos else "")
    return None


# ---- Pack Worlds : gagné aux Worlds, il ne contient que les cartes des équipes que le joueur a déjà éliminées.
def chemin_carte_pro(pseudo):
    return os.path.join(DOSSIER_PROS, "cartes", pseudo + ".png")


def texte_part_coach(n):
    """Où un coach donne son bonus, en clair."""
    if data.COACHS[n].get("partout"):
        return f"**{data.texte_bonus_coach(n)}** partout"
    return f"**{data.texte_bonus_coach(n)}** aux Worlds, à la LEC et au raid (et {data.texte_bonus_coach(n, data.WORLDS_COACH_AILLEURS)} partout ailleurs)"


async def ouvrir_pack_pro(i, remplacer=False, circuit="worlds"):
    p = await charger(i)
    if not p:
        return
    lec = circuit == "lec"
    nom_pack, champ = ("pack LEC", "packs_lec") if lec else ("pack Worlds", "packs_pro")
    repondre = i.response.edit_message if remplacer else i.response.send_message
    extra = {"embed": None, "view": None, "attachments": []} if remplacer else {"ephemeral": True}
    equipes = db.lec_equipes(i.guild_id, i.user.id) if lec else db.worlds_equipes(i.guild_id, i.user.id)
    if p[champ] <= 0 or not equipes:
        return await repondre(content=("Tu n'as pas de pack LEC à ouvrir. Ils se gagnent en battant des équipes de la LEC : "
                                       + " · ".join(f"{t['equipe']} {n}" for t, n in zip(data.LEC_PALIERS, data.LEC_PACKS)) + " packs au total, à chaque tournoi.") if lec else
                              ("Tu n'as pas de pack Worlds à ouvrir. Ils se gagnent en éliminant des équipes aux Worlds : "
                               f"{data.WORLDS_PACKS_PAR_PALIER} packs pour le Play-In, {2 * data.WORLDS_PACKS_PAR_PALIER} pour le round 1, et ainsi de suite."), **extra)
    p[champ] -= 1
    bonus = []
    if lec:
        genre, tire = combat.tirer_lec(p, equipes, set(db.cartes(i.guild_id, i.user.id)))
        pied = f"{p['packs_lec']} pack(s) LEC restant(s) · SSR garanti dans {max(1, data.LEC_PITIE - p['pitie_lec'])} packs LEC au plus"
    else:
        genre, tire = combat.tirer_pro(p, equipes, set(db.cartes(i.guild_id, i.user.id)))   # le tirage est fait et sauvegardé tout de suite : l'animation n'est que de l'affichage
        pied = f"{p['packs_pro']} pack(s) Worlds restant(s) · UR garanti dans {max(1, data.PITIE_PRO_UR - p['pitie_pro_ur'])} packs Worlds au plus"
        bonus = [c for c in (combat.tirer_pro_bonus(equipes) for _ in range(data.PRO_CARTES_BONUS)) if c]
    suite = EncorePro(circuit) if p[champ] > 0 else None
    texte_bonus = "\n".join(f"{data.EMOJIS[data.CARTES[c]['rarete']]} **{data.CARTES[c]['nom']}** · {donner(p, c).split(chr(10))[0]}" for c in bonus)
    if genre == "coach":
        if not p["coach"]:
            p["coach"] = tire   # le premier coach s'équipe tout seul
        db.sauver(p)
        db.journal_pack(i.guild_id, i.user.id, "lec" if lec else "pro", -1, f"coach {tire}")
        nombre = db.coach_ajouter(i.guild_id, i.user.id, tire)
        c = data.COACHS[tire]
        e = discord.Embed(color=0xECC86E, description=f"# 🎓 {tire}\n## Carte de pro · {c['poste']} · {c['nom_equipe']}\n"
                          f"Équipé comme coach, il donne {texte_part_coach(tire)} à tes cartes.\n"
                          + ("🆕 Nouveau coach !" if nombre == 1 else f"Tu en as maintenant {nombre} exemplaires.")
                          + ("\n✅ Il est équipé." if p["coach"] == tire else "\nChange de coach avec le bouton **Mon coach**."))
        if texte_bonus:
            e.add_field(name="➕ Et aussi", value=texte_bonus[:1024], inline=False)
            db.sauver(p)
        e.set_footer(text=pied)
        chemin = chemin_carte_pro(tire)
        fichier = lambda: [discord.File(chemin, "coach.png")] if os.path.exists(chemin) else []
        if fichier():
            e.set_image(url="attachment://coach.png")
        try:
            film, duree = await dessiner("ouverture_pro", chemin) if fichier() else (None, 0)
        except Exception:
            film, duree = None, 0
        debut = discord.Embed(color=0xECC86E, description=f"# 📦 Le {nom_pack} s'ouvre…")
        if film:
            debut.set_image(url="attachment://ouverture.gif")
        if remplacer:
            await i.response.edit_message(content=None, embed=debut, view=None, attachments=[discord.File(film, "ouverture.gif")] if film else [])
        else:
            await i.response.send_message(embed=debut, files=[discord.File(film, "ouverture.gif")] if film else [], ephemeral=True)
        try:
            await asyncio.sleep(max(1.2, duree - 1.5))
            await editer(i, embed=e, view=suite, attachments=fichier())
        except ERREURS_RESEAU:
            pass
        await annoncer_coach(i.guild, i.user, tire)
        if bonus:
            await annoncer(i.guild, i.user, bonus)
        return
    statut = donner(p, tire)
    db.sauver(p)
    db.journal_pack(i.guild_id, i.user.id, "lec" if lec else "pro", -1, tire + (" (garantie)" if p.pop("_garantie", False) else ""))
    rarete = "LR" if tire.endswith("LR") else data.CARTES[tire]["rarete"]
    film, duree, anim = None, 0, f"ouverture_{'SSR' if rarete == 'UR' else rarete}.gif"
    if rarete == "LR":
        try:
            film, duree = await dessiner("ouverture_lr", tire)
        except Exception:
            film, duree = None, 0
    animee = os.path.exists(os.path.join(DOSSIER_IMAGES, anim)) and not film
    debut = embed_suspense(f"📦 Le {nom_pack} s'ouvre…", image=None if film else (anim if animee else "pack_ferme.png"))
    if film:
        debut.set_image(url="attachment://ouverture.gif")
    pieces = [discord.File(film, "ouverture.gif")] if film else joindre(anim if animee else "pack_ferme.png")
    if remplacer:
        await i.response.edit_message(content=None, embed=debut, view=None, attachments=pieces)
    else:
        await i.response.send_message(embed=debut, files=pieces, ephemeral=True)
    try:
        await asyncio.sleep(max(1.2, duree - 1.5) if film else DUREE_OUVERTURE if animee else 1.4)
        e = embed_carte(tire, statut, locale=True)
        if texte_bonus:
            e.add_field(name="➕ Et aussi", value=texte_bonus[:1024], inline=False)
        e.set_footer(text=pied)
        await editer(i, embed=e, view=suite, attachments=joindre(image_carte(tire)))
    except ERREURS_RESEAU:
        pass
    await annoncer(i.guild, i.user, [tire] + bonus)


async def ouvrir_packs_pro_x5(i, remplacer=False, circuit="worlds"):
    """14 octobre : ouvre jusqu'à 5 packs Worlds (ou LEC) d'un coup, sans animation, et montre tout le butin dans un seul message."""
    p = await charger(i)
    if not p:
        return
    lec = circuit == "lec"
    nom_pack, champ = ("packs LEC", "packs_lec") if lec else ("packs Worlds", "packs_pro")
    repondre = i.response.edit_message if remplacer else i.response.send_message
    extra = {"embed": None, "view": None, "attachments": []} if remplacer else {"ephemeral": True}
    equipes = db.lec_equipes(i.guild_id, i.user.id) if lec else db.worlds_equipes(i.guild_id, i.user.id)
    if p[champ] <= 0 or not equipes:
        return await repondre(content=f"Tu n'as pas de {nom_pack} à ouvrir.", **extra)
    nombre = min(5, p[champ])
    possedees = set(db.cartes(i.guild_id, i.user.id))
    lignes, a_annoncer, coachs = [], [], []
    for _ in range(nombre):
        p[champ] -= 1
        if lec:
            genre, tire = combat.tirer_lec(p, equipes, possedees)
            bonus = []
        else:
            genre, tire = combat.tirer_pro(p, equipes, possedees)
            bonus = [c for c in (combat.tirer_pro_bonus(equipes) for _ in range(data.PRO_CARTES_BONUS)) if c]
        db.journal_pack(i.guild_id, i.user.id, champ.replace("packs_", ""), -1, ("coach " if genre == "coach" else "") + tire + (" (garantie)" if p.pop("_garantie", False) else "") + " · x5")
        if genre == "coach":
            if not p["coach"]:
                p["coach"] = tire   # le premier coach s'équipe tout seul
            n = db.coach_ajouter(i.guild_id, i.user.id, tire)
            c = data.COACHS[tire]
            lignes.append(f"🎓 **{tire}** · carte de pro · {c['poste']} · {c['nom_equipe']} · " + ("🆕 nouveau coach !" if n == 1 else f"{n} exemplaires"))
            coachs.append(tire)
        else:
            rarete = "LR" if tire.endswith("LR") else data.CARTES[tire]["rarete"]
            statut = donner(p, tire).split("\n")[0].split(" · ")[0]
            possedees.add(tire)
            lignes.append(f"{'🔴' if rarete == 'LR' else data.EMOJIS[data.CARTES[tire]['rarete']]} **{data.CARTES[tire]['nom']}** · {rarete} · {statut}")
            a_annoncer.append(tire)
        for c in bonus:
            statut = donner(p, c).split("\n")[0].split(" · ")[0]
            possedees.add(c)
            lignes.append(f"-# ➕ {data.EMOJIS[data.CARTES[c]['rarete']]} {data.CARTES[c]['nom']} · {statut}")
            a_annoncer.append(c)
    db.sauver(p)
    pied = (f"{p['packs_lec']} pack(s) LEC restant(s) · SSR garanti dans {max(1, data.LEC_PITIE - p['pitie_lec'])} packs LEC au plus" if lec else
            f"{p['packs_pro']} pack(s) Worlds restant(s) · UR garanti dans {max(1, data.PITIE_PRO_UR - p['pitie_pro_ur'])} packs Worlds au plus")
    meilleure = next((c for c in a_annoncer if c.endswith("LR")), None) or next((c for c in a_annoncer if data.CARTES[c]["rarete"] == "UR"), None) \
        or next((c for c in a_annoncer if data.CARTES[c]["rarete"] == "SSR"), None)
    e = discord.Embed(color=0xECC86E, description=f"# 📦 {nombre} {nom_pack if nombre > 1 else nom_pack.replace('packs', 'pack')} ouvert{'s' if nombre > 1 else ''}\n" + "\n".join(lignes)[:3900])
    e.set_footer(text=pied)
    fichiers = joindre(image_carte(meilleure)) if meilleure else []
    if fichiers:
        e.set_thumbnail(url=f"attachment://{image_carte(meilleure)}")
    suite = EncorePro(circuit) if p[champ] > 0 else None
    if remplacer:
        await i.response.edit_message(content=None, embed=e, view=suite, attachments=fichiers)
    else:
        await i.response.send_message(embed=e, view=suite or discord.utils.MISSING, files=fichiers, ephemeral=True)
    for tire in coachs:
        await annoncer_coach(i.guild, i.user, tire)
    if a_annoncer:
        await annoncer(i.guild, i.user, a_annoncer)


class EncorePro(discord.ui.View):
    def __init__(self, circuit="worlds"):
        super().__init__(timeout=300)
        self.circuit = circuit

    @discord.ui.button(label="Ouvrir le suivant", emoji="📦", style=discord.ButtonStyle.success)
    async def encore(self, i, _):
        await ouvrir_pack_pro(i, remplacer=True, circuit=self.circuit)

    @discord.ui.button(label="Ouvrir x5", emoji="📦", style=discord.ButtonStyle.primary)
    async def encore5(self, i, _):
        await ouvrir_packs_pro_x5(i, remplacer=True, circuit=self.circuit)


class MonCoach(discord.ui.View):
    """Choisir le coach équipé, parmi les cartes de pro du joueur."""

    def __init__(self, p, possedes):
        super().__init__(timeout=300)
        ordre = sorted(possedes, key=lambda n: (-data.COACHS[n]["equipe"], n))[:24]
        menu = discord.ui.Select(placeholder="Choisis ton coach", options=[
            discord.SelectOption(label=f"{n} · {data.COACHS[n]['poste']} · {data.COACHS[n]['nom_equipe']}"[:100], value=n, default=p["coach"] == n,
                                 description=data.texte_bonus_coach(n) + (" partout" if data.COACHS[n].get("partout") else " Worlds, LEC, raid")) for n in ordre]
            + [discord.SelectOption(label="Aucun coach", value="-", default=not p["coach"])])

        async def clic(i):
            q = db.get_joueur(i.guild_id, i.user.id)
            choix = menu.values[0]
            if not q or (choix != "-" and choix not in db.coachs(i.guild_id, i.user.id)):
                return await i.response.edit_message(content="Ce coach n'est pas à toi.", embed=None, view=None)
            q["coach"] = "" if choix == "-" else choix
            db.sauver(q)
            await i.response.edit_message(embed=embed_coach(q, db.coachs(i.guild_id, i.user.id)), view=MonCoach(q, db.coachs(i.guild_id, i.user.id)))
        menu.callback = clic
        self.add_item(menu)


def embed_coach(p, possedes):
    actuel = p["coach"] if p["coach"] in data.COACHS else ""
    lignes = [f"{'✅' if n == actuel else '•'} **{n}** · {data.COACHS[n]['poste']} · {data.COACHS[n]['nom_equipe']} · {data.texte_bonus_coach(n)}" + (f" ×{k}" if k > 1 else "")
              for n, k in sorted(possedes.items(), key=lambda kv: (-data.COACHS[kv[0]]["equipe"], kv[0])) if n in data.COACHS]
    return discord.Embed(color=0xECC86E, description="# 🎓 Ton coach\n"
                         + (f"Équipé : **{actuel}**, {texte_part_coach(actuel)}.\n"
                            if actuel else "Aucun coach équipé.\n")
                         + "Un seul coach à la fois. Aux Worlds, il renforce la carte que tu envoies ; partout ailleurs, tes trois cartes.\n\n"
                         + ("\n".join(lignes) if lignes else f"Tu n'as pas encore de carte de pro : elles sortent des packs Worlds ({data.TAUX_PRO['coach']} % par pack) et des packs LEC ({data.LEC_TAUX['coach']} %)."))


def embed_progression(p, g, u):
    faites = db.worlds_equipes(g, u)
    lignes = []
    for k, palier in enumerate(data.TOUR_PROS):
        nom = "Faker" if k == len(data.TOUR_PROS) - 1 else palier["equipe"]   # l'équipe n'est nommée qu'une fois éliminée : la suite reste une surprise
        lignes.append(f"{'✅' if k in faites else '⬛'} **{PHASES_COURTES[k]}**" + (f" · {nom}" if k in faites else "") + f" · {(k + 1) * data.WORLDS_PACKS_PAR_PALIER} packs")
    aujourd = p["worlds_palier"] if p["worlds_jour"] == aujourdhui() else 0
    repos = db.worlds_au_repos(g, u)
    return discord.Embed(color=0xECC86E, description="# 🏆 Tes Worlds\n"
                         f"📦 Packs Worlds à ouvrir : **{p['packs_pro']}** · 👑 Titres de champion du monde : **{p['worlds_titres']}**\n"
                         + (f"🎟️ Tickets Worlds : **{p['tickets_worlds']}/{data.WORLDS_TICKETS_MAX}**\n" if data.WORLDS_TICKETS else "")
                         + 
                         f"Meilleur palier aujourd'hui : " + (f"**{aujourd}**." if aujourd else "aucun pour l'instant.")
                         + f"\n\n**Équipes éliminées** (leurs cartes sortent de tes packs Worlds)\n" + "\n".join(lignes))


class PanneauTourPros(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        # Les boutons de test (tournoi joué seul par le propriétaire) sont retirés du panneau : DATA.WORLDS_BOUTONS_TEST les remet.
        if getattr(data, "WORLDS_BOUTONS_TEST", False):
            for numero, palier in enumerate(data.TOUR_PROS[1:], start=1):   # test : démarrer le tournoi directement à une équipe
                bouton = discord.ui.Button(label=("Test · Faker" if numero == len(data.TOUR_PROS) - 1 else f"Test · {palier['equipe']}")[:80], style=discord.ButtonStyle.secondary,
                                           custom_id=f"f:tp_test_{numero}", row=2 + numero // 4)
                bouton.callback = self.phase(numero)
                self.add_item(bouton)
            for libelle, emoji, cle, action in (("Changer d'équipe de test", "🔁", "f:tp_equipe", self.changer_equipe), ("Changer de coach de test", "🎓", "f:tp_coach", self.changer_coach)):
                bouton = discord.ui.Button(label=libelle, emoji=emoji, style=discord.ButtonStyle.secondary, custom_id=cle, row=4)
                bouton.callback = action
                self.add_item(bouton)

    def phase(self, numero):
        async def clic(i):
            await lancer_essai_pros(i, numero)
        return clic

    async def changer_equipe(self, i):
        if not await proprietaire_du_jeu(i):
            return await i.response.send_message("Réservé au propriétaire du jeu.", ephemeral=True)
        EQUIPE_TEST[i.guild_id] = "copies" if EQUIPE_TEST.get(i.guild_id, "ur") == "ur" else "ur"
        await i.response.send_message(
            "🔁 Équipe de test : **les 6 UR au niveau 100, item au maximum et rune** (chaque place en inscrit 3)."
            if EQUIPE_TEST[i.guild_id] == "ur" else "🔁 Équipe de test : **les vraies cartes des trois joueurs** (chaque place inscrit 3 de leurs cartes, les plus fortes en tête de liste).", ephemeral=True)

    async def changer_coach(self, i):
        if not await proprietaire_du_jeu(i):
            return await i.response.send_message("Réservé au propriétaire du jeu.", ephemeral=True)
        ordre = ["pv", "atk", "vitesse", "ulti", "soin", None]
        COACH_TEST[i.guild_id] = ordre[(ordre.index(COACH_TEST.get(i.guild_id, "pv")) + 1) % len(ordre)]
        stat = COACH_TEST[i.guild_id]
        await i.response.send_message(
            "🎓 Coach de test : **aucun** (tu joues sans coach)." if not stat else
            f"🎓 Coach de test : **{COACHS_NOMS[stat]}**. Sa force est celle du coach de l'équipe d'avant : rien contre Karmine Corp, "
            f"+{round(data.WORLDS_COACHS[0] * 100)} % contre IG… jusqu'à +{round(data.WORLDS_COACHS[6] * 100)} % contre Faker"
            + (" (une fois et demie plus pour l'ulti)." if stat == "ulti" else "."), ephemeral=True)

    @discord.ui.button(label="Former un groupe", emoji="🏆", style=discord.ButtonStyle.success, custom_id="f:tp_groupe", row=0)
    async def groupe(self, i, _):
        raison = refus_worlds(i.guild_id, i.user.id)
        if raison:
            return await i.response.send_message(raison, ephemeral=True)
        if i.guild_id in GROUPES_WORLDS:
            return await i.response.send_message("Un groupe se forme déjà : clique sur **Rejoindre** sous son message, plus bas dans ce salon.", ephemeral=True)
        GROUPES_WORLDS[i.guild_id] = {"joueurs": {i.user.id: i.user.display_name}, "chef": i.user.id}
        vue = VueGroupeWorlds(i.guild_id)
        await i.response.send_message(embed=vue.embed(), view=vue)
        vue.message = await message_durable(i)

    @discord.ui.button(label="Jouer en solo", emoji="👤", style=discord.ButtonStyle.success, custom_id="f:tp_solo", row=0)
    async def jouer_solo(self, i, _):
        await lancer_worlds_solo(i)

    @discord.ui.button(label="Ouvrir un pack Worlds", emoji="📦", style=discord.ButtonStyle.primary, custom_id="f:tp_pack", row=0)
    async def pack(self, i, _):
        await ouvrir_pack_pro(i)

    @discord.ui.button(label="Ouvrir x5", emoji="📦", style=discord.ButtonStyle.primary, custom_id="f:tp_pack5", row=0)
    async def pack5(self, i, _):
        await ouvrir_packs_pro_x5(i)

    @discord.ui.button(label="Mon coach", emoji="🎓", style=discord.ButtonStyle.primary, custom_id="f:tp_moncoach", row=0)
    async def coach(self, i, _):
        p = await charger(i)
        if not p:
            return
        possedes = db.coachs(i.guild_id, i.user.id)
        await i.response.send_message(embed=embed_coach(p, possedes), view=MonCoach(p, possedes) if possedes else discord.utils.MISSING, ephemeral=True)

    @discord.ui.button(label="Mes tickets", emoji="🎟️", style=discord.ButtonStyle.primary, custom_id="f:tp_tickets", row=1)
    async def tickets(self, i, _):
        p = await charger(i)
        if p:
            await i.response.send_message(f"🎟️ Tu as **{p['tickets_worlds']}/{data.WORLDS_TICKETS_MAX} tickets Worlds**.\n"
                                          "Un ticket est utilisé par joueur **au lancement** d'un tournoi (bouton *Commencer le tournoi*), quel qu'en soit le résultat. "
                                          f"On en gagne {data.LEC_TICKETS_FINALE} en atteignant la finale de la LEC, et {data.LEC_TICKETS_VICTOIRE} de plus en la gagnant ({data.LEC_ESSAIS} LEC par jour).", ephemeral=True)

    @discord.ui.button(label="Ma progression", emoji="📊", style=discord.ButtonStyle.secondary, custom_id="f:tp_progres", row=1)
    async def progression(self, i, _):
        p = await charger(i)
        if p:
            await i.response.send_message(embed=embed_progression(p, i.guild_id, i.user.id), ephemeral=True)




PHASES_COURTES = ["Play-In", "Round 1", "Round 2", "Round 3", "Quart", "Demi", "Finale", "Grande finale"]


def embed_tour_pros():
    paliers = " · ".join(f"{nom} **{(k + 1) * data.WORLDS_PACKS_PAR_PALIER}**" for k, nom in enumerate(PHASES_COURTES))
    return discord.Embed(color=0xECC86E, description="# 🏆 Worlds\n"
                         "**Le tournoi** : trois joueurs (**Former un groupe**), chacun inscrit **3 cartes**. Huit étapes s'enchaînent, du Play-In à la grande finale ; à chaque match, "
                         "chaque joueur envoie une de ses 3 cartes. Une équipe aligne 3 pros : **chaque carte ne joue qu'une fois par équipe**. Le tournoi s'arrête à la **première défaite**. "
                         + ("Chaque joueur utilise un **🎟️ ticket Worlds** par tournoi ; les cartes ne se reposent pas.\n\n" if not data.WORLDS_REPOS else
                            f"Les cartes inscrites se reposent ensuite **{data.WORLDS_REPOS // 3600} h** (aux Worlds seulement) : on peut repartir avec d'autres.\n\n")
                         + "👤 **En solo** (**Jouer en solo**) : tu tiens les trois places, avec **9 cartes différentes** en 3 trios. Même difficulté, un seul ticket, les mêmes packs.\n\n"
                         + 
                         f"**Les packs Worlds** : chaque tournoi rapporte des packs, selon la dernière équipe éliminée (total du tournoi).\n{paliers}\n"
                         "Un pack Worlds ne contient que les cartes des équipes que **tu as déjà éliminées** : leurs champions, leurs UR, et parfois "
                         "une **carte de pro**, à équiper comme **coach**. Gagner la grande finale ouvre trois cartes **LR**, les plus rares du jeu.\n\n"
                         + (f"🎟️ **Ticket Worlds** : chaque joueur en utilise un pour lancer un tournoi. On en gagne {data.LEC_TICKETS_FINALE} en atteignant la finale de la LEC, "
                            f"et {data.LEC_TICKETS_VICTOIRE} de plus en la gagnant ; {data.WORLDS_TICKETS_MAX} au plus.\n\n" if data.WORLDS_TICKETS else "")
                         + "Le bouton **Mon coach** équipe une carte de pro ; **Ma progression** montre les équipes que tu as éliminées.")


ANNONCE_WORLDS = (
    "# 🏆 Les Worlds sont ouverts !\n"
    "Un nouveau mode à **3 joueurs** arrive : un tournoi contre des équipes de joueurs pros, du **Play-In** jusqu'à la **grande finale**. "
    "Qui vous attend au bout ? À vous de le découvrir.\n\n"
    "**⚔️ Le tournoi**\n"
    "• Formez un groupe de **3 joueurs** dans {salon}.\n"
    "• Chacun inscrit **3 cartes**. Elles feront tout le tournoi.\n"
    "• Chaque équipe aligne 3 pros, chacun avec ses 3 champions. À chaque match, chaque joueur envoie **une** de ses 3 cartes, au choix.\n"
    "• **Une seule défaite et le tournoi s'arrête.**\n"
    "• Vos 3 cartes inscrites se reposent ensuite **{repos} h** (aux Worlds seulement). Vous pouvez repartir tout de suite avec d'autres cartes.\n\n"
    "**📦 Les packs Worlds**\n"
    "• Éliminer une équipe entière rapporte des packs Worlds : plus vous allez loin, plus vous en gagnez.\n{paliers}\n"
    "• Une fois par jour, sur votre meilleur tournoi.\n"
    "• Un pack Worlds ne contient que des cartes **introuvables ailleurs** : les champions des pros que vous avez éliminés, et leurs versions **UR**.\n"
    "• Chaque équipe éliminée ajoute ses cartes à vos packs, pour toujours.\n"
    "• **Les taux** : SR {sr} % · SSR {ssr} % · UR {ur} % · carte de pro {coach} %. Un SSR est garanti au bout de {pitie} packs Worlds sans en avoir eu, un UR au bout de {pitie_ur}.\n"
    "• Après la grande finale : {lr} % de carte **LR**.\n\n"
    "**🎓 Les coachs**\n"
    "• Un pack Worlds peut aussi contenir une **carte de pro**. Équipez-la comme **coach** : elle renforce vos cartes, surtout aux Worlds et au raid.\n"
    "• Plus le pro est loin dans le tournoi, plus son bonus est fort, et plus sa carte est rare.\n\n"
    "**👑 La grande finale**\n"
    "• La gagner vous donne le titre et le grade de **champion du monde**, et ouvre les cartes **LR**, les plus rares du jeu.\n\n"
    "Bonne chance, il vous en faudra pour devenir le GOAT.")


async def ouvrir_worlds(guilde):
    """Ouverture des Worlds à tout le serveur, une seule fois : le salon des annonces est créé s'il manque, l'annonce y est postée
    avec @everyone, et le guide est réécrit."""
    cle = f"annonce_worlds_{guilde.id}"
    if db.con.execute("SELECT 1 FROM operations WHERE cle=?", (cle,)).fetchone():
        return
    salon = trouver_salon(guilde, data.SALON_ANNONCES)
    if not salon:
        nom_categorie = next(c for c, cles in data.CATEGORIES if "annonces" in cles)
        categorie = discord.utils.get(guilde.categories, name=nom_categorie) or await guilde.create_category(nom_categorie)
        droits = {guilde.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False, create_public_threads=False, create_private_threads=False),
                  guilde.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, attach_files=True, mention_everyone=True)}
        salon = await guilde.create_text_channel(data.SALON_ANNONCES, category=categorie, overwrites=droits, topic="Les grandes annonces du jeu.", position=1)
    worlds = trouver_salon(guilde, data.SALON_TOUR_PROS)
    texte = ANNONCE_WORLDS.format(
        salon=worlds.mention if worlds else "le salon des Worlds", repos=data.WORLDS_REPOS // 3600,
        paliers=" · ".join(f"{nom} **{(k + 1) * data.WORLDS_PACKS_PAR_PALIER}**" for k, nom in enumerate(PHASES_COURTES)),
        sr=data.TAUX_PRO["SR"], ssr=data.TAUX_PRO["SSR"], ur=data.TAUX_PRO["UR"], coach=data.TAUX_PRO["coach"],
        pitie=data.PITIE_PRO, pitie_ur=data.PITIE_PRO_UR, lr=str(data.WORLDS_LR).replace(".", ","))
    e = discord.Embed(color=0xECC86E, description=texte)
    fichier = fichier_image("banniere_worlds.jpg")
    if fichier:
        e.set_image(url="attachment://banniere_worlds.jpg")
    await salon.send(content="@everyone", embed=e, allowed_mentions=discord.AllowedMentions(everyone=True), **({"file": fichier} if fichier else {}))
    db.operation_unique(cle)   # noté seulement une fois l'annonce partie
    db.con.commit()
    try:
        await ecrire_guide(guilde)
    except Exception as erreur:
        print(f"Guide non réécrit ({erreur!r}).")


def embed_progression_lec(p, g, u):
    faites = db.lec_equipes(g, u)
    lignes = [f"{'✅' if k in faites else '⬛'} **{t['phase']}** · {t['equipe']} · {n} pack{'s' if n > 1 else ''} au total" for k, (t, n) in enumerate(zip(data.LEC_PALIERS, data.LEC_PACKS))]
    repos = db.lec_au_repos(g, u)
    possedees = db.cartes(g, u)
    urs = " · ".join(f"{'✅' if c in possedees else '⬛'} {data.CARTES[c]['nom']}" for c in data.LEC_UR)
    return discord.Embed(color=0x00B4D8, description="# 🇪🇺 Ta LEC\n"
                         f"📦 Packs LEC à ouvrir : **{p['packs_lec']}** · 🏆 LEC gagnées : **{p['lec_titres']}** · 🎟️ Tickets Worlds : **{p['tickets_worlds']}/{data.WORLDS_TICKETS_MAX}**\n"
                         f"🎮 LEC restantes aujourd'hui : **{lec_essais_restants(p)}/{data.LEC_ESSAIS}**\n\n**Équipes battues** (leurs cartes sortent de tes packs LEC)\n" + "\n".join(lignes)
                         + f"\n\n**UR de la LEC** (une seule fois chacune)\n{urs}")


def texte_annonce_lec(guilde):
    lec = trouver_salon(guilde, data.SALON_LEC)
    worlds = trouver_salon(guilde, data.SALON_TOUR_PROS)
    urs = " · ".join(f"**{data.CARTES[c]['nom']}** {str(v).replace('.', ',')} %" for c, v in data.LEC_UR.items())
    nouveaux = ", ".join(data.CARTES[c]["nom"] for c in ("Sion", "Chogath", "Sivir")) + " et " + data.CARTES["Rakan"]["nom"]
    return ("# 🇪🇺 La LEC est ouverte !\n"
        "Un nouveau tournoi à **3 joueurs**, plus court que les Worlds, contre les équipes de la LEC : "
        + " → ".join(t["equipe"] for t in data.LEC_PALIERS) + ".\n\n"
        "**⚔️ Le tournoi**\n"
        f"• Formez un groupe de 3 dans {lec.mention if lec else 'le salon de la LEC'}. Chacun inscrit **3 cartes** pour tout le tournoi.\n"
        "• Chaque équipe aligne 3 pros. À chaque match, chacun envoie une de ses cartes, et chaque carte joue une fois par équipe.\n"
        "• **Une défaite et le tournoi s'arrête.**\n"
        f"• Vos 3 cartes se reposent ensuite **{data.LEC_REPOS // 3600} h** (à la LEC seulement). Vous pouvez repartir tout de suite avec d'autres cartes, **autant de fois que vous voulez**.\n\n"
        "**📦 Les packs LEC**\n"
        "• **Chaque tournoi rapporte des packs**, sans limite par jour, selon la dernière équipe battue :\n"
        + " · ".join(f"{t['equipe']} **{n}**" for t, n in zip(data.LEC_PALIERS, data.LEC_PACKS)) + "\n"
        "• Un pack LEC ne contient que les champions des équipes **que vous avez battues**, et chaque nouvelle équipe battue ajoute les siens, pour toujours.\n"
        f"• **Les taux** : SR {data.LEC_TAUX['SR']} % · SSR {str(data.LEC_TAUX['SSR']).replace('.', ',')} % · carte de pro {data.LEC_TAUX['coach']} %. "
        f"Un SSR garanti au bout de {data.LEC_PITIE} packs sans en avoir eu.\n"
        f"• **Trois UR**, chacune avec sa chance : {urs}. Une UR qu'on a déjà ne retombe pas. Pas de garanti : à vous la chance.\n"
        f"• Chaque équipe battue rapporte aussi **{data.GOLDS_LEC_EQUIPE} golds**, et un pack LEC apparaît parfois dans la **boutique** ({data.BOUTIQUE['pack_lec']['prix']} golds).\n\n"
        "**🆕 Les nouveaux champions**\n"
        f"• {nouveaux} arrivent, à trouver dans les packs LEC.\n"
        "• **Viego, Nidalee, Varus, Akali et Sylas** deviennent des **SR**, et se trouvent eux aussi dans les packs LEC.\n\n"
        "**🎓 Les coachs LEC**\n"
        "• Les packs LEC donnent aussi des cartes de pro de la LEC. Plus faibles que les coachs des Worlds, ils donnent **le même bonus partout**.\n\n"
        f"**🎟️ Le ticket Worlds** · {worlds.mention if worlds else 'les Worlds'}\n"
        "• Il faut maintenant **un ticket pour lancer un tournoi des Worlds** (un par joueur).\n"
        f"• Tout le monde en reçoit **{data.WORLDS_TICKETS_DEPART}** aujourd'hui. On en gagne un en **atteignant la finale de la LEC**, {data.WORLDS_TICKETS_MAX} au plus.\n"
        f"• En échange, le repos des cartes aux Worlds passe de 8 h à **{data.WORLDS_REPOS // 3600} h**.\n\n"
        "🧮 Perdus entre tous vos packs ? Le bouton **Mes packs**, dans le salon des packs, montre tout ce que vous avez à ouvrir, et où.\n\n"
        "Bonne chance pour la finale contre Movistar KOI !")


async def annonce_13_octobre(guilde):
    """13 octobre : annonce @everyone (LEC et Worlds plus rapides, nouvelles cartes dans les packs), une seule fois."""
    cle = f"annonce_2026_10_13_{guilde.id}"
    if db.con.execute("SELECT 1 FROM operations WHERE cle=?", (cle,)).fetchone():
        return
    salon = trouver_salon(guilde, data.SALON_ANNONCES)
    if not salon:
        return
    worlds = trouver_salon(guilde, data.SALON_TOUR_PROS) if hasattr(data, "SALON_TOUR_PROS") else None
    lec = trouver_salon(guilde, data.SALON_LEC) if hasattr(data, "SALON_LEC") else None
    texte = (
        "# ⚡ La LEC et les Worlds deviennent plus rapides\n"
        f"**🇪🇺 La LEC** {lec.mention if lec else ''}\n"
        f"• **{data.LEC_ESSAIS} tournoi par jour**, mais **deux fois plus de packs** : jusqu'à **{data.LEC_PACKS[-1]} packs LEC** pour une LEC gagnée.\n"
        f"• Atteindre la finale donne **{data.LEC_TICKETS_FINALE} 🎟️ tickets Worlds**, et la gagner **{data.LEC_TICKETS_VICTOIRE} de plus** : "
        f"jusqu'à **3 tournois des Worlds par jour**. Tu peux garder **{data.WORLDS_TICKETS_MAX} tickets**.\n"
        f"• **Départ direct** : une fois {data.LEC_PALIERS[data.LEC_DEPART]['equipe']} battue, tu peux commencer ta LEC contre elle, "
        "avec les packs des équipes d'avant donnés au départ.\n\n"
        f"**🏆 Les Worlds** {worlds.mention if worlds else ''}\n"
        f"• **Départ direct** : une fois {data.TOUR_PROS[data.WORLDS_DEPART]['equipe']} battue par tout le groupe, vous pouvez commencer contre elle. "
        "Le chef de groupe le choisit à l'inscription (bouton ⏩), et les packs des équipes sautées sont donnés au départ.\n\n"
        "**🎉 Tes victoires remplissent tes packs**\n"
        "• **Battre la LEC** te donne une chance d'avoir **Sylas, Gragas et Xin Zhao UR** dans tes packs à golds (packs de 10 et méga tirage), en plus des SR et SSR des équipes battues.\n"
        "• **Battre une équipe des Worlds** débloque sa **UR dans tes packs UR**, en plus des UR habituelles. Elle ne tombe jamais grâce au garanti : c'est une chance en plus.\n"
        "• Les **packs Worlds** restent la meilleure façon d'avoir ces cartes, et **la seule façon d'obtenir un pro** comme coach.\n\n"
        "Bonne chance à tous ! 🍀")
    e = discord.Embed(color=0xECC86E, description=texte)
    await salon.send(content="@everyone", embed=e, allowed_mentions=discord.AllowedMentions(everyone=True))
    db.operation_unique(cle)
    db.con.commit()


async def ouvrir_lec(guilde):
    """Ouverture de la LEC à tout le serveur, une seule fois : annonce @everyone dans le salon des annonces, puis le guide est réécrit."""
    cle = f"annonce_lec_{guilde.id}"
    if db.con.execute("SELECT 1 FROM operations WHERE cle=?", (cle,)).fetchone():
        return
    salon = trouver_salon(guilde, data.SALON_ANNONCES)
    if not salon:
        return
    e = discord.Embed(color=0x00B4D8, description=texte_annonce_lec(guilde))
    fichier = fichier_image("fond_koi.jpg")
    if fichier:
        e.set_image(url="attachment://fond_koi.jpg")
    await salon.send(content="@everyone", embed=e, allowed_mentions=discord.AllowedMentions(everyone=True), **({"file": fichier} if fichier else {}))
    db.operation_unique(cle)
    db.con.commit()
    try:
        await ecrire_guide(guilde)
    except Exception as erreur:
        print(f"Guide non réécrit ({erreur!r}).")


class PanneauLEC(discord.ui.View):
    """Le panneau du salon de la LEC : le vrai tournoi à 3, les packs LEC, et (LEC fermée) les boutons de test du propriétaire."""
    def __init__(self):
        super().__init__(timeout=None)
        if not data.LEC_OUVERTE:
            for libelle, cle, numero in (("Test · début", "f:lec_test_0", 0), ("Test · demi-finale", "f:lec_test_3", 3), ("Test · finale", "f:lec_test_4", len(data.LEC_PALIERS) - 1)):
                bouton = discord.ui.Button(label=libelle, emoji="🧪", style=discord.ButtonStyle.secondary, custom_id=cle, row=2)
                bouton.callback = self.test(numero)
                self.add_item(bouton)
            bouton = discord.ui.Button(label="Changer d'équipe de test", emoji="🔁", style=discord.ButtonStyle.secondary, custom_id="f:lec_equipe", row=2)
            bouton.callback = self.equipe
            self.add_item(bouton)

    def test(self, numero):
        async def clic(i):
            await lancer_essai_pros(i, numero, "lec")
        return clic

    async def equipe(self, i):
        if not await proprietaire_du_jeu(i):
            return await i.response.send_message("Réservé au propriétaire du jeu.", ephemeral=True)
        EQUIPE_TEST[i.guild_id] = "copies" if EQUIPE_TEST.get(i.guild_id, "ur") == "ur" else "ur"
        await i.response.send_message(
            "🔁 Équipe de test : **les 6 UR au niveau 100, item au maximum et rune** (chaque place en inscrit 3)."
            if EQUIPE_TEST[i.guild_id] == "ur" else "🔁 Équipe de test : **les vraies cartes de Joueur A, Joueur E et Joueur C** (chaque place inscrit 3 de leurs cartes).", ephemeral=True)

    @discord.ui.button(label="Jouer la LEC", emoji="🇪🇺", style=discord.ButtonStyle.success, custom_id="f:lec_solo", row=0)
    async def solo(self, i, _):
        await lancer_lec_solo(i)

    @discord.ui.button(label="Ouvrir un pack LEC", emoji="📦", style=discord.ButtonStyle.primary, custom_id="f:lec_pack", row=0)
    async def pack(self, i, _):
        await ouvrir_pack_pro(i, circuit="lec")

    @discord.ui.button(label="Ouvrir x5", emoji="📦", style=discord.ButtonStyle.primary, custom_id="f:lec_pack5", row=0)
    async def pack5(self, i, _):
        await ouvrir_packs_pro_x5(i, circuit="lec")

    @discord.ui.button(label="Mon coach", emoji="🎓", style=discord.ButtonStyle.primary, custom_id="f:lec_moncoach", row=0)
    async def coach(self, i, _):
        p = await charger(i)
        if not p:
            return
        possedes = db.coachs(i.guild_id, i.user.id)
        await i.response.send_message(embed=embed_coach(p, possedes), view=MonCoach(p, possedes) if possedes else discord.utils.MISSING, ephemeral=True)

    @discord.ui.button(label="Ma progression", emoji="📊", style=discord.ButtonStyle.secondary, custom_id="f:lec_progres", row=1)
    async def progression(self, i, _):
        p = await charger(i)
        if p:
            await i.response.send_message(embed=embed_progression_lec(p, i.guild_id, i.user.id), ephemeral=True)


def embed_lec():
    equipes = "\n".join(f"**{t['phase']}** · {t['equipe']} · {n} pack{'s' if n > 1 else ''}" for t, n in zip(data.LEC_PALIERS, data.LEC_PACKS))
    taux_ur = " · ".join(f"{data.CARTES[c]['nom']} {str(v).replace('.', ',')} %" for c, v in data.LEC_UR.items())
    return discord.Embed(color=0x00B4D8, description="# 🇪🇺 LEC\n" + ("" if data.LEC_OUVERTE else "*En construction : salon privé.*\n") + "\n"
                         "**Le tournoi, en solo** : tu inscris **9 cartes**, en 3 trios. Contre chaque pro, tu envoies un trio, "
                         f"et chaque carte ne joue qu'une fois par équipe. **{len(data.LEC_PALIERS)} équipes**, la première défaite arrête le tournoi. "
                         f'**{data.LEC_ESSAIS} tournoi{"s" if data.LEC_ESSAIS > 1 else ""} par jour**, sans repos des cartes.\n\n'
                         "**Les packs LEC** : chaque tournoi rapporte des packs, selon la dernière équipe battue (total du tournoi) :\n" + equipes + "\n"
                         f"Atteindre la finale donne aussi **{data.LEC_TICKETS_FINALE} 🎟️ tickets Worlds**, et la gagner **{data.LEC_TICKETS_VICTOIRE} de plus** "
                         f"({data.WORLDS_TICKETS_MAX} au plus).\n\n"
                         "Un pack LEC ne contient que les cartes des équipes que **tu as déjà battues** : "
                         f"SR {data.LEC_TAUX['SR']} % · SSR {str(data.LEC_TAUX['SSR']).replace('.', ',')} % · carte de pro {data.LEC_TAUX['coach']} %, "
                         f"et un SSR garanti au bout de {data.LEC_PITIE} packs sans en avoir eu. "
                         f"Trois **UR**, chacune une seule fois : {taux_ur}. Pas de garanti UR.\n\n"
                         "**Les coachs LEC** sont plus faibles que ceux des Worlds, mais donnent le même bonus partout."
                         + ("" if data.LEC_OUVERTE else "\n\n-# Les boutons 🧪 de test sont réservés au propriétaire : rien n'y est enregistré."))


async def installer_lec(guilde):
    """Crée le salon de la LEC s'il manque (privé : le propriétaire et le bot), sinon remet son panneau à jour."""
    salon = trouver_salon(guilde, data.SALON_LEC)
    if salon:
        panneau = None
        async for message in salon.history(limit=30, oldest_first=True):
            if message.author == guilde.me and message.components:
                panneau = message
                break
        if panneau:
            await panneau.edit(embed=embed_lec(), view=PanneauLEC())
        else:
            await salon.send(embed=embed_lec(), view=PanneauLEC())
        if data.LEC_OUVERTE:   # ouverte : le salon se règle comme celui des Worlds (visible par les joueurs, on n'y écrit pas)
            try:
                worlds = trouver_salon(guilde, data.SALON_TOUR_PROS)   # la LEC juste au-dessus des Worlds : le boss final reste les Worlds
                if worlds and (salon.category_id != worlds.category_id or salon.position > worlds.position):
                    await salon.edit(category=worlds.category, position=worlds.position)
                sujet = "Un tournoi à 3 joueurs, plus court que les Worlds. Gagnez des packs LEC, des coachs et des tickets Worlds."
                if (salon.topic or "") != sujet:
                    await salon.edit(topic=sujet)
                role = discord.utils.get(guilde.roles, name=data.ROLE_JOUEUR)
                tous = {"send_messages": False, "create_public_threads": False, "create_private_threads": False, "view_channel": not role}
                if role and salon.overwrites_for(role).view_channel is not True:
                    await salon.set_permissions(role, view_channel=True)
                actuel = salon.overwrites_for(guilde.default_role)
                if any(getattr(actuel, droit) is not valeur for droit, valeur in tous.items()):
                    await salon.set_permissions(guilde.default_role, **tous)
            except discord.HTTPException as erreur:
                print(f"Salon de la LEC : {erreur!r}")
        return
    nom_categorie = next(c for c, cles in data.CATEGORIES if "raid" in cles)
    categorie = discord.utils.get(guilde.categories, name=nom_categorie) or await guilde.create_category(nom_categorie)
    droits = {guilde.default_role: discord.PermissionOverwrite(view_channel=False),
              guilde.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, attach_files=True)}
    for u in set(bot.proprietaires or ()) | {guilde.owner_id}:
        try:
            membre = guilde.get_member(u) or await guilde.fetch_member(u)
            droits[membre] = discord.PermissionOverwrite(view_channel=True)
        except discord.HTTPException:
            pass
    salon = await guilde.create_text_channel(data.SALON_LEC, category=categorie, overwrites=droits, topic="LEC : en construction (salon privé, mode test).")
    await salon.send(embed=embed_lec(), view=PanneauLEC())


async def installer_tour_pros(guilde):
    """Crée le salon des Worlds s'il manque (sinon remet son panneau à jour). Tant que le mode est en construction, seuls le
    propriétaire et le bot le voient."""
    salon = trouver_salon(guilde, data.SALON_TOUR_PROS)
    if salon:
        try:
            async for message in salon.history(limit=30, oldest_first=True):
                if message.author == guilde.me and message.components:
                    e, fichier = embed_tour_pros(), fichier_image("banniere_worlds.jpg")
                    if fichier:
                        e.set_image(url="attachment://banniere_worlds.jpg")
                    await message.edit(embed=e, view=PanneauTourPros(), attachments=[fichier] if fichier else [])
                    break
            if data.TOUR_PROS_OUVERTE:   # le mode est ouvert : le salon se règle comme les autres salons du jeu
                sujet = "Un tournoi à 3 joueurs, ou en solo, contre des équipes de pros. Gagnez des packs Worlds, des coachs et le titre de champion du monde."
                if (salon.topic or "") != sujet:
                    await salon.edit(topic=sujet)
                role = discord.utils.get(guilde.roles, name=data.ROLE_JOUEUR)
                tous = {"send_messages": False, "create_public_threads": False, "create_private_threads": False, "view_channel": not role}
                if role and salon.overwrites_for(role).view_channel is not True:
                    await salon.set_permissions(role, view_channel=True)
                actuel = salon.overwrites_for(guilde.default_role)
                if any(getattr(actuel, droit) is not valeur for droit, valeur in tous.items()):
                    await salon.set_permissions(guilde.default_role, **tous)
            else:   # le mode est refermé (rééquilibrage) : seuls le propriétaire et le bot voient le salon
                if (salon.topic or "") != "Worlds : en construction (salon privé, mode test).":
                    await salon.edit(topic="Worlds : en construction (salon privé, mode test).")
                role = discord.utils.get(guilde.roles, name=data.ROLE_JOUEUR)
                if role and salon.overwrites_for(role).view_channel is not False:
                    await salon.set_permissions(role, view_channel=False)
                if salon.overwrites_for(guilde.default_role).view_channel is not False:
                    await salon.set_permissions(guilde.default_role, view_channel=False)
                if salon.overwrites_for(guilde.me).view_channel is not True:
                    await salon.set_permissions(guilde.me, view_channel=True, send_messages=True, embed_links=True, attach_files=True)
                for u in set(bot.proprietaires or ()) | {guilde.owner_id}:
                    try:
                        membre = guilde.get_member(u) or await guilde.fetch_member(u)
                        if salon.overwrites_for(membre).view_channel is not True:
                            await salon.set_permissions(membre, view_channel=True)
                    except discord.HTTPException:
                        pass
        except discord.HTTPException as erreur:
            print(f"Salon des Worlds : {erreur!r}")
        return None
    nom_categorie = next(c for c, cles in data.CATEGORIES if "raid" in cles)
    categorie = discord.utils.get(guilde.categories, name=nom_categorie) or await guilde.create_category(nom_categorie)
    droits = {guilde.default_role: discord.PermissionOverwrite(view_channel=False),
              guilde.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, attach_files=True)}
    if not data.TOUR_PROS_OUVERTE:
        for u in set(bot.proprietaires or ()) | {guilde.owner_id}:
            try:
                membre = guilde.get_member(u) or await guilde.fetch_member(u)
                droits[membre] = discord.PermissionOverwrite(view_channel=True)
            except discord.HTTPException:
                pass
    salon = await guilde.create_text_channel(data.SALON_TOUR_PROS, category=categorie, overwrites=droits,
                                             topic="Worlds : en construction (salon privé, mode test).")
    e, fichier = embed_tour_pros(), fichier_image("banniere_worlds.jpg")
    if fichier:
        e.set_image(url="attachment://banniere_worlds.jpg")
        await salon.send(embed=e, view=PanneauTourPros(), file=fichier)
    else:
        await salon.send(embed=e, view=PanneauTourPros())
    return salon


PANNEAUX = {
    "accueil": {"salon": "🎮・accueil", "vue": PanneauAccueil, "titre": "Bienvenue sur 2Hot4Deck",
                "sujet": "Crée ton compte et reçois ton premier champion.",
                "texte": "Collectionne les champions, compose ton équipe et grimpe.\n**Commencer** t'envoie ton pack de départ en message privé : un champion SR garanti.\n\n-# " + AVERTISSEMENT},
    "profil": {"salon": data.SALON_PROFIL, "vue": PanneauProfil, "titre": "Ton profil",
               "sujet": "Tes golds, ton niveau de compte, tes charges et ta progression.",
               "texte": "**Mon profil** affiche tes golds, ton niveau de compte, tes charges de Châtiment, ta réserve d'XP, ton étage et ton rang.\n"
                        "Tout ce que tu fais dans le jeu rapporte de l'XP de compte."},
    "packs": {"salon": "🎁・packs", "vue": PanneauPacks, "titre": "Les packs",
              "sujet": "Ouvre des packs pour obtenir de nouvelles cartes.",
              "texte": f"**Gratuit** toutes les 6 heures · **{data.PRIX_PACK_10} golds** les dix, avec un SR garanti · 🎰 **Méga tirage** : {data.MEGA_CARTES} cartes pour {data.MEGA_PRIX} golds, au moins un SSR et un pack UR offert.\n⭐ **Packs de niveau** : un pack gagné à chaque niveau de compte, à ouvrir ici.\n"
                       f"💎 **Pack UR** : un pack UR gagné tous les {data.UR_TOUS_LES} packs ouverts (toutes origines). {data.UR_TAUX['UR']} % d'UR, et un UR garanti au {data.UR_PITIE}e pack UR sans en avoir eu.\n"
                       f"Un doublon donne une étoile à la carte (+10 % de stats, +{data.ETOILE_NIVEAUX} niveaux maximum) et remplit ta **réserve d'XP**, à dépenser sur la carte de ton choix depuis sa fiche."},
    "collection": {"salon": "🃏・collection", "vue": PanneauCollection, "titre": "Ta collection",
                   "sujet": "Tes cartes, leurs fiches et ton équipe de 3.",
                   "texte": "Parcours tes cartes, ouvre leur fiche et compose ton équipe de 3.\nLes tanks protègent, et les champions d'une même région se renforcent."},
    "tour": {"salon": "🗼・tour", "vue": PanneauTour, "titre": "La tour",
             "sujet": f"{data.TOUR_MAX} étages (la tour difficile commence au 101), un pack à taux doublés tous les 5, un boss tous les 10.",
             "texte": f"Chaque étage oppose ton équipe à des champions adverses, avec leurs passifs et leurs ultis. Retente autant que tu veux, c'est gratuit.\n"
                      f"🎯 **Entraînement** : rejoue n'importe quel étage déjà vaincu, sans limite et sans rien gagner, pour essayer tes champions.\n"
                      f"Un **pack à taux doublés** tous les {data.TOUR_PACK_SR} étages, et **un item au choix** pour avoir vaincu le Héraut (étage {data.ITEM_ETAGE})."},
    "jungle": {"salon": data.SALON_JUNGLE, "vue": PanneauJungle, "titre": "La jungle",
               "sujet": "Entraîne ton équipe : XP, golds et parfois un pack. Une charge de Châtiment par carte.",
               "texte": f"🗺️ **Explorer la jungle** : une carte de 16 buissons à fouiller. Camps, trésors et gros monstres à achever au **Châtiment**… "
                        f"mais aussi des **ganks** : chaque buisson fouillé indique combien il y en a autour de lui. Un gank déjà découvert est désamorcé : il ne compte plus dans les chiffres.\n"
                        f"**Une charge de Châtiment ⚡ = une carte complète** : fouiller ne coûte rien. Au {data.EXPLO_VIES}e gank, ton équipe rentre et la carte est finie ; si tu fouilles tout sauf les ganks, c'est un clear complet (+{data.EXPLO_CLEAR} %).\n"
                        f"⏩ **Clear rapide** : {data.CLEAR_RAPIDE} % du butin d'un clear complet, tout de suite, sans jouer.\n"
                        f"Tu as {data.CHARGES_PALIERS[0][1]} charges au départ (le stock grandit tous les 10 niveaux de compte) et une charge revient toutes les {data.CHARGES_DELAI[0] // 60} heures, plus vite avec les donjons défi."},
    "donjons": {"salon": data.SALON_DONJONS, "vue": PanneauDonjons, "titre": "Les donjons",
                "sujet": "Bats les gardiens pour gagner des composants, puis fabrique tes items à la forge.",
                "texte": f"Chaque donjon donne ses propres **composants**. Assemble-les à **la forge** pour fabriquer des items, à équiper sur tes champions.\n"
                         f"**Un seul combat** contre les deux gardiens du donjon. Une victoire donne **{data.DONJON_BUTIN} composants, +1 tous les {data.DONJON_PALIER} étages** de la tour.\n"
                         f"Une **réserve de {data.DONJON_STOCK} victoires**, commune aux trois donjons : une victoire revient toutes les {data.DONJON_DELAI // 3600} heures. Une défaite ne consomme rien.\n"
                         f"🗿 Les **donjons défi** s'ouvrent tous les 10 niveaux de compte, se gagnent une seule fois, et donnent un totem : tes charges de jungle reviennent plus vite et tu peux en miser plusieurs sur une carte."},
    "arene": {"salon": "🏟️・arène", "vue": PanneauArene, "titre": "L'arène",
              "sujet": "Affronte la défense des autres joueurs et monte au classement.",
              "texte": f"Bats l'équipe de défense des autres joueurs pour grimper de **Fer** à **Challenger**.\n{data.ARENE_COMBATS_PAR_JOUR} combats par jour. Ton rang te donne son rôle Discord."},
    "duels": {"salon": data.SALON_DUELS, "vue": PanneauDuels, "titre": "Les duels",
              "sujet": "Défie un joueur en direct, tour par tour.",
              "texte": f"Défie un joueur : vous jouez tour par tour, ici, devant tout le monde.\nLes {data.DUELS_CLASSES_PAR_JOUR} premiers duels du jour comptent pour le classement, les suivants sont amicaux."},
    "raid": {"salon": data.SALON_RAID, "vue": PanneauRaid, "titre": "Le raid : Ryze",
             "sujet": "Unissez vos équipes contre Ryze pour gagner des runes.",
             "texte": f"De **{data.RAID_JOUEURS[0]} à {data.RAID_JOUEURS[1]} joueurs** unissent leurs équipes contre **Ryze**, qui s'adapte au groupe. Une victoire par jour, les défaites ne comptent pas.\n"
                      "Trois difficultés, ouvertes aux étages " + ", ".join(str(e) for e in data.RUNE_ETAGES) + " de la tour. Chaque victoire donne **une rune au choix** : "
                      "un pouvoir à équiper sur une carte, en plus de son item.\n"
                      "Clique sur une difficulté pour former un groupe ; les autres le rejoignent sous le message qui apparaît."},
    "boss": {"salon": data.SALON_BOSS, "vue": PanneauBoss, "titre": "Les boss de salon",
             "sujet": "Un drake ou le Baron apparaît pour tout le serveur : tuez-le ensemble.",
             "texte": "Tous les jours à " + ", ".join(f"{h} h" for h in data.BOSS_HEURES) + ", un boss apparaît ici **pour tout le serveur**.\n"
                      f"Chacun peut l'attaquer {data.BOSS_ATTAQUES} fois avec son équipe ; vous avez {data.BOSS_DUREE // 60} minutes. "
                      f"Sous {data.BOSS_SEUIL} % de PV, le **Châtiment** se débloque : le coup fatal vole le boss et gagne un pack à taux doublés.\n"
                      f"S'il meurt, **tout le serveur** gagne son buff pendant {data.BOSS_BUFF_HEURES} heures. 🔔 **Me prévenir** te mentionne à chaque apparition."},
    "quiz": {"salon": data.SALON_QUIZ, "vue": PanneauQuiz, "titre": "Qui est ce champion ?",
             "sujet": "Le champion mystère du jour : devine-le en un minimum d'essais.",
             "texte": f"Chaque jour, **le même champion mystère pour tout le monde**. Tu vois un tout petit morceau de son illustration : écris son nom.\n"
                      f"À chaque erreur l'image se dévoile un peu plus ({len(data.QUIZ_ZOOMS)} essais). Tu gagnes **un pack, ouvert tout de suite** : "
                      + bareme_essais() + ".\n"
                      "Le classement du jour départage d'abord au nombre d'essais, puis à la vitesse. Garde la réponse pour toi !"},
    "pros": {"salon": data.SALON_PROS, "vue": PanneauPros, "titre": "Le quiz des pros",
             "sujet": "Deux questions par jour sur la scène pro : un visage à reconnaître, un effectif à retrouver.",
             "texte": f"**🎤 Qui est ce pro ?** Une photo, écris son pseudo. Un indice de plus à chaque erreur. Tu gagnes **un pack** : "
                      + bareme_essais() + ".\n"
                      f"**🧩 L'effectif du jour** : une équipe et une année (LCK, LPL, LEC, LCS). Donne le top, le jungler, le mid, l'ADC et le support en {data.PROS_EQUIPE_ESSAIS} essais : "
                      "les 5 = pack à taux doublés · 3 ou 4 = taux améliorés · 1 ou 2 = pack normal.\n"
                      "Les mêmes questions pour tout le monde, nouvelles chaque jour à minuit. Données et photos : Leaguepedia."},
    "coffre": {"salon": data.SALON_EXPEDITION, "vue": PanneauCoffre, "titre": "L'expédition",
               "sujet": "Récupère les golds, l'XP et les packs que ton équipe a rapportés de son expédition.",
               "texte": f"Ton équipe part en expédition quand tu n'es pas là et en rapporte des golds, de l'XP et **un pack toutes les {data.COFFRE_PACK_HEURES} heures**. Plus tu es haut dans la tour, plus ça rapporte.\n"
                        f"Elle s'arrête au bout de {data.COFFRE_HEURES} heures : pense à récupérer ton butin."},
}
# Salons sans boutons : clé -> (nom, sujet, bannière, texte d'accueil, les joueurs peuvent-ils y écrire ?)
SALONS_SIMPLES = {
    "guide": (data.SALON_GUIDE, "Les règles et le mode d'emploi du jeu.", "guide", None, False),
    "tirages": (data.SALON_TIRAGES, "Les belles cartes tirées sur le serveur, à partir de SR.", "tirages",
                "Toutes les belles cartes tirées sur le serveur s'affichent ici, à partir de la rareté SR.", False),
    "annonces": (data.SALON_ANNONCES, "Les grandes annonces du jeu.", None, None, False),
    "maj": (data.SALON_MAJ, "Les nouveautés du jeu, annoncées par le bot à chaque mise à jour.", None, None, False),
    "discussion": (data.SALON_DISCUSSION, "Parlez du jeu : équipes, tirages, idées.", None, None, True),
}


async def vider_tirages(guilde):
    """Efface une fois les anciennes annonces du salon des tirages (remise à zéro du 10 octobre 2026)."""
    cle = "vidage_tirages_2026_10_10"
    salon = trouver_salon(guilde, data.SALON_TIRAGES)
    if not salon or db.maj_deja_postee(guilde.id, cle):
        return
    try:
        # Un par un : le bot n'a besoin d'aucune permission pour effacer ses propres messages.
        await salon.purge(limit=1000, check=lambda m: m.author == guilde.me and not m.pinned and not (m.embeds and m.embeds[0].image and "banniere" in str(m.embeds[0].image.url)), bulk=False)
        db.noter_maj(guilde.id, cle)
        print(f"  {guilde.name} : salon des tirages vidé")
    except ERREURS_RESEAU as e:
        print(f"  {guilde.name} : impossible de vider le salon des tirages ({e})")


async def publier_maj(guilde):
    """Publie dans le salon des mises à jour les notes pas encore annoncées sur ce serveur. Renvoie le nombre de notes publiées."""
    salon = trouver_salon(guilde, data.SALON_MAJ)
    if not salon or data.MAJ_EN_PAUSE:
        return 0   # pas de salon, ou publication en pause : les notes attendent, rien n'est perdu
    publiees = 0
    for cle, date, titre, texte in data.MISES_A_JOUR:
        if db.maj_deja_postee(guilde.id, cle):
            continue
        e = discord.Embed(color=COULEUR, description=f"# 📰 {titre}\n-# {date}\n\n{texte}")
        try:
            await salon.send(embed=e)
        except ERREURS_RESEAU:
            break   # on réessaiera au prochain démarrage, dans l'ordre
        db.noter_maj(guilde.id, cle)
        publiees += 1
    return publiees


def embed_panneau(cle):
    """Embed d'un panneau et fichier de sa bannière (None si l'image manque)."""
    pan = PANNEAUX[cle]
    e = discord.Embed(description=f"# {pan['titre']}\n{pan['texte']}", color=COULEUR)
    fichier = fichier_image(banniere(cle))
    if fichier:
        e.set_image(url=f"attachment://{banniere(cle)}")
    return e, fichier


async def poster_panneau(salon, cle):
    e, fichier = embed_panneau(cle)
    vue = PANNEAUX[cle]["vue"]()
    try:
        if fichier:
            await salon.send(embed=e, view=vue, file=fichier)
            return
    except discord.Forbidden:
        e.set_image(url=None)   # pas le droit de joindre des fichiers : panneau sans bannière
    await salon.send(embed=e, view=vue)


# ================================== GUIDE ====================================
def sections_guide(guilde):
    """Les messages du salon du guide, écrits à partir des réglages actuels du jeu : (titre, texte, couleur)."""
    def lien(nom):
        salon = trouver_salon(guilde, nom) if guilde else None
        return salon.mention if salon else f"**{nom}**"
    S = {cle: lien(p["salon"]) for cle, p in PANNEAUX.items()}
    S.update({cle: lien(v[0]) for cle, v in SALONS_SIMPLES.items()})
    rangs = " → ".join(f"{emoji} {nom}" for _, nom, emoji, _ in data.ARENE_RANGS)
    return [
        ("Bienvenue sur 2Hot4Deck", 0x63B3ED, (
            "Un jeu de collection : tu ouvres des packs, tu obtiens des champions, tu composes une équipe de 3 et tu la fais combattre.\n\n"
            "### Pour commencer\n"
            f"**1.** Va dans {S['accueil']} et appuie sur **Commencer**. Le bot t'envoie en message privé ton pack de départ : un champion SR garanti et {data.GOLDS_DEPART} golds.\n"
            f"**2.** Ouvre des packs dans {S['packs']}.\n"
            f"**3.** Compose ton équipe dans {S['collection']}, puis grimpe {S['tour']}.\n\n"
            "Tout se joue avec les boutons des salons. Les réponses du bot ne sont visibles que par toi, sauf les duels et les annonces.")),
        ("À quoi sert chaque salon", 0x0AC8B9, "\n".join([
            f"{S['accueil']} · créer ton compte",
            f"{S['guide']} · ce que tu lis en ce moment",
            f"{S['tirages']} · les belles cartes tirées par tout le serveur",
            f"{S['discussion']} · pour parler du jeu",
            f"{S['packs']} · ouvrir des packs, gratuits ou payants",
            f"{S['collection']} · voir tes cartes, leurs fiches, et choisir ton équipe",
            f"{S['coffre']} · récupérer ce que ton équipe a rapporté de son expédition en ton absence",
            f"{S['tour']} · les combats contre le jeu, étage par étage",
            f"{S.get('boss', 'le salon des boss')} · un boss apparaît à heures fixes pour tout le serveur : tuez-le ensemble pour un buff commun",
            f"{S.get('quiz', 'le salon qui-est-ce')} · deviner chaque jour le champion mystère, le même pour tout le monde",
            f"{S.get('pros', 'le salon quiz-des-pros')} · reconnaître un joueur pro et retrouver un effectif ; chaque mini-jeu réussi donne un pack ouvert tout de suite",
            f"{S['arene']} · affronter l'équipe de défense des autres joueurs",
            f"{S['duels']} · défier un joueur en direct, tour par tour"])),
        ("Les cartes et les packs", 0xF59E0B, (
            f"**Le pack gratuit.** Un toutes les {data.DELAI_GRATUIT // 3600} heures, avec un peu moins de chances de SSR. Il ne s'accumule pas : passe le chercher.\n"
            f"**Les packs payants.** {data.PRIX_PACK_10} golds les dix avec au moins un SR garanti ({data.PRIX_PACK} golds le pack avec **Encore un**, après un pack gratuit). "
            f"**Le méga tirage** : {data.MEGA_CARTES} cartes pour {data.MEGA_PRIX} golds, au moins un SSR, et un pack UR offert (ces cartes ne comptent pas pour le pack UR tous les {data.UR_TOUS_LES} packs).\n"
            f"**La garantie.** Un SSR est assuré au bout de {data.PITIE} packs sans en avoir eu.\n"            f"**La boutique.** La même pour tout le serveur, renouvelée toutes les {data.BOUTIQUE_DELAI // 3600} heures : des composants, un SSR au hasard, et parfois un pack LEC, un pack Worlds ou un pack UR, à payer en golds. Le bouton **Mes packs** montre tout ce que tu as à ouvrir.\n"
            f"**Le SSR ciblé.** Choisis un SSR à viser : quand un SSR tombe, il a {data.CIBLE_CHANCE} % de chances d'être celui-là. Tu peux changer de cible quand tu veux.\n"
            f"**Les doublons.** Retomber sur une carte lui donne une étoile : +{int(data.BONUS_ETOILE * 100)} % de stats, jusqu'à {data.ETOILES_MAX} étoiles.\n"
            f"**Les niveaux.** Tes cartes gagnent de l'XP en combattant : +{int(data.BONUS_NIVEAU * 100)} % de stats par niveau.")),
        ("Ton équipe et les combats", 0xA855F7, (
            "**Trois cartes.** Tu les choisis dans la collection. Le bouton **Meilleure équipe** prend tes trois plus puissantes.\n"
            "**Les rôles.** Les tanks encaissent et attirent les coups. Assassins, tireurs et mages frappent fort mais sont fragiles. Les supports soignent ou gênent l'ennemi.\n"
            "**La vitesse.** Elle décide de qui joue : un champion deux fois plus rapide joue deux fois plus souvent. Les assassins et les tireurs sont les plus vifs, les tanks les plus lents.\n"
            "**Physique et magique.** Chaque champion frappe en physique ou en magique, et a une résistance contre chacun. Varie tes dégâts : un tank résiste mieux au physique qu'au magique.\n"
            "**L'ulti.** Chaque champion a une jauge qui se remplit à chacune de ses actions. Pleine, il lance son ulti.\n"
            "**Passifs et actifs.** Chaque champion a un passif (un pouvoir permanent) et un actif (son ulti) qui lui sont propres : boucliers, vol de vie, exécutions, ralentissements… Lis la fiche de tes cartes dans la collection pour monter une équipe qui se complète.\n"
            "**Le leader.** Le premier champion de ton équipe 👑 donne le bonus de sa région à toute l'équipe, même aux champions d'ailleurs : "
            + ", ".join(f"{r} +{v} % {data.NOMS_STATS[st]}" for r, (st, v) in data.LEADERS.items()) + ".\n"
            "**Les lignes.** Chaque carte se place devant ou derrière (boutons sous ton équipe). Sur la ligne de son rôle, elle gagne un petit bonus : "
            + ", ".join(f"{role} {'devant' if ligne == 'avant' else 'derrière'} {data.TEXTES_LIGNE[role]}" for role, ligne in data.LIGNES.items())
            + f". Dans les combats automatiques, les ennemis visent la ligne avant {data.CIBLE_AVANT} fois sur 100, sauf les assassins et les attaques de zone.\n"
"**Les items.** Ils se fabriquent à **la forge** (salon des donjons) avec des composants. Un item s'équipe sur le champion de ton choix, et le refabriquer l'améliore jusqu'au niveau 3.\n"
            "**L'aperçu.** Avant un étage, **Voir l'étage** compare ta force à celle des ennemis.")),
        ("La tour, la jungle, les donjons et l'expédition", 0x3B82F6, (
            f"**La tour.** {data.TOUR_MAX} étages. Les premiers sont faciles, puis les boss font office de murs : les larves du Néant à l'étage 10 pour s'échauffer, le Héraut au 20, puis un drake tous les 10 étages, Nashor au 90 et le Dragon ancestral au 100. Chaque boss a sa particularité, visible avec **Voir l'étage**. Ton équipe combat toute seule contre des champions adverses qui ont leurs vrais passifs et actifs (les boss restent le Héraut, les drakes et Nashor). Chaque étage a toujours la même équipe en face, et c'est un mur : c'est ta composition, tes niveaux et tes items qui décident. Elle ne coûte rien et tu peux retenter autant que tu veux.\n"
            f"**Ses récompenses** ne se gagnent qu'une fois : des golds à chaque étage, un pack à taux doublés tous les {data.TOUR_PACK_SR} étages, et un item au choix parmi trois pour avoir vaincu le Héraut (étage {data.ITEM_ETAGE}).\n"
            f"**La jungle.** C'est là que tu t'entraînes. **Explorer la jungle** dépense une **charge de Châtiment** et ouvre une carte de 16 buissons ; fouiller ne coûte rien. Ton premier buisson n'est jamais un gank. Chaque buisson fouillé affiche le nombre de ganks cachés autour de lui : à toi d'en déduire où ne pas aller. **Précision : un gank sur lequel tu es tombé est désamorcé et ne compte plus dans les chiffres.** Si un buisson voisin indique 1 ou 2, ce sont donc des ganks encore cachés, EN PLUS de celui que tu viens de découvrir. Fais attention, "
            f"car au {data.EXPLO_VIES}e gank ton équipe rentre à la base : tu gardes le butin ramassé, mais la carte est finie. À partir de ton deuxième buisson, les ganks se déplacent d'une case après chaque fouille, et les chiffres changent avec eux. S'il ne reste plus que des ganks cachés, c'est un clear complet : +{data.EXPLO_CLEAR} % du butin de la carte. La Sentinelle bleue et le Roncier rouge s'achèvent au Châtiment, en appuyant au bon moment. "
            f"Le **clear rapide** dépense une charge sans jouer et donne {data.CLEAR_RAPIDE} % d'un clear complet. "
            f"Tu as {data.CHARGES_PALIERS[0][1]} charges au départ et une charge revient toutes les {data.CHARGES_DELAI[0] // 60} heures. Le stock grandit avec ton niveau de compte : "
            + ", ".join(f"{nombre} au niveau {niveau}" for niveau, nombre in data.CHARGES_PALIERS[1:]) + ". "
            + " ".join(f"À {c} camps nettoyés, +{bo} % de butin." for c, bo in data.EXPLO_BONUS) + "\n"
            f"**Les donjons.** Trois donjons, chacun avec ses composants. Dans chacun : un seul combat contre ses deux gardiens. Une victoire donne {data.DONJON_BUTIN} composants, +1 tous les {data.DONJON_PALIER} étages de la tour. Une réserve de {data.DONJON_STOCK} victoires commune aux trois donjons, une victoire revient toutes les {data.DONJON_DELAI // 3600} heures ; une défaite ne consomme rien. Le bouton **Recettes** montre ce qu'il faut pour chaque item.\n"
            f"**Les donjons défi.** {len(data.DEFIS)} combats très durs, à gagner une seule fois chacun (essais gratuits). Ils s'ouvrent aux niveaux de compte "
            + ", ".join(str(n) for n, _ in data.DEFIS) + ". Chaque victoire donne un totem permanent : une charge de jungle revient plus vite ("
            + " → ".join(texte_delai(m * 60) for m in data.CHARGES_DELAI) + ") et tu peux miser plus de charges sur une seule carte ("
            + " → ".join(str(m) for m in data.CHARGES_MISE) + "). Miser multiplie le butin, mais tout est perdu si tu sors trop tôt.\n"
            f"**Le niveau de compte.** Tout ce que tu fais rapporte de l'XP de compte. Chaque niveau donne des golds et **un pack à taux triplés à ouvrir dans le salon des packs**. Le niveau maximum est {data.NIVEAU_COMPTE_MAX}. "
            f"**La réserve d'XP.** Chaque doublon tiré dans un pack remplit ta réserve d'XP (jusqu'à {data.RESERVE_MAX}). Dans la collection, ouvre la fiche d'une carte pour y verser ta réserve : idéal pour un champion que tu viens de tirer. "
            + "Un rôle Discord récompense chaque palier : " + ", ".join(f"{nom} au niveau {n}" for n, nom, _ in data.ROLES_NIVEAU) + ". Les modes se débloquent peu à peu : " + ", ".join(f"{NOMS_MODES[c]} au niveau {n}" for c, n in data.DEBLOCAGES.items()) + ". Ton profil (golds, niveau, charges, réserve d'XP) est dans le salon du profil.\n"
            f"**L'expédition.** Ton équipe part en expédition quand tu n'es pas là et rapporte des golds, de l'XP et un pack toutes les {data.COFFRE_PACK_HEURES} heures, ouverts d'un coup à la récolte. Plus tu es haut dans la tour, plus elle rapporte. Elle s'arrête au bout de {data.COFFRE_HEURES} heures : pense à récupérer ton butin.")),
    ] + ([
        ("La LEC", 0x00B4D8, (
            f"**Le tournoi, en solo.** {len(data.LEC_PALIERS)} équipes de la LEC, de la semaine 1 à la finale. Tu inscris 9 cartes en 3 trios ; contre chaque pro, tu envoies un trio, "
            f"chaque carte joue une fois par équipe, et une défaite arrête le tournoi. {data.LEC_ESSAIS} tournoi{"s" if data.LEC_ESSAIS > 1 else ""} par jour, sans repos des cartes.\n"
            "**Les packs LEC.** Chaque tournoi rapporte des packs selon la dernière équipe battue : "
            + " · ".join(f"{t['equipe']} {n}" for t, n in zip(data.LEC_PALIERS, data.LEC_PACKS)) + " packs au total. "
            "Un pack LEC ne contient que les cartes des équipes que tu as battues. "
            f"Taux : SR {data.LEC_TAUX['SR']} %, SSR {str(data.LEC_TAUX['SSR']).replace('.', ',')} %, carte de pro {data.LEC_TAUX['coach']} %, SSR garanti au bout de {data.LEC_PITIE} packs. "
            "Trois UR, chacune une seule fois et sans garanti : " + ", ".join(f"{data.CARTES[c]['nom']} {str(v).replace('.', ',')} %" for c, v in data.LEC_UR.items()) + ".\n"
            f"**Le ticket Worlds.** Atteindre la finale de la LEC donne {data.LEC_TICKETS_FINALE} tickets Worlds, la gagner {data.LEC_TICKETS_VICTOIRE} de plus.\n"
            "**Les coachs LEC.** Plus faibles que ceux des Worlds, ils donnent le même bonus partout.")),
    ] if data.LEC_OUVERTE else []) + [
        ("Les Worlds", 0xECC86E, (
            f"**Le tournoi.** À **3 joueurs**, contre des équipes de joueurs pros, du Play-In à la grande finale. Chacun inscrit 3 cartes ; "
            f"à chaque match, chaque joueur en envoie une, et chaque carte ne joue qu'une fois par équipe. Une seule défaite arrête le tournoi. "
            + ("Les cartes ne se reposent pas : tu peux réinscrire les mêmes à chaque tournoi.\n" if not data.WORLDS_REPOS else
               f"Les 3 cartes inscrites se reposent ensuite {data.WORLDS_REPOS // 3600} h (aux Worlds seulement) : tu peux repartir tout de suite avec d'autres cartes.\n")
            + (f"**Le ticket Worlds.** Chaque joueur en utilise un pour lancer un tournoi. On en gagne {data.LEC_TICKETS_FINALE} en atteignant la finale de la LEC, et {data.LEC_TICKETS_VICTOIRE} de plus en la gagnant ; "
               f"{data.WORLDS_TICKETS_MAX} au plus.\n" if data.WORLDS_TICKETS else "")
            + "**Les packs Worlds.** Chaque tournoi rapporte des packs Worlds, selon la dernière équipe éliminée (total du tournoi) : "
            + " · ".join(f"{nom} {(k + 1) * data.WORLDS_PACKS_PAR_PALIER}" for k, nom in enumerate(PHASES_COURTES)) + ". "
            "Un pack Worlds ne contient que les cartes des équipes que tu as déjà éliminées, pour toujours : leurs champions et leurs UR. "
            f"Taux : SR {data.TAUX_PRO['SR']} %, SSR {data.TAUX_PRO['SSR']} %, UR {data.TAUX_PRO['UR']} %, carte de pro {data.TAUX_PRO['coach']} %. "
            f"Chaque pack Worlds donne {1 + data.PRO_CARTES_BONUS} cartes : une principale avec ces taux, et {data.PRO_CARTES_BONUS} bonus en SR ou SSR. UR garanti au bout de {data.PITIE_PRO_UR} packs Worlds.\n"
            "**Les coachs.** Une carte de pro s'équipe comme coach (bouton **Mon coach**), une seule à la fois. Elle renforce tes cartes : "
            f"bonus complet aux Worlds, à la LEC et au raid, {round(data.WORLDS_COACH_AILLEURS * 100)} % du bonus partout ailleurs. "
            "Aux Worlds, ton coach renforce la carte que tu envoies. Le type de bonus dépend du poste du pro : PV pour un Top, vitesse pour un Jungle, "
            "dégâts d'ulti pour un Mid, attaque pour un ADC, soins et boucliers pour un Support.\n"
            "**La grande finale.** La gagner donne le titre et le grade de champion du monde, et ouvre les cartes LR, les plus rares du jeu.")),
        ("Le classement : arène et duels", 0xE74C3C, (
            f"**Les rangs.** {rangs}. Ton rang te donne le rôle Discord du même nom. L'arène et les duels partagent le même classement.\n\n"
            f"**L'arène.** Tu attaques l'équipe de défense d'un autre joueur, jouée par le bot. {data.ARENE_COMBATS_PAR_JOUR} combats par jour, dont {data.ARENE_MAX_CONTRE_UN_JOUEUR} au plus contre le même joueur. "
            f"Victoire +{data.ARENE_GAIN} pts ou plus, défaite -{data.ARENE_PERTE}. Enregistre ton équipe avec **Ma défense**. "
            "Quand on t'attaque, le bot te prévient en message privé, et **Mon historique** garde la trace de tout.\n\n"
            f"**Les duels.** Tu défies un joueur en direct. Chacun fait agir ses trois champions l'un après l'autre, en choisissant d'attaquer ou de lancer l'ulti. "
            f"Tant qu'un tank adverse est debout, il faut passer par lui. {Duel.DELAI} secondes par action. "
            f"Les {data.DUELS_CLASSES_PAR_JOUR} premiers duels de ta journée sont classés (+{data.DUEL_GAIN} / -{data.DUEL_PERTE} pts), les suivants sont amicaux et illimités.")),
        ("Les règles du serveur", 0x718096, (
            "\n".join(f"**{n}.** {regle}" for n, regle in enumerate(data.REGLES_SERVEUR, 1)) + f"\n\n-# {AVERTISSEMENT}")),
    ]


def embeds_guide(guilde):
    """Renvoie la liste (embed, fichier de bannière ou None) des messages du guide."""
    messages = []
    for n, (titre, couleur, texte) in enumerate(sections_guide(guilde)):
        e = discord.Embed(description=f"# {titre}\n{texte}", color=couleur)
        fichier = fichier_image(banniere("guide")) if n == 0 else None
        if fichier:
            e.set_image(url=f"attachment://{banniere('guide')}")
        messages.append((e, fichier))
    return messages


async def ecrire_guide(guilde):
    """Écrit ou met à jour le guide dans son salon. Renvoie True si le salon existe."""
    salon = trouver_salon(guilde, data.SALON_GUIDE)
    if not salon:
        return False
    messages = embeds_guide(guilde)
    try:
        anciens = [m async for m in salon.history(limit=50) if m.author.id == bot.user.id]
        anciens.reverse()   # du plus ancien au plus récent
        if len(anciens) == len(messages):   # même nombre de messages : on les met à jour sur place
            for rang, ancien in enumerate(anciens):
                async def poser(ancien=ancien, rang=rang):
                    e, fichier = embeds_guide(guilde)[rang]
                    await ancien.edit(embed=e, attachments=[fichier] if fichier else [])
                await reessayer(poser)
            return True
        for ancien in anciens:   # sinon on réécrit le guide (uniquement les messages du bot)
            await ancien.delete()
        for e, fichier in messages:
            try:
                if fichier:
                    await salon.send(embed=e, file=fichier)
                    continue
            except discord.Forbidden:
                e.set_image(url=None)
            await salon.send(embed=e)
    except ERREURS_RESEAU:
        pass
    return True


def plan_des_salons():
    """Renvoie la liste ordonnée des salons du jeu : (catégorie, clé, nom, sujet, ouvert à l'écriture ?)."""
    simples = SALONS_SIMPLES
    plan = []
    for categorie, cles in data.CATEGORIES:
        for cle in cles:
            if cle in PANNEAUX:
                plan.append((categorie, cle, PANNEAUX[cle]["salon"], PANNEAUX[cle]["sujet"], False))
            elif cle in simples:
                plan.append((categorie, cle, simples[cle][0], simples[cle][1], simples[cle][4]))
    return plan


def trouver_salon(guilde, nom):
    return next((c for c in guilde.text_channels if c.name == nom), None)


async def renommer_anciens_salons(guilde):
    """Un salon qui a changé de nom dans le jeu est renommé sur place (avec son panneau), au lieu d'être recréé à côté."""
    for ancien, nouveau in data.SALONS_RENOMMES.items():
        salon = trouver_salon(guilde, ancien)
        if salon and not trouver_salon(guilde, nouveau):
            try:
                await salon.edit(name=nouveau)
            except discord.HTTPException:
                pass


async def amenager(guilde):
    """Range les salons du jeu : bonne catégorie, ordre, sujet, et écriture réservée au bot dans les salons à boutons.
    Renvoie une remarque si une permission manque."""
    remarque = ""
    categories = {}
    await renommer_anciens_salons(guilde)
    try:
        for position, (nom, _) in enumerate(data.CATEGORIES):
            categories[nom] = discord.utils.get(guilde.categories, name=nom) or await guilde.create_category(nom)
        role = discord.utils.get(guilde.roles, name=data.ROLE_JOUEUR)
        for position, (categorie, cle, nom, sujet, ouvert) in enumerate(plan_des_salons()):
            salon = trouver_salon(guilde, nom)
            if not salon:
                continue
            try:
                # On ne modifie que ce qui a changé : Discord limite très fort les modifications de salons,
                # et tout refaire à chaque fois bloquait la commande pendant de longues minutes.
                besoin = {}
                if salon.category != categories[categorie]:
                    besoin["category"], besoin["position"] = categories[categorie], position
                if (salon.topic or "") != sujet:
                    besoin["topic"] = sujet
                if besoin:
                    await salon.edit(**besoin)
                # Le bot d'abord, pour ne jamais se retrouver enfermé dehors.
                moi = salon.overwrites_for(guilde.me)
                if not (moi.view_channel and moi.send_messages and moi.embed_links and moi.attach_files):
                    await salon.set_permissions(guilde.me, view_channel=True, send_messages=True, embed_links=True, attach_files=True)
                tous = {} if ouvert else {"send_messages": False, "create_public_threads": False, "create_private_threads": False}
                if role and cle not in data.SALONS_PUBLICS:   # salon du jeu : visible seulement après avoir appuyé sur Commencer
                    if salon.overwrites_for(role).view_channel is not True:
                        await salon.set_permissions(role, view_channel=True)
                    tous["view_channel"] = False
                actuel = salon.overwrites_for(guilde.default_role)
                if any(getattr(actuel, droit) is not valeur for droit, valeur in tous.items()):
                    await salon.set_permissions(guilde.default_role, **tous)
            except discord.HTTPException:
                remarque = "\nJe n'ai pas pu régler tous les salons (catégorie, sujet, verrouillage) : vérifie que j'ai **Gérer les salons** et **Gérer les rôles**."
        ancienne = discord.utils.get(guilde.categories, name=data.ANCIENNE_CATEGORIE)
        if ancienne and not ancienne.channels:   # l'ancienne catégorie unique, une fois vidée
            await ancienne.delete(reason="Remplacée par les nouvelles catégories")
    except discord.HTTPException:
        remarque = "\nJe n'ai pas pu créer ou ranger les catégories : il me manque la permission **Gérer les salons**."
    return remarque


async def installer_salons(guilde):
    """Crée les catégories, les salons manquants et les rôles de rang, puis range le tout. Renvoie le message de résultat."""
    crees = []
    simples = SALONS_SIMPLES
    await renommer_anciens_salons(guilde)
    try:
        for categorie, _ in data.CATEGORIES:   # créées d'abord, dans l'ordre, pour qu'elles s'affichent dans cet ordre
            if not discord.utils.get(guilde.categories, name=categorie):
                await guilde.create_category(categorie)
        for categorie, cle, nom, _, _ in plan_des_salons():
            if trouver_salon(guilde, nom):
                continue
            cat = discord.utils.get(guilde.categories, name=categorie) or await guilde.create_category(categorie)
            salon = await guilde.create_text_channel(nom, category=cat)
            if cle in PANNEAUX:
                await poster_panneau(salon, cle)
            elif simples[cle][3]:
                _, _, image, texte, _ = simples[cle]
                e = discord.Embed(description=texte, color=COULEUR)
                fichier = fichier_image(banniere(image)) if image else None
                try:
                    if fichier:
                        e.set_image(url=f"attachment://{banniere(image)}")
                        await salon.send(embed=e, file=fichier)
                    else:
                        await salon.send(embed=e)
                except discord.Forbidden:
                    pass
            crees.append(salon.mention)
        prive = await installer_tour_pros(guilde)
        if prive:
            crees.append(prive.mention + " (privé)")
    except discord.Forbidden:
        return ("Il me manque la permission **Gérer les salons**. Ajoute-la à mon rôle (Paramètres du serveur > Rôles) puis relance, "
                "ou crée les salons toi-même et utilise `/panneau` dans chacun.")
    roles = ""
    try:
        existants = {r.name for r in guilde.roles}
        nouveaux = [r for r in data.ARENE_RANGS if r[1] not in existants]
        for _, nom, _, couleur in nouveaux:
            await guilde.create_role(name=nom, colour=discord.Colour(couleur), reason="Rangs de l'arène")
        if nouveaux:
            roles = f"\nRôles de rang créés : {', '.join(r[1] for r in nouveaux)}."
    except discord.HTTPException:
        roles = "\nJe n'ai pas pu créer les rôles de rang : il me manque la permission **Gérer les rôles**."
    try:
        for _, nom_role, couleur in data.ROLES_NIVEAU:
            if not discord.utils.get(guilde.roles, name=nom_role):
                await guilde.create_role(name=nom_role, colour=discord.Colour(couleur), reason="Paliers de niveau de compte")
                roles += f"\nRôle de niveau créé : {nom_role}."
        if not discord.utils.get(guilde.roles, name=data.ROLE_BOSS):
            await guilde.create_role(name=data.ROLE_BOSS, mentionable=True, reason="Mentionné à l'apparition d'un boss de salon")
            roles += f"\nRôle **{data.ROLE_BOSS}** créé : les joueurs le prennent dans le salon des boss pour être prévenus."
        role = discord.utils.get(guilde.roles, name=data.ROLE_JOUEUR)
        if not role:
            role = await guilde.create_role(name=data.ROLE_JOUEUR, colour=discord.Colour(data.COULEUR_ROLE_JOUEUR), hoist=True,
                                            reason="Débloque les salons du jeu")
            roles += f"\nRôle **{data.ROLE_JOUEUR}** créé : il débloque les salons du jeu quand on appuie sur Commencer."
        # Les joueurs déjà inscrits le reçoivent tout de suite, sinon ils perdraient l'accès aux salons.
        deja = [dict(j)["user_id"] for j in db.tous_les_joueurs(guilde.id)]
        donnes = sum([await donner_role_joueur(guilde, u) for u in deja])
        if deja:
            roles += f"\nRôle {data.ROLE_JOUEUR} donné à {donnes} joueur(s) déjà inscrit(s) sur {len(deja)}."
    except discord.HTTPException:
        roles += f"\nJe n'ai pas pu créer le rôle {data.ROLE_JOUEUR} : il me manque la permission **Gérer les rôles**."
    roles += await amenager(guilde)
    await ecrire_guide(guilde)
    await publier_maj(guilde)
    rangement = "Salons rangés par catégories : " + " · ".join(c for c, _ in data.CATEGORIES) + "."
    if not crees:
        return rangement + roles
    return "Salons créés : " + " ".join(crees) + "\n" + rangement + roles


# ============================ MÉNAGE DES MESSAGES =============================
# Les messages privés du jeu (« Toi seul peux voir ceci ») s'effacent tout seuls : quelques minutes après le dernier clic dessus,
# ou tout de suite quand le joueur en ouvre un autre depuis un panneau du même salon. La liste est gardée dans la base :
# un redémarrage du bot n'oublie rien. Discord ne permet d'effacer ces messages que pendant 15 minutes après le dernier clic.
MENAGE_DELAI = 5 * 60
MENAGE_LIMITE = 14 * 60


async def effacer_prive(app, jeton, message):
    try:
        await discord.Webhook.partial(app, jeton, client=bot).delete_message(message)
    except Exception:
        pass   # déjà fermé par le joueur, ou trop vieux


async def menage(i):
    """Note le message privé auquel cette interaction a répondu, pour l'effacer plus tard."""
    if i.guild_id is None:
        return
    depuis_panneau = i.message is not None and not i.message.flags.ephemeral

    async def noter():
        await asyncio.sleep(3)   # le temps que la réponse parte
        try:
            message = await i.original_response()
        except Exception:
            return
        if not message.flags.ephemeral:   # jamais un message public (panneau, duel, boss)
            return
        if depuis_panneau:   # un nouveau message s'ouvre : les précédents du joueur dans ce salon s'en vont
            for ancien in db.menage_du_joueur(i.channel_id, i.user.id):
                if ancien["message_id"] != message.id:
                    db.menage_oublier(ancien["message_id"])
                    asyncio.create_task(effacer_prive(ancien["app_id"], ancien["jeton"], ancien["message_id"]))
        db.menage_noter(message.id, i.token, i.application_id, time.time(), i.channel_id, i.user.id)

    asyncio.create_task(noter())


SALONS_BALAYES_DELAI = 30 * 60   # raid et Worlds : les messages de combat s'effacent 30 minutes après leur dernière modification


async def balayer_salons_de_combat():
    """Efface les vieux messages du bot dans les salons du raid et des Worlds. Les panneaux (et les messages épinglés) restent."""
    limite = discord.utils.utcnow().timestamp() - SALONS_BALAYES_DELAI
    for guilde in bot.guilds:
        for nom in (data.SALON_RAID, data.SALON_TOUR_PROS):
            salon = trouver_salon(guilde, nom)
            if not salon:
                continue
            try:
                async for m in salon.history(limit=60):
                    if m.author.id != bot.user.id or m.pinned or (m.edited_at or m.created_at).timestamp() > limite:
                        continue
                    boutons = [str(getattr(c, "custom_id", "") or "") for rangee in m.components for c in getattr(rangee, "children", [])]
                    if any(c.startswith(("f:raid_", "f:tp_")) and c != "f:raid_rune" for c in boutons):
                        continue   # le panneau du salon
                    await m.delete()
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"Balayage de {nom} : {e}")


async def boucle_menage():
    """Efface les messages privés restés sans clic depuis MENAGE_DELAI."""
    passages = 0
    while True:
        await asyncio.sleep(20)
        passages += 1
        if passages % 9 == 0:   # toutes les trois minutes
            try:
                await balayer_salons_de_combat()
            except Exception as e:
                print(f"Balayage des salons : {e}")
        try:
            maintenant = time.time()
            for m in db.menage_dus(maintenant - MENAGE_DELAI):
                db.menage_oublier(m["message_id"])
                if maintenant - m["moment"] < MENAGE_LIMITE:
                    await effacer_prive(m["app_id"], m["jeton"], m["message_id"])
        except Exception as e:
            print(f"Ménage des messages : {e}")


# ====================== COMMANDES D'ADMINISTRATION ===========================
@bot.tree.command(description="Crée et range les catégories, les salons et les panneaux du jeu")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
async def installer(i: discord.Interaction):
    await i.response.defer(ephemeral=True)
    try:
        texte = await installer_salons(i.guild)
    except ERREURS_RESEAU as erreur:
        texte = f"La connexion à Discord a eu un raté pendant l'installation ({type(erreur).__name__}). Relance `/installer` : ce qui est déjà fait ne sera pas refait."
    await reessayer(lambda: i.followup.send(texte, ephemeral=True))


@bot.tree.command(description="Poste un panneau à boutons dans ce salon")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.choices(type=[app_commands.Choice(name=p["titre"], value=c) for c, p in PANNEAUX.items()])
async def panneau(i: discord.Interaction, type: app_commands.Choice[str]):
    try:
        await poster_panneau(i.channel, type.value)
    except discord.Forbidden:
        await i.response.send_message("Je n'ai pas le droit d'écrire dans ce salon.", ephemeral=True)
        return
    await i.response.send_message("Panneau posté.", ephemeral=True)


async def actualiser_panneaux(guilde):
    """Met à jour en place tous les panneaux du serveur (texte et boutons). Renvoie le nombre de panneaux mis à jour."""
    # N'importe quel bouton du panneau permet de le reconnaître (le premier affiché n'est pas toujours le premier déclaré).
    premier_bouton = {enfant.custom_id: cle for cle, pan in PANNEAUX.items() for enfant in pan["vue"]().children
                      if getattr(enfant, "custom_id", None)}
    total = 0
    for salon in guilde.text_channels:
        try:
            async for message in salon.history(limit=30):
                if message.author.id != bot.user.id or not message.components:
                    continue
                enfants = getattr(message.components[0], "children", [])
                cle = premier_bouton.get(getattr(enfants[0], "custom_id", None)) if enfants else None
                if cle:
                    async def poser(message=message, cle=cle):   # refait l'embed et rouvre la bannière à chaque essai
                        e, fichier = embed_panneau(cle)
                        await message.edit(embed=e, view=PANNEAUX[cle]["vue"](), attachments=[fichier] if fichier else [])
                    try:
                        await reessayer(poser)
                    except discord.Forbidden:
                        e, _ = embed_panneau(cle)
                        e.set_image(url=None)
                        await message.edit(embed=e, view=PANNEAUX[cle]["vue"](), attachments=[])
                    total += 1
        except ERREURS_RESEAU:
            continue   # salon illisible pour le bot, ou connexion coupée malgré les nouveaux essais : on passe au suivant
    return total


@bot.tree.command(description="Met à jour tous les panneaux à boutons après une modification du bot")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
async def actualiser(i: discord.Interaction):
    await i.response.defer(ephemeral=True)
    try:
        n = await actualiser_panneaux(i.guild)
        remarque = await amenager(i.guild)
        await ecrire_guide(i.guild)
        await publier_maj(i.guild)
        texte = (f"{n} panneau(x) mis à jour, salons rangés et verrouillés." if n else "Aucun panneau trouvé. Utilise `/installer` ou `/panneau`.") + remarque
    except ERREURS_RESEAU as erreur:
        texte = f"La connexion à Discord a eu un raté pendant la mise à jour ({type(erreur).__name__}). Relance `/actualiser`."
    await reessayer(lambda: i.followup.send(texte, ephemeral=True))


async def est_proprietaire(i):
    """True si c'est le propriétaire du bot : celui qui l'a créé sur le portail développeur
    (ou l'identifiant indiqué par PROPRIETAIRE= dans le fichier .env)."""
    force = os.environ.get("PROPRIETAIRE", "").strip()
    if force.isdigit():
        return i.user.id == int(force)
    if bot.proprietaires is None:
        info = await bot.application_info()
        bot.proprietaires = {m.id for m in info.team.members} if info.team else {info.owner.id}
    return i.user.id in bot.proprietaires


@bot.tree.command(description="Réservé au propriétaire du bot : donne ou retire des golds à un joueur")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.describe(joueur="Le joueur à créditer", montant="Nombre de golds (négatif pour en retirer)")
async def golds(i: discord.Interaction, joueur: discord.Member, montant: app_commands.Range[int, -1000000, 1000000]):
    if not await est_proprietaire(i):
        await i.response.send_message("Cette commande est réservée au propriétaire du bot.", ephemeral=True)
        return
    p = db.get_joueur(i.guild_id, joueur.id)
    if not p:
        await i.response.send_message(f"{joueur.display_name} n'a pas encore de compte.", ephemeral=True)
        return
    p["golds"] = max(0, p["golds"] + montant)
    db.sauver(p)
    await i.response.send_message(f"{'+' if montant >= 0 else ''}{montant} golds pour {joueur.mention}. Nouveau solde : {p['golds']} golds.", ephemeral=True)


CADEAUX = {   # /cadeau : (champ du joueur, nom au pluriel, emoji)
    "tickets": ("tickets_worlds", "tickets Worlds", "🎟️"),
    "charges": ("charges", "charges de jungle", "⚡"),
    "lec": ("lec_essais", "LEC du jour rendue(s)", "🎮"),
    "packs": ("packs_niveau", "packs de niveau", "📦"),
    "packs_ur": ("packs_ur", "packs UR", "💎"),
    "packs_pro": ("packs_pro", "packs Worlds", "🏆"),
    "packs_lec": ("packs_lec", "packs LEC", "🇪🇺"),
}


def donner_cadeau(p, quoi, nombre):
    """Applique un cadeau à un joueur. Renvoie le texte du message privé."""
    champ, nom, emoji = CADEAUX[quoi]
    if quoi == "charges":
        charges(p)
        p["charges"] += nombre
        reste = f"⚡ {p['charges']} charges"
    elif quoi == "tickets":
        p["tickets_worlds"] = min(data.WORLDS_TICKETS_MAX, p["tickets_worlds"] + nombre)
        reste = f"🎟️ {p['tickets_worlds']}/{data.WORLDS_TICKETS_MAX}"
    elif quoi == "lec":   # rend des essais LEC du jour
        if p["lec_jour"] == aujourdhui():
            p["lec_essais"] = max(0, p["lec_essais"] - nombre)
        reste = f"🎮 {lec_essais_restants(p)}/{data.LEC_ESSAIS} LEC aujourd'hui"
    else:
        p[champ] = p.get(champ, 0) + nombre
        reste = f"{emoji} {p[champ]} à ouvrir"
        if champ.startswith("packs"):
            db.journal_pack(p["guild_id"], p["user_id"], champ.replace("packs_", "") if champ != "packs_niveau" else "niveau", nombre, "cadeau")
    db.sauver(p)
    return f"🎁 **Cadeau** : {emoji} **+{nombre} {nom}** ({reste})."


@bot.tree.command(description="Réservé au propriétaire : offre tickets, charges, LEC ou packs à un joueur ou à tous")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.describe(quoi="Ce que tu offres", nombre="Combien", joueur="Laisse vide pour tout le monde", message="Un mot ajouté au message privé (facultatif)")
@app_commands.choices(quoi=[app_commands.Choice(name=f"{v[2]} {v[1]}", value=k) for k, v in CADEAUX.items()])
async def cadeau(i: discord.Interaction, quoi: app_commands.Choice[str], nombre: app_commands.Range[int, 1, 100], joueur: discord.Member = None, message: str = ""):
    if not await est_proprietaire(i):
        await i.response.send_message("Cette commande est réservée au propriétaire du bot.", ephemeral=True)
        return
    ids = [joueur.id] if joueur else [r[0] for r in db.con.execute("SELECT user_id FROM joueurs WHERE guild_id=?", (i.guild_id,)).fetchall()]
    servis = []
    for u in ids:
        p = db.get_joueur(i.guild_id, u)
        if not p:
            continue
        texte = donner_cadeau(p, quoi.value, nombre)
        message_prive(p, texte + (f"\n{message}" if message else ""))
        servis.append(p.get("pseudo") or str(u))
    db.con.commit()
    if not servis:
        return await i.response.send_message(f"{joueur.display_name if joueur else 'Personne'} n'a pas encore de compte.", ephemeral=True)
    await i.response.send_message(f"🎁 {quoi.name} ×{nombre} offert à **{len(servis)}** joueur{'s' if len(servis) > 1 else ''} : {', '.join(servis)}. "
                                  "Chacun a reçu un message privé.", ephemeral=True)


class ModaleAnnonce(discord.ui.Modal, title="Annonce dans le salon des annonces"):
    titre = discord.ui.TextInput(label="Titre", max_length=200, placeholder="Par exemple : Nouveau mode de jeu !")
    texte = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph, max_length=3800,
                                 placeholder="Le texte de l'annonce. Le gras s'écrit **comme ça**.")

    def __init__(self, mentionner=False):
        super().__init__()
        self.mentionner = mentionner

    async def on_submit(self, i):
        salon = trouver_salon(i.guild, data.SALON_ANNONCES) or trouver_salon(i.guild, data.SALON_MAJ)
        if not salon:
            return await i.response.send_message("Je ne trouve pas le salon des annonces.", ephemeral=True)
        e = discord.Embed(color=COULEUR, description=f"# 📰 {self.titre.value}\n-# {time.strftime('%d/%m/%Y')}\n\n{self.texte.value}")
        try:
            await salon.send(content="@everyone" if self.mentionner else None, embed=e,
                             allowed_mentions=discord.AllowedMentions(everyone=self.mentionner))
        except discord.HTTPException as erreur:
            return await i.response.send_message(f"L'annonce n'a pas pu partir : {erreur}", ephemeral=True)
        await i.response.send_message(f"📰 Annonce publiée dans {salon.mention}.", ephemeral=True)


@bot.tree.command(description="Réservé au propriétaire : publie une annonce dans le salon des annonces")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.describe(mentionner="Prévenir tout le monde avec @everyone (non par défaut)")
async def annonce(i: discord.Interaction, mentionner: bool = False):
    if not await est_proprietaire(i):
        await i.response.send_message("Cette commande est réservée au propriétaire du bot.", ephemeral=True)
        return
    await i.response.send_modal(ModaleAnnonce(mentionner))


@bot.tree.command(description="Réservé au propriétaire du bot : fait apparaître un boss de salon tout de suite")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.choices(lequel=[app_commands.Choice(name=nom, value=cle) for cle, nom, _, _, _ in data.BOSS_MONDE])
async def boss(i: discord.Interaction, lequel: app_commands.Choice[str] = None):
    if not await est_proprietaire(i):
        await i.response.send_message("Cette commande est réservée au propriétaire du bot.", ephemeral=True)
        return
    await i.response.defer(ephemeral=True)
    await i.followup.send(await apparaitre(i.guild, lequel.value if lequel else None), ephemeral=True)


@bot.tree.command(description="Réservé au propriétaire du bot : affiche les golds des joueurs")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.describe(joueur="Laisse vide pour voir tous les joueurs")
async def goldcheck(i: discord.Interaction, joueur: discord.Member = None):
    if not await est_proprietaire(i):
        await i.response.send_message("Cette commande est réservée au propriétaire du bot.", ephemeral=True)
        return
    if joueur:
        p = db.get_joueur(i.guild_id, joueur.id)
        if not p:
            await i.response.send_message(f"{joueur.display_name} n'a pas encore de compte.", ephemeral=True)
            return
        await i.response.send_message(
            f"**{joueur.display_name}** : **{p['golds']} golds** · étage {p['etage']} · {p['packs']} packs ouverts · {len(db.cartes(i.guild_id, joueur.id))} cartes",
            ephemeral=True)
        return
    joueurs = db.tous_les_joueurs(i.guild_id)
    lignes = [f"**{n}.** <@{p['user_id']}> · **{p['golds']} golds** · étage {p['etage']} · {p['packs']} packs" for n, p in enumerate(joueurs[:40], 1)]
    total = sum(p["golds"] for p in joueurs)
    e = discord.Embed(color=COULEUR, description=(
        f"# 💰 Golds des joueurs\n" + ("\n".join(lignes) or "Aucun joueur pour l'instant.")
        + (f"\n… et {len(joueurs) - 40} autres" if len(joueurs) > 40 else "")))
    e.set_footer(text=f"{len(joueurs)} joueurs · {total} golds en circulation")
    await i.response.send_message(embed=e, ephemeral=True)


# ============================ PORTE DU SITE ==================================
# 16 octobre : le site (site_web/serveur.py) demande au bot d'ouvrir les packs. Tout passe ainsi par le même code et la même base que
# sur Discord (taux, garanties, doublons, annonces), sans risque que le site et le bot s'écrasent l'un l'autre.
# La porte n'écoute que sur cet ordinateur (127.0.0.1), jamais sur internet, et demande une clé rangée dans site_web/cle_bot.txt.
PORTE_SITE_PORT = 8082
CLE_SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site_web", "cle_bot.txt")
PACKS_SITE = ("gratuit", "normal", "niveau", "ur", "pro", "lec", "normal10", "mega", "niveau5", "ur5", "pro5", "lec5")


def cle_site():
    """La clé partagée avec le site : créée au premier lancement, puis relue."""
    import secrets
    try:
        with open(CLE_SITE, encoding="utf-8") as f:
            cle = f.read().strip()
        if len(cle) >= 32:
            return cle
    except OSError:
        pass
    cle = secrets.token_urlsafe(32)
    os.makedirs(os.path.dirname(CLE_SITE), exist_ok=True)
    with open(CLE_SITE, "w", encoding="utf-8") as f:
        f.write(cle)
    return cle


def carte_site(cid, statut):
    lignes = (statut or "").split("\n")
    return {"id": cid, "nom": data.CARTES[cid]["nom"], "rarete": "LR" if cid.endswith("LR") else data.CARTES[cid]["rarete"],
            "statut": lignes[0], "en_plus": [l for l in lignes[1:] if l.strip()]}


def coach_site(tire, nombre, equipe_auto):
    c = data.COACHS[tire]
    return {"pseudo": tire, "poste": c["poste"], "equipe": c["nom_equipe"], "bonus": texte_part_coach(tire).replace("**", ""),
            "nouveau": nombre == 1, "nombre": nombre, "equipe_auto": equipe_auto}


def ouvrir_pour_site(g, u, pack):
    """Ouvre un ou plusieurs packs pour le site, exactement comme les boutons Discord, sans l'animation :
    gratuit / normal / niveau / ur / pro / lec (ouvrir_pack, ouvrir_pack_pro), normal10 (bouton « 10 packs »), mega (mega_tirage),
    ur5 / pro5 / lec5 (les boutons « Ouvrir x5 »), niveau5 (cinq packs de niveau à la suite).
    Aucune attente (await) entre la lecture du joueur et sa sauvegarde : rien d'autre ne peut se glisser au milieu."""
    from types import SimpleNamespace
    p = db.get_joueur(g, u)
    if not p:
        return {"erreur": "Tu n'as pas encore de compte. Va dans le salon d'accueil du serveur Discord et appuie sur « Commencer »."}
    faux = SimpleNamespace(guild_id=g, user=SimpleNamespace(id=u))

    if pack in ("gratuit", "normal", "niveau", "ur"):   # ouvrir_pack
        if pack == "ur":
            if p["packs_ur"] <= 0:
                reste = data.UR_TOUS_LES - p["packs"] % data.UR_TOUS_LES
                return {"erreur": f"Tu n'as pas de pack UR. Tu en gagnes un tous les {data.UR_TOUS_LES} packs ouverts : encore {reste}."}
            p["packs_ur"] -= 1
        elif pack == "niveau":
            if p["packs_niveau"] <= 0:
                return {"erreur": "Tu n'as pas de pack de niveau à ouvrir. Tu en gagnes un à chaque niveau de compte."}
            p["packs_niveau"] -= 1
        elif pack == "gratuit":
            attente = data.DELAI_GRATUIT - (time.time() - p["dernier_gratuit"])
            if attente > 0:
                return {"erreur": f"Prochain pack gratuit dans {duree(attente)}."}
            p["dernier_gratuit"] = time.time()
        else:
            if p["golds"] < data.PRIX_PACK:
                return {"erreur": f"Il te faut {data.PRIX_PACK} golds, tu en as {p['golds']}."}
            p["golds"] -= data.PRIX_PACK
        cid = (tirer_pack_ur(faux, p, set(db.cartes(g, u))) if pack == "ur" else
               combat.tirer(p, gratuit=pack == "gratuit", taux=data.TAUX_NIVEAU if pack == "niveau" else None, bonus=bonus_packs(g, u)))
        statut = donner(p, cid)
        db.sauver(p)
        if pack == "ur":
            db.journal_pack(g, u, "ur", -1, cid + (" (garantie)" if p.pop("_garantie", False) else "") + " · site")
        return {"cartes": [carte_site(cid, statut)], "annonce": [cid]}

    if pack == "niveau5":   # comme cinq ouvertures de pack de niveau à la suite
        if p["packs_niveau"] <= 0:
            return {"erreur": "Tu n'as pas de pack de niveau à ouvrir. Tu en gagnes un à chaque niveau de compte."}
        cartes, tirees, ouverts = [], [], min(5, p["packs_niveau"])
        for _ in range(ouverts):
            p["packs_niveau"] -= 1
            cid = combat.tirer(p, taux=data.TAUX_NIVEAU, bonus=bonus_packs(g, u))
            cartes.append(carte_site(cid, donner(p, cid)))
            tirees.append(cid)
        db.sauver(p)
        return {"cartes": cartes, "annonce": tirees, "ouverts": ouverts}

    if pack == "ur5":   # ouvrir_packs_ur_x5
        if p["packs_ur"] <= 0:
            reste = data.UR_TOUS_LES - p["packs"] % data.UR_TOUS_LES
            return {"erreur": f"Tu n'as pas de pack UR. Tu en gagnes un tous les {data.UR_TOUS_LES} packs ouverts : encore {reste}."}
        possedees = set(db.cartes(g, u))
        cartes, tirees, ouverts = [], [], min(5, p["packs_ur"])
        for _ in range(ouverts):
            p["packs_ur"] -= 1
            cid = tirer_pack_ur(faux, p, possedees)
            db.journal_pack(g, u, "ur", -1, cid + (" (garantie)" if p.pop("_garantie", False) else "") + " · x5 · site")
            cartes.append(carte_site(cid, donner(p, cid)))
            possedees.add(cid)
            tirees.append(cid)
        db.sauver(p)
        return {"cartes": cartes, "annonce": tirees, "ouverts": ouverts}

    if pack == "normal10":   # le bouton « 10 packs »
        if p["golds"] < data.PRIX_PACK_10:
            return {"erreur": f"Il te faut {data.PRIX_PACK_10} golds, tu en as {p['golds']}."}
        p["golds"] -= data.PRIX_PACK_10
        lec = db.lec_equipes(g, u)
        bonus = bonus_packs(g, u)
        tirages = [combat.tirer(p, bonus=bonus) for _ in range(9)]
        garanti = None if any(data.CARTES[c]["rarete"] in ("SR", "SSR", "UR") for c in tirages) else "SR"
        tirages.append(combat.tirer(p, minimum=garanti, bonus=bonus))
        for ur in combat.ur_lec_multi(lec, set(db.cartes(g, u)), 1):   # UR de la LEC, très rare
            faible = min(range(len(tirages)), key=lambda k: data.RARETES.index(data.CARTES[tirages[k]]["rarete"]))
            tirages[faible] = ur
        tirages.sort(key=lambda c: data.RARETES.index(data.CARTES[c]["rarete"]))   # les plus rares à la fin
        cartes = [carte_site(c, donner(p, c)) for c in tirages]
        db.sauver(p)
        return {"cartes": cartes, "annonce": tirages}

    if pack == "mega":   # mega_tirage
        if p["golds"] < data.MEGA_PRIX:
            return {"erreur": f"Il te faut {data.MEGA_PRIX} golds pour un méga tirage, tu en as {p['golds']}."}
        p["golds"] -= data.MEGA_PRIX
        packs_ur = p["packs_ur"]
        lec = db.lec_equipes(g, u)
        bonus = bonus_packs(g, u)
        tirages = [combat.tirer(p, bonus=bonus) for _ in range(data.MEGA_CARTES)]
        for ur in combat.ur_lec_multi(lec, set(db.cartes(g, u)), data.MEGA_CARTES // 10):
            faible = min(range(len(tirages)), key=lambda k: data.RARETES.index(data.CARTES[tirages[k]]["rarete"]))
            tirages[faible] = ur
        p["packs_ur"] = packs_ur + 1   # le pack UR offert remplace celui du compteur
        p.pop("_pack_ur", None)
        if not any(data.CARTES[c]["rarete"] in ("SSR", "UR") for c in tirages):   # le SSR garanti
            faible = min(range(len(tirages)), key=lambda k: data.RARETES.index(data.CARTES[tirages[k]]["rarete"]))
            tirages[faible] = random.choice(data.PAR_RARETE["SSR"])
            p["pitie"] = 0
        tirages.sort(key=lambda c: (-data.RARETES.index(data.CARTES[c]["rarete"]), data.CARTES[c]["nom"]))
        cartes = [carte_site(c, donner(p, c)) for c in tirages]
        db.sauver(p)
        return {"cartes": cartes, "annonce": tirages, "message": "💎 Un pack UR t'est offert avec le méga tirage."}

    lec = pack in ("lec", "lec5")
    champ = "packs_lec" if lec else "packs_pro"
    equipes = db.lec_equipes(g, u) if lec else db.worlds_equipes(g, u)
    if p[champ] <= 0 or not equipes:
        return {"erreur": "Tu n'as pas de pack LEC à ouvrir : ils se gagnent en battant des équipes de la LEC." if lec else
                          "Tu n'as pas de pack Worlds à ouvrir : ils se gagnent en éliminant des équipes aux Worlds."}

    if pack in ("pro5", "lec5"):   # ouvrir_packs_pro_x5
        possedees = set(db.cartes(g, u))
        cartes, coachs, a_annoncer, ouverts = [], [], [], min(5, p[champ])
        for _ in range(ouverts):
            p[champ] -= 1
            if lec:
                genre, tire = combat.tirer_lec(p, equipes, possedees)
                bonus = []
            else:
                genre, tire = combat.tirer_pro(p, equipes, possedees)
                bonus = [c for c in (combat.tirer_pro_bonus(equipes) for _ in range(data.PRO_CARTES_BONUS)) if c]
            db.journal_pack(g, u, champ.replace("packs_", ""), -1, ("coach " if genre == "coach" else "") + tire
                            + (" (garantie)" if p.pop("_garantie", False) else "") + " · x5 · site")
            if genre == "coach":
                if not p["coach"]:
                    p["coach"] = tire   # le premier coach s'équipe tout seul
                n = db.coach_ajouter(g, u, tire)
                coachs.append(coach_site(tire, n, p["coach"] == tire))
            else:
                cartes.append(carte_site(tire, donner(p, tire)))
                possedees.add(tire)
                a_annoncer.append(tire)
            for c in bonus:
                cartes.append(carte_site(c, donner(p, c)))
                possedees.add(c)
                a_annoncer.append(c)
        db.sauver(p)
        return {"cartes": cartes, "coachs": coachs, "annonce": a_annoncer, "annonce_coachs": [c["pseudo"] for c in coachs], "ouverts": ouverts}

    p[champ] -= 1   # ouvrir_pack_pro
    bonus = []
    if lec:
        genre, tire = combat.tirer_lec(p, equipes, set(db.cartes(g, u)))
    else:
        genre, tire = combat.tirer_pro(p, equipes, set(db.cartes(g, u)))
        bonus = [c for c in (combat.tirer_pro_bonus(equipes) for _ in range(data.PRO_CARTES_BONUS)) if c]
    cartes_bonus = [carte_site(c, donner(p, c)) for c in bonus]
    if genre == "coach":
        if not p["coach"]:
            p["coach"] = tire
        db.sauver(p)
        db.journal_pack(g, u, "lec" if lec else "pro", -1, f"coach {tire} · site")
        nombre = db.coach_ajouter(g, u, tire)
        return {"cartes": cartes_bonus, "coachs": [coach_site(tire, nombre, p["coach"] == tire)], "annonce": bonus, "annonce_coachs": [tire]}
    statut = donner(p, tire)
    db.sauver(p)
    db.journal_pack(g, u, "lec" if lec else "pro", -1, tire + (" (garantie)" if p.pop("_garantie", False) else "") + " · site")
    return {"cartes": [carte_site(tire, statut)] + cartes_bonus, "annonce": [tire] + bonus}


async def annonces_site(g, u, resultat):
    """Les belles cartes tirées sur le site s'annoncent dans le salon des tirages, comme celles tirées sur Discord."""
    from types import SimpleNamespace
    guilde = bot.get_guild(g)
    if not guilde:
        return
    joueur = guilde.get_member(u) or SimpleNamespace(mention=f"<@{u}>")
    try:
        for pseudo in resultat.get("annonce_coachs", []):
            await annoncer_coach(guilde, joueur, pseudo)
        if resultat.get("annonce"):
            await annoncer(guilde, joueur, resultat["annonce"])
    except Exception as erreur:
        print(f"Annonce d'un tirage du site : {erreur!r}")


async def ouvrir_porte_site():
    """Démarre la petite porte locale du site. Si elle ne peut pas s'ouvrir, le bot continue sans elle."""
    import secrets
    from aiohttp import web
    cle = cle_site()

    async def ouvrir(requete):
        if requete.remote not in ("127.0.0.1", "::1") or not secrets.compare_digest(requete.headers.get("X-Cle", ""), cle):
            return web.json_response({"erreur": "Refusé."}, status=403)
        try:
            corps = await requete.json()
            g, u, pack = int(corps["guild_id"]), int(corps["user_id"]), str(corps["pack"])
        except Exception:
            return web.json_response({"erreur": "Demande illisible."}, status=400)
        if pack not in PACKS_SITE:
            return web.json_response({"erreur": "Ce pack ne s'ouvre pas sur le site."}, status=400)
        try:
            resultat = ouvrir_pour_site(g, u, pack)
        except Exception as erreur:
            print(f"Ouverture depuis le site ({u}, {pack}) : {erreur!r}")
            return web.json_response({"erreur": "Le pack n'a pas pu s'ouvrir. Réessaie."}, status=500)
        if "erreur" in resultat:
            return web.json_response(resultat, status=400)
        asyncio.create_task(annonces_site(g, u, resultat))
        return web.json_response({k: v for k, v in resultat.items() if not k.startswith("annonce")})

    app = web.Application()
    app.router.add_post("/ouvrir", ouvrir)
    app.router.add_get("/etat", lambda r: web.json_response({"ok": True}))
    try:
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", PORT_PORTE_SITE()).start()
        print(f"Porte du site ouverte sur 127.0.0.1:{PORT_PORTE_SITE()}")
    except Exception as erreur:
        print(f"Porte du site : impossible de l'ouvrir ({erreur!r}). Les packs ne s'ouvriront pas depuis le site.")


def PORT_PORTE_SITE():
    return int(os.environ.get("PORTE_SITE_PORT", PORTE_SITE_PORT))


if __name__ == "__main__":
    token = os.environ.get("TOKEN")
    if not token:
        raise SystemExit("Token manquant : copie ton fichier .env dans ce dossier (TOKEN=ton_token)")
    bot.run(token)
