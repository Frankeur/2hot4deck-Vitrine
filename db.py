"""Sauvegarde dans un fichier SQLite (faille.db, créé tout seul)."""
import os
import sqlite3
import time
import data

con = sqlite3.connect(os.environ.get("FAILLE_DB", "faille.db"))
con.row_factory = sqlite3.Row
con.executescript("""
CREATE TABLE IF NOT EXISTS joueurs (
    guild_id INTEGER, user_id INTEGER, golds INTEGER DEFAULT 0, etage INTEGER DEFAULT 0,
    pitie INTEGER DEFAULT 0, packs INTEGER DEFAULT 0, dernier_gratuit REAL DEFAULT 0,
    dernier_coffre REAL DEFAULT 0, equipe TEXT DEFAULT '',
    PRIMARY KEY (guild_id, user_id));
CREATE TABLE IF NOT EXISTS cartes (
    guild_id INTEGER, user_id INTEGER, carte TEXT, niveau INTEGER DEFAULT 1, xp INTEGER DEFAULT 0,
    etoiles INTEGER DEFAULT 0, PRIMARY KEY (guild_id, user_id, carte));
""")
# Colonnes ajoutées après la première version : créées automatiquement si la base existe déjà.
NOUVELLES = {"arene_points": "INTEGER DEFAULT 0", "arene_jour": "TEXT DEFAULT ''", "arene_combats": "INTEGER DEFAULT 0",
             "arene_victoires": "INTEGER DEFAULT 0", "arene_defaites": "INTEGER DEFAULT 0",
             "defense": "TEXT DEFAULT ''", "pseudo": "TEXT DEFAULT ''", "arene_vu": "REAL DEFAULT 0",
             "arene_notif": "INTEGER DEFAULT 1", "arene_message": "REAL DEFAULT 0",
             "points_max": "INTEGER DEFAULT 0", "items_choisis": "INTEGER DEFAULT 0", "items_offre": "TEXT DEFAULT ''",
             "energie": "INTEGER DEFAULT 12", "energie_moment": "REAL DEFAULT 0",
             "cible": "TEXT DEFAULT ''", "cible_jour": "TEXT DEFAULT ''", "donjon_jour": "TEXT DEFAULT ''",
             "donjon_essais": "INTEGER DEFAULT 0", "xp_compte": "INTEGER DEFAULT 0", "niveau": "INTEGER DEFAULT 1",
             "chasses": "INTEGER DEFAULT 0", "totems": "INTEGER DEFAULT 0", "lignes": "TEXT DEFAULT ''",
             "cles": "INTEGER DEFAULT 3", "cles_moment": "REAL DEFAULT 0",
             "charges": "INTEGER DEFAULT 3", "charges_moment": "REAL DEFAULT 0", "packs_niveau": "INTEGER DEFAULT 0", "reserve_xp": "INTEGER DEFAULT 0",
             "packs_ur": "INTEGER DEFAULT 0", "pitie_ur": "INTEGER DEFAULT 0",
             "runes": "TEXT DEFAULT ''", "runes_equipees": "TEXT DEFAULT ''", "raid_jour": "TEXT DEFAULT ''", "rune_a_choisir": "INTEGER DEFAULT 0",
             # Worlds : packs pro à ouvrir, pitié du pack pro, coach équipé, palier déjà récompensé aujourd'hui, titres de champion du monde
             "packs_pro": "INTEGER DEFAULT 0", "pitie_pro": "INTEGER DEFAULT 0", "pitie_pro_ur": "INTEGER DEFAULT 0", "coach": "TEXT DEFAULT ''",
             "donjon_stock": "INTEGER DEFAULT 5", "donjon_moment": "REAL DEFAULT 0",
             "worlds_jour": "TEXT DEFAULT ''", "worlds_palier": "INTEGER DEFAULT 0", "worlds_titres": "INTEGER DEFAULT 0",
             # LEC : packs LEC à ouvrir, pitié du pack LEC, titres LEC ; tickets Worlds (3 au départ)
             "packs_lec": "INTEGER DEFAULT 0", "pitie_lec": "INTEGER DEFAULT 0", "lec_titres": "INTEGER DEFAULT 0", "tickets_worlds": "INTEGER DEFAULT 3",
             "lec_jour": "TEXT DEFAULT ''", "lec_essais": "INTEGER DEFAULT 0"}
