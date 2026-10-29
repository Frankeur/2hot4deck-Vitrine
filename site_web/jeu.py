"""2Hot4Deck · le moteur du jeu, côté site (16 octobre 2026).

Le site joue tout seul, sans le bot Discord : il reprend les mêmes règles (data.py, combat.py, et les fonctions de jeu de
bot.py) mais avec SA PROPRE base, site_web/site.db. Le jeu Discord (faille.db) n'est jamais touché.

- Au premier lancement, site.db est une copie de faille.db (les joueurs gardent leur progression du moment).
- remettre_a_zero() refait cette copie quand on veut repartir de l'état actuel du jeu Discord.
- Toutes les actions passent par un seul verrou : une à la fois, rien ne peut s'écraser.
"""
import json, os, random, sqlite3, sys, threading, time

ICI = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.dirname(ICI)
BASE_DISCORD = os.path.join(BOT, "faille.db")
BASE_SITE = os.path.join(ICI, "site.db")
VERROU = threading.RLock()


def copier_depuis_discord():
    """Copie propre de faille.db vers site.db, même si le bot est en train de tourner (sauvegarde intégrée de SQLite)."""
    source = sqlite3.connect(f"file:{BASE_DISCORD}?mode=ro", uri=True)
    cible = sqlite3.connect(BASE_SITE + ".tmp")
    with cible:
        source.backup(cible)
    source.close(); cible.close()
    os.replace(BASE_SITE + ".tmp", BASE_SITE)


if not os.path.exists(BASE_SITE):
    copier_depuis_discord()

# Le moteur du bot ouvre sa base au moment de l'import : on lui donne site.db, utilisable depuis plusieurs fils du serveur web.
os.environ["FAILLE_DB"] = BASE_SITE
sys.path.insert(0, BOT)
_connect = sqlite3.connect
sqlite3.connect = lambda *a, **k: _connect(*a, **{**k, "check_same_thread": False})
try:
    import db, data, combat
    import bot as regles          # seulement pour ses fonctions de jeu (tirages, dons, XP) : rien ne se connecte à Discord
finally:
    sqlite3.connect = _connect


def remettre_a_zero():
    """Refait site.db à partir de faille.db (la progression du site repart de celle du jeu Discord)."""
    with VERROU:
        db.con.close()
        copier_depuis_discord()
        db.con = sqlite3.connect(BASE_SITE, check_same_thread=False)
        db.con.row_factory = sqlite3.Row


# ---------------------------------------------------------------- les packs
def ouvrir(g, u, pack):
    """Mêmes packs, mêmes taux et mêmes garanties que sur Discord (le code est celui du bot)."""
    if pack not in regles.PACKS_SITE:
        return {"erreur": "Ce pack ne s'ouvre pas sur le site."}
    with VERROU:
        return regles.ouvrir_pour_site(g, u, pack)


# ---------------------------------------------------------------- la tour
def _jouer(etage, ids, possedees):
    return _jouer_contre(combat.ennemis(etage), ids, possedees, hemorragie=etage > 100)


def _jouer_contre(adversaires, ids, possedees, hemorragie=False):
    """Joue le combat avec le moteur du bot et enregistre chaque action (qui agit, ce qui se passe, l'état de tous après),
    pour que le site puisse le rejouer pas à pas. Le moteur n'est pas modifié : on écoute seulement ses étapes."""
    actions, etat, tous_ref = [], {"jref": None, "n": 0, "tour": 0}, {}
    orig_c, orig_f = combat.commencer_action, combat.finir_action

    def noter(u, passe=False):
        j, tous = etat["jref"], tous_ref["t"]
        lignes = j[etat["n"]:]
        etat["n"] = len(j)
        actions.append({"t": etat["tour"], "a": next(k for k, x in enumerate(tous) if x is u), "passe": passe,
                        "l": [l.replace("**", "") for l in lignes],
                        "e": [[max(0, round(x["pv"])), round(x["bouclier"]), round(x["jauge"]), x["cout"] or 0] for x in tous]})

    def c(u, tous, journal):
        tous_ref["t"] = tous
        if journal is not etat["jref"]:
            etat["jref"], etat["n"] = journal, 0
            etat["tour"] += 1
        r = orig_c(u, tous, journal)
        if not r:
            noter(u, passe=True)
        return r

    def f(u):
        orig_f(u)
        noter(u)

    combat.commencer_action, combat.finir_action = c, f
    try:
        equipe = combat.equipe_joueur(ids, possedees)
        depart = combat.photo(equipe + adversaires)
        victoire, tours = combat.simuler_detail(equipe, adversaires, hemorragie=hemorragie)
    finally:
        combat.commencer_action, combat.finir_action = orig_c, orig_f
    return victoire, tours, depart, actions


