"""2Hot4Deck · le site (16 octobre 2026).

Le jeu sur le web, sans avoir besoin du bot Discord : il a sa propre base (site_web/site.db, copiée au départ de faille.db)
et le même moteur de jeu que le bot (jeu.py). Le jeu Discord n'est jamais touché. On se connecte avec son compte Discord
(ça sert seulement à savoir qui on est).

Lancement : double-clic sur lancer_site.bat (ou « python serveur.py »).
Réglages : un fichier .env dans ce dossier (voir exemple_env.txt). Ne montre jamais le secret à personne.
"""
import json, os, re, secrets, sqlite3, sys, threading, time, urllib.error, urllib.parse, urllib.request
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ICI = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.dirname(ICI)                       # le dossier du bot, juste au-dessus
sys.path.insert(0, BOT)
import jeu                                       # le moteur du jeu, avec la base du site (site.db) : Discord n'est pas nécessaire
import data                                      # les données des cartes (noms, kits, items, runes…)
import combat                                    # les règles du jeu (combats, tirages)


def lire_env(chemin=None):
    reglages = {}
    chemin = chemin or os.path.join(ICI, ".env")
    if os.path.exists(chemin):
        for ligne in open(chemin, encoding="utf-8"):
            if "=" in ligne and not ligne.strip().startswith("#"):
                cle, _, valeur = ligne.partition("=")
                reglages[cle.strip()] = valeur.strip().strip('"')
    return reglages


ENV = lire_env()
CLIENT_ID = ENV.get("DISCORD_CLIENT_ID", "")
CLIENT_SECRET = ENV.get("DISCORD_CLIENT_SECRET", "")
SERVEUR_ID = int(ENV.get("SERVEUR_ID", "100000000000000007"))
PORT = int(ENV.get("PORT", "8081"))
ECRITURE = ENV.get("ECRITURE", "oui").lower() in ("1", "oui", "true", "yes")   # « ECRITURE=non » dans .env : le site redevient lecture seule
# Pour prévenir un joueur sur Discord d'un message privé : le site parle au nom du bot, avec la clé du bot
# (lue dans le .env du bot, jamais affichée). Sans clé, les messages privés restent sur le site.
JETON_BOT = ENV.get("TOKEN") or lire_env(os.path.join(os.path.dirname(ICI), ".env")).get("TOKEN", "")
BASE = jeu.BASE_SITE                             # 16 octobre : le site a sa propre base ; le jeu Discord (faille.db) n'est jamais touché
IMAGES = os.path.join(BOT, "images")
STATIC = os.path.join(ICI, "static")
ORDRE = {"LR": 0, "UR": 1, "SSR": 2, "SR": 3, "R": 4, "N": 5}
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".svg": "image/svg+xml", ".ico": "image/x-icon"}
DUREE_SESSION = 7 * 24 * 3600                    # on reste connecté une semaine
SESSIONS = {}                                    # jeton -> {"user": id Discord, "fin": horodatage}  (en mémoire : un redémarrage déconnecte)
ETATS = {}                                       # « state » de connexion -> horodatage (protège la connexion contre les liens piégés)


def image_carte(cid):
    """Le fichier image d'une carte (c_<carte>.png ou .jpg), ou None."""
    for nom in (f"c_{cid}", cid):   # la carte encadrée, sinon l'illustration seule (comme le bot)
        for ext in (".png", ".jpg", ".webp"):
            chemin = os.path.join(IMAGES, nom + ext)
            if os.path.exists(chemin):
                return chemin
    c = data.CARTES.get(cid)
    generique = os.path.join(IMAGES, f"carte_{c['rarete']}.png") if c else ""
    if c and not c.get("image") and os.path.exists(generique):   # sbires et monstres sans illustration : l'image de leur rareté
        return generique
    return None


def appel_discord(url, donnees=None, jeton=None):
    """Appelle l'API de Discord (échange du code, ou « qui est connecté ? »)."""
    entetes = {"User-Agent": "2Hot4Deck-Site (test, 1.0)"}
    corps = None
    if donnees is not None:
        corps = urllib.parse.urlencode(donnees).encode()
        entetes["Content-Type"] = "application/x-www-form-urlencoded"
    if jeton:
        entetes["Authorization"] = f"Bearer {jeton}"
    with urllib.request.urlopen(urllib.request.Request(url, data=corps, headers=entetes), timeout=10) as r:
        return json.loads(r.read())


def lire_base():
    con = sqlite3.connect(f"file:{BASE}?mode=ro", uri=True, timeout=5)   # mode=ro : lecture seule, impossible d'écrire
    con.row_factory = sqlite3.Row
    return con


def icone(genre, cle):
    """L'icône officielle de l'item ou de la rune (téléchargée chez Riot, rangée dans static/icones), sinon rien."""
    nom = f"{genre}_{cle}.webp"
    return f"/static/icones/{nom}" if os.path.exists(os.path.join(ICI, "static", "icones", nom)) else None


def texte_item(cle, niveau):
    nom, emoji, _, valeurs, texte = data.ITEMS[cle]
    v = valeurs[max(0, min(niveau, len(valeurs)) - 1)] if isinstance(valeurs, (tuple, list)) else valeurs
    return {"nom": nom, "emoji": emoji, "icone": icone("item", cle), "niveau": niveau, "effet": texte.format(v) if "{}" in texte else texte}


def regles_forge():
    """Les recettes et composants de la forge (les mêmes que dans le bot), pour que le site affiche ce qui est possible."""
    ou = {c: d[0] for d in data.DONJONS for c in d[2]}
    return {"max": data.ITEM_NIVEAU_MAX, "quantites": list(data.RECETTE_QUANTITES),
            "composants": {k: {"nom": n, "emoji": e, "donjon": ou.get(k, "")} for k, (n, e) in data.COMPOSANTS.items()},
            "recettes": {k: {"nom": v[0], "emoji": v[1], "icone": icone("item", k), "composants": list(data.RECETTES[k]),
                             "effets": [v[4].format(x) if "{}" in v[4] else v[4] for x in v[3]]} for k, v in data.ITEMS.items()}}