con.execute("""CREATE TABLE IF NOT EXISTS arene_journal (
    guild_id INTEGER, moment REAL, attaquant INTEGER, defenseur INTEGER, nom_attaquant TEXT, nom_defenseur TEXT,
    victoire INTEGER, points_attaquant INTEGER, points_defenseur INTEGER)""")
for colonne, definition in {"mode": "TEXT DEFAULT 'arene'", "classe": "INTEGER DEFAULT 1"}.items():
    if colonne not in {r["name"] for r in con.execute("PRAGMA table_info(arene_journal)")}:
        con.execute(f"ALTER TABLE arene_journal ADD COLUMN {colonne} {definition}")
existantes = {r["name"] for r in con.execute("PRAGMA table_info(joueurs)")}
for colonne, definition in NOUVELLES.items():
    if colonne not in existantes:
        con.execute(f"ALTER TABLE joueurs ADD COLUMN {colonne} {definition}")
con.execute("""CREATE TABLE IF NOT EXISTS items (
    guild_id INTEGER, user_id INTEGER, item TEXT, niveau INTEGER DEFAULT 1, carte TEXT DEFAULT '',
    PRIMARY KEY (guild_id, user_id, item))""")
con.execute("""CREATE TABLE IF NOT EXISTS composants (
    guild_id INTEGER, user_id INTEGER, composant TEXT, quantite INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, composant))""")
con.execute("UPDATE joueurs SET points_max = arene_points WHERE arene_points > points_max")   # meilleur classement atteint
con.commit()

CHAMPS = ["golds", "etage", "pitie", "packs", "dernier_gratuit", "dernier_coffre", "equipe"] + list(NOUVELLES)

# --- Opérations exceptionnelles, exécutées une seule fois au démarrage ---------
con.execute("CREATE TABLE IF NOT EXISTS operations (cle TEXT PRIMARY KEY, moment REAL)")
con.execute("CREATE TABLE IF NOT EXISTS golds_sauvegarde (operation TEXT, guild_id INTEGER, user_id INTEGER, golds INTEGER)")


def operation_unique(cle):
    """Renvoie True la première fois qu'on l'appelle avec cette clé, False ensuite."""
    if con.execute("SELECT 1 FROM operations WHERE cle=?", (cle,)).fetchone():
        return False
    con.execute("INSERT INTO operations VALUES (?, ?)", (cle, time.time()))
    return True


con.commit()

con.commit()

con.commit()

con.commit()

con.commit()

con.commit()

con.commit()

con.commit()

con.commit()

con.commit()

con.commit()


con.commit()

con.execute("CREATE TABLE IF NOT EXISTS maj_postees (guild_id INTEGER, cle TEXT, PRIMARY KEY (guild_id, cle))")
con.commit()


def maj_deja_postee(g, cle):
    return con.execute("SELECT 1 FROM maj_postees WHERE guild_id=? AND cle=?", (g, cle)).fetchone() is not None


def noter_maj(g, cle):
    con.execute("INSERT OR IGNORE INTO maj_postees VALUES (?, ?)", (g, cle))
    con.commit()


con.execute("CREATE TABLE IF NOT EXISTS quiz (guild_id INTEGER, user_id INTEGER, jour TEXT, essais INTEGER DEFAULT 0, trouve INTEGER DEFAULT 0, "
            "fini INTEGER DEFAULT 0, debut REAL DEFAULT 0, fin REAL DEFAULT 0, pseudo TEXT DEFAULT '', PRIMARY KEY (guild_id, user_id, jour))")