def _nom_boss(nom):
    import re, unicodedata
    s = unicodedata.normalize("NFD", nom.lower())
    return "boss_" + re.sub(r"[^a-z0-9]+", "_", "".join(ch for ch in s if unicodedata.category(ch) != "Mn")).strip("_")


def image_unite(cid, nom):
    if cid:
        return f"/cartes/{cid}"
    boss = _nom_boss(nom)
    return f"/img/{boss}.jpg" if os.path.exists(os.path.join(BOT, "images", boss + ".jpg")) else None


def fiches_unites(depart, portraits=None):
    """Ce que l'arène du site doit savoir de chaque combattant. portraits : {nom : carte} pour les gardiens qui ont une carte."""
    portraits = portraits or {}
    res = []
    for x in depart:
        cid = x["cid"] or portraits.get(x["nom"])
        res.append({"nom": x["nom"], "cid": x["cid"], "camp": x["camp"], "pvmax": round(x["pvmax"]), "pv": round(x["pv"]),
                    "bouclier": round(x["bouclier"]), "jauge": round(x["jauge"]), "cout": x["cout"] or 0,
                    "image": image_unite(cid, x["nom"]), "boss": x["camp"] == 1 and not cid,
                    "rarete": ("LR" if cid.endswith("LR") else data.CARTES[cid]["rarete"]) if cid in data.CARTES else None})
    return res


def tour_etat(g, u):
    """Ce que montre la page de la tour : l'étage, le prochain adversaire, l'équipe."""
    with VERROU:
        p = db.get_joueur(g, u)
        if not p:
            return None
        possedees = db.cartes(g, u)
        ids = regles.equipe_ids(p, possedees)
        prochain = min(p["etage"] + 1, data.TOUR_MAX)
        adv = combat.ennemis(prochain)
        return {"etage": p["etage"], "max": data.TOUR_MAX, "prochain": prochain, "fini": p["etage"] >= data.TOUR_MAX,
                "boss": combat.est_boss(prochain), "equipe": ids,
                "adversaires": [{"nom": a["nom"], "image": image_unite(a["cid"], a["nom"]), "pv": round(a["pvmax"]), "boss": not a["cid"]} for a in adv]}