def cible_forge(sac, x):
    """Comme la forge du bot : l'exemplaire le moins avancé qui n'est pas au maximum, sinon un nouvel exemplaire (« x~2 »…)."""
    exemplaires = sorted([k for k in sac if k.split("~")[0] == x], key=lambda k: sac[k]["niveau"])
    pas_fini = [k for k in exemplaires if sac[k]["niveau"] < data.ITEM_NIVEAU_MAX]
    if pas_fini:
        cible = pas_fini[0]
    elif x not in sac:
        cible = x
    else:
        n = 2
        while f"{x}~{n}" in sac:
            n += 1
        cible = f"{x}~{n}"
    return cible, sac.get(cible, {}).get("niveau", 0) + 1, len(exemplaires)


def texte_rune(cle):
    nom, emoji, _, effet = data.RUNES[cle]
    return {"nom": nom, "emoji": emoji, "icone": icone("rune", cle), "effet": effet}


TIER = json.load(open(os.path.join(ICI, "tier.json"), encoding="utf-8")) if os.path.exists(os.path.join(ICI, "tier.json")) else {}
_PAR_NOM = {**{v[0]: icone("item", k) for k, v in data.ITEMS.items()}, **{v[0]: icone("rune", k) for k, v in data.RUNES.items()}}
for _t in TIER.values():                       # la tier list donne les noms : on y ajoute les icônes
    for _m in ("worlds", "pvp", "boss"):
        if isinstance(_t.get(_m), dict):
            _t[_m]["item_icone"] = _PAR_NOM.get(_t[_m].get("item"))
            _t[_m]["rune_icone"] = _PAR_NOM.get(_t[_m].get("rune"))
EQUIPES_WORLDS = [t["equipe"] if k < len(data.TOUR_PROS) - 1 else "Faker" for k, t in enumerate(data.TOUR_PROS)]


def jouables():
    """Les cartes qu'on peut obtenir (celles de la tier list)."""
    return [c for c, v in data.CARTES.items() if v.get("ulti") and (
        v.get("en_jeu") or c in data.UR_PACK or c in data.WORLDS_LRS or any(c in l for l in data.WORLDS_CARTES)
        or any(c in l for l in data.LEC_CARTES) or c in data.LEC_UR)]


def fiche_carte(cid, niveau=None, etoiles=None):
    """Tout ce qu'on montre d'une carte. Sans niveau : la carte au maximum (5★ pour les SR et SSR)."""
    c = data.CARTES[cid]
    rarete = "LR" if cid.endswith("LR") else c["rarete"]
    if niveau is None:
        etoiles = 0 if rarete in ("UR", "LR") else data.ETOILES_MAX
        niveau = combat.niveau_max(cid, etoiles)
    base = c.get("base", cid)
    passif, actif = data.TEXTES_KITS.get(cid) or data.TEXTES_KITS.get(base) or (None, None)
    try:
        pv, atk = combat.stats(cid, niveau, etoiles)
    except Exception:
        pv, atk = None, None
    return {"id": cid, "nom": c["nom"], "rarete": rarete, "role": c["role"], "region": c["region"], "niveau": niveau, "etoiles": etoiles,
            "pv": pv, "atk": atk, "vitesse": c.get("vitesse"), "ulti": c.get("ulti"), "passif": passif, "actif": actif,
            "eveil": getattr(data, "EVEILS", {}).get(cid), "tier": TIER.get(cid), "image": f"/cartes/{cid}" if image_carte(cid) else None,
            "encadree": os.path.basename(image_carte(cid) or "").startswith("c_")}


def runes_portees(j):
    possedees = [x for x in (j["runes"] or "").split(",") if x in data.RUNES]
    runes = {}
    for morceau in (j["runes_equipees"] or "").split(","):
        carte, _, rune = morceau.partition(":")
        if rune in possedees and list(runes.values()).count(rune) < possedees.count(rune) and len(runes) < 3:
            runes[carte] = rune
    return runes


REGLES_FORGE = regles_forge()


def collection(user_id):
    """La fiche du joueur et ses cartes. Lecture seule."""
    con = lire_base()
    try:
        j = con.execute("SELECT * FROM joueurs WHERE guild_id=? AND user_id=?", (SERVEUR_ID, user_id)).fetchone()
        if not j:
            return None
        items = {}
        for r in con.execute("SELECT * FROM items WHERE guild_id=? AND user_id=?", (SERVEUR_ID, user_id)):
            cle = r["item"].split("~")[0]
            if r["carte"] and cle in data.ITEMS:
                items[r["carte"]] = texte_item(cle, r["niveau"])
        runes = runes_portees(j)
        equipe = [c for c in (j["equipe"] or "").split(",") if c]
        cartes = []
        for r in con.execute("SELECT carte, niveau, etoiles FROM cartes WHERE guild_id=? AND user_id=?", (SERVEUR_ID, user_id)):
            cid = r["carte"]
            c = data.CARTES.get(cid)
            if not c or c.get("role") == "sbire":
                continue
            f = fiche_carte(cid, r["niveau"], r["etoiles"])
            f.update(item=items.get(cid), rune=texte_rune(runes[cid]) if cid in runes else None, equipe=cid in equipe)
            cartes.append(f)
        cartes.sort(key=lambda x: (ORDRE.get(x["rarete"], 9), -x["niveau"], x["nom"]))
        sac = []
        for r in con.execute("SELECT * FROM items WHERE guild_id=? AND user_id=?", (SERVEUR_ID, user_id)):
            cle = r["item"].split("~")[0]
            if cle in data.ITEMS:
                sac.append(dict(texte_item(cle, r["niveau"]), id=r["item"], carte=r["carte"] or ""))
        sac.sort(key=lambda x: (x["carte"] == "", x["nom"], -x["niveau"]))
        possedees_r = [x for x in (j["runes"] or "").split(",") if x in data.RUNES]
        runes = [dict(texte_rune(k), id=k, nombre=possedees_r.count(k)) for k in dict.fromkeys(possedees_r)]
        return {"id": str(user_id), "pseudo": j["pseudo"] or "Joueur", "golds": j["golds"], "niveau": j["niveau"], "etage": j["etage"],
                "packs": {"pro": j["packs_pro"], "ur": j["packs_ur"], "lec": j["packs_lec"], "niveau": j["packs_niveau"]},
                "gratuit_dans": max(0, round(data.DELAI_GRATUIT - (time.time() - (j["dernier_gratuit"] or 0)))),
                "prix": {"normal": data.PRIX_PACK, "normal10": data.PRIX_PACK_10, "mega": data.MEGA_PRIX, "mega_cartes": data.MEGA_CARTES},
                "titres": j["worlds_titres"], "cartes": cartes, "equipe": [c for c in equipe if any(x["id"] == c for x in cartes)][:3],
                "sac": sac, "runes": runes, "runes_portees": runes_portees(j), "ecriture": ECRITURE,
                "composants": {r["composant"]: r["quantite"] for r in con.execute("SELECT * FROM composants WHERE guild_id=? AND user_id=?", (SERVEUR_ID, user_id)) if r["quantite"] > 0},
                "forge": REGLES_FORGE}
    finally:
        con.close()