def quiz(g, u, jour, pseudo=""):
    """Partie du jour d'un joueur au « Qui est ce champion ? » (créée au premier appel)."""
    r = con.execute("SELECT * FROM quiz WHERE guild_id=? AND user_id=? AND jour=?", (g, u, jour)).fetchone()
    if not r:
        import time
        con.execute("INSERT INTO quiz (guild_id, user_id, jour, debut, pseudo) VALUES (?,?,?,?,?)", (g, u, jour, time.time(), pseudo))
        con.commit()
        r = con.execute("SELECT * FROM quiz WHERE guild_id=? AND user_id=? AND jour=?", (g, u, jour)).fetchone()
    return dict(r)


def sauver_quiz(q):
    con.execute("UPDATE quiz SET essais=?, trouve=?, fini=?, fin=?, pseudo=? WHERE guild_id=? AND user_id=? AND jour=?",
                (q["essais"], q["trouve"], q["fini"], q["fin"], q["pseudo"], q["guild_id"], q["user_id"], q["jour"]))
    con.commit()


def classement_quiz(g, jour):
    """Ceux qui ont trouvé aujourd'hui : le moins d'essais d'abord, puis le plus rapide."""
    rows = con.execute("SELECT * FROM quiz WHERE guild_id=? AND jour=? AND trouve=1 ORDER BY essais, fin - debut", (g, jour)).fetchall()
    return [dict(r) for r in rows]


con.execute("CREATE TABLE IF NOT EXISTS jeux_jour (guild_id INTEGER, user_id INTEGER, jour TEXT, jeu TEXT, essais INTEGER DEFAULT 0, trouve INTEGER DEFAULT 0, "
            "fini INTEGER DEFAULT 0, debut REAL DEFAULT 0, fin REAL DEFAULT 0, pseudo TEXT DEFAULT '', donnees TEXT DEFAULT '{}', PRIMARY KEY (guild_id, user_id, jour, jeu))")


def jeu_jour(g, u, jour, jeu, pseudo=""):
    """Partie du jour d'un joueur à un mini-jeu quotidien (créée au premier appel). donnees : dictionnaire libre."""
    import json, time
    cle = (g, u, jour, jeu)
    r = con.execute("SELECT * FROM jeux_jour WHERE guild_id=? AND user_id=? AND jour=? AND jeu=?", cle).fetchone()
    if not r:
        con.execute("INSERT INTO jeux_jour (guild_id, user_id, jour, jeu, debut, pseudo) VALUES (?,?,?,?,?,?)", cle + (time.time(), pseudo))
        con.commit()
        r = con.execute("SELECT * FROM jeux_jour WHERE guild_id=? AND user_id=? AND jour=? AND jeu=?", cle).fetchone()
    q = dict(r)
    q["donnees"] = json.loads(q["donnees"] or "{}")
    return q


def sauver_jeu_jour(q):
    import json
    con.execute("UPDATE jeux_jour SET essais=?, trouve=?, fini=?, fin=?, pseudo=?, donnees=? WHERE guild_id=? AND user_id=? AND jour=? AND jeu=?",
                (q["essais"], q["trouve"], q["fini"], q["fin"], q["pseudo"], json.dumps(q["donnees"]), q["guild_id"], q["user_id"], q["jour"], q["jeu"]))
    con.commit()


def classement_jeu_jour(g, jour, jeu):
    """Parties terminées du jour : le plus de bonnes réponses d'abord, puis le moins d'essais, puis le plus rapide."""
    rows = con.execute("SELECT * FROM jeux_jour WHERE guild_id=? AND jour=? AND jeu=? AND fini=1 AND trouve>0 ORDER BY trouve DESC, essais, fin - debut", (g, jour, jeu)).fetchall()
    return [dict(r) for r in rows]