def tour_combattre(g, u):
    """L'étage suivant, avec les mêmes récompenses que le bouton « Étage suivant » de Discord (golds, XP des cartes,
    XP de compte et packs de niveau, pack de palier tous les 5 étages)."""
    with VERROU:
        p = db.get_joueur(g, u)
        if not p:
            return {"erreur": "Pas de compte 2Hot4Deck."}
        possedees = db.cartes(g, u)
        ids = regles.equipe_ids(p, possedees)
        if not ids:
            return {"erreur": "Ton équipe est vide : compose-la dans « Ma collection »."}
        if p["etage"] >= data.TOUR_MAX:
            return {"erreur": f"Tu as vaincu les {data.TOUR_MAX} étages de la tour."}
        etage = p["etage"] + 1
        victoire, tours, depart, actions = _jouer(etage, ids, possedees)
        regles.noter_combat(p, "tour_site", etage, victoire, len(tours), tours[-1]["etat"], possedees)
        unites = fiches_unites(depart)
        fin = tours[-1]["journal"][-1] if tours and tours[-1]["journal"] and tours[-1]["journal"][-1].startswith("⏱️") else ""
        res = {"etage": etage, "boss": combat.est_boss(etage), "victoire": victoire, "tours": len(tours), "unites": unites,
               "actions": actions, "fin": fin.replace("**", "")}
        if victoire:
            golds = int((data.TOUR_GOLDS[0] + data.TOUR_GOLDS[1] * etage) * regles.bonus_golds(ids, possedees))
            xp = data.TOUR_XP[0] + data.TOUR_XP[1] * etage
            p["etage"] = etage
            p["golds"] += golds
            carte_pack, nom_pack = None, ""
            if etage == data.TOUR_SSR_GARANTI:
                carte_pack, nom_pack = combat.tirer(p, taux={"SSR": 100}), "Pack du boss : SSR garanti"
            elif combat.est_boss(etage):
                carte_pack, nom_pack = combat.tirer(p, taux=data.TAUX_BOSS), "Pack du boss (taux doublés)"
            elif etage % data.TOUR_PACK_SR == 0:
                carte_pack, nom_pack = combat.tirer(p, taux=data.TAUX_BOSS), "Pack de palier (taux doublés)"
            pack = None
            if carte_pack:
                pack = regles.carte_site(carte_pack, regles.donner(p, carte_pack))
                pack["titre"] = nom_pack
            montees = []
            for cid in ids:
                if combat.gagner_xp(cid, possedees[cid], xp):
                    montees.append(f"{data.CARTES[cid]['nom']} niv. {possedees[cid]['niveau']}")
                db.sauver_carte(g, u, cid, possedees[cid]["niveau"], possedees[cid]["xp"], possedees[cid]["etoiles"])
            part = 1.0
            if etage >= data.TOUR_XP_COMPTE[2]:
                part = data.TOUR_XP_COMPTE[0] ** (min(etage, 100) - data.TOUR_XP_COMPTE[2]) * (data.TOUR_XP_COMPTE[1] if combat.est_boss(etage) else 1)
            niveau_avant = p["niveau"]
            lignes, _ = regles.gagner_xp_compte(p, "tour", part)
            db.sauver(p)
            res["recompenses"] = {"golds": golds, "xp": xp, "xp_compte": int(round(data.XP_COMPTE["tour"] * part)), "montees": montees,
                                  "pack": pack, "niveau": p["niveau"] if p["niveau"] > niveau_avant else None,
                                  "niveau_lignes": [l.replace("**", "") for l in lignes]}
        else:
            conseils = []
            mieux = combat.meilleure_equipe(possedees)
            if combat.puissance_equipe(mieux, possedees) > combat.puissance_equipe(ids, possedees):
                oubliees = [data.CARTES[c]["nom"] for c in mieux if c not in ids]
                conseils.append(f"Tu as plus fort dans ta collection : {', '.join(oubliees)}.")
            try:
                conseils += [x.replace("**", "").replace("dans le salon des packs", "dans « Mes packs »") for x in regles.conseils_defaite(p, possedees, ids)]
            except Exception:
                pass
            res["conseils"] = conseils[:3] or ["Monte le niveau de tes cartes et essaie un autre item ou une autre rune."]
        return res


# ---------------------------------------------------------------- les donjons
def _portraits_donjon(numero):
    d = data.DESCENTES[numero]
    return {g[1]: g[0] for g in (d["gardien"], d["boss"])}


def donjons_etat(g, u):
    """La page des donjons : la réserve de victoires, et pour chaque donjon ses gardiens et ce qu'on y gagne."""
    with VERROU:
        p = db.get_joueur(g, u)
        if not p:
            return None
        stock = regles.donjons_restants(p)
        db.sauver(p)
        prochaine = None if stock >= data.DONJON_STOCK else round(max(60, data.DONJON_DELAI - (time.time() - p["donjon_moment"])))
        possedees = db.cartes(g, u)
        donjons = []
        for k, (nom, emoji, butin) in enumerate(data.DONJONS):
            portraits = _portraits_donjon(k)
            gardiens = [{"nom": x["nom"], "pv": round(x["pvmax"]), "image": image_unite(portraits.get(x["nom"]), x["nom"])}
                        for x in combat.gardiens_donjon(k, p["etage"])]
            donjons.append({"numero": k, "nom": nom, "emoji": emoji, "gardiens": gardiens,
                            "composants": [{"id": c, "nom": data.COMPOSANTS[c][0], "emoji": data.COMPOSANTS[c][1]} for c in butin]})
        return {"stock": stock, "max": data.DONJON_STOCK, "prochaine": prochaine, "delai": data.DONJON_DELAI,
                "requis": data.DEBLOCAGES.get("donjons", 1), "niveau": p["niveau"], "equipe": regles.equipe_ids(p, possedees),
                "butin": data.DONJON_BUTIN + p["etage"] // data.DONJON_PALIER, "palier": data.DONJON_PALIER, "hemorragie": data.HEMORRAGIE,
                "donjons": donjons}