# -- écritures : les mêmes règles que les menus du bot (équipe, items, runes) --
class Refus(Exception):
    pass


def ecrire(fonction):
    """Ouvre la base en écriture le temps d'une seule modification, puis la referme (une action à la fois, avec le moteur)."""
    with jeu.VERROU:
        return _ecrire(fonction)


def _ecrire(fonction):
    con = sqlite3.connect(BASE, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        with con:   # tout ou rien
            return fonction(con)
    finally:
        con.close()


def joueur_et_cartes(con, user_id):
    j = con.execute("SELECT * FROM joueurs WHERE guild_id=? AND user_id=?", (SERVEUR_ID, user_id)).fetchone()
    if not j:
        raise Refus("Pas de compte 2Hot4Deck.")
    cartes = {r["carte"] for r in con.execute("SELECT carte FROM cartes WHERE guild_id=? AND user_id=?", (SERVEUR_ID, user_id))}
    return j, cartes


def changer_equipe(user_id, choix):
    """1 à 3 cartes possédées, la première est le leader (comme le menu « Mon équipe » du bot)."""
    def f(con):
        j, cartes = joueur_et_cartes(con, user_id)
        propre = [c for c in dict.fromkeys(choix) if c in cartes and c in data.CARTES and data.CARTES[c].get("role") != "sbire"]
        if not 1 <= len(propre) <= 3:
            raise Refus("Une équipe, c'est de 1 à 3 cartes que tu possèdes.")
        con.execute("UPDATE joueurs SET equipe=? WHERE guild_id=? AND user_id=?", (",".join(propre), SERVEUR_ID, user_id))
    ecrire(f)


def equiper_item(user_id, item, carte):
    """Un item par carte : celui qui y était retourne dans le sac. carte vide : on retire l'item."""
    def f(con):
        j, cartes = joueur_et_cartes(con, user_id)
        r = con.execute("SELECT * FROM items WHERE guild_id=? AND user_id=? AND item=?", (SERVEUR_ID, user_id, item)).fetchone()
        if not r:
            raise Refus("Tu n'as pas cet item.")
        if carte and carte not in cartes:
            raise Refus("Tu n'as pas cette carte.")
        if carte:
            con.execute("UPDATE items SET carte='' WHERE guild_id=? AND user_id=? AND carte=?", (SERVEUR_ID, user_id, carte))
        con.execute("UPDATE items SET carte=? WHERE guild_id=? AND user_id=? AND item=?", (carte, SERVEUR_ID, user_id, item))
    ecrire(f)


def forger(user_id, x):
    """Fabrique ou améliore un item avec les composants du joueur (mêmes règles et mêmes coûts que la forge du bot)."""
    def f(con):
        joueur_et_cartes(con, user_id)
        if x not in data.ITEMS:
            raise Refus("Cette recette n'existe pas.")
        sac = {r["item"]: {"niveau": r["niveau"], "carte": r["carte"]} for r in con.execute("SELECT * FROM items WHERE guild_id=? AND user_id=?", (SERVEUR_ID, user_id))}
        stock = {r["composant"]: r["quantite"] for r in con.execute("SELECT * FROM composants WHERE guild_id=? AND user_id=?", (SERVEUR_ID, user_id))}
        cible, n, exemplaires = cible_forge(sac, x)
        cout = combat.cout_recette(x, n)
        manque = [f"{q - stock.get(c, 0)} {data.COMPOSANTS[c][0]}" for c, q in cout.items() if stock.get(c, 0) < q]
        if manque:
            raise Refus("Il te manque " + " et ".join(manque) + ".")
        for c, q in cout.items():
            con.execute("UPDATE composants SET quantite = quantite - ? WHERE guild_id=? AND user_id=? AND composant=?", (q, SERVEUR_ID, user_id, c))
        con.execute("""INSERT INTO items VALUES (?,?,?,?,?) ON CONFLICT(guild_id, user_id, item) DO UPDATE SET niveau=excluded.niveau""",
                    (SERVEUR_ID, user_id, cible, n, sac.get(cible, {}).get("carte", "")))
        nom = data.ITEMS[x][0]
        if n > 1:
            return f"{nom} passe au niveau {n} !"
        return f"{nom} est fabriqué" + (f" (exemplaire {exemplaires + 1})" if exemplaires else "") + " ! Équipe-le sur un champion."
    return ecrire(f)


# -- le fil des tirages et le chat : propres au site, rangés dans site.db --
def preparer_tables():
    def f(con):
        con.execute("CREATE TABLE IF NOT EXISTS site_tirages (id INTEGER PRIMARY KEY AUTOINCREMENT, moment REAL, user_id INTEGER, pseudo TEXT, cartes TEXT, coachs TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS site_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, moment REAL, user_id INTEGER, pseudo TEXT, texte TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS site_mp (id INTEGER PRIMARY KEY AUTOINCREMENT, moment REAL, de INTEGER, a INTEGER, texte TEXT, lu INTEGER DEFAULT 0)")
        con.execute("CREATE INDEX IF NOT EXISTS site_mp_a ON site_mp (a, lu)")
    ecrire(f)


def pseudo_de(con, user_id, defaut="Joueur"):
    j = con.execute("SELECT pseudo FROM joueurs WHERE guild_id=? AND user_id=?", (SERVEUR_ID, user_id)).fetchone()
    return (j["pseudo"] if j and j["pseudo"] else None) or defaut


def belle_carte(cid):
    """Les mêmes cartes que le salon des tirages du bot : les UR et LR, et les SSR des pros (absentes des packs normaux)."""
    c = data.CARTES.get(cid)
    return bool(c) and (c["rarete"] == "UR" or (c["rarete"] == "SSR" and not c.get("en_jeu", True)))


def noter_tirage(user_id, cids, coachs=()):
    rares = sorted({c for c in cids if belle_carte(c)}, key=lambda c: -data.RARETES.index(data.CARTES[c]["rarete"]))
    coachs = [str(x) for x in coachs if x]
    if not rares and not coachs:
        return
    def f(con):
        con.execute("INSERT INTO site_tirages (moment, user_id, pseudo, cartes, coachs) VALUES (?,?,?,?,?)",
                    (time.time(), user_id, pseudo_de(con, user_id), json.dumps(rares), json.dumps(coachs)))
    try:
        ecrire(f)
    except sqlite3.Error as erreur:   # le fil ne doit jamais gêner un tirage
        print("   fil des tirages :", erreur)


def fil_tirages():
    con = lire_base()
    try:
        lignes = con.execute("SELECT * FROM site_tirages ORDER BY id DESC LIMIT 40").fetchall()
    except sqlite3.Error:
        lignes = []
    finally:
        con.close()
    fil = []
    for r in lignes:
        cartes = [{"id": c, "nom": data.CARTES[c]["nom"], "rarete": "LR" if c.endswith("LR") else data.CARTES[c]["rarete"]}
                  for c in json.loads(r["cartes"] or "[]") if c in data.CARTES]
        coachs = [{"pseudo": x, "image": f"/coach/{urllib.parse.quote(x)}" if os.path.exists(os.path.join(BOT, "pros", "cartes", x + ".png")) else None}
                  for x in json.loads(r["coachs"] or "[]")]
        fil.append({"id": r["id"], "il_y_a": round(time.time() - r["moment"]), "joueur": str(r["user_id"]), "pseudo": r["pseudo"], "cartes": cartes, "coachs": coachs})
    return fil


CHAT_DERNIER = {}


def lire_chat(apres=0):
    con = lire_base()
    try:
        lignes = con.execute("SELECT * FROM (SELECT * FROM site_chat WHERE id > ? ORDER BY id DESC LIMIT 80) ORDER BY id", (apres,)).fetchall()
    except sqlite3.Error:
        lignes = []
    finally:
        con.close()
    return [{"id": r["id"], "il_y_a": round(time.time() - r["moment"]), "joueur": str(r["user_id"]), "pseudo": r["pseudo"], "texte": r["texte"]} for r in lignes]


def ecrire_chat(user_id, nom, texte):
    texte = re.sub(r"\s+", " ", str(texte or "")).strip()
    if not texte:
        raise Refus("Ton message est vide.")
    if len(texte) > 300:
        raise Refus("300 caractères au maximum.")
    if time.time() - CHAT_DERNIER.get(user_id, 0) < 1.5:
        raise Refus("Doucement : un message à la fois.")
    CHAT_DERNIER[user_id] = time.time()
    def f(con):
        con.execute("INSERT INTO site_chat (moment, user_id, pseudo, texte) VALUES (?,?,?,?)", (time.time(), user_id, pseudo_de(con, user_id, nom or "Joueur"), texte))
        con.execute("DELETE FROM site_chat WHERE id <= (SELECT MAX(id) - 500 FROM site_chat)")   # on garde les 500 derniers messages
    ecrire(f)


# -- les messages privés : entre deux joueurs, avec un avertissement sur Discord --
MP_DERNIER, MP_DISCORD = {}, {}


def texte_propre(texte, maxi=500):
    texte = re.sub(r"[ \t]+", " ", str(texte or "")).strip()
    texte = re.sub(r"\n{3,}", "\n\n", texte)
    if not texte:
        raise Refus("Ton message est vide.")
    if len(texte) > maxi:
        raise Refus(f"{maxi} caractères au maximum.")
    return texte


def conversations(user_id):
    """Les personnes avec qui on a échangé, la plus récente d'abord, avec le nombre de messages non lus."""
    con = lire_base()
    try:
        lignes = con.execute("""SELECT CASE WHEN de=? THEN a ELSE de END AS autre, MAX(id) AS dernier,
                                       SUM(CASE WHEN a=? AND lu=0 THEN 1 ELSE 0 END) AS non_lus
                                FROM site_mp WHERE de=? OR a=? GROUP BY autre ORDER BY dernier DESC LIMIT 50""", (user_id, user_id, user_id, user_id)).fetchall()
        res = []
        for r in lignes:
            m = con.execute("SELECT * FROM site_mp WHERE id=?", (r["dernier"],)).fetchone()
            res.append({"joueur": str(r["autre"]), "pseudo": pseudo_de(con, r["autre"]), "dernier": m["texte"][:80], "de_moi": m["de"] == user_id,
                        "il_y_a": round(time.time() - m["moment"]), "non_lus": r["non_lus"] or 0})
        return res
    except sqlite3.Error:
        return []
    finally:
        con.close()


def mp_non_lus(user_id):
    con = lire_base()
    try:
        return con.execute("SELECT COUNT(*) FROM site_mp WHERE a=? AND lu=0", (user_id,)).fetchone()[0]
    except sqlite3.Error:
        return 0
    finally:
        con.close()


def fil_mp(user_id, autre, apres=0):
    """Les messages échangés avec un joueur ; ceux qu'on reçoit passent en « lus »."""
    def f(con):
        con.execute("UPDATE site_mp SET lu=1 WHERE a=? AND de=? AND lu=0", (user_id, autre))
        lignes = con.execute("""SELECT * FROM (SELECT * FROM site_mp WHERE id > ? AND ((de=? AND a=?) OR (de=? AND a=?)) ORDER BY id DESC LIMIT 100)
                                ORDER BY id""", (apres, user_id, autre, autre, user_id)).fetchall()
        return {"joueur": str(autre), "pseudo": pseudo_de(con, autre),
                "messages": [{"id": r["id"], "de_moi": r["de"] == user_id, "texte": r["texte"], "il_y_a": round(time.time() - r["moment"])} for r in lignes]}
    return ecrire(f)


def envoyer_mp(user_id, nom, autre, texte, adresse):
    texte = texte_propre(texte)
    if autre == user_id:
        raise Refus("Tu ne peux pas t'écrire à toi-même.")
    if time.time() - MP_DERNIER.get(user_id, 0) < 1.5:
        raise Refus("Doucement : un message à la fois.")
    MP_DERNIER[user_id] = time.time()
    def f(con):
        if not con.execute("SELECT 1 FROM joueurs WHERE guild_id=? AND user_id=?", (SERVEUR_ID, autre)).fetchone():
            raise Refus("Ce joueur n'existe pas.")
        con.execute("INSERT INTO site_mp (moment, de, a, texte) VALUES (?,?,?,?)", (time.time(), user_id, autre, texte))
        return pseudo_de(con, user_id, nom or "Un joueur")
    pseudo = ecrire(f)
    # sur Discord : un avertissement au plus toutes les 2 minutes par conversation, pour ne pas inonder ses messages privés
    cle = (user_id, autre)
    if JETON_BOT and time.time() - MP_DISCORD.get(cle, 0) > 120:
        MP_DISCORD[cle] = time.time()
        threading.Thread(target=prevenir_sur_discord, args=(autre, user_id, pseudo, texte, adresse), daemon=True).start()


def prevenir_sur_discord(destinataire, expediteur, pseudo, texte, adresse):
    """Envoie un message privé Discord au destinataire, au nom du bot. S'il a fermé ses messages privés, tant pis : le message reste sur le site."""
    def appel(url, donnees):
        req = urllib.request.Request(url, data=json.dumps(donnees).encode(), method="POST",
                                     headers={"Authorization": f"Bot {JETON_BOT}", "Content-Type": "application/json", "User-Agent": "2Hot4Deck-Site (messages, 1.0)"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read() or b"{}")
    try:
        salon = appel("https://discord.com/api/v10/users/@me/channels", {"recipient_id": str(destinataire)})
        lien = f"{adresse}/#mp/{expediteur}"
        carte = {"title": f"📩 Message de {pseudo[:80]}", "description": texte[:1500], "color": 0xD9B25F,
                 "footer": {"text": "Envoyé depuis le site 2Hot4Deck · réponds-lui sur le site"}}
        if lien.startswith("https://"):   # en local (http://localhost), Discord refuse le lien : on ne le met pas
            carte["url"] = lien
        appel(f"https://discord.com/api/v10/channels/{salon['id']}/messages", {"embeds": [carte]})
    except Exception as erreur:   # messages privés fermés, pas de connexion… : sans gravité
        print("   avertissement Discord non envoyé :", erreur)


def poser_rune(user_id, carte, rune):
    """Une rune par carte de l'équipe, un exemplaire par carte, 3 emplacements. rune « - » : on l'enlève."""
    def f(con):
        j, cartes = joueur_et_cartes(con, user_id)
        if carte not in cartes:
            raise Refus("Tu n'as pas cette carte.")
        possedees = [x for x in (j["runes"] or "").split(",") if x in data.RUNES]
        portees = runes_portees(j)
        portees.pop(carte, None)
        if rune != "-":
            if rune not in possedees:
                raise Refus("Tu n'as pas cette rune.")
            autres = [k for k, v in portees.items() if v == rune]
            while autres and len(autres) >= possedees.count(rune):   # plus d'exemplaire libre : la rune change de carte
                portees.pop(autres.pop(0))
            if len(portees) >= 3:
                raise Refus("Tu as déjà 3 runes équipées : retires-en une d'abord.")
            portees[carte] = rune
        con.execute("UPDATE joueurs SET runes_equipees=? WHERE guild_id=? AND user_id=?",
                    (",".join(f"{k}:{v}" for k, v in portees.items()), SERVEUR_ID, user_id))
    ecrire(f)


# -- ouverture des packs : le moteur du jeu (mêmes règles que le bot), sur la base du site --
DERNIERE_OUVERTURE = {}                         # anti-spam : une ouverture par seconde et par joueur


def ouvrir_pack(user_id, pack):
    if time.time() - DERNIERE_OUVERTURE.get(user_id, 0) < 1.0:
        raise Refus("Doucement : un pack à la fois.")
    DERNIERE_OUVERTURE[user_id] = time.time()
    res = jeu.ouvrir(SERVEUR_ID, user_id, pack)
    if "erreur" in res:
        raise Refus(res["erreur"])
    con = lire_base()   # les cartes tirées, avec leur niveau et leurs étoiles d'après le tirage
    try:
        miennes = {r["carte"]: r for r in con.execute("SELECT * FROM cartes WHERE guild_id=? AND user_id=?", (SERVEUR_ID, user_id))}
    finally:
        con.close()
    cartes = []
    for c in res.get("cartes", []):
        if c["id"] not in data.CARTES:
            continue
        r = miennes.get(c["id"])
        f = fiche_carte(c["id"], r["niveau"], r["etoiles"]) if r else fiche_carte(c["id"])
        f.update(statut=c.get("statut", ""), en_plus=c.get("en_plus", []), nouvelle=c.get("statut", "").startswith("🆕"))
        cartes.append(f)
    noter_tirage(user_id, res.get("annonce", []), res.get("annonce_coachs", []))
    coachs = res.get("coachs", [])
    for coach in coachs:
        coach["image"] = f"/coach/{urllib.parse.quote(coach['pseudo'])}" if os.path.exists(os.path.join(BOT, "pros", "cartes", coach["pseudo"] + ".png")) else None
    return {"pack": pack, "cartes": cartes, "coachs": coachs, "message": res.get("message", ""), "ouverts": res.get("ouverts")}


def toutes_les_cartes():
    """Les cartes du jeu, au maximum, avec le nombre de joueurs qui les ont."""
    con = lire_base()
    try:
        nb = dict(con.execute("SELECT carte, COUNT(DISTINCT user_id) FROM cartes WHERE guild_id=? GROUP BY carte", (SERVEUR_ID,)).fetchall())
    finally:
        con.close()
    liste = []
    for cid in jouables():
        f = fiche_carte(cid)
        f["possedee_par"] = nb.get(cid, 0)
        liste.append(f)
    liste.sort(key=lambda x: (ORDRE.get(x["rarete"], 9), x["nom"]))
    return liste


def meilleure_equipe_worlds(con, user_id):
    r = con.execute("SELECT MAX(equipe) FROM worlds_equipes WHERE guild_id=? AND user_id=?", (SERVEUR_ID, user_id)).fetchone()
    return EQUIPES_WORLDS[r[0]] if r and r[0] is not None and r[0] < len(EQUIPES_WORLDS) else None


def classement():
    con = lire_base()
    try:
        joueurs = []
        for j in con.execute("SELECT * FROM joueurs WHERE guild_id=?", (SERVEUR_ID,)):
            rar = {}
            for (cid,) in con.execute("SELECT carte FROM cartes WHERE guild_id=? AND user_id=?", (SERVEUR_ID, j["user_id"])):
                c = data.CARTES.get(cid)
                if c and c.get("ulti"):
                    r = "LR" if cid.endswith("LR") else c["rarete"]
                    rar[r] = rar.get(r, 0) + 1
            joueurs.append({"id": str(j["user_id"]), "pseudo": j["pseudo"] or "Joueur", "niveau": j["niveau"], "etage": j["etage"],
                            "arene": j["arene_points"], "worlds": meilleure_equipe_worlds(con, j["user_id"]), "titres": j["worlds_titres"],
                            "cartes": sum(rar.values()), "ur": rar.get("UR", 0), "lr": rar.get("LR", 0)})
        return {"joueurs": joueurs, "equipes_worlds": EQUIPES_WORLDS}
    finally:
        con.close()


def profil(user_id):
    """Le profil public d'un joueur : ses chiffres, son équipe et ses meilleures cartes. Pas ses golds ni ses packs."""
    con = lire_base()
    try:
        j = con.execute("SELECT * FROM joueurs WHERE guild_id=? AND user_id=?", (SERVEUR_ID, user_id)).fetchone()
        if not j:
            return None
        cartes = []
        for r in con.execute("SELECT carte, niveau, etoiles FROM cartes WHERE guild_id=? AND user_id=?", (SERVEUR_ID, user_id)):
            c = data.CARTES.get(r["carte"])
            if c and c.get("ulti"):
                cartes.append(fiche_carte(r["carte"], r["niveau"], r["etoiles"]))
        force = lambda x: (x["pv"] or 0) / 5 + (x["atk"] or 0) * 2
        cartes.sort(key=force, reverse=True)
        equipe = [c for c in (j["equipe"] or "").split(",") if c]
        rar = {}
        for c in cartes:
            rar[c["rarete"]] = rar.get(c["rarete"], 0) + 1
        return {"id": str(user_id), "pseudo": j["pseudo"] or "Joueur", "niveau": j["niveau"], "etage": j["etage"], "arene": j["arene_points"],
                "worlds": meilleure_equipe_worlds(con, user_id), "titres": j["worlds_titres"], "nb_cartes": len(cartes), "raretes": rar,
                "equipe": [c for c in cartes if c["id"] in equipe], "vitrine": cartes[:8]}
    finally:
        con.close()


def accueil_public():
    """Quelques chiffres pour la page d'accueil, sans connexion."""
    con = lire_base()
    try:
        joueurs = con.execute("SELECT COUNT(*) FROM joueurs WHERE guild_id=?", (SERVEUR_ID,)).fetchone()[0]
        cartes = con.execute("SELECT COUNT(*) FROM cartes WHERE guild_id=?", (SERVEUR_ID,)).fetchone()[0]
        vitrine = [c for c in ("RyzeLR", "AhriLR", "AzirLR") if image_carte(c)]
        return {"joueurs": joueurs, "cartes_obtenues": cartes, "cartes_jeu": len(jouables()), "vitrine": vitrine}
    finally:
        con.close()


preparer_tables()


class Page(BaseHTTPRequestHandler):
    def do_POST(self):
        chemin = urllib.parse.urlparse(self.path).path
        if chemin not in ("/api/equipe", "/api/item", "/api/rune", "/api/ouvrir", "/api/tour", "/api/forger", "/api/donjon", "/api/chat", "/api/mp", "/api/jungle"):
            return self.envoyer(404, {"erreur": "introuvable"})
        if not ECRITURE:
            return self.envoyer(403, {"erreur": "Les changements depuis le site sont désactivés pour l'instant."})
        origine = self.headers.get("Origin", "")
        if origine and urllib.parse.urlparse(origine).netloc != (self.headers.get("X-Forwarded-Host") or self.headers.get("Host")):
            return self.envoyer(403, {"erreur": "Requête refusée."})   # un autre site ne peut pas agir à ta place
        _, s = self.session()
        if not s:
            return self.envoyer(401, {"erreur": "Connecte-toi d'abord."})
        try:
            corps = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", "0") or 0), 10000)) or b"{}")
            tirage, forge = None, None
            if chemin == "/api/jungle":   # la carte de la jungle : une action à la fois, jouée par le moteur
                res = jeu.jungle_action(SERVEUR_ID, s["user"], str(corps.get("action", "")), corps.get("valeur"))
                if "erreur" in res:
                    raise Refus(res["erreur"])
                noter_tirage(s["user"], res.get("trouvees", []))
                fiche = collection(s["user"])
                fiche["avatar"] = f"https://cdn.discordapp.com/avatars/{s['user']}/{s['avatar']}.png?size=64" if s.get("avatar") else None
                return self.envoyer(200, {"jungle": res, "moi": fiche})
            if chemin == "/api/mp":
                autre = int(corps.get("a", 0) or 0)
                envoyer_mp(s["user"], s.get("nom"), autre, corps.get("texte", ""), self.adresse())
                return self.envoyer(200, fil_mp(s["user"], autre, int(corps.get("apres", 0) or 0)))
            if chemin == "/api/chat":
                ecrire_chat(s["user"], s.get("nom"), corps.get("texte", ""))
                return self.envoyer(200, {"messages": lire_chat(int(corps.get("apres", 0) or 0))})
            if chemin in ("/api/tour", "/api/donjon"):   # un combat (tour ou donjon), joué par le moteur ; le site le rejoue ensuite à l'écran
                res = (jeu.tour_combattre(SERVEUR_ID, s["user"]) if chemin == "/api/tour"
                       else jeu.donjon_combattre(SERVEUR_ID, s["user"], int(corps.get("numero", -1))))
                if "erreur" in res:
                    raise Refus(res["erreur"])
                pack = (res.get("recompenses") or {}).get("pack")
                if isinstance(pack, dict) and pack.get("id"):
                    noter_tirage(s["user"], [pack["id"]])
                fiche = collection(s["user"])
                fiche["avatar"] = f"https://cdn.discordapp.com/avatars/{s['user']}/{s['avatar']}.png?size=64" if s.get("avatar") else None
                return self.envoyer(200, {"combat": res, "moi": fiche})
            if chemin == "/api/ouvrir":
                tirage = ouvrir_pack(s["user"], str(corps.get("pack", "")))
            elif chemin == "/api/equipe":
                changer_equipe(s["user"], [str(c) for c in corps.get("cartes", [])][:3])
            elif chemin == "/api/forger":
                forge = forger(s["user"], str(corps.get("item", "")))
            elif chemin == "/api/item":
                equiper_item(s["user"], str(corps.get("item", "")), str(corps.get("carte", "")))
            else:
                poser_rune(s["user"], str(corps.get("carte", "")), str(corps.get("rune", "-")))
        except Refus as refus:
            return self.envoyer(400, {"erreur": str(refus)})
        except (ValueError, sqlite3.Error) as erreur:
            print("   écriture refusée :", erreur)
            return self.envoyer(500, {"erreur": "Le changement n'a pas pu être enregistré. Réessaie."})
        fiche = collection(s["user"])
        fiche["avatar"] = f"https://cdn.discordapp.com/avatars/{s['user']}/{s['avatar']}.png?size=64" if s.get("avatar") else None
        if tirage is not None:
            fiche["tirage"] = tirage
        if forge:
            fiche["message_forge"] = forge
        return self.envoyer(200, fiche)

    def log_message(self, fmt, *args):
        print("  ", time.strftime("%H:%M:%S"), fmt % args)

    # -- outils --
    def adresse(self):
        """L'adresse publique du site (celle du tunnel), pour le retour de Discord."""
        hote = self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or f"localhost:{PORT}"
        schema = "http" if hote.startswith(("localhost", "127.0.0.1")) else "https"
        return f"{schema}://{hote}"

    def session(self):
        biscuit = SimpleCookie(self.headers.get("Cookie", ""))
        jeton = biscuit["session"].value if "session" in biscuit else ""
        s = SESSIONS.get(jeton)
        if s and s["fin"] > time.time():
            return jeton, s
        return None, None

    def envoyer(self, code, corps, type_="application/json; charset=utf-8", cache=False, entetes=()):
        if isinstance(corps, (dict, list)):
            corps = json.dumps(corps, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "public, max-age=3600" if cache else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        for k, v in entetes:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corps)

    def rediriger(self, ou, entetes=()):
        self.send_response(302)
        self.send_header("Location", ou)
        self.send_header("Cache-Control", "no-store")
        for k, v in entetes:
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def fichier(self, chemin, cache=False):
        if not os.path.isfile(chemin):
            return self.envoyer(404, {"erreur": "introuvable"})
        with open(chemin, "rb") as f:
            self.envoyer(200, f.read(), TYPES.get(os.path.splitext(chemin)[1].lower(), "application/octet-stream"), cache)

    def biscuit(self, jeton, duree):
        securise = "" if self.adresse().startswith("http://") else "; Secure"
        return ("Set-Cookie", f"session={jeton}; Path=/; Max-Age={duree}; HttpOnly; SameSite=Lax{securise}")

    # -- pages --
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        chemin, params = url.path, urllib.parse.parse_qs(url.query)
        if chemin in ("/", "/index.html"):
            return self.fichier(os.path.join(STATIC, "index.html"))
        if chemin.startswith("/static/"):
            rel = chemin[len("/static/"):]
            if not re.fullmatch(r"(icones/)?[A-Za-z0-9_.-]+", rel) or ".." in rel:   # seulement static/ et static/icones/
                return self.envoyer(404, {"erreur": "introuvable"})
            return self.fichier(os.path.join(STATIC, *rel.split("/")), cache=False)
        if chemin.startswith("/img/"):   # décors du site (bannières et fonds)
            nom = os.path.basename(chemin)
            if re.fullmatch(r"(banniere|fond|boss)_[a-z0-9_]+\.(jpg|png)", nom) and "zed" not in nom:
                return self.fichier(os.path.join(IMAGES, nom), cache=True)
            return self.envoyer(404, {"erreur": "image inconnue"})
        if chemin.startswith("/cartes/"):
            cid = os.path.basename(chemin)
            if cid in data.CARTES and image_carte(cid):
                return self.fichier(image_carte(cid), cache=True)
            return self.envoyer(404, {"erreur": "carte inconnue"})

        if chemin.startswith("/coach/"):   # la carte d'un pro (coach) tirée dans un pack Worlds ou LEC
            pseudo = urllib.parse.unquote(os.path.basename(chemin))
            if pseudo in data.COACHS:
                return self.fichier(os.path.join(BOT, "pros", "cartes", pseudo + ".png"), cache=True)
            return self.envoyer(404, {"erreur": "coach inconnu"})

        if chemin == "/connexion":   # on part chez Discord pour se connecter
            if not CLIENT_ID:
                return self.envoyer(500, "Il manque DISCORD_CLIENT_ID dans le fichier .env".encode(), "text/plain; charset=utf-8")
            etat = secrets.token_urlsafe(24)
            ETATS[etat] = time.time()
            for e, t in list(ETATS.items()):
                if t < time.time() - 600:
                    ETATS.pop(e, None)
            q = urllib.parse.urlencode({"client_id": CLIENT_ID, "response_type": "code", "scope": "identify",
                                        "redirect_uri": self.adresse() + "/retour", "state": etat, "prompt": "none"})
            return self.rediriger("https://discord.com/oauth2/authorize?" + q)

        if chemin == "/retour":      # Discord nous renvoie ici avec un code
            etat, code = params.get("state", [""])[0], params.get("code", [""])[0]
            if not code or ETATS.pop(etat, 0) < time.time() - 600:
                return self.rediriger("/?erreur=connexion")
            try:
                reponse = appel_discord("https://discord.com/api/oauth2/token", {
                    "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "authorization_code",
                    "code": code, "redirect_uri": self.adresse() + "/retour"})
                moi = appel_discord("https://discord.com/api/users/@me", jeton=reponse["access_token"])
            except Exception as erreur:
                print("   connexion refusée :", erreur)
                return self.rediriger("/?erreur=discord")
            jeton = secrets.token_urlsafe(32)
            SESSIONS[jeton] = {"user": int(moi["id"]), "fin": time.time() + DUREE_SESSION, "avatar": moi.get("avatar"), "nom": moi.get("global_name") or moi.get("username")}
            return self.rediriger("/#collection", [self.biscuit(jeton, DUREE_SESSION)])

        if chemin == "/deconnexion":
            jeton, _ = self.session()
            SESSIONS.pop(jeton, None)
            return self.rediriger("/", [self.biscuit("", 0)])

        if chemin == "/api/tirages":
            return self.envoyer(200, fil_tirages())
        if chemin == "/api/chat":
            _, s = self.session()
            if not s:
                return self.envoyer(401, {"erreur": "Connecte-toi pour lire le chat."})
            try:
                apres = int(params.get("apres", ["0"])[0])
            except ValueError:
                apres = 0
            return self.envoyer(200, {"messages": lire_chat(apres), "moi": str(s["user"]), "mp_non_lus": mp_non_lus(s["user"])})
        if chemin == "/api/mp" or chemin.startswith("/api/mp/"):
            _, s = self.session()
            if not s:
                return self.envoyer(401, {"erreur": "Connecte-toi pour lire tes messages."})
            if chemin == "/api/mp":
                return self.envoyer(200, {"conversations": conversations(s["user"]), "discord": bool(JETON_BOT)})
            try:
                autre, apres = int(os.path.basename(chemin)), int(params.get("apres", ["0"])[0])
            except ValueError:
                return self.envoyer(404, {"erreur": "introuvable"})
            return self.envoyer(200, fil_mp(s["user"], autre, apres))
        if chemin == "/api/public":
            return self.envoyer(200, accueil_public())
        if chemin == "/api/cartes":
            return self.envoyer(200, toutes_les_cartes())
        if chemin == "/api/classement":
            return self.envoyer(200, classement())
        if chemin.startswith("/api/joueur/"):
            ident = chemin.rsplit("/", 1)[-1]
            fiche = profil(int(ident)) if ident.isdigit() else None
            return self.envoyer(200, fiche) if fiche else self.envoyer(404, {"erreur": "joueur introuvable"})

        if chemin == "/api/tour":
            _, s = self.session()
            if not s:
                return self.envoyer(401, {"erreur": "pas connecté"})
            t = jeu.tour_etat(SERVEUR_ID, s["user"])
            return self.envoyer(200, t) if t else self.envoyer(404, {"erreur": "Pas de compte 2Hot4Deck."})

        if chemin == "/api/jungle":
            _, s = self.session()
            if not s:
                return self.envoyer(401, {"erreur": "pas connecté"})
            t = jeu.jungle_etat(SERVEUR_ID, s["user"])
            return self.envoyer(200, t) if t else self.envoyer(404, {"erreur": "Pas de compte 2Hot4Deck."})

        if chemin == "/api/donjons":
            _, s = self.session()
            if not s:
                return self.envoyer(401, {"erreur": "pas connecté"})
            t = jeu.donjons_etat(SERVEUR_ID, s["user"])
            return self.envoyer(200, t) if t else self.envoyer(404, {"erreur": "Pas de compte 2Hot4Deck."})

        if chemin == "/api/moi":
            _, s = self.session()
            if not s:
                return self.envoyer(401, {"erreur": "pas connecté"})
            fiche = collection(s["user"])
            if fiche is None:
                return self.envoyer(404, {"erreur": "Tu n'as pas encore de compte 2Hot4Deck : appuie sur « Commencer » dans le salon d'accueil du serveur Discord."})
            fiche["avatar"] = f"https://cdn.discordapp.com/avatars/{s['user']}/{s['avatar']}.png?size=64" if s.get("avatar") else None
            return self.envoyer(200, fiche)

        self.envoyer(404, {"erreur": "introuvable"})


if __name__ == "__main__":
    if not CLIENT_ID or not CLIENT_SECRET:
        print("⚠️  Il manque DISCORD_CLIENT_ID ou DISCORD_CLIENT_SECRET dans le fichier .env (voir exemple_env.txt).")
    print(f"Site 2Hot4Deck : http://localhost:{PORT}  (Ctrl+C pour arrêter)")
    ThreadingHTTPServer(("0.0.0.0", PORT), Page).serve_forever()