# ---- Worlds : cartes au repos après un tournoi, équipes déjà éliminées par chaque joueur (elles ouvrent leurs cartes dans le
# pack pro, pour toujours), et coachs possédés.
con.execute("CREATE TABLE IF NOT EXISTS worlds_repos (guild_id INTEGER, user_id INTEGER, carte TEXT, fin REAL, PRIMARY KEY (guild_id, user_id, carte))")
con.execute("CREATE TABLE IF NOT EXISTS worlds_equipes (guild_id INTEGER, user_id INTEGER, equipe INTEGER, moment REAL, victoires INTEGER DEFAULT 1, PRIMARY KEY (guild_id, user_id, equipe))")
con.execute("CREATE TABLE IF NOT EXISTS coachs (guild_id INTEGER, user_id INTEGER, pro TEXT, nombre INTEGER DEFAULT 1, moment REAL, PRIMARY KEY (guild_id, user_id, pro))")
con.commit()


def worlds_reposer(g, u, cartes, fin):
    for c in cartes:
        con.execute("INSERT OR REPLACE INTO worlds_repos VALUES (?,?,?,?)", (g, u, c, fin))
    con.commit()


con.execute("CREATE TABLE IF NOT EXISTS lec_repos (guild_id INTEGER, user_id INTEGER, carte TEXT, fin REAL, PRIMARY KEY (guild_id, user_id, carte))")


con.execute("CREATE TABLE IF NOT EXISTS boutique_achats (guild_id INTEGER, user_id INTEGER, periode INTEGER, article TEXT, nombre INTEGER, PRIMARY KEY (guild_id, user_id, periode, article))")


def boutique_achats(g, u, periode):
    """Ce que ce joueur a déjà acheté dans la boutique en cours : {article: nombre}."""
    return {r["article"]: r["nombre"] for r in con.execute("SELECT article, nombre FROM boutique_achats WHERE guild_id=? AND user_id=? AND periode=?", (g, u, periode))}


def boutique_acheter(g, u, periode, article):
    con.execute("INSERT INTO boutique_achats VALUES (?,?,?,?,1) ON CONFLICT(guild_id, user_id, periode, article) DO UPDATE SET nombre = nombre + 1", (g, u, periode, article))
    con.commit()


con.execute("CREATE TABLE IF NOT EXISTS lec_equipes (guild_id INTEGER, user_id INTEGER, equipe INTEGER, moment REAL, victoires INTEGER DEFAULT 1, PRIMARY KEY (guild_id, user_id, equipe))")


def lec_eliminer(g, u, equipe):
    """Note qu'un joueur a battu une équipe de la LEC (numéro dans data.LEC_PALIERS). Renvoie True si c'est la première fois."""
    nouveau = con.execute("SELECT 1 FROM lec_equipes WHERE guild_id=? AND user_id=? AND equipe=?", (g, u, equipe)).fetchone() is None
    con.execute("INSERT INTO lec_equipes VALUES (?,?,?,?,1) ON CONFLICT(guild_id, user_id, equipe) DO UPDATE SET victoires = victoires + 1", (g, u, equipe, time.time()))
    con.commit()
    return nouveau


def lec_equipes(g, u):
    """Numéros des équipes de la LEC déjà battues par ce joueur."""
    return sorted(r["equipe"] for r in con.execute("SELECT equipe FROM lec_equipes WHERE guild_id=? AND user_id=?", (g, u)).fetchall())


def lec_reposer(g, u, cartes, fin):
    for c in cartes:
        con.execute("INSERT OR REPLACE INTO lec_repos VALUES (?,?,?,?)", (g, u, c, fin))
    con.commit()


def lec_au_repos(g, u):
    """Cartes de ce joueur encore au repos en LEC : {carte: moment du réveil}."""
    con.execute("DELETE FROM lec_repos WHERE fin <= ?", (time.time(),))
    return {r["carte"]: r["fin"] for r in con.execute("SELECT carte, fin FROM lec_repos WHERE guild_id=? AND user_id=?", (g, u)).fetchall()}