def donjon_combattre(g, u, numero):
    """Un combat de donjon, avec les mêmes règles que le bouton du salon des donjons sur Discord :
    une victoire consomme une victoire de la réserve et rapporte des composants ; une défaite ne coûte rien."""
    with VERROU:
        p = db.get_joueur(g, u)
        if not p:
            return {"erreur": "Pas de compte 2Hot4Deck."}
        if not 0 <= numero < len(data.DONJONS):
            return {"erreur": "Ce donjon n'existe pas."}
        requis = data.DEBLOCAGES.get("donjons", 1)
        if p["niveau"] < requis:
            return {"erreur": f"Les donjons se débloquent au niveau {requis} de compte (tu es niveau {p['niveau']})."}
        if regles.donjons_restants(p) <= 0:
            db.sauver(p)
            return {"erreur": "Ta réserve de victoires de donjon est vide. Une victoire revient toutes les 5 heures."}
        possedees = db.cartes(g, u)
        ids = regles.equipe_ids(p, possedees)
        if not ids:
            return {"erreur": "Ton équipe est vide : compose-la dans « Ma collection »."}
        nom, emoji, butin = data.DONJONS[numero]
        victoire, tours, depart, actions = _jouer_contre(combat.gardiens_donjon(numero, p["etage"]), ids, possedees, hemorragie=True)
        regles.noter_combat(p, "donjon_site", numero, victoire, len(tours), tours[-1]["etat"], possedees)
        fin = tours[-1]["journal"][-1] if tours and tours[-1]["journal"] and tours[-1]["journal"][-1].startswith("⏱️") else ""
        res = {"mode": "donjon", "numero": numero, "nom": nom, "emoji": emoji, "boss": False, "victoire": victoire, "tours": len(tours),
               "unites": fiches_unites(depart, _portraits_donjon(numero)), "actions": actions, "fin": fin.replace("**", "")}
        if victoire:
            if p["donjon_stock"] >= data.DONJON_STOCK:
                p["donjon_moment"] = time.time()   # la recharge démarre quand la réserve n'est plus pleine
            p["donjon_stock"] -= 1
            gagnes = {}
            for _ in range(data.DONJON_BUTIN + p["etage"] // data.DONJON_PALIER):
                c = random.choice(butin)
                gagnes[c] = gagnes.get(c, 0) + 1
            for c, q in gagnes.items():
                db.ajouter_composant(g, u, c, q)
            niveau_avant = p["niveau"]
            lignes, _ = regles.gagner_xp_compte(p, "donjon")
            db.sauver(p)
            res["recompenses"] = {"composants": [{"id": c, "nom": data.COMPOSANTS[c][0], "emoji": data.COMPOSANTS[c][1], "q": q} for c, q in gagnes.items()],
                                  "xp_compte": data.XP_COMPTE["donjon"], "niveau": p["niveau"] if p["niveau"] > niveau_avant else None,
                                  "niveau_lignes": [l.replace("**", "") for l in lignes]}
        else:
            db.sauver(p)
            res["conseils"] = ["L'essai n'est pas décompté : ta réserve reste intacte.",
                               f"Hémorragie : dans les donjons, les soins sont réduits à {data.HEMORRAGIE} %.",
                               "Monte le niveau de tes cartes ou change d'item, puis retente ta chance."]
        res["stock"] = regles.donjons_restants(p)
        return res


# ---------------------------------------------------------------- la jungle
# La carte de 16 buissons du bot (classe Exploration), sans Discord : mêmes cases, mêmes ganks qui bougent, même butin.
# L'état d'une carte en cours est rangé dans site.db : un redémarrage du site ne fait rien perdre.
JUNGLE_TABLE = "CREATE TABLE IF NOT EXISTS site_jungle (user_id INTEGER PRIMARY KEY, etat TEXT)"
LATENCE = 0.35   # secondes retirées au clic du Châtiment, pour le temps que met le clic à arriver


def _propre(texte):
    return texte.replace("**", "")


class Carte:
    COTE = 4

    def __init__(self, etat):
        self.__dict__.update(etat)

    @classmethod
    def nouvelle(cls, p, ids, mise):
        bonus = max([b for c, b in data.EXPLO_BONUS if p["chasses"] >= c] or [0])
        buff = regles.buff_actif(p["guild_id"])
        if buff and buff["stat"] == "jungle":   # buff du Baron Nashor
            bonus += buff["valeur"]
        c = cls({"g": p["guild_id"], "u": p["user_id"], "ids": ids, "etage": min(p["etage"], 100), "mise": mise,
                 "mult": data.JUNGLE_BUTIN * mise, "xp": 0, "golds": 0, "fini": False, "bonus": bonus, "attente": None,
                 "journal": ["Choisis un buisson à fouiller."], "evenement": None, "trouvees": []})
        c.tirer_cases()
        return c

    def tirer_cases(self):
        contenu = [cle for cle, nombre in data.EXPLO_CASES for _ in range(nombre)]
        contenu += ["vide"] * (self.COTE ** 2 - len(contenu))
        if "vide" in contenu and random.random() * 100 < data.COFFRE_HEXTECH_CHANCE:
            contenu[contenu.index("vide")] = "coffre"
        random.shuffle(contenu)
        self.cases = contenu[:self.COTE ** 2]
        self.vues, self.reperes, self.vies = [], [], data.EXPLO_VIES
        self.carte_xp, self.carte_golds = 0, 0

    # -- la carte --
    def voisins(self, k):
        x, y = k % self.COTE, k // self.COTE
        return [yy * self.COTE + xx for xx in range(x - 1, x + 2) for yy in range(y - 1, y + 2)
                if 0 <= xx < self.COTE and 0 <= yy < self.COTE and (xx, yy) != (x, y)]

    def ganks_autour(self, k):
        return sum(1 for v in self.voisins(k) if self.cases[v] == "gank" and v not in self.vues)

    def bouger_ganks(self):
        caches = [k for k in range(len(self.cases)) if self.cases[k] == "gank" and k not in self.vues]
        random.shuffle(caches)
        for k in caches:
            libres = [v for v in self.voisins(k) if v not in self.vues and self.cases[v] != "gank"]
            if not libres:
                continue
            v = random.choice(libres)
            self.cases[k], self.cases[v] = self.cases[v], self.cases[k]
            if k in self.reperes:
                self.reperes.remove(k)
                self.reperes.append(v)

    def suite(self, p):
        caches = [k for k in range(len(self.cases)) if k not in self.vues]
        if self.vies <= 0:
            self.terminer(f"💀 {data.EXPLO_VIES} ganks : ton équipe rentre à la base. Le butin ramassé est gardé.", "ganks")
        elif all(self.cases[k] == "gank" for k in caches):
            xp, golds = int(self.carte_xp * data.EXPLO_CLEAR / 100), int(self.carte_golds * data.EXPLO_CLEAR / 100)
            if xp:
                possedees = db.cartes(self.g, self.u)
                for cid in self.ids:
                    if cid in possedees:
                        combat.gagner_xp(cid, possedees[cid], xp)
                        db.sauver_carte(self.g, self.u, cid, possedees[cid]["niveau"], possedees[cid]["xp"], possedees[cid]["etoiles"])
            p["golds"] += golds
            self.xp, self.golds = self.xp + xp, self.golds + golds
            self.terminer(f"🏆 Clear complet ! Il ne restait que des ganks : +{data.EXPLO_CLEAR} % du butin de la carte (✨ +{xp} XP par carte · 💰 +{golds} golds).", "clear")
        elif len(self.vues) >= 2:   # immobiles après le tout premier buisson, pour laisser un premier indice fiable
            self.bouger_ganks()

    def terminer(self, texte, comment="base"):
        self.fini = comment
        self.journal.append(texte)

    def verser(self, p, chasses_xp=0.0, chasses_golds=0.0):
        plus = 1 + self.bonus / 100
        possedees = db.cartes(self.g, self.u)
        xp = int((data.JUNGLE_XP[0] + data.JUNGLE_XP[1] * self.etage) * chasses_xp * plus)
        golds = int((data.JUNGLE_GOLDS[0] + data.JUNGLE_GOLDS[1] * self.etage) * chasses_golds * plus * regles.bonus_golds(self.ids, possedees))
        montees = []
        if xp:
            for cid in self.ids:
                if cid in possedees:
                    if combat.gagner_xp(cid, possedees[cid], xp):
                        montees.append(f"{data.CARTES[cid]['nom']} niv. {possedees[cid]['niveau']}")
                    db.sauver_carte(self.g, self.u, cid, possedees[cid]["niveau"], possedees[cid]["xp"], possedees[cid]["etoiles"])
        p["golds"] += golds
        self.xp, self.golds = self.xp + xp, self.golds + golds
        self.carte_xp, self.carte_golds = self.carte_xp + xp, self.carte_golds + golds
        texte = " · ".join(t for t in (f"✨ +{xp} XP par carte" if xp else "", f"💰 +{golds} golds" if golds else "") if t)
        return texte + (f" · ⬆️ {', '.join(montees)}" if montees else ""), xp, golds

    def fouiller(self, p, k):
        if self.fini or self.attente or not 0 <= k < len(self.cases) or k in self.vues:
            return
        if not self.vues and self.cases[k] == "gank":   # premier buisson : jamais un gank
            autres = [v for v in range(len(self.cases)) if self.cases[v] != "gank"]
            v = random.choice(autres)
            self.cases[k], self.cases[v] = self.cases[v], self.cases[k]
        cle = self.cases[k]
        cout = self.mult
        self.vues.append(k)
        if k in self.reperes:
            self.reperes.remove(k)
        ev = {"case": k, "cle": cle, "xp": 0, "golds": 0, "cartes": [], "lignes": []}
        lignes, _ = regles.gagner_xp_compte(p, "jungle", self.mise) if cle in ("camp", "tresor", "bleu", "rouge") else ([], [])
        if cle == "camp":
            p["chasses"] += 1
            nom = random.choice(data.JUNGLE_MONSTRES[:4])
            ev["monstre"] = nom
            if not hasattr(self, "monstres"):
                self.monstres = {}
            self.monstres[str(k)] = nom   # pour afficher le bon monstre sur la case ouverte
            texte, ev["xp"], ev["golds"] = self.verser(p, data.EXPLO_CAMP * cout, data.EXPLO_CAMP * cout)
            emo = {"Gromp": "🐸", "Loup des ténèbres": "🐺", "Corbin écarlate": "🐦", "Golem ancien": "🪨"}.get(nom, "🐺")
            self.journal.append(f"{emo} {nom} : camp nettoyé. {texte}")
            for _ in range(self.mise):
                if random.random() * 100 < data.JUNGLE_CHANCE_PACK:
                    trouvee = combat.tirer(p, gratuit=True)
                    statut = regles.donner(p, trouvee)
                    ev["cartes"].append(regles.carte_site(trouvee, statut))
                    self.trouvees.append(trouvee)
                    self.journal.append(f"🎁 Un pack traînait dans le buisson : {data.CARTES[trouvee]['nom']} ({data.CARTES[trouvee]['rarete']}) · {_propre(statut.splitlines()[0])}")
        elif cle == "tresor":
            texte, ev["xp"], ev["golds"] = self.verser(p, 0, data.EXPLO_TRESOR * cout)
            self.journal.append(f"💰 Un trésor oublié ! {texte}")
        elif cle == "gank":
            self.vies -= 1
            self.journal.append("⚔️ Gank ! Un jungler ennemi t'attendait." + (f" Encore {self.vies} et ton équipe rentre à la base." if self.vies else ""))
        elif cle == "fruit":
            ev["efface"] = self.vies < data.EXPLO_VIES
            self.vies = min(data.EXPLO_VIES, self.vies + 1)
            self.journal.append("🍯 Fruit de miel : " + ("un gank est effacé." if ev["efface"] else "aucun gank à effacer."))
        elif cle == "coffre":
            cartes = []
            self.journal.append(_propre(regles.ouvrir_coffre_hextech(p, cartes)))
            for c in cartes:
                ev["cartes"].append(regles.carte_site(c, ""))
                self.trouvees.append(c)
        elif cle == "vide":
            self.journal.append("🍃 Rien dans ce buisson.")
        for ligne in lignes:
            self.journal.append("⭐ " + _propre(ligne.replace("\n", " · ")))
            ev["lignes"].append(_propre(ligne.replace("\n", " · ")))
        if cle in ("bleu", "rouge"):   # gros monstre : place au Châtiment
            p["chasses"] += 1
            paliers, rythme = data.EXPLO_CHATIMENT[cle]
            self.attente = {"cle": cle, "nom": "Sentinelle bleue" if cle == "bleu" else "Roncier rouge", "cout": cout,
                            "debut": time.time(), "paliers": list(paliers), "rythme": rythme}
        else:
            self.suite(p)
        self.evenement = ev

    def chatiment(self, p, clic):
        """Le clic du joueur, mesuré par le serveur : le palier de PV affiché à ce moment-là (comme dans le bot)."""
        a = self.attente
        if not a:
            return
        # Deux mesures : l'instant exact et l'instant moins le délai réseau. Si l'une des deux tombe
        # dans la zone dorée, le Châtiment compte (on ne punit pas le joueur pour sa connexion).
        brut = time.time() - a["debut"]
        idx = [int(max(0, e) // a["rythme"]) for e in (brut, brut - LATENCE)]
        idx = [i for i in idx if i < len(a["paliers"])]
        bons = [i for i in idx if a["paliers"][i] <= data.CLEAR_FENETRE]
        pris = (a["paliers"][bons[0]] if bons else a["paliers"][idx[-1]]) if clic and idx else None
        reussi = pris is not None and pris <= data.CLEAR_FENETRE
        part = (data.EXPLO_GROS[0] if reussi else data.EXPLO_GROS[1]) * a["cout"]
        texte, xp, golds = self.verser(p, part, part)
        if reussi:
            self.journal.append(f"⚡ Châtiment réussi sur {a['nom']} (à {pris} % de PV) ! {texte}")
        elif pris is None:
            self.journal.append(f"{data.EXPLO_EMOJIS[a['cle']]} {a['nom']} vaincu sans Châtiment : petit butin. {texte}")
        else:
            self.journal.append(f"{data.EXPLO_EMOJIS[a['cle']]} {a['nom']} : Châtiment trop tôt (à {pris} % de PV), petit butin. {texte}")
        self.evenement = {"case": None, "cle": "chatiment", "monstre": a["nom"], "reussi": reussi, "pris": pris, "xp": xp, "golds": golds, "cartes": [], "lignes": []}
        self.attente = None
        self.suite(p)

    def public(self, p):
        """Ce que voit le joueur : jamais le contenu des buissons encore cachés."""
        att = None
        if self.attente:
            a = self.attente
            att = {"cle": a["cle"], "nom": a["nom"], "paliers": a["paliers"], "rythme": a["rythme"], "fenetre": data.CLEAR_FENETRE,
                   "ecoule": round(time.time() - a["debut"], 2)}
        return {"cote": self.COTE, "mise": self.mise, "vies": self.vies, "vies_max": data.EXPLO_VIES, "fini": self.fini, "xp": self.xp, "golds": self.golds,
                "bonus": self.bonus, "journal": self.journal[-6:], "evenement": self.evenement, "chatiment": att,
                "restants": self.COTE ** 2 - len(self.vues),
                "cases": [{"vu": True, "cle": self.cases[k], "n": self.ganks_autour(k), "monstre": getattr(self, "monstres", {}).get(str(k))} if k in self.vues else {"vu": False, "repere": k in self.reperes}
                          for k in range(len(self.cases))]}


def _carte_lire(u):
    db.con.execute(JUNGLE_TABLE)
    r = db.con.execute("SELECT etat FROM site_jungle WHERE user_id=?", (u,)).fetchone()
    return Carte(json.loads(r[0])) if r and r[0] else None


def _carte_ecrire(u, carte):
    db.con.execute(JUNGLE_TABLE)
    if carte is None:
        db.con.execute("DELETE FROM site_jungle WHERE user_id=?", (u,))
    else:
        db.con.execute("INSERT INTO site_jungle VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET etat=excluded.etat", (u, json.dumps(carte.__dict__)))
    db.con.commit()


def _jungle_infos(p):
    c = regles.charges(p)
    xp, golds = regles.butin_clear_complet(p)
    prochaine = None if c >= regles.charges_max(p) else round(max(0, regles.delai_charge(p) - (time.time() - p["charges_moment"])))
    bonus = max([b for n, b in data.EXPLO_BONUS if p["chasses"] >= n] or [0])
    return {"charges": c, "max": regles.charges_max(p), "prochaine": prochaine, "mise_max": max(1, min(c, regles.mise_max(p))),
            "mise_limite": regles.mise_max(p), "chasses": p["chasses"], "bonus": bonus, "paliers_bonus": data.EXPLO_BONUS,
            "clear_xp": xp, "clear_golds": golds, "rapide_pct": data.CLEAR_RAPIDE, "requis": data.DEBLOCAGES.get("jungle", 1), "niveau": p["niveau"]}


def jungle_etat(g, u):
    with VERROU:
        p = db.get_joueur(g, u)
        if not p:
            return None
        infos = _jungle_infos(p)
        db.sauver(p)
        carte = _carte_lire(u)
        infos["carte"] = carte.public(p) if carte and not carte.fini else None
        return infos


def jungle_action(g, u, action, valeur=None):
    """explorer (mise), fouiller (case), chatiment (clic), rentrer, rapide (mise)."""
    with VERROU:
        p = db.get_joueur(g, u)
        if not p:
            return {"erreur": "Pas de compte 2Hot4Deck."}
        requis = data.DEBLOCAGES.get("jungle", 1)
        if p["niveau"] < requis:
            return {"erreur": f"La jungle se débloque au niveau {requis} de compte (tu es niveau {p['niveau']})."}
        carte = _carte_lire(u)
        res = {}
        if action in ("explorer", "rapide"):
            if carte and not carte.fini:
                return {"erreur": "Tu as déjà une carte en cours : termine-la ou rentre à la base."}
            if regles.charges(p) <= 0:
                db.sauver(p)
                return {"erreur": "Tu n'as plus de charge de Châtiment. La tour et les donjons, eux, ne coûtent rien."}
            possedees = db.cartes(g, u)
            ids = regles.equipe_ids(p, possedees)
            if not ids:
                return {"erreur": "Ton équipe est vide : compose-la dans « Ma collection »."}
            mise = max(1, min(int(valeur or 1), regles.charges(p), regles.mise_max(p)))
            regles.depenser_charges(p, mise)
            if action == "explorer":
                carte = Carte.nouvelle(p, ids, mise)
            else:   # clear rapide : une part du butin d'un clear complet, tout de suite
                bonus = max([b for c, b in data.EXPLO_BONUS if p["chasses"] >= c] or [0])
                buff = regles.buff_actif(g)
                if buff and buff["stat"] == "jungle":
                    bonus += buff["valeur"]
                xp, golds = regles.butin_clear_complet(p, mise)
                part = data.CLEAR_RAPIDE / 100 * (1 + bonus / 100)
                xp, golds = int(xp * part), int(golds * part * regles.bonus_golds(ids, possedees))
                montees = []
                for cid in ids:
                    if cid in possedees:
                        if combat.gagner_xp(cid, possedees[cid], xp):
                            montees.append(f"{data.CARTES[cid]['nom']} niv. {possedees[cid]['niveau']}")
                        db.sauver_carte(g, u, cid, possedees[cid]["niveau"], possedees[cid]["xp"], possedees[cid]["etoiles"])
                p["golds"] += golds
                p["chasses"] += 4 * mise
                lignes, _ = regles.gagner_xp_compte(p, "jungle", 5 * mise)
                res["rapide"] = {"xp": xp, "golds": golds, "mise": mise, "montees": montees, "lignes": [_propre(l) for l in lignes]}
                carte = None
        elif not carte or carte.fini:
            return {"erreur": "Pas de carte en cours : lance une exploration."}
        elif action == "fouiller":
            carte.trouvees = []
            carte.fouiller(p, int(valeur))
        elif action == "chatiment":
            carte.trouvees = []
            carte.chatiment(p, bool(valeur))
        elif action == "rentrer":
            if carte.attente:
                carte.chatiment(p, False)
            carte.terminer("🏠 Ton équipe rentre à la base, butin en poche.")
            carte.evenement = None
        else:
            return {"erreur": "Action inconnue."}
        db.sauver(p)
        if carte is not None:
            res["trouvees"] = list(carte.trouvees)
            res["carte"] = carte.public(p)
            _carte_ecrire(u, None if carte.fini else carte)
        res.update({k: v for k, v in _jungle_infos(p).items() if k != "carte"})
        db.sauver(p)
        return res