def worlds_au_repos(g, u):
    """Cartes de ce joueur encore au repos : {carte: moment du réveil}."""
    con.execute("DELETE FROM worlds_repos WHERE fin <= ?", (time.time(),))
    return {r["carte"]: r["fin"] for r in con.execute("SELECT carte, fin FROM worlds_repos WHERE guild_id=? AND user_id=?", (g, u)).fetchall()}


def worlds_eliminer(g, u, equipe):
    """Note qu'un joueur a éliminé une équipe (numéro dans data.TOUR_PROS). Renvoie True si c'est la première fois."""
    nouveau = con.execute("SELECT 1 FROM worlds_equipes WHERE guild_id=? AND user_id=? AND equipe=?", (g, u, equipe)).fetchone() is None
    con.execute("INSERT INTO worlds_equipes VALUES (?,?,?,?,1) ON CONFLICT(guild_id, user_id, equipe) DO UPDATE SET victoires = victoires + 1", (g, u, equipe, time.time()))
    con.commit()
    return nouveau


def worlds_equipes(g, u):
    """Numéros des équipes déjà éliminées par ce joueur."""
    return sorted(r["equipe"] for r in con.execute("SELECT equipe FROM worlds_equipes WHERE guild_id=? AND user_id=?", (g, u)).fetchall())


def coach_ajouter(g, u, pro):
    """Ajoute une carte de pro. Renvoie le nombre d'exemplaires possédés ensuite."""
    con.execute("INSERT INTO coachs VALUES (?,?,?,1,?) ON CONFLICT(guild_id, user_id, pro) DO UPDATE SET nombre = nombre + 1", (g, u, pro, time.time()))
    con.commit()
    return con.execute("SELECT nombre FROM coachs WHERE guild_id=? AND user_id=? AND pro=?", (g, u, pro)).fetchone()["nombre"]


def coachs(g, u):
    """Cartes de pro du joueur : {pseudo: nombre}."""
    return {r["pro"]: r["nombre"] for r in con.execute("SELECT pro, nombre FROM coachs WHERE guild_id=? AND user_id=?", (g, u)).fetchall()}


con.commit()


con.commit()


con.commit()


con.commit()


con.commit()

con.commit()

con.commit()

con.commit()


class Cartes(dict):
    """Les cartes d'un joueur, avec en plus le coach qu'il a équipé (coach : pseudo du pro, ou "").
    Chaque carte connaît sa collection (« _collection ») : l'XP en trop d'une carte au maximum peut ainsi aller à une autre."""
    coach = ""
    proprietaire = None   # (serveur, joueur)

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.recus = {}   # carte -> XP reçue par recyclage, pour pouvoir le dire au joueur

    def enregistrer(self, cid):
        if self.proprietaire:
            sauver_carte(self.proprietaire[0], self.proprietaire[1], cid, self[cid]["niveau"], self[cid]["xp"], self[cid]["etoiles"])


con.execute("CREATE TABLE IF NOT EXISTS menage (message_id INTEGER PRIMARY KEY, jeton TEXT, app_id INTEGER, moment REAL, salon INTEGER, joueur INTEGER)")


def menage_noter(message, jeton, app, moment, salon, joueur):
    """Retient un message privé à effacer plus tard (un nouveau clic dessus remplace le jeton et relance le délai)."""
    con.execute("INSERT OR REPLACE INTO menage VALUES (?,?,?,?,?,?)", (message, jeton, app, moment, salon, joueur))
    con.commit()


def menage_oublier(message):
    con.execute("DELETE FROM menage WHERE message_id=?", (message,))
    con.commit()


def menage_du_joueur(salon, joueur):
    return [dict(r) for r in con.execute("SELECT * FROM menage WHERE salon=? AND joueur=?", (salon, joueur)).fetchall()]


def menage_dus(avant):
    return [dict(r) for r in con.execute("SELECT * FROM menage WHERE moment<?", (avant,)).fetchall()]


con.execute("CREATE TABLE IF NOT EXISTS monde (guild_id INTEGER PRIMARY KEY, donnees TEXT)")


def monde(g):
    """État commun du serveur pour les boss de salon : {"boss": …ou None, "coups": {joueur: …}, "buff": …ou None, "numero": n, "creneau": "…"}."""
    import json
    r = con.execute("SELECT donnees FROM monde WHERE guild_id=?", (g,)).fetchone()
    m = json.loads(r["donnees"]) if r else {}
    for cle, defaut in (("boss", None), ("coups", {}), ("buff", None), ("numero", 0), ("creneau", "")):
        m.setdefault(cle, defaut)
    return m


def sauver_monde(g, m):
    import json
    con.execute("INSERT INTO monde VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET donnees=excluded.donnees", (g, json.dumps(m, ensure_ascii=False)))
    con.commit()


def journal_combat(g, u, moment, mode, detail, victoire, tours, donnees):
    """Journal des combats, gardé pour l'équilibrage (jamais effacé par un reset de compte)."""
    con.execute("CREATE TABLE IF NOT EXISTS combats_journal (guild_id INTEGER, user_id INTEGER, moment REAL, mode TEXT, detail TEXT, "
                "victoire INTEGER, tours INTEGER, donnees TEXT)")
    con.execute("INSERT INTO combats_journal VALUES (?,?,?,?,?,?,?,?)", (g, u, moment, mode, str(detail), int(bool(victoire)), tours, donnees))
    con.commit()


def get_joueur(g, u):
    r = con.execute("SELECT * FROM joueurs WHERE guild_id=? AND user_id=?", (g, u)).fetchone()
    return dict(r) if r else None


def creer_joueur(g, u, golds, maintenant):
    con.execute("INSERT INTO joueurs (guild_id, user_id, golds, dernier_coffre, tickets_worlds) VALUES (?,?,?,?,?)",
                (g, u, golds, maintenant, getattr(data, "WORLDS_TICKETS_DEPART", 2)))
    con.commit()
    return get_joueur(g, u)


def sauver(p):
    p["points_max"] = max(p["points_max"], p["arene_points"])   # sert à débloquer les items de rang, une seule fois
    con.execute(f"UPDATE joueurs SET {', '.join(c + '=?' for c in CHAMPS)} WHERE guild_id=? AND user_id=?",
                [p[c] for c in CHAMPS] + [p["guild_id"], p["user_id"]])
    con.commit()


def cartes(g, u):
    """Renvoie {identifiant: {niveau, xp, etoiles}}."""
    rows = con.execute("SELECT * FROM cartes WHERE guild_id=? AND user_id=?", (g, u)).fetchall()
    resultat = Cartes({r["carte"]: dict(r) for r in rows})
    coach = con.execute("SELECT coach FROM joueurs WHERE guild_id=? AND user_id=?", (g, u)).fetchone()
    resultat.coach = (coach["coach"] or "") if coach else ""
    resultat.proprietaire = (g, u)
    for _carte in resultat.values():
        _carte["_collection"] = resultat
    for nom, objet in items(g, u).items():   # l'item équipé voyage avec la carte : (identifiant, niveau)
        if objet["carte"] in resultat:
            resultat[objet["carte"]]["item"] = (nom.split("~")[0], objet["niveau"])   # 14 octobre : « lame_infini~2 » = 2e exemplaire
    return resultat


con.execute("CREATE TABLE IF NOT EXISTS journal_packs (guild_id INTEGER, user_id INTEGER, moment REAL, pack TEXT, variation INTEGER, detail TEXT)")
con.commit()


def journal_pack(g, u, pack, variation, detail=""):
    """14 octobre : garde la trace des packs gagnés (+) et ouverts (-), pour pouvoir vérifier plus tard. pack : "pro", "lec", "ur"…"""
    try:
        con.execute("INSERT INTO journal_packs VALUES (?,?,?,?,?,?)", (g, u, time.time(), pack, variation, detail))
        con.commit()
    except Exception as erreur:
        print(f"Journal des packs : {erreur!r}")


def items(g, u):
    """Renvoie {item: {niveau, carte}} ; carte est vide si l'item n'est équipé sur personne."""
    rows = con.execute("SELECT * FROM items WHERE guild_id=? AND user_id=?", (g, u)).fetchall()
    return {r["item"]: {"niveau": r["niveau"], "carte": r["carte"]} for r in rows}


def composants(g, u):
    """Renvoie {composant: quantité}."""
    return {r["composant"]: r["quantite"] for r in con.execute("SELECT * FROM composants WHERE guild_id=? AND user_id=?", (g, u))}


def ajouter_composant(g, u, composant, quantite):
    """Ajoute (ou retire, si quantité négative) des composants."""
    con.execute("""INSERT INTO composants VALUES (?,?,?,?) ON CONFLICT(guild_id, user_id, composant)
                   DO UPDATE SET quantite = quantite + excluded.quantite""", (g, u, composant, quantite))
    con.commit()


def sauver_item(g, u, item, niveau, carte=""):
    if carte:   # un seul item par carte
        con.execute("UPDATE items SET carte='' WHERE guild_id=? AND user_id=? AND carte=?", (g, u, carte))
    con.execute("""INSERT INTO items VALUES (?,?,?,?,?) ON CONFLICT(guild_id, user_id, item)
                   DO UPDATE SET niveau=excluded.niveau, carte=excluded.carte""", (g, u, item, niveau, carte))
    con.commit()


def sauver_carte(g, u, carte, niveau=1, xp=0, etoiles=0):
    con.execute("""INSERT INTO cartes (guild_id, user_id, carte, niveau, xp, etoiles) VALUES (?,?,?,?,?,?) ON CONFLICT(guild_id, user_id, carte)
                   DO UPDATE SET niveau=excluded.niveau, xp=excluded.xp, etoiles=excluded.etoiles""",
                (g, u, carte, niveau, xp, etoiles))
    con.commit()


if "doublons" not in {r["name"] for r in con.execute("PRAGMA table_info(cartes)")}:
    con.execute("ALTER TABLE cartes ADD COLUMN doublons INTEGER DEFAULT 0")   # doublons en attente de la prochaine étoile
    con.commit()


def sauver_doublons(g, u, carte, nombre):
    con.execute("UPDATE cartes SET doublons=? WHERE guild_id=? AND user_id=? AND carte=?", (nombre, g, u, carte))
    con.commit()


def classement(g, n=10):
    return [dict(r) for r in con.execute(
        """SELECT j.*, (SELECT COUNT(*) FROM cartes c WHERE c.guild_id=j.guild_id AND c.user_id=j.user_id) AS nb
           FROM joueurs j WHERE guild_id=? ORDER BY etage DESC, nb DESC LIMIT ?""", (g, n))]


def classement_arene(g, n=10):
    return [dict(r) for r in con.execute(
        "SELECT * FROM joueurs WHERE guild_id=? AND arene_victoires + arene_defaites > 0 ORDER BY arene_points DESC, arene_victoires DESC LIMIT ?", (g, n))]


def autres_joueurs(g, u):
    """Tous les joueurs du serveur sauf celui-ci (adversaires possibles en arène)."""
    return [dict(r) for r in con.execute("SELECT * FROM joueurs WHERE guild_id=? AND user_id<>? AND equipe<>''", (g, u))]


def noter_combat(g, attaquant, defenseur, nom_attaquant, nom_defenseur, victoire, points_attaquant, points_defenseur,
                 mode="arene", classe=True):
    """Enregistre un combat. mode : 'arene' (défenseur à 0 pour un reflet) ou 'duel' (attaquant = celui qui a lancé le défi)."""
    con.execute("""INSERT INTO arene_journal (guild_id, moment, attaquant, defenseur, nom_attaquant, nom_defenseur,
                   victoire, points_attaquant, points_defenseur, mode, classe) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (g, time.time(), attaquant, defenseur, nom_attaquant, nom_defenseur, int(victoire), points_attaquant,
                 points_defenseur, mode, int(classe)))
    con.commit()


def historique_arene(g, u, n=15):
    """Les derniers combats du joueur, en attaque comme en défense, du plus récent au plus ancien."""
    return [dict(r) for r in con.execute(
        "SELECT * FROM arene_journal WHERE guild_id=? AND (attaquant=? OR defenseur=?) ORDER BY moment DESC LIMIT ?", (g, u, u, n))]


def attaques_non_vues(g, u, depuis):
    return con.execute("SELECT COUNT(*) FROM arene_journal WHERE guild_id=? AND defenseur=? AND moment>? AND mode='arene'", (g, u, depuis)).fetchone()[0]


def combats_contre(g, attaquant, defenseur, depuis):
    """Nombre de combats de cet attaquant contre ce joueur depuis le moment donné."""
    return con.execute("SELECT COUNT(*) FROM arene_journal WHERE guild_id=? AND attaquant=? AND defenseur=? AND moment>=? AND mode='arene'",
                       (g, attaquant, defenseur, depuis)).fetchone()[0]


def defenses_perdues(g, defenseur, depuis):
    return con.execute("SELECT COUNT(*) FROM arene_journal WHERE guild_id=? AND defenseur=? AND victoire=1 AND moment>=? AND mode='arene'",
                       (g, defenseur, depuis)).fetchone()[0]


def duels_classes(g, u, depuis):
    """Nombre de duels classés joués par ce joueur depuis le moment donné."""
    return con.execute("""SELECT COUNT(*) FROM arene_journal WHERE guild_id=? AND mode='duel' AND classe=1
                          AND (attaquant=? OR defenseur=?) AND moment>=?""", (g, u, u, depuis)).fetchone()[0]


def duel_classe_entre(g, a, b, depuis):
    return con.execute("""SELECT COUNT(*) FROM arene_journal WHERE guild_id=? AND mode='duel' AND classe=1 AND moment>=?
                          AND ((attaquant=? AND defenseur=?) OR (attaquant=? AND defenseur=?))""", (g, depuis, a, b, b, a)).fetchone()[0]


def supprimer_joueur(g, u):
    """Efface entièrement le compte d'un joueur (bouton de réinitialisation de la bêta).
    Une photo complète du compte est d'abord rangée dans la table comptes_archives, pour étudier l'équilibrage plus tard."""
    import json
    import time
    tables = ("joueurs", "cartes", "items", "composants")
    photo = {}
    for table in tables:
        curseur = con.execute(f"SELECT * FROM {table} WHERE guild_id=? AND user_id=?", (g, u))
        colonnes = [c[0] for c in curseur.description]
        photo[table] = [dict(zip(colonnes, ligne)) for ligne in curseur.fetchall()]
    if photo["joueurs"]:
        con.execute("CREATE TABLE IF NOT EXISTS comptes_archives (guild_id INTEGER, user_id INTEGER, moment REAL, donnees TEXT)")
        con.execute("INSERT INTO comptes_archives VALUES (?,?,?,?)", (g, u, time.time(), json.dumps(photo, ensure_ascii=False, default=str)))
    for table in tables:
        con.execute(f"DELETE FROM {table} WHERE guild_id=? AND user_id=?", (g, u))
    con.commit()


def tous_les_joueurs(g):
    return [dict(r) for r in con.execute("SELECT * FROM joueurs WHERE guild_id=? ORDER BY golds DESC", (g,))]


con.commit()

con.commit()


con.commit()

con.commit()
