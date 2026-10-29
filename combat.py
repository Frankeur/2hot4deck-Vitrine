"""Règles : stats des cartes, tirage des packs, combat automatique."""
import copy
import random

import data


# ------------------------------- Cartes --------------------------------------
def role_joueur(cid):
    """Le rôle d'une carte de joueur : Graves joue en tank depuis le 13 octobre (les pros gardent l'ancien Graves)."""
    c = data.CARTES[cid]
    return "tank" if c.get("base", cid) in data.JOUEUR_TANK else c["role"]


def stats(cid, niveau=1, etoiles=0):
    """Renvoie (PV, attaque) d'une carte."""
    c = data.CARTES[cid]
    pv, atk, _ = data.BASE[c["rarete"]]
    mpv, matk, _, _ = data.ROLES[role_joueur(cid)]
    m = 1 + data.BONUS_NIVEAU * (niveau - 1) + data.BONUS_ETOILE * etoiles
    mpv *= data.PARTICULARITES.get(c.get("base", cid), {}).get("pv", 1.0)   # réglage propre à une carte (ex. Maokai, tank UR)
    p = 1 + data.UR_PALIERS.get(cid, 0) / 100   # UR des Worlds : plus fortes (cartes des joueurs seulement ; les pros passent par ennemi_champion)
    p *= 1 + data.AJUST_CARTES.get(cid, 0) / 100   # 13 octobre (soir) : équilibrage carte par carte (joueurs seulement)
    return int(pv * mpv * m * p), int(atk * matk * m * p)


def puissance(cid, niveau=1, etoiles=0):
    pv, atk = stats(cid, niveau, etoiles)
    return pv // 5 + atk * 2


def force_reelle(cid, carte):
    """14 octobre : la puissance d'une carte en comptant son item (+8 % par niveau d'item) et sa rune (+10 %). """
    f = puissance(cid, carte["niveau"], carte["etoiles"])
    item = carte.get("item")
    if item and item[0] in data.ITEMS:
        f *= 1 + 8 * item[1] / 100
    if carte.get("rune"):
        f *= 1 + 10 / 100
    return f


def niveau_max(cid, etoiles=0):
    """Niveau maximum d'une carte : celui de sa rareté, relevé par chaque étoile."""
    return data.BASE[data.CARTES[cid]["rarete"]][2] + data.ETOILE_NIVEAUX * etoiles


def xp_requis(niveau):
    return 30 * niveau


def gagner_xp(cid, carte, xp, recyclage=False):
    """Ajoute de l'XP à une carte (dict niveau/xp) et renvoie le nombre de niveaux gagnés."""
    gagnes = 0
    carte["xp"] += xp
    plafond = niveau_max(cid, carte.get("etoiles", 0))
    while carte["niveau"] < plafond and carte["xp"] >= xp_requis(carte["niveau"]):
        carte["xp"] -= xp_requis(carte["niveau"])
        carte["niveau"] += 1
        gagnes += 1
    if carte["niveau"] >= plafond:
        perdu, carte["xp"] = carte["xp"], 0
        collection = carte.get("_collection")   # l'XP en trop d'une carte au maximum n'est plus perdue : elle va à une autre carte
        if perdu > 0 and collection is not None and not recyclage:
            recycler_xp(collection, perdu, sauf=cid)
    return gagnes


def recycler_xp(collection, xp, sauf=None):
    """Verse de l'XP en trop sur la carte la plus haute de la collection qui n'est pas au maximum, une SSR ou mieux en priorité. Renvoie son identifiant, ou None."""
    libres = [c for c, v in collection.items() if c != sauf and c in data.CARTES and data.CARTES[c].get("ulti")
              and v["niveau"] < niveau_max(c, v.get("etoiles", 0))]
    if not libres or xp <= 0:
        return None
    # de préférence une SSR ou mieux (UR, LR), puis la plus haute (12 octobre)
    cible = max(libres, key=lambda c: (data.CARTES[c]["rarete"] in ("SSR", "UR", "LR"), collection[c]["niveau"], collection[c]["xp"]))
    gagner_xp(cible, collection[cible], xp, recyclage=True)
    collection.enregistrer(cible)
    collection.recus[cible] = collection.recus.get(cible, 0) + xp
    return cible


def leader(ids):
    """Le leader est le premier champion de l'équipe. Renvoie (carte, stat, valeur en %) ou None s'il n'a pas de bonus."""
    if ids and data.CARTES[ids[0]]["region"] in data.LEADERS:
        return (ids[0],) + data.LEADERS[data.CARTES[ids[0]]["region"]]
    return None


def texte_leader(ids):
    chef = leader(ids)
    if not chef:
        return None
    cid, stat, valeur = chef
    return f"👑 **{data.CARTES[cid]['nom']}** ({data.CARTES[cid]['region']}) : +{valeur} % {data.NOMS_STATS[stat]} pour toute l'équipe"


# ------------------------------- Packs ---------------------------------------
def cartes_debloquees(worlds, lec):
    """SR et SSR des équipes battues aux Worlds et à la LEC qui ne sont pas déjà dans les packs : {rareté: [cartes]}.
    Depuis le 13 octobre (20 h), leurs SSR tombent aussi des packs normaux (pack, pack de 10, méga tirage)."""
    cartes = {c for k in worlds if 0 <= k < len(data.WORLDS_CARTES) for c in data.WORLDS_CARTES[k]} \
        | {c for k in lec if 0 <= k < len(data.LEC_CARTES) for c in data.LEC_CARTES[k]}
    return {r: sorted(c for c in cartes if c in data.CARTES and data.CARTES[c]["rarete"] == r and c not in data.PAR_RARETE[r] and not c.endswith("LR"))
            for r in ("SR", "SSR")}


def ur_lec_multi(lec, possedees, tranches):
    """Packs multiples : à chaque tranche de 10 cartes, une petite chance d'UR de la LEC (équipes battues, jamais en double)."""
    gagnees = []
    dispo = {c for k in lec if 0 <= k < len(data.LEC_CARTES) for c in data.LEC_CARTES[k]}
    for _ in range(tranches):
        tirage = random.random() * 100
        for ur, chance in data.MULTI_UR_LEC.items():
            if ur not in dispo or ur in possedees or ur in gagnees:
                continue
            if tirage < chance:
                gagnees.append(ur)
                break
            tirage -= chance
    return gagnees


def tirer(p, gratuit=False, minimum=None, taux=None, bonus=None):
    """Tire une carte et met à jour le compteur de pitié du joueur. taux : table particulière (pack de boss).
    bonus : cartes ajoutées au tirage par rareté (packs multiples : cartes débloquées aux Worlds et à la LEC)."""
    p["pitie"] += 1
    p["packs"] += 1
    if p["packs"] % data.UR_TOUS_LES == 0:   # tous les 50 packs ouverts, toutes origines confondues : un pack UR
        p["packs_ur"] = p.get("packs_ur", 0) + 1
        p["_pack_ur"] = True
    taux = taux or (data.TAUX_GRATUIT if gratuit else data.TAUX)
    rarete = "SSR" if p["pitie"] >= data.PITIE else random.choices(list(taux), weights=list(taux.values()))[0]
    if minimum and data.RARETES.index(rarete) < data.RARETES.index(minimum):
        rarete = minimum
    if rarete == "SSR":
        p["pitie"] = 0
        cible = data.CARTES.get(p.get("cible") or "")
        if cible and cible["rarete"] == "SSR" and random.random() * 100 < data.CIBLE_CHANCE:   # 13 octobre : un SSR des pros ou de la LEC peut aussi être visé
            p["cible_jour"] = ""   # cible obtenue : le joueur peut en choisir une autre tout de suite
            return p["cible"]      # le SSR que le joueur a choisi de viser
    carte = random.choice(data.PAR_RARETE[rarete] + list((bonus or {}).get(rarete, ())))
    if carte == p.get("cible"):
        p["cible_jour"] = ""       # obtenue par le hasard normal : même chose
    return carte


def tirer_pro(p, equipes, possedees=()):
    """Ouvre un pack pro. equipes : numéros des équipes déjà éliminées par le joueur (data.TOUR_PROS). Seules leurs cartes peuvent sortir.
    possedees : cartes du joueur. 14 octobre : comme en LEC, une UR (ou une LR) déjà possédée ne retombe pas tant qu'il en reste à avoir.
    Renvoie ("carte", identifiant) ou ("coach", pseudo du pro). Ne compte pas dans les packs ouverts (pas de pack UR à la clé)."""
    equipes = [k for k in equipes if 0 <= k < len(data.TOUR_PROS)]
    cartes = sorted({c for k in equipes for c in data.WORLDS_CARTES[k]})
    par_rarete = {r: [c for c in cartes if data.CARTES[c]["rarete"] == r] for r in ("SR", "SSR", "UR")}
    faker = len(data.TOUR_PROS) - 1 in equipes
    p["pitie_pro"] = p.get("pitie_pro", 0) + 1
    taux = dict(data.TAUX_PRO)
    if faker and data.WORLDS_LRS:
        taux["LR"] = data.WORLDS_LR
        taux["SR"] -= data.WORLDS_LR
    rarete = random.choices(list(taux), weights=list(taux.values()))[0]
    p["pitie_pro_ur"] = p.get("pitie_pro_ur", 0) + 1
    if rarete in ("SR", "SSR") and p["pitie_pro_ur"] >= data.PITIE_PRO_UR and par_rarete["UR"]:
        rarete = "UR"   # garantie : le compteur attend, s'il le faut, qu'une équipe éliminée possède une UR
        p["_garantie"] = True
    if rarete == "SR" and data.PITIE_PRO and p["pitie_pro"] >= data.PITIE_PRO:   # garanti SSR retiré le 12 octobre (PITIE_PRO = 0)
        rarete = "SSR"
    if rarete != "SR":
        p["pitie_pro"] = 0
    if rarete == "UR" and par_rarete["UR"]:
        p["pitie_pro_ur"] = 0
    if rarete == "LR":
        return "carte", random.choice([c for c in data.WORLDS_LRS if c not in possedees] or data.WORLDS_LRS)
    if rarete == "coach":
        pros = [(nom, data.WORLDS_COACH_POIDS[c["equipe"]]) for nom, c in data.COACHS.items() if c["equipe"] in equipes and c["equipe"] < len(data.WORLDS_COACH_POIDS)]
        if faker and pros and random.random() * 100 < data.WORLDS_COACH_FAKER:
            return "coach", next(nom for nom, c in data.COACHS.items() if c["equipe"] == len(data.TOUR_PROS) - 1)
        if pros:
            return "coach", random.choices([n for n, _ in pros], weights=[w for _, w in pros])[0]
        rarete = "SSR"
    for essai in (rarete, "SSR", "SR", "UR"):   # une rareté absente des équipes éliminées (pas d'UR chez KC) : on retombe sur la suivante
        if par_rarete.get(essai):
            if essai == "UR":
                return "carte", random.choice([c for c in par_rarete["UR"] if c not in possedees] or par_rarete["UR"])
            return "carte", random.choice(par_rarete[essai])
    return "carte", random.choice(cartes)


def tirer_lec(p, equipes, possedees=()):
    """Ouvre un pack LEC. equipes : numéros des équipes LEC déjà battues (data.LEC_PALIERS) ; possedees : cartes du joueur (une UR déjà
    possédée ne retombe pas). Renvoie ("carte", identifiant) ou ("coach", pseudo du pro)."""
    equipes = [k for k in equipes if 0 <= k < len(data.LEC_PALIERS)]
    cartes = sorted({c for k in equipes for c in data.LEC_CARTES[k]})
    par_rarete = {r: [c for c in cartes if data.CARTES[c]["rarete"] == r] for r in ("SR", "SSR")}
    p["pitie_lec"] = p.get("pitie_lec", 0) + 1
    tirage = random.random() * 100
    for ur in sorted(c for c in cartes if c in data.LEC_UR and c not in possedees):   # chaque UR a sa propre chance
        if tirage < data.LEC_UR[ur]:
            p["pitie_lec"] = 0
            return "carte", ur
        tirage -= data.LEC_UR[ur]
    tirage = random.random() * 100
    if tirage < data.LEC_TAUX["coach"]:
        pros = [(nom, data.LEC_COACH_POIDS[c["lec"]]) for nom, c in data.COACHS.items() if c.get("lec") in equipes]
        if pros:
            p["pitie_lec"] = 0
            return "coach", random.choices([n for n, _ in pros], weights=[w for _, w in pros])[0]
    rarete = "SR" if tirage >= 100 - data.LEC_TAUX["SR"] else "SSR"   # le reste (UR absentes ou déjà possédées comprises) va aux SSR
    if rarete == "SR" and p["pitie_lec"] >= data.LEC_PITIE:
        rarete = "SSR"
    if rarete != "SR":
        p["pitie_lec"] = 0
    for essai in (rarete, "SSR", "SR"):
        if par_rarete.get(essai):
            return "carte", random.choice(par_rarete[essai])
    return "carte", random.choice(cartes)


def tirer_pro_bonus(equipes):
    """Une carte bonus d'un pack pro : SR ou SSR des équipes éliminées (taux du pack pro, sans UR, LR ni coach)."""
    equipes = [k for k in equipes if 0 <= k < len(data.TOUR_PROS)]
    cartes = sorted({c for k in equipes for c in data.WORLDS_CARTES[k]})
    par_rarete = {r: [c for c in cartes if data.CARTES[c]["rarete"] == r] for r in ("SR", "SSR")}
    rarete = random.choices(["SR", "SSR"], weights=[data.TAUX_PRO["SR"], data.TAUX_PRO["SSR"]])[0]
    for essai in (rarete, "SSR" if rarete == "SR" else "SR"):
        if par_rarete[essai]:
            return random.choice(par_rarete[essai])
    return random.choice(cartes) if cartes else None


def tirer_ur(p, possedees=(), worlds=()):
    """Ouvre un pack UR : un UR très rare (garanti au bout d'un certain nombre de packs UR), sinon un SSR ou un SR.
    Une UR déjà possédée ne retombe pas (12 octobre), sauf si le joueur les a toutes. 13 octobre : data.UR_WORLDS_CHANCE % de tomber sur
    une UR des Worlds des équipes battues par le joueur (worlds) ; le garanti ne donne que les UR de data.UR_PACK."""
    p["pitie_ur"] = p.get("pitie_ur", 0) + 1
    extra = sorted({c for k in worlds if 0 <= k < len(data.WORLDS_CARTES) for c in data.WORLDS_CARTES[k]
                    if data.CARTES[c]["rarete"] == "UR" and not c.endswith("LR") and c not in data.UR_PACK and c not in possedees})
    if extra and random.random() * 100 < data.UR_WORLDS_CHANCE:
        p["pitie_ur"] = 0   # 14 octobre : toute UR sortie d'un pack UR remet la garantie à zéro, UR des Worlds comprises
        return random.choice(extra)
    taux = data.UR_TAUX
    p["_garantie"] = p["pitie_ur"] >= data.UR_PITIE
    rarete = "UR" if p["_garantie"] else random.choices(list(taux), weights=list(taux.values()))[0]
    if rarete == "UR":
        p["pitie_ur"] = 0
        nouvelles = [c for c in data.UR_PACK if c not in possedees]
        return random.choice(nouvelles or data.UR_PACK)
    return random.choice(data.PAR_RARETE[rarete])


# ------------------------------- Combat --------------------------------------
PAR_NOM = {c["nom"]: k for k, c in data.CARTES.items()}   # pour retrouver l'illustration d'une unité

SEUIL = 1000   # une unité joue quand sa jauge d'action atteint ce seuil ; elle se remplit selon la vitesse
LR = data.KITS_LR
UK = data.KITS_UR
EV = data.KITS_EVEIL   # chiffres des éveils des UR   # chiffres des trois UR à kit propre  # chiffres des kits propres aux cartes LR
K = data.KITS  # chiffres des passifs et des actifs
R = data.RUNE  # chiffres des runes


def unite(nom, pv, atk, role, camp, ulti=None, effet=None, cout=0, type_degats=None, res=None, vitesse=None):
    cid = PAR_NOM.get(nom)
    carte = data.CARTES.get(cid, {})
    v = vitesse or carte.get("vitesse") or data.ROLES.get(role, (0, 0, 90, 0))[2]
    r = tuple(res or carte.get("res") or data.RESISTANCES.get(role, (20, 20)))
    return {"nom": nom, "pv": pv, "pvmax": pv, "atk": atk, "atk_base": atk, "role": role, "camp": camp, "ulti": ulti,
            "effet": effet, "cout": cout, "jauge": 0, "stun": False, "cid": cid, "action": 0,
            "vitesse": v, "vitesse_base": v, "type": type_degats or carte.get("type", "physique"), "res": r, "res_base": r,
            "bonus": {},        # bonus de leader qui ne sont pas des stats : resistance, ulti, vol, soin
            "kit": carte.get("base", cid) if (ulti and carte.get("base", cid) in data.TEXTES_KITS) else None,   # passif et actif personnalisés du champion
            "bouclier": 0, "blocages": 0, "effets": [], "cumuls": 0, "coups": 0, "marque": 0, "actions": 0, "inflige": 0,
            "objet": {},        # effets de l'item équipé : {effet: valeur}
            "trait": None,      # particularité d'un boss de la tour
            "saigne": [], "derniere": None, "suite": 0, "hemorragie": False,   # saignements subis, dernière cible, attaques d'affilée
            "rune": None, "r_cumuls": 0, "r_attente": 0, "r_kills": 0, "r_coups": 0,   # rune équipée et ses compteurs
            "ligne": data.LIGNES.get(role, "avant"),   # sbires, monstres et boss sont devant
            "lr": bool(cid and cid.endswith("LR")), "urk": cid in ("ViegoUR", "SylasUR", "GragasUR"), "eveil": cid in data.EVEILS, "puissance": 1.0, "possede": None,
            "une_fois": [], "intouchable": 0, "provoque": None, "aveugle": False, "tibbers": 0, "brulure": 0, "touche": False}


def bonus_ligne(u, ligne=None):
    """Place l'unité sur une ligne. Si c'est celle de son rôle, elle reçoit son petit bonus (à appeler avant passifs_permanents)."""
    u["ligne"] = ligne if ligne in ("avant", "arriere") else data.LIGNES.get(u["role"], "avant")
    if data.LIGNES.get(u["role"]) != u["ligne"]:
        return u
    b = data.BONUS_LIGNE / 100
    if u["role"] == "tank":
        u["pv"] = u["pvmax"] = int(u["pvmax"] * (1 + b))
        u["res_base"] = (u["res_base"][0] + data.BONUS_LIGNE, u["res_base"][1] + data.BONUS_LIGNE)
    elif u["role"] in ("combattant", "tireur"):
        u["atk_base"] = int(round(u["atk_base"] * (1 + b)))
    elif u["role"] == "assassin":
        u["vitesse_base"] = round(u["vitesse_base"] * (1 + b))
    elif u["role"] == "mage":
        u["bonus"]["ulti"] = u["bonus"].get("ulti", 0) + b
    elif u["role"] == "support":
        u["bonus"]["soin"] = u["bonus"].get("soin", 0) + data.BONUS_LIGNE_SOIN / 100
    return u


def maj(u):
    """Recalcule vitesse, résistances et attaque d'une unité à partir de ses effets en cours et de ses cumuls."""
    somme = lambda stat: sum(e["valeur"] for e in u["effets"] if e["stat"] == stat)
    vit = 1 + somme("vitesse") / 100 + (K["jinx_vitesse"] * u["cumuls"] / 100 if u["kit"] == "Jinx" else 0) \
        + (K["zeri_vitesse"] * u["cumuls"] / 100 if u["kit"] == "Zeri" else 0)
    if u.get("rune") == "tempo":
        vit += R["tempo_vitesse"] * u["r_cumuls"] / 100
    u["vitesse"] = max(20, round(u["vitesse_base"] * vit))
    plus = somme("res") + (K["darius_res"] * u["cumuls"] if u["kit"] == "Darius" else 0)
    u["res"] = (u["res_base"][0] + plus, u["res_base"][1] + plus)
    cumul = (K["veigar_atk"] if u["kit"] == "Veigar" else K["cumul_atk"]) * u["cumuls"] / 100 if u["kit"] in ("Senna", "Veigar", "Nasus", "Jax") else 0
    if u["trait"] == "feu":
        cumul = data.TRAITS_BOSS["feu_atk"] * u["cumuls"] / 100
    if u.get("rune") == "conquerant":
        cumul += R["conquerant_atk"] * u["r_cumuls"] / 100
    u["atk"] = int(u["atk_base"] * (1 + cumul + somme("atk") / 100))


def ajouter_effet(u, cle, stat, valeur, duree):
    """Effet temporaire (durée en actions de celui qui le porte). Le même effet ne se cumule pas : il est renouvelé."""
    u["effets"] = [e for e in u["effets"] if e["cle"] != cle] + [{"cle": cle, "stat": stat, "valeur": valeur, "duree": duree}]
    maj(u)


def cumuler(u):
    u["cumuls"] = min(K["cumuls_max"], u["cumuls"] + 1)
    maj(u)


def equipe_joueur(ids, possedees, camp=0, sans_leader=False, coach_plein=False):
    """coach_plein : le coach du joueur donne tout son bonus (Worlds, raid) ; sinon seulement data.WORLDS_COACH_AILLEURS."""
    chef = None if sans_leader else leader(ids)
    stat, valeur = (chef[1], chef[2] / 100) if chef else (None, 0)
    unites = []
    for cid in ids:
        c = data.CARTES[cid]
        pv, atk = stats(cid, possedees[cid]["niveau"], possedees[cid]["etoiles"])
        if stat == "pv":
            pv = int(pv * (1 + valeur))
        if stat == "atk":
            atk = int(atk * (1 + valeur))
        u = unite(c["nom"], pv, atk, role_joueur(cid), camp, c["ulti"], c["effet"], c["cout"])
        u["joueur"] = True   # carte d'un joueur : nouveaux kits du 13 octobre (les pros gardent les anciens)
        if stat == "vitesse":
            u["vitesse_base"] = round(u["vitesse_base"] * (1 + valeur))
        elif stat in ("resistance", "ulti", "vol", "soin", "charge", "achever"):
            u["bonus"][stat] = valeur
        equiper(u, possedees[cid].get("item"))
        u["rune"] = possedees[cid].get("rune") if possedees[cid].get("rune") in data.RUNES else None
        bonus_ligne(u, possedees[cid].get("ligne"))
        buff = possedees[cid].get("buff")   # buff de serveur gagné sur un boss de salon : (statistique, valeur)
        if buff:
            stat_b, val_b = buff
            if stat_b == "atk":
                u["atk_base"] = int(round(u["atk_base"] * (1 + val_b / 100)))
            elif stat_b == "res":
                u["res_base"] = (u["res_base"][0] + val_b, u["res_base"][1] + val_b)
            elif stat_b == "vitesse":
                u["vitesse_base"] = round(u["vitesse_base"] * (1 + val_b / 100))
            elif stat_b == "pv":
                u["pv"] = u["pvmax"] = int(u["pvmax"] * (1 + val_b / 100))
        unites.append(u)
    coach = data.COACHS.get(getattr(possedees, "coach", "") or "")   # la carte de pro équipée par le joueur
    if coach:
        appliquer_coach(unites, coach["stat"], coach["valeur"] * data.part_coach(getattr(possedees, "coach", ""), coach_plein), exact=True)
    return passifs_permanents(unites)


def passifs_permanents(unites):
    """Applique à une équipe les passifs qui valent pour tout le combat (auras, bonus de stats, boucliers de départ)."""
    kits = [u["kit"] for u in unites]
    for u in unites:
        zil = [z for z in unites if z["kit"] == "Zilean"]
        if zil:   # 14 octobre : le nerf de Zilean ne touche que les cartes des joueurs (les adversaires gardent +10 %)
            u["vitesse_base"] = round(u["vitesse_base"] * (1 + (K["zilean_vitesse"] if zil[0].get("joueur") else 10) / 100))
        if "Sona" in kits:
            u["atk_base"] = int(u["atk_base"] * (1 + K["sona_atk"] / 100))
        if u["kit"] == "Sejuani" and not u.get("joueur"):   # 13 octobre : la Sejuani des joueurs n'a plus ce bonus
            u["pv"] = u["pvmax"] = int(u["pvmax"] * (1 + K["sejuani_pv"] / 100))
            u["res_base"] = (u["res_base"][0] + K["sejuani_res"], u["res_base"][1] + K["sejuani_res"])
        if u["kit"] == "Malphite":
            u["res_base"] = (u["res_base"][0] + K["malphite_res"], u["res_base"][1])
        if u["kit"] == "MasterYi":
            u["effets"].append({"cle": "yi", "stat": "vitesse", "valeur": K["yi_vitesse"], "duree": K["yi_actions"]})
        if u["kit"] == "Yasuo":
            u["bouclier"] = int(u["pvmax"] * (K["yasuo_bouclier"] if u.get("joueur") else 10) / 100)
        if "Ornn" in kits:
            u["pv"] = u["pvmax"] = int(u["pvmax"] * (1 + K["ornn_pv"] / 100))
        if "Renata" in kits:
            u["atk_base"] = int(u["atk_base"] * (1 + K["renata_atk"] / 100))
        if u["kit"] == "Graves":
            u["res_base"] = (u["res_base"][0] + K["graves_tank_res" if u.get("joueur") else "graves_res"], u["res_base"][1])
        if u.get("eveil"):   # éveil des UR : ce qu'elles ont au début du combat
            if u["kit"] == "Xayah":
                u["plumes"] = EV["xayah_plumes"]
            elif u["kit"] in ("Zeri", "Jax"):
                u["cumuls"] = EV["zeri_cumuls" if u["kit"] == "Zeri" else "jax_cumuls"]
        if u["kit"] == "Corki":
            u["objet"] = dict(u["objet"], pen=max(u["objet"].get("pen", 0), K["corki_pen"]))
        maj(u)
    return unites


def texte_item(item, niveau):
    nom, emoji, _, valeurs, texte = data.ITEMS[item]
    return f"{emoji} **{nom}** niv. {niveau} · {texte.format(valeurs[niveau - 1])}"


def equiper(u, objet):
    """Applique l'item équipé (identifiant, niveau) à une unité."""
    if not objet or objet[0] not in data.ITEMS:
        return
    effet, v = data.ITEMS[objet[0]][2], data.ITEMS[objet[0]][3][objet[1] - 1]
    if effet == "atk":
        u["atk_base"] = int(u["atk_base"] * (1 + v / 100))
    elif effet == "pv":
        u["pv"] = u["pvmax"] = int(u["pvmax"] * (1 + v / 100))
    elif effet == "vitesse":
        u["vitesse_base"] = round(u["vitesse_base"] * (1 + v / 100))
    elif effet == "res_phys":
        u["res_base"] = (u["res_base"][0] + v, u["res_base"][1])
    elif effet == "res_mag":
        u["res_base"] = (u["res_base"][0], u["res_base"][1] + v)
    elif effet in ("ulti", "vol"):
        u["bonus"][effet] = u["bonus"].get(effet, 0) + v / 100
    elif effet == "elan":
        u["action"] = SEUIL * v / 100 - 1
    else:
        u["objet"][effet] = v


def est_boss(etage):
    return etage % 10 == 0


def etage_de_base(etage):
    """La tour difficile (étages 101 à 200) rejoue les étages 1 à 100 en plus fort : mêmes boss, dans le même ordre."""
    return etage - 100 if etage > 100 else etage


def force(niveau):
    """Multiplicateur de puissance des ennemis d'un étage, d'après la courbe de la tour (points reliés en ligne droite)."""
    points = data.TOUR_COURBE
    if niveau <= points[0][0]:
        return points[0][1]
    for (e1, f1), (e2, f2) in zip(points, points[1:]):
        if niveau <= e2:
            return f1 + (f2 - f1) * (niveau - e1) / (e2 - e1)
    (e1, f1), (e2, f2) = points[-2], points[-1]   # au-delà du dernier point : même pente
    return f2 + (f2 - f1) / (e2 - e1) * (niveau - e2)


CHAMPIONS_ENNEMIS = [k for k, v in data.CARTES.items() if v["ulti"] and (v["en_jeu"] or k in data.TOUR_PROS_HORS_PACKS) and v["rarete"] != "UR"]


def champions_ennemis(niveau, hasard):
    """Une équipe de champions adverses de la force d'un étage : ils ont leurs vrais passifs et actifs."""
    echelle = force(niveau)
    nombre = 1 if niveau <= 2 else 2 if niveau <= 5 else 3
    unites = []
    for cid in hasard.sample(CHAMPIONS_ENNEMIS, nombre):
        carte = data.CARTES[cid]
        mpv, matk, _, _ = data.ROLES[carte["role"]]
        u = unite(carte["nom"], int(data.TOUR_BASE[0] * echelle * mpv), int(data.TOUR_BASE[1] * echelle * matk), carte["role"], 1,
                  carte["ulti"], carte["effet"], carte["cout"])
        u["nom"] = f"{carte['nom']} adverse"   # pour ne pas le confondre avec le tien dans le récit du combat
        bonus_ligne(u)   # les adversaires se placent tout seuls sur la ligne de leur rôle
        unites.append(u)
    return passifs_permanents(unites)


def ennemi_champion(cid, echelle, pv=1.0, atk=1.0, nom=None, role=None):
    """Un champion adverse précis (avec son vrai passif et son actif), de la force voulue. Sert aux donjons à gardiens fixes."""
    carte = data.CARTES[cid]
    role = role or carte["role"]
    mpv, matk, _, _ = data.ROLES[role]
    u = unite(carte["nom"], int(data.TOUR_BASE[0] * echelle * mpv * pv), int(data.TOUR_BASE[1] * echelle * matk * atk), role, 1,
              carte["ulti"], carte["effet"], carte["cout"])
    u["nom"] = nom or f"{carte['nom']} adverse"
    bonus_ligne(u)
    return u


def equipe_pro(champions, etage, bonus=1.0, nouveaux_kits=False):
    """Les trois champions d'un pro des Worlds, de la force d'un étage de la tour. bonus : multiplicateur propre à ce pro.
    Une carte UR est plus forte que les autres (data.TOUR_PROS_UR). nouveaux_kits : le pro joue les kits des joueurs (Graves tank, Corki, Renata…)."""
    unites = []
    bonus, frappe = bonus if isinstance(bonus, (tuple, list)) else (bonus, 1.0)   # (force, attaque en plus) : un pro peut frapper plus fort sans être plus solide
    for cid in champions:
        plus = data.TOUR_PROS_UR if data.CARTES[cid]["rarete"] == "UR" else 1.0
        u = ennemi_champion(cid, force(etage) * bonus, plus, plus * frappe, nom=data.CARTES[cid]["nom"] if plus > 1 else None,
                            role=role_joueur(cid) if nouveaux_kits else None)
        if nouveaux_kits:
            u["joueur"] = True
        unites.append(u)
    return passifs_permanents(unites)


def appliquer_coach(unites, stat, valeur, exact=False):
    """Le bonus d'un coach sur toute une équipe. stat : "pv", "atk", "vitesse", "ulti" ou "soin" ; valeur : 0.10 pour +10 %."""
    for u in unites:
        if stat == "pv":
            u["pvmax"] = int(u["pvmax"] * (1 + valeur))
            u["pv"] = u["pvmax"]
        elif stat == "atk":
            u["atk_base"] = int(round(u["atk_base"] * (1 + valeur)))
        elif stat == "vitesse":
            u["vitesse_base"] = round(u["vitesse_base"] * (1 + valeur))
        elif stat == "ulti":
            u["bonus"]["ulti"] = u["bonus"].get("ulti", 0) + valeur * (1 if exact else data.WORLDS_COACH_ULTI)
        elif stat == "soin":
            u["bonus"]["soin"] = u["bonus"].get("soin", 0) + valeur
        maj(u)
    return unites


def equipe_melee(choix):
    """Une équipe faite d'un champion par joueur (tour des pros). choix : [(identifiant, cartes du joueur)]. Pas de bonus de leader."""
    return passifs_permanents([equipe_joueur([cid], possedees, sans_leader=True, coach_plein=True)[0] for cid, possedees in choix])


def salle_donjon(numero, salle, etage):
    """Les gardiens d'une descente de donjon. salle : "garde" (vague), "darius" (le gardien) ou "boss". Force calée sur l'étage du joueur."""
    r, d = data.NOXUS, data.DESCENTES[numero]
    echelle = force(max(1, min(etage, 100))) * r["force"]   # les donjons ne suivent pas la tour difficile
    nom, gpv, gatk = d["garde"]
    def gardes(nombre, mult=1.0):
        return [unite(f"{nom} {k + 1}", int(data.TOUR_BASE[0] * echelle * mult * gpv), int(data.TOUR_BASE[1] * echelle * mult * gatk),
                      "combattant", 1) for k in range(nombre)]
    if salle == "garde":
        unites = gardes(*r["vague"])
    elif salle == "darius":
        g = d["gardien"]
        unites = [ennemi_champion(g[0], echelle, pv=g[2], atk=g[3], nom=g[1])]
    else:
        g = d["boss"]
        unites = [ennemi_champion(g[0], echelle, pv=g[2], atk=g[3], nom=g[1])] + gardes(2)
    return passifs_permanents(unites)


def gardiens_donjon(numero, etage):
    """Le combat unique d'un donjon : son gardien et son boss ensemble, de la force de l'étage du joueur (adoucie par DONJON_ENSEMBLE)."""
    d, m = data.DESCENTES[numero], data.DONJON_ENSEMBLE
    echelle = force(max(1, min(etage, 100))) * data.NOXUS["force"]
    return passifs_permanents([ennemi_champion(g[0], echelle, pv=g[2] * m, atk=g[3] * m, nom=g[1]) for g in (d["gardien"], d["boss"])])


def salle_noxus(salle, etage):
    return salle_donjon(0, salle, etage)


def ryze(difficulte, groupe):
    """Ryze, boss de raid. Sa force dépend pour moitié de la difficulté (niveau de référence) et pour moitié du groupe qui l'affronte."""
    reglages = data.RAID_RYZE
    niveau = data.RAID_NIVEAU[difficulte]
    m = 1 + data.BONUS_NIVEAU * (niveau - 1)
    pv_ref, atk_ref = data.BASE["SSR"][0] * 1.15 * m, data.BASE["SSR"][1] * m   # un combattant SSR au niveau de référence
    pv_moyen = (pv_ref + sum(u["pvmax"] for u in groupe) / len(groupe)) / 2
    dur = data.RAID_DIFFICULTE[difficulte]   # chaque difficulté a ses propres multiplicateurs
    pv = int(pv_moyen * len(groupe) * reglages["pv"] * dur["pv"])
    atk = int(pv_moyen * reglages["atk"] * dur["atk"])
    vitesse = int(reglages["vitesse"] * (len(groupe) / 9) ** 0.72)   # plus le groupe est grand, plus il agit souvent : le combat reste aussi dur à 5 qu'à 3
    boss = unite("Ryze", pv, atk, "boss", 1, "Surcharge", "zone", 3, "magique", res=(60, 60), vitesse=vitesse)
    boss["trait"] = "ryze"
    boss["kit"] = None   # le boss garde sa Surcharge de raid, pas le kit du champion Ryze des Worlds
    boss["flux"] = dur["flux"]
    boss["rage"] = dur["rage"]
    boss["nom"] = f"Ryze, Mage runique ({data.RAID_NOMS[difficulte]})"
    maj(boss)
    return [boss]


def ennemis(etage):
    """Les adversaires d'un étage de la tour. Un étage donné a toujours la même équipe : on peut s'y préparer."""
    if not est_boss(etage):
        return champions_ennemis(etage, random.Random(etage * 7919))
    nom, trait, mpv, matk, _ = data.BOSS[min(etage_de_base(etage), max(data.BOSS))]
    if etage > 100:
        mpv, matk = max(mpv, data.TOUR_DIFFICILE_BOSS[0]), max(matk, data.TOUR_DIFFICILE_BOSS[1])   # même les premiers boss y sont de vrais boss
    pv, atk, T = int(data.TOUR_BASE[0] * force(etage) * mpv), int(data.TOUR_BASE[1] * force(etage) * matk), data.TRAITS_BOSS
    if trait == "larves":   # le boss d'échauffement : trois petites larves, sans rien de spécial
        larves = [unite(nom, pv, atk, "sbire", 1) for _ in range(3)]
        for k, larve in enumerate(larves, 1):
            larve["nom"] = f"Larve du Néant {k}"
        return larves
    if trait == "charge":
        boss = unite(nom, pv, atk, "boss", 1, "Charge du Héraut", "degats", 3, "physique")
    else:
        boss = unite(nom, pv, atk, "boss", 1, "Souffle dévastateur", "zone", 3, "magique")
    boss["trait"] = trait
    if trait == "vent":
        boss["vitesse_base"] = T["vent_vitesse"]
    if trait == "terre":
        boss["res_base"] = T["terre_res"]
    maj(boss)
    return [boss]


def texte_boss(etage):
    """Le trait du boss d'un étage, pour l'aperçu avant le combat."""
    return data.BOSS[min(etage_de_base(etage), max(data.BOSS))][4]


def gardiens(etage):
    """Les gardiens d'un donjon : des champions tirés au hasard, un peu en dessous de ton étage."""
    return champions_ennemis(max(1, etage - data.DONJON_RETARD), random)


def xp_compte_requis(niveau):
    base, hausse, palier, douce = data.XP_COMPTE_NIVEAU   # hausse forte jusqu'au palier, plus douce ensuite
    if niveau <= 50:
        return int(round(base * hausse ** (min(niveau, palier) - 1) * douce ** max(0, niveau - palier)))
    xp = base * hausse ** (palier - 1) * douce ** (50 - palier)   # au-delà de 50 : chaque niveau coûte de plus en plus (12 octobre)
    for n in range(50, niveau):
        xp *= next(h for debut, h in reversed(data.XP_COMPTE_APRES_50) if n >= debut)
    return int(round(xp))


def cout_recette(item, niveau_vise):
    """Composants nécessaires pour fabriquer cet item à ce niveau : {composant: quantité}."""
    return {comp: data.RECETTE_QUANTITES[niveau_vise - 1] for comp in data.RECETTES[item]}


def niveau_jungle(etage, difficulte):
    """Force des monstres de la jungle : calée sur l'étage du joueur, avec un retard selon la difficulté."""
    return max(1, etage - data.JUNGLE[difficulte][2])


def monstres(niveau):
    """Monstres de la jungle, de la force d'un étage normal de la tour."""
    echelle = force(niveau)
    nombre = 1 if niveau <= 2 else 2 if niveau <= 5 else 3
    noms = random.sample(data.JUNGLE_MONSTRES, nombre)
    return [unite(nom, int(data.TOUR_BASE[0] * echelle), int(data.TOUR_BASE[1] * echelle), "sbire", 1) for nom in noms]


def camp_jungle(niveau, rang):
    """Un camp du clear de jungle. rang : 0 pour le premier camp… Chaque camp est plus fort que le précédent,
    et le dernier est un seul gros monstre (celui du Châtiment)."""
    echelle = force(niveau) * (1 + data.CLEAR_FORCE * rang)
    nombre = 1 if niveau <= 2 else 2 if niveau <= 5 else 3
    nom = data.JUNGLE_MONSTRES[rang % len(data.JUNGLE_MONSTRES)]
    pv, atk = int(data.TOUR_BASE[0] * echelle), int(data.TOUR_BASE[1] * echelle)
    if rang == len(data.JUNGLE_MONSTRES) - 1:
        return [unite(nom, int(pv * nombre * 1.3), int(atk * (1 + 0.35 * (nombre - 1))), "sbire", 1)]
    return [unite(nom if nombre == 1 else f"{nom} {k + 1}", pv, atk, "sbire", 1) for k in range(nombre)]


def vivants(tous, camp):
    return [x for x in tous if x["camp"] == camp and x["pv"] > 0]


def soin(a, montant):
    if a.get("hemorragie"):   # règle « Hémorragie » des donjons et du raid
        montant *= data.HEMORRAGIE / 100
    if a["pv"] > 0:
        a["pv"] = min(a["pvmax"], a["pv"] + int(montant))


def tuer(cible, journal, tous):
    """Une unité tombe à 0 PV : certains passifs se déclenchent à ce moment-là."""
    if cible["kit"] == "Aatrox" and cible.get("eveil") and "aatrox" not in cible["une_fois"] and cible["jauge"] >= cible["cout"]:
        cible["une_fois"].append("aatrox")
        cible["pv"] = 1
        journal.append(f"🩸 **{cible['nom']}** refuse de tomber : son actif est prêt.")
        return
    if cible["kit"] == "Sion" and "sion" not in cible["une_fois"]:
        cible["une_fois"].append("sion")
        cible["pv"] = max(1, int(cible["pvmax"] * K["sion_pv"] / 100))
        journal.append(f"💀 **{cible['nom']}** se relève, implacable !")
        return
    if cible["kit"] == "Tryndamere" and "rage" not in cible["une_fois"]:
        cible["une_fois"].append("rage")
        cible["pv"] = max(1, int(cible["pvmax"] * K["tryndamere_pv"] / 100))
        journal.append(f"😤 **{cible['nom']}** refuse de mourir et se relève !")
        return
    if cible.get("renata", 0) > 0:   # protégé par Renata : il ne peut pas tomber
        cible["pv"] = 1
        journal.append(f"🛟 Renata garde **{cible['nom']}** debout.")
        return
    if cible["objet"].get("ange") and "ange" not in cible["une_fois"]:
        cible["une_fois"].append("ange")
        cible["pv"] = max(1, int(cible["pvmax"] * cible["objet"]["ange"] / 100))
        journal.append(f"😇 L'Ange gardien relève **{cible['nom']}** !")
        return
    if cible["trait"] == "chemtech" and "zombie" not in cible["une_fois"]:
        cible["une_fois"].append("zombie")
        cible["pv"] = int(cible["pvmax"] * data.TRAITS_BOSS["chemtech_pv"] / 100)
        journal.append(f"☣️ **{cible['nom']}** se relève, porté par les vapeurs chemtech !")
        return
    cible["pv"], cible["bouclier"] = 0, 0
    journal.append(f"💀 **{cible['nom']}** est K.O.")
    if cible["kit"] == "Lux":   # en tombant, Lux étourdit l'ennemi qui tape le plus fort (UR : et le frappe)
        ennemis = [a for a in vivants(tous, 1 - cible["camp"]) if a["pv"] > 0]
        if ennemis:
            fort = max(ennemis, key=lambda a: a["atk"])
            etourdir(fort)
            journal.append(f"✨ La dernière lumière de {cible['nom']} aveugle **{fort['nom']}**.")
            if cible.get("eveil"):
                degats = int(cible["atk"] * EV["lux_mort"] / 100)
                fort["pv"] -= degats
                if fort["pv"] <= 0:
                    tuer(fort, journal, tous)
    for a in vivants(tous, 1 - cible["camp"]):
        if a["kit"] == "Thresh":   # il récolte l'âme de l'ennemi tombé
            a["bouclier"] += int(a["pvmax"] * K["thresh_ame"] / 100)
    if cible["objet"].get("redemption"):
        for a in vivants(tous, cible["camp"]):
            soin(a, a["pvmax"] * cible["objet"]["redemption"] / 100)
        journal.append(f"✝️ La Rédemption de {cible['nom']} soigne ses alliés.")
    if cible["kit"] == "Karthus" and "mort" not in cible["une_fois"]:
        cible["une_fois"].append("mort")
        total = sum(frapper(cible, c, K["karthus_mort"] / 100, journal, tous) for c in vivants(tous, 1 - cible["camp"]))
        journal.append(f"👻 {cible['nom']} frappe une dernière fois depuis l'au-delà : {total} dégâts.")


def frapper(u, cible, mult, journal, tous, ulti=False, vol=0.0):
    """Un coup. Tient compte du blocage, du bouclier, de la résistance (physique ou magique) et des passifs."""
    if cible["pv"] <= 0 or (u["pv"] <= 0 and u["kit"] != "Karthus"):
        return 0
    if cible["intouchable"]:
        journal.append(f"💨 {cible['nom']} est intouchable : le coup passe à travers.")
        return 0
    if cible["blocages"] and (u["role"] == "boss") and data.BOSS_BLOCAGE < 100:   # 14 octobre : un boss ne se bloque qu'en partie (Xin Zhao le figeait pour toujours)
        cible["blocages"] -= 1
        mult *= 1 - data.BOSS_BLOCAGE / 100
        journal.append(f"🛡️ {cible['nom']} pare une partie du coup.")
    elif cible["blocages"]:
        cible["blocages"] -= 1
        journal.append(f"🛡️ {cible['nom']} bloque l'attaque.")
        return 0
    d = u["atk"] * mult * random.uniform(0.9, 1.1)
    pen_ev = 0
    if random.random() < 0.10:
        d *= 1.5
    if ulti:
        d *= (1 + u["bonus"].get("ulti", 0)) * u.get("puissance", 1.0)   # puissance : actif volé par Sylas UR (70 %)
    if cible.get("soleil") and u["kit"] != "Leona":   # lumière du soleil de Leona : le coup d'un allié consomme la marque
        d *= 1 + K["leona_soleil"] / 100
        cible["soleil"] = 0
    if u["bonus"].get("achever") and cible["pv"] < cible["pvmax"] * data.ACHEVER_SEUIL / 100:   # leader Bilgewater : « À l'abordage »
        d *= 1 + u["bonus"]["achever"]
    if u["kit"] == "Vayne":
        u["coups"] += 1
        if u["coups"] % 3 == 0:
            d *= 1 + K["vayne_bonus"] / 100
            if u.get("eveil"):
                pen_ev = EV["vayne_pen"]
    elif u["kit"] == "Caitlyn" and not ulti:
        u["coups"] += 1
        if u["coups"] % K["caitlyn_coups"] == 0:
            d *= 1 + K["caitlyn_bonus"] / 100
    elif u["kit"] == "Shaco" and not ulti and "premier" not in u["une_fois"]:
        u["une_fois"].append("premier")
        d *= 1 + K["shaco_premier"] / 100
    elif u["kit"] == "MissFortune" and not ulti:
        if u["derniere"] is not None and u["derniere"] is not cible:   # 14 octobre : up réservé aux joueurs (adversaires : +25 %)
            d *= 1 + (K["mf_bonus"] if u.get("joueur") else 25) / 100
        u["derniere"] = cible
    elif u["kit"] == "Orianna" and not ulti:
        u["suite"] = min(K["orianna_max"], u["suite"] + 1) if u["derniere"] is cible else 0
        u["derniere"] = cible
        d *= 1 + K["orianna_cumul"] * u["suite"] / 100
    elif u["kit"] == "Gnar" and not ulti:
        u["coups"] += 1
        if u["coups"] % K["gnar_coups"] == 0:
            d *= 1 + K["gnar_bonus"] / 100
    elif u["kit"] == "Jayce" and not ulti:
        u["coups"] += 1
        if u["coups"] % 2:
            d *= 1 + K["jayce_canon"] / 100
    elif u["kit"] == "Qiyana" and not ulti and ("qiyana", id(cible)) not in u["une_fois"]:
        u["une_fois"].append(("qiyana", id(cible)))
        d *= 1 + K["qiyana_premier"] / 100
    elif u["kit"] == "Khazix" and len(vivants(tous, cible["camp"])) <= 2:
        d *= 1 + K["khazix_isole"] / 100
    elif u["kit"] == "Draven" and not ulti:
        d *= 1 + K["draven_cumul"] * u["suite"] / 100
        u["suite"] = min(K["draven_max"], u["suite"] + 1)
    elif u["kit"] in ("Fiora", "Tristana", "Aphelios") and not ulti:
        u["coups"] += 1
        if u["kit"] == "Fiora" and u["coups"] % K["fiora_coups"] == 0:
            d *= 1 + K["fiora_bonus"] / 100
        elif u["kit"] == "Tristana" and u["coups"] % (EV["tristana_coups"] if u.get("eveil") else K["tristana_coups"]) == 0:
            d *= 1 + K["tristana_bonus"] / 100
        elif u["kit"] == "Aphelios" and u["coups"] % 3 == 2:
            d *= 1 + K["aphelios_bonus"] / 100
    elif u["kit"] in ("Yone", "Jhin") and not ulti:
        u["coups"] += 1
        if u["kit"] == "Jhin" and u["coups"] % K["jhin_coups"] == 0:
            d *= 1 + K["jhin_bonus"] / 100
        elif u["kit"] == "Yone" and u["coups"] % K["yone_coups"] == 0:
            d *= 1 + K["yone_echo"] / 100
    elif u["kit"] == "Kaisa" and not ulti:
        cible["plasma"] = cible.get("plasma", 0) + 1
        if cible["plasma"] >= K["kaisa_coups"]:
            cible["plasma"] = 0
            d *= 1 + K["kaisa_bonus"] / 100
    elif u["kit"] == "Ezreal" and not ulti:
        d *= 1 + K["ezreal_cumul"] * u["suite"] / 100
        u["suite"] = min(K["ezreal_max"], u["suite"] + 1)
    elif u["kit"] in ("Ambessa", "Ziggs", "XinZhao", "Maokai") and not ulti:
        u["coups"] += 1
        if u["kit"] == "Ambessa" and u["coups"] % K["ambessa_coups"] == 0:
            d *= 1 + K["ambessa_echo"] / 100
        elif u["kit"] == "Ziggs" and u["coups"] % K["ziggs_coups"] == 0:
            d *= 1 + K["ziggs_bonus"] / 100
    elif u["kit"] == "Nidalee" and cible["pv"] < cible["pvmax"] * (EV["nidalee_seuil"] if u.get("eveil") else K["nidalee_seuil"]) / 100:
        d *= 1 + K["nidalee_bonus"] / 100
    elif u["kit"] == "Azir" and not ulti:
        d *= 1 + (LR["azir_soldat"] * min(LR["azir_max"], u["actions"] + 1) if u["lr"] else K["azir_soldat"] * min(K["azir_max"], u["actions"])) / 100
    elif u["kit"] == "Ryze" and not ulti:
        u["coups"] += 1
    elif u["kit"] == "Leblanc" and not ulti:
        if u["derniere"] is cible and not u["suite"]:
            d *= 1 + K["leblanc_bonus"] / 100
            u["suite"] = 1
        else:
            u["suite"] = 0
        u["derniere"] = cible
    elif u["kit"] == "Sylas" and not ulti and u["suite"] > 0:
        d *= 1 + (UK["sylas_bonus"] if u.get("urk") else K["sylas_bonus"]) / 100
    if u["kit"] in ("KSante", "Gwen") and not ulti:   # une part des PV max de la cible, plafonnée contre les boss
        part = cible["pvmax"] * K["ksante_pv" if u["kit"] == "KSante" else "gwen_pv"] / 100
        d += min(part, u["atk"] * K["pv_max_plafond"] / 100) if cible["role"] == "boss" else part
    rune = u.get("rune")
    if rune == "premier" and u["actions"] <= R["premier_actions"]:
        d *= 1 + R["premier_degats"] / 100
    elif rune == "tempo" and u["r_cumuls"] >= R["tempo_max"]:
        d *= 1 + R["tempo_degats"] / 100
    elif rune == "moisson" and u["r_attente"] <= 0 and cible["pv"] < cible["pvmax"] * R["moisson_seuil"] / 100:
        d *= 1 + min(R["moisson_max"], R["moisson_degats"] + R["moisson_plus"] * u["r_kills"]) / 100
        u["r_attente"] = R["moisson_attente"]
    d *= 100 / (100 + max(0, cible["res"][1 if u["type"] == "magique" else 0]) * (1 - min(100, u["objet"].get("pen", 0) + pen_ev) / 100))
    d *= 1 - cible["bonus"].get("resistance", 0)
    d = max(1, int(d))
    u["inflige"] += d
    cible["touche"] = True
    absorbe = min(cible["bouclier"], d)
    cible["bouclier"] -= absorbe
    cible["pv"] -= d - absorbe
    vol += u["bonus"].get("vol", 0) + ((EV["aatrox_passif"] if u.get("eveil") else K["aatrox_vol"]) / 100 if u["kit"] == "Aatrox" else 0) \
        + (K["darius_vol"] * u["cumuls"] / 100 if u["kit"] == "Darius" else 0) \
        + (R["conquerant_vol"] / 100 if rune == "conquerant" and u["actions"] >= R["conquerant_actions"] else 0) \
        + (K["ksante_vol"] / 100 if u["kit"] == "KSante" and "azimuts" in u["une_fois"] else 0) \
        + ((LR["ahri_vol"] if u["lr"] else K["ahri_vol"]) / 100 if u["kit"] == "Ahri" and not ulti else 0)
    if vol:
        soin(u, d * vol)
    if u["kit"] == "Ashe":
        ajouter_effet(cible, "ashe", "vitesse", -K["ashe_lent"], 2)
    if u["kit"] == "Talon" and not ulti:
        u["coups"] += 1
        if u["coups"] % K["talon_coups"] == 0 and cible["pv"] > 0:
            cible["saigne"].append([int(u["atk"] * K["talon_saigne"] / 100), 2])
    if u["kit"] == "Morgana" and ulti:
        soin(u, d * K["morgana_vol"] / 100)
    if not ulti and cible["pv"] > 0:
        if u["kit"] == "Rumble":
            cible["saigne"].append([int(u["atk"] * K["rumble_brule"] / 100), 2])
        elif u["kit"] == "Graves" and u.get("joueur") and u.get("g_cumuls", 0) < K["graves_max"]:   # Graves tank : il se blinde
            u["g_cumuls"] = u.get("g_cumuls", 0) + 1
            u["res_base"] = (u["res_base"][0] + K["graves_cumul"], u["res_base"][1] + K["graves_cumul"])
            maj(u)
        elif u["kit"] == "Corki" and u.get("joueur"):   # une attaque sur 3 : un missile sur un 2e ennemi
            u["ck"] = u.get("ck", 0) + 1
            autres = [a for a in vivants(tous, 1 - u["camp"]) if a is not cible]
            if u["ck"] % K["corki_coups"] == 0 and autres:
                frapper(u, random.choice(autres), K["corki_eclat"] / 100, journal, tous, True)
        elif u["kit"] == "Gnar" and u["coups"] % K["gnar_coups"] == 0:
            etourdir(cible)
            journal.append(f"🦖 Méga Gnar écrase {cible['nom']}." + ("" if cible["stun"] else " Il résiste à l'étourdissement."))
        elif u["kit"] == "Jayce" and u["coups"] % 2 == 0:
            ajouter_effet(cible, "jayce", "res", -K["jayce_res"], 2)
        elif u["kit"] == "Kalista":
            cible["lances"] = min(K["kalista_max"], cible.get("lances", 0) + 1)
        elif u["kit"] == "Aphelios" and u["coups"] % 3 == 0:
            ajouter_effet(cible, "aphelios", "vitesse", -K["aphelios_lent"], 2)
    if not ulti:
        if u["kit"] == "Ambessa" and u["coups"] % K["ambessa_coups"] == 0:
            u["bouclier"] += int(u["pvmax"] * K["ambessa_bouclier"] / 100)
        elif u["kit"] == "XinZhao" and u["coups"] % K["xin_coups"] == 0:
            soin(u, u["pvmax"] * K["xin_soin"] / 100)
        elif u["kit"] == "Maokai" and u["coups"] % K["maokai_coups"] == 0:
            soin(u, u["pvmax"] * K["maokai_soin"] / 100)
        elif u["kit"] == "Varus" and cible["pv"] > 0:
            cible["fletrissure"] = min(K["varus_max"], cible.get("fletrissure", 0) + (EV["varus_marques"] if u.get("eveil") else 1))
        if u["kit"] == "Sivir" and cible["pv"] >= 0:
            autres = [a for a in vivants(tous, cible["camp"]) if a is not cible]
            if autres:
                frapper(u, random.choice(autres), K["sivir_rebond"] / 100, journal, tous, True)
        if u["kit"] == "Ahri" and u["lr"]:
            u["charme"] = u.get("charme", 0) + 1
            if u["charme"] % LR["ahri_coups"] == 0 and cible["pv"] > 0:
                etourdir(cible)
        if u["kit"] == "Ryze" and (u["lr"] or u["coups"] % K["ryze_coups"] == 0):
            autres = [a for a in vivants(tous, cible["camp"]) if a is not cible]
            if autres:
                frapper(u, random.choice(autres), (LR["ryze_rebond"] if u["lr"] else K["ryze_rebond"]) / 100, journal, tous, True)
        if u["kit"] == "Syndra":
            u["spheres"] = min(K["syndra_max"], u.get("spheres", 0) + 1)
        elif u["kit"] == "Xayah":
            u["plumes"] = min(K["xayah_max"], u.get("plumes", 0) + 1)
        elif u["kit"] == "Fiora" and u["coups"] % K["fiora_coups"] == 0:
            soin(u, u["pvmax"] * K["fiora_soin"] / 100)
        elif u["kit"] == "Aphelios" and u["coups"] % 3 == 1:
            soin(u, d * K["aphelios_vol"] / 100)
        elif u["kit"] == "Sylas" and u["suite"] > 0:
            u["suite"] -= 1
            soin(u, u["pvmax"] * (UK["sylas_soin"] if u.get("urk") else K["sylas_soin"]) / 100)
        elif u["kit"] == "Tristana" and u["coups"] % (EV["tristana_coups"] if u.get("eveil") else K["tristana_coups"]) == 0:
            autres = [a for a in vivants(tous, cible["camp"]) if a is not cible]
            if autres:
                frapper(u, random.choice(autres), K["tristana_eclat"] / 100, journal, tous, True)   # l'éclat (un actif) ne recompte pas la charge
    if u["trait"] == "hextech":
        ajouter_effet(cible, "hextech", "vitesse", -data.TRAITS_BOSS["hextech_lent"], 2)
    if u["trait"] == "nashor":   # se cumule : chaque coup ronge un peu plus
        deja = sum(e["valeur"] for e in cible["effets"] if e["cle"] == "nashor")
        ajouter_effet(cible, "nashor", "res", deja - data.TRAITS_BOSS["nashor_res"], 4)
    if u["kit"] == "Leona" and cible["pv"] > 0:
        cible["soleil"] = 1
    if u["kit"] == "Braum" and not cible["marque"]:
        cible["marque"] = 1
    elif cible["marque"]:
        cible["marque"] += 1
        if cible["marque"] >= K["braum_coups"] and cible["pv"] > 0:
            cible["marque"] = 0
            etourdir(cible)
            journal.append(f"❄️ {cible['nom']} est gelé par la marque de Braum." if cible["stun"] else f"❄️ {cible['nom']} résiste au gel.")
    if cible.get("rune") == "gardien" and "gardien" not in cible["une_fois"] and 0 < cible["pv"] < cible["pvmax"] * R["gardien_seuil"] / 100:
        cible["une_fois"].append("gardien")
        bouclier = int(cible["pvmax"] * R["gardien_bouclier"] / 100 * (1 + sum(cible["res"]) / 200))
        for a in vivants(tous, cible["camp"]):
            a["bouclier"] += bouclier
        journal.append(f"🛡️ Le Gardien de {cible['nom']} protège son équipe ({bouclier} de bouclier chacun).")
    if cible["pv"] <= 0:
        tuer(cible, journal, tous)
        if u["kit"] == "Chogath" and cible["pv"] <= 0 and u["pv"] > 0:   # il grandit à chaque élimination
            gain = int(u["pvmax"] * K["chogath_pv"] / 100)
            u["pvmax"] += gain
            u["pv"] += gain
        if u["kit"] == "Viego" and u.get("urk") and cible["pv"] <= 0 and u["pv"] > 0:   # Viego UR : il possède sa victime
            soin(u, u["pvmax"] * UK["viego_soin"] / 100)
            if cible.get("kit") and cible["kit"] not in ("Viego", "Sylas"):
                u["possede"] = cible["kit"]
                journal.append(f"👑 {u['nom']} possède {cible['nom']} : son prochain actif sera le sien.")
        elif u["kit"] == "Viego" and cible["pv"] <= 0 and u["pv"] > 0:
            soin(u, u["pvmax"] * K["viego_soin"] / 100)
            u["atk_base"] = int(u["atk_base"] * (1 + K["viego_atk"] / 100))
            maj(u)
            journal.append(f"👑 {u['nom']} s'empare de la force de {cible['nom']}.")
        if rune == "moisson" and cible["pv"] <= 0:
            u["r_kills"] += 1
            u["r_attente"] = 0
    elif u["trait"] == "ancestral" and cible["pv"] < cible["pvmax"] * data.TRAITS_BOSS["ancestral_seuil"] / 100:
        journal.append(f"🐉 Le Dragon ancestral réduit {cible['nom']} en cendres.")
        tuer(cible, journal, tous)
    elif u["kit"] == "Zed" and "zed" not in u["une_fois"] and cible["role"] != "boss" and cible["pv"] < cible["pvmax"] * K["execution"] / 100:
        u["une_fois"].append("zed")
        journal.append(f"🗡️ {u['nom']} achève {cible['nom']} dans l'ombre.")
        tuer(cible, journal, tous)
    elif cible["kit"] == "Akali" and "voile" not in cible["une_fois"] and cible["pv"] < cible["pvmax"] * 0.5:
        cible["une_fois"].append("voile")
        cible["intouchable"] = 1
        journal.append(f"🌫️ {cible['nom']} disparaît dans son voile.")
    if cible["pv"] > 0 and cible["objet"].get("zhonya") and "zhonya" not in cible["une_fois"] \
            and cible["pv"] < cible["pvmax"] * cible["objet"]["zhonya"] / 100:
        cible["une_fois"].append("zhonya")
        cible["intouchable"] = 1
        journal.append(f"⏳ {cible['nom']} se fige dans son Sablier de Zhonya.")
    return d


def etourdir(cible):
    """Étourdit une cible. Les boss y sont insensibles : on ne les enferme pas dans une chaîne d'étourdissements."""
    if cible["role"] != "boss":
        cible["stun"] = True


def soigner(u, tous, part):
    part *= 1 + u["bonus"].get("soin", 0)
    for a in vivants(tous, u["camp"]):
        soin(a, a["pvmax"] * part)


def ranimer(a):
    a["pv"] = a["pvmax"] // 2
    a["action"] = 0


def suivant(tous):
    """Fait avancer les jauges d'action jusqu'à ce qu'une unité soit prête, et la renvoie. À égalité, la plus rapide passe."""
    debout = [u for u in tous if u["pv"] > 0]
    u = min(debout, key=lambda x: ((SEUIL - x["action"]) / x["vitesse"], -x["vitesse"]))
    temps = max(0, (SEUIL - u["action"]) / u["vitesse"])
    for v in debout:
        v["action"] += v["vitesse"] * temps
    u["action"] = 0
    return u


def prochains(tous, combien=5):
    """Les prochaines unités à jouer, sans rien modifier (pour l'affichage)."""
    copies = [{"pv": u["pv"], "action": u["action"], "vitesse": u["vitesse"], "nom": u["nom"], "camp": u["camp"]} for u in tous]
    return [suivant(copies) for _ in range(combien)] if any(c["pv"] > 0 for c in copies) else []


def visables(u, tous):
    """Ennemis que cette unité a le droit de viser : provocation d'Amumu, camouflage de Teemo."""
    cibles = vivants(tous, 1 - u["camp"])
    if any(c is u["provoque"] for c in cibles):
        return [u["provoque"]]
    def cache(c):
        autres = [a for a in tous if a["camp"] == c["camp"] and a is not c]
        return c["kit"] == "Teemo" and autres and all(a["pv"] > 0 for a in autres)
    return [c for c in cibles if not cache(c)] or cibles


def choisir_cible(u, cibles):
    # La ligne avant attire les coups, sans y obliger : seule la provocation force une cible. Les assassins visent qui ils veulent.
    devant = [c for c in cibles if c.get("ligne") == "avant"]
    if u["role"] != "assassin" and devant and len(devant) < len(cibles) and random.random() * 100 < data.CIBLE_AVANT:
        cibles = devant
    tanks = [c for c in cibles if c["role"] == "tank"]
    if tanks and random.random() < 0.7:
        return random.choice(tanks)
    if u["camp"] == 0:
        return min(cibles, key=lambda c: c["pv"])   # ton équipe achève les plus faibles
    return random.choice(cibles)


def commencer_action(u, tous, journal):
    """Début du tour d'une unité : étourdissement et passifs. Renvoie False si elle passe son tour."""
    u["actions"] += 1
    if u["stun"]:
        if u.get("gel", 0) > 0:   # figé dans le temps (Bard) : l'étourdissement dure un tour de plus
            u["gel"] -= 1
        else:
            u["stun"] = False
        journal.append(f"💫 {u['nom']} est étourdi et passe son tour.")
        finir_action(u)
        return False
    u["jauge"] += 1
    if u["bonus"].get("charge") and random.random() < u["bonus"]["charge"]:
        u["jauge"] += 1   # bonus de leader de Piltover
    u["r_attente"] = max(0, u["r_attente"] - 1)
    k = u["kit"]
    if u["saigne"]:
        perte = sum(d for d, _ in u["saigne"])
        u["saigne"] = [[d, n - 1] for d, n in u["saigne"] if n > 1]
        absorbe = min(u["bouclier"], perte)
        u["bouclier"] -= absorbe
        u["pv"] -= perte - absorbe
        journal.append(f"🩸 {u['nom']} saigne : {perte} dégâts.")
        if u["pv"] <= 0:
            tuer(u, journal, tous)
            if u["pv"] <= 0:
                finir_action(u)
                return False
    if k == "Rakan":
        blesses = [a for a in vivants(tous, u["camp"]) if a["pv"] < a["pvmax"]]
        if blesses:
            min(blesses, key=lambda a: a["pv"] / a["pvmax"])["bouclier"] += int(u["pvmax"] * K["rakan_bouclier"] / 100 * (1 + u["bonus"].get("soin", 0)))
    if k == "Gragas":
        soin(u, u["pvmax"] * UK["gragas_soin"] / 100)
        if u["pv"] < u["pvmax"] * UK["gragas_seuil"] / 100 and "gragas_res" not in u["une_fois"]:
            u["une_fois"].append("gragas_res")
            ajouter_effet(u, "gragas", "res", UK["gragas_res"], 99)
            journal.append(f"🍺 {u['nom']} tient bon : +{UK['gragas_res']} de résistances.")
    if k == "Janna":
        blesses = [a for a in vivants(tous, u["camp"]) if a["pv"] < a["pvmax"]]
        if blesses:
            min(blesses, key=lambda a: a["pv"] / a["pvmax"])["bouclier"] += int(u["pvmax"] * K["janna_bouclier"] / 100 * (1 + u["bonus"].get("soin", 0)))
    if u["trait"] == "ryze":
        ryze = data.RAID_RYZE
        if "enrage" not in u["une_fois"] and u["pv"] < u["pvmax"] * u.get("rage", ryze["enrage_seuil"]) / 100:
            u["une_fois"].append("enrage")
            u["atk_base"] = int(u["atk_base"] * (1 + ryze["enrage_atk"] / 100))
            maj(u)
            journal.append(f"🔮 **Ryze entre en rage** : ses sorts frappent {ryze['enrage_atk']} % plus fort !")
        if u["actions"] % ryze["prison"] == 0 and vivants(tous, 1 - u["camp"]):
            prisonnier = random.choice(vivants(tous, 1 - u["camp"]))
            etourdir(prisonnier)
            journal.append(f"🔮 Ryze enferme **{prisonnier['nom']}** dans sa Prison runique.")
        if u.get("flux") and u["actions"] % ryze["flux_tous_les"] == 1 and vivants(tous, 1 - u["camp"]):
            menace = max(vivants(tous, 1 - u["camp"]), key=lambda a: a.get("inflige", 0))   # il vise celui qui lui fait le plus mal
            journal.append(f"🔮 Ryze déchaîne son **Flux runique** sur {menace['nom']}.")
            frapper(u, menace, u["flux"], journal, tous)
    if u["trait"] == "eau":
        soin(u, u["pvmax"] * data.TRAITS_BOSS["eau_soin"] / 100)
    if u["trait"] == "feu" and u["cumuls"] < data.TRAITS_BOSS["feu_max"]:
        u["cumuls"] += 1
        maj(u)
    if k == "Garen":
        soin(u, u["pvmax"] * K["garen_regen"] / 100)
    if k == "Yasuo":   # 14 octobre : nerf réservé aux cartes des joueurs (adversaires : 10 %, 3 actions)
        if u["actions"] <= (K["yasuo_actions"] if u.get("joueur") else 3) and not u["touche"]:
            u["bouclier"] = max(u["bouclier"], int(u["pvmax"] * (K["yasuo_bouclier"] if u.get("joueur") else 10) / 100))
        u["touche"] = False
    if k == "Renata" and u.get("joueur"):   # 13 octobre : soigne l'allié le plus blessé à chaque action
        blesses = [a for a in vivants(tous, u["camp"]) if a["pv"] < a["pvmax"]]
        if blesses:
            a = min(blesses, key=lambda a: a["pv"] / a["pvmax"])
            soin(a, a["pvmax"] * K["renata_passif"] / 100 * (1 + u["bonus"].get("soin", 0)))
    if k == "LeeSin":
        u["bouclier"] = max(u["bouclier"], int(u["pvmax"] * K["leesin_bouclier"] / 100))
    if k == "Varus" and u.get("eveil") and "varus" not in u["une_fois"]:
        u["une_fois"].append("varus")
        for a in vivants(tous, 1 - u["camp"]):
            a["fletrissure"] = max(a.get("fletrissure", 0), EV["varus_depart"])
    if k == "Bard" and u["actions"] % (EV["bard_actions"] if u.get("eveil") else K["bard_actions"]) == 0:
        blesses = [a for a in vivants(tous, u["camp"]) if a["pv"] < a["pvmax"]]
        if blesses:
            soin(min(blesses, key=lambda a: a["pv"] / a["pvmax"]), u["pvmax"] * K["bard_soin"] / 100 * (1 + u["bonus"].get("soin", 0)))
    if k == "Camille" and u["actions"] % K["camille_actions"] == 1:
        u["bouclier"] = max(u["bouclier"], int(u["pvmax"] * K["camille_bouclier"] / 100))
    if k == "Draven":
        if u["touche"]:
            u["suite"] = 0   # touché depuis sa dernière action : il laisse tomber ses haches
        u["touche"] = False
    cibles = visables(u, tous)
    if k == "Blitzcrank" and cibles:
        cible = random.choice(cibles)
        d = frapper(u, cible, K["blitz_passif"] / 100, journal, tous)
        journal.append(f"⚡ {u['nom']} électrise {cible['nom']} : {d} dégâts.")
    if u["tibbers"] and visables(u, tous):
        u["tibbers"] -= 1
        cible = random.choice(visables(u, tous))
        d = frapper(u, cible, K["tibbers"] / 100, journal, tous)
        journal.append(f"🐻 Tibbers griffe {cible['nom']} : {d} dégâts.")
    if u["brulure"]:
        u["brulure"] -= 1
        total = sum(frapper(u, c, K["nasus_feu"] / 100, journal, tous) for c in vivants(tous, 1 - u["camp"]))
        journal.append(f"🔥 La tempête de sable de {u['nom']} brûle les ennemis : {total} dégâts.")
    return True


def finir_action(u):
    if u.get("renata"):
        u["renata"] -= 1
    if u.get("lux_rebouclier"):   # Lux UR : le bouclier revient au tour suivant
        u["lux_rebouclier"] -= 1
        if u["lux_rebouclier"] == 0 and u["pv"] > 0:
            for a in u.get("lux_amis", []):
                if a["pv"] > 0:
                    a["bouclier"] += int(u["atk"] * EV["lux_rebouclier"] / 100)
    for e in u["effets"]:
        e["duree"] -= 1
    u["effets"] = [e for e in u["effets"] if e["duree"] > 0]
    u["intouchable"] = max(0, u["intouchable"] - 1)
    u["provoque"] = None
    maj(u)


def attaque_simple(u, cible, tous, journal, detail=False):
    debut = len(journal)
    if u["aveugle"]:
        u["aveugle"] = False
        journal.append(f"🍄 {u['nom']} est aveuglé et rate son attaque.")
        return
    rune = u.get("rune")
    d = frapper(u, cible, 1.0 + (R["aery_degats"] / 100 if rune == "aery" else 0), journal, tous)
    if u["kit"] in ("Senna", "Veigar", "Jinx", "Jax", "Zeri") or (u["kit"] == "Nasus" and d):
        cumuler(u)
    if rune and d:
        d += rune_attaque(u, cible, rune, journal, tous)
    if detail:
        journal.insert(debut, f"🗡️ {u['nom']} frappe {cible['nom']} : {d} dégâts.")


def rune_attaque(u, cible, rune, journal, tous):
    """Effet de la rune d'une unité après une attaque de base réussie. Renvoie les dégâts bonus infligés."""
    bonus = 0
    if rune == "jambes":
        soin(u, u["pvmax"] * R["jambes_soin"] / 100)
    elif rune == "tempo" and u["r_cumuls"] < R["tempo_max"]:
        u["r_cumuls"] += 1
        maj(u)
    elif rune == "conquerant" and u["r_cumuls"] < R["conquerant_max"]:
        u["r_cumuls"] += 1
        maj(u)
    elif rune == "poigne" and u["actions"] % 2 == 0 and cible["pv"] > 0:
        bonus = max(1, int(u["pvmax"] * R["poigne_degats"] / 100))
        absorbe = min(cible["bouclier"], bonus)
        cible["bouclier"] -= absorbe
        cible["pv"] -= bonus - absorbe
        u["inflige"] += bonus
        soin(u, u["pvmax"] * R["poigne_soin"] / 100)
        if cible["pv"] <= 0:
            tuer(cible, journal, tous)
    elif rune == "glacial" and u["actions"] % R["glacial_actions"] == 0 and cible["pv"] > 0:
        ajouter_effet(cible, "glacial", "vitesse", -R["glacial_lent"], 1)
    elif rune == "comete":
        u["r_coups"] += 1
        if u["r_coups"] % R["comete_attaques"] == 0 and cible["pv"] > 0:
            nature, u["type"] = u["type"], "magique"
            bonus = frapper(u, cible, R["comete_degats"] / 100, journal, tous)
            u["type"] = nature
    elif rune == "aery":
        blesses = [a for a in vivants(tous, u["camp"]) if a["pv"] < a["pvmax"]]
        if blesses:
            min(blesses, key=lambda a: a["pv"] / a["pvmax"])["bouclier"] += int(u["pvmax"] * R["aery_bouclier"] / 100)
    return bonus


def soin_soraka(u, allie, journal):
    soin(allie, allie["pvmax"] * K["soraka_soin"] / 100 * (1 + u["bonus"].get("soin", 0)))
    u["pv"] = max(1, u["pv"] - int(u["pvmax"] * K["soraka_cout"] / 100))
    journal.append(f"💚 {u['nom']} donne de sa vie pour soigner {allie['nom']}.")


def lancer_ulti(u, tous, cible, journal, icone="✨"):
    """L'actif d'un champion. cible peut être None pour les sorts qui ne visent personne."""
    u["jauge"] = 0
    debut = len(journal)
    k, e, nom = u["kit"], u["effet"], f"{icone} {u['nom']} lance **{u['ulti']}**"
    adverses, amis = vivants(tous, 1 - u["camp"]), vivants(tous, u["camp"])
    zone = lambda pct: sum(frapper(u, c, pct / 100, journal, tous, True) for c in adverses)
    if cible is None and ulti_cible(u) and visables(u, tous):
        cible = choisir_cible(u, visables(u, tous))
    dire = lambda texte: journal.insert(debut, f"{nom}{texte}")

    if k == "Lux" and u.get("joueur"):   # 13 octobre (soir) : Lux élémentaliste (SSR : feu puis lumière ; UR : feu, glace, lumière)
        ur = bool(u.get("eveil"))
        e = u.get("elem", 0)
        u["elem"] = (e + 1) % (3 if ur else 2)
        debout = [a for a in adverses if a["pv"] > 0]
        if e == 0:
            total = zone(EV["luxur_feu"] if ur else K["lux_feu"])
            for a in adverses:
                if a["pv"] > 0:
                    a["saigne"].append([int(u["atk"] * (EV["luxur_brulure"] if ur else K["lux_brulure"]) / 100), 2])
            dire(f" · 🔥 feu : {total} dégâts, les ennemis brûlent.")
        elif e == 1 and ur:
            total = zone(EV["luxur_glace"])
            debout = [a for a in adverses if a["pv"] > 0]
            if debout:
                etourdir(max(debout, key=lambda a: a["atk"]))
            dire(f" · ❄️ glace : {total} dégâts, l'ennemi le plus dangereux est gelé.")
        elif debout:
            v = max(debout, key=lambda a: a["atk"])
            d = frapper(u, v, (EV["luxur_lumiere"] if ur else K["lux_lumiere"]) / 100, journal, tous, True)
            dire(f" · ✨ lumière sur {v['nom']} : {d} dégâts.")
        else:
            dire(".")
    elif k == "Sejuani" and u.get("joueur") and cible:   # 13 octobre (soir)
        d = frapper(u, cible, K["sejuani_ulti2"] / 100, journal, tous, True)
        if cible["pv"] > 0:
            etourdir(cible)
        for a in adverses:
            if a is not cible and a["pv"] > 0:
                ajouter_effet(a, "sejuani", "vitesse", -K["sejuani_lent"], 2)
        dire(f" sur {cible['nom']} : {d} dégâts, il est pris dans la glace et les autres sont ralentis.")
    elif k == "Corki" and u.get("joueur"):   # 13 octobre (soir)
        total = 0
        for _ in range(K["corki_missiles"]):
            restants = [a for a in adverses if a["pv"] > 0]
            if restants:
                total += frapper(u, random.choice(restants), K["corki_missile"] / 100, journal, tous, True)
        total += zone(K["corki_gros"])
        dire(f" : {K['corki_missiles']} missiles puis le gros missile sur tous les ennemis, {total} dégâts.")
    elif k == "Renata" and u.get("joueur"):   # 13 octobre (soir) : vraie support
        tombes = [a for a in tous if a["camp"] == u["camp"] and a["pv"] <= 0]
        if tombes:
            ranimer(tombes[0])
            dire(f" : {tombes[0]['nom']} revient au combat !")
        else:
            vivants_amis = [a for a in amis if a["pv"] > 0]
            for a in vivants_amis:
                a["bouclier"] += int(a["pvmax"] * K["renata_equipe"] / 100 * (1 + u["bonus"].get("soin", 0)))
            if vivants_amis:
                faible = min(vivants_amis, key=lambda a: a["pv"] / a["pvmax"])
                faible["renata"] = K["renata_protege"]
            dire(" : un bouclier protège toute l'équipe, et l'allié le plus fragile ne peut plus tomber pour un moment.")
    elif k == "Galio":
        total = zone(K["galio_zone"])
        for a in amis:
            ajouter_effet(a, "galio", "res", K["galio_res"], 3 if a is u else 2)
        dire(f" : {total} dégâts, et ses alliés gagnent +{K['galio_res']} de résistances.")
    elif k == "Lux":   # 13 octobre (après-midi) : Barrière prismatique, Lux devient support
        valeur = int(u["atk"] * K["lux_bouclier"] / 100)
        for a in amis:
            if a["pv"] > 0:
                a["bouclier"] += valeur
        if u.get("eveil"):   # UR : un deuxième bouclier, à la fin de sa prochaine action
            u["lux_rebouclier"], u["lux_amis"] = 2, amis
        dire(f" : un bouclier de {valeur} protège toute son équipe.")
    elif k == "Senna":
        total = zone(K["senna_zone"])
        for a in amis:
            a["bouclier"] += int(a["pvmax"] * (EV["senna_bouclier"] if u.get("eveil") else K["senna_bouclier"]) / 100 * (1 + u["bonus"].get("soin", 0)))
        dire(f" : {total} dégâts, et un bouclier protège ses alliés.")
    elif k in ("Nami", "Janna"):
        soigner(u, tous, K["nami_soin" if k == "Nami" else "janna_soin"] / 100)
        if k == "Nami":
            for a in amis:
                ajouter_effet(a, "nami", "vitesse", K["nami_vitesse"], 3 if a is u else 2)
            if adverses:
                menace = max(adverses, key=lambda a: a["atk"])
                etourdir(menace)
                dire(f" : son équipe est soignée et accélérée, {menace['nom']} est emporté par la vague." if menace["stun"] else " : son équipe est soignée et accélérée.")
            else:
                dire(" : son équipe est soignée.")
        else:
            for a in adverses:
                a["jauge"] = max(0, a["jauge"] - 1) if a["role"] == "boss" else 0
            dire(" : son équipe est soignée, et la tempête disperse les sorts que préparaient les ennemis.")
    elif k == "Rumble":
        total = zone(K["rumble_zone"])
        for a in adverses:
            if a["pv"] > 0:
                a["saigne"].append([int(u["atk"] * K["rumble_ulti_brule"] / 100), 2])
        dire(f" : {total} dégâts, et tous les ennemis sont en flammes.")
    elif k == "Gnar":
        total = zone(K["gnar_zone"])
        for a in adverses:
            ajouter_effet(a, "gnar", "vitesse", -K["gnar_lent"], 2)
        dire(f" : {total} dégâts, les ennemis sont projetés et ralentis.")
    elif k == "Jayce" and u.get("eveil"):
        cible = min(adverses, key=lambda a: a["pv"] / a["pvmax"])
        d = frapper(u, cible, K["jayce_ulti"] / 100, journal, tous, True)
        autres = [a for a in vivants(tous, 1 - u["camp"]) if a is not cible]
        if autres:
            d += frapper(u, min(autres, key=lambda a: a["pv"] / a["pvmax"]), K["jayce_ulti"] * EV["jayce_second"] / 10000, journal, tous, True)
        dire(f" : {d} dégâts, le tir traverse jusqu'à un second ennemi.")
    elif k in ("Jayce", "Khazix"):
        cible = min(visables(u, tous) or adverses, key=lambda a: a["pv"] / a["pvmax"])
        d = frapper(u, cible, K["jayce_ulti" if k == "Jayce" else "khazix_ulti"] / 100, journal, tous, True)
        if k == "Khazix":
            u["intouchable"] = 2
        dire(f" sur {cible['nom']} : {d} dégâts." + (" Il disparaît." if k == "Khazix" else ""))
    elif k == "Viego" and u.get("urk") and u.get("possede"):
        vole, u["possede"] = u["possede"], None
        u["kit"] = vole
        try:
            journal.insert(debut, f"{icone} {u['nom']} utilise le pouvoir de sa possession…")
            lancer_ulti(u, tous, None, journal, "👑")
        finally:
            u["kit"] = "Viego"
    elif k == "Viego" and u.get("urk"):
        fort = cible["pv"] < cible["pvmax"] * UK["viego_seuil"] / 100
        d = frapper(u, cible, UK["viego_fort" if fort else "viego_ulti"] / 100, journal, tous, True)
        dire(f" sur {cible['nom']} : {d} dégâts.")
        if cible["pv"] <= 0 and u["pv"] > 0:
            u["jauge"] = u["cout"]   # il a tué : son actif se recharge aussitôt
    elif k == "Sion":
        d = frapper(u, cible, K["sion_ulti"] / 100, journal, tous, True)
        if cible["pv"] > 0:
            etourdir(cible)
        dire(f" sur {cible['nom']} : {d} dégâts, il est sonné.")
    elif k == "Chogath":
        if cible["role"] != "boss" and 0 < cible["pv"] < cible["pvmax"] * K["chogath_seuil"] / 100 and not cible["intouchable"]:
            cible["pv"] = 0
            tuer(cible, journal, tous)
            if cible["pv"] <= 0 and u["pv"] > 0:
                gain = int(u["pvmax"] * K["chogath_pv"] / 100)
                u["pvmax"] += gain
                u["pv"] += gain
            dire(f" : il dévore {cible['nom']} !")
        else:
            d = frapper(u, cible, K["chogath_ulti"] / 100, journal, tous, True)
            dire(f" sur {cible['nom']} : {d} dégâts.")
    elif k == "Sivir":
        d = frapper(u, cible, K["sivir_ulti"] / 100, journal, tous, True)
        for a in amis:
            ajouter_effet(a, "sivir", "vitesse", K["sivir_vitesse"], 3 if a is u else 2)
        dire(f" sur {cible['nom']} : {d} dégâts, et toute son équipe accélère.")
    elif k == "Rakan":
        total = zone(K["rakan_zone"])
        charmes = [a for a in vivants(tous, 1 - u["camp"]) if a["role"] != "boss"]
        random.shuffle(charmes)
        for a in charmes[:K["rakan_charmes"]]:
            etourdir(a)
        dire(f" : {total} dégâts, et {min(len(charmes), K['rakan_charmes'])} ennemis sont charmés.")
    elif k == "Gragas":
        total = zone(UK["gragas_zone"])
        for a in adverses:
            if a["pv"] > 0:
                a["jauge"] = max(0, a["jauge"] - 1) if a["role"] == "boss" else 0
                ajouter_effet(a, "gragas", "vitesse", -UK["gragas_lent"], 2)
        dire(f" : {total} dégâts, les ennemis sont repoussés et ralentis.")
    elif k == "Viego":
        fort = cible["pv"] < cible["pvmax"] * K["viego_seuil"] / 100
        d = frapper(u, cible, K["viego_fort" if fort else "viego_ulti"] / 100, journal, tous, True)
        dire(f" sur {cible['nom']} : {d} dégâts.")
    elif k == "Qiyana":
        total = zone(K["qiyana_zone"])
        debout = [a for a in adverses if a["pv"] > 0]
        if debout:
            etourdir(random.choice(debout))
        dire(f" : {total} dégâts, un ennemi est projeté contre le mur.")
    elif k == "Draven":
        total = zone(K["draven_zone"]) + zone(K["draven_zone"])
        dire(f" : ses haches traversent tout le monde deux fois, {total} dégâts.")
    elif k == "Kalista":
        perces = [a for a in adverses if a.get("lances")]
        if perces:
            total = 0
            for a in perces:
                total += frapper(u, a, a["lances"] * K["kalista_lance"] / 100, journal, tous, True)
                a["lances"] = 0
            dire(f" : elle arrache ses lances, {total} dégâts.")
        else:
            d = frapper(u, cible, K["kalista_ulti"] / 100, journal, tous, True)
            dire(f" sur {cible['nom']} : {d} dégâts.")
    elif k == "Yone":
        total = zone(EV["yone_zone"] if u.get("eveil") else K["yone_zone"])
        debout = [a for a in adverses if a["pv"] > 0]
        if debout:
            vise = min(debout, key=lambda a: a["pv"] / a["pvmax"])
            etourdir(vise)
        dire(f" : {total} dégâts, et l'ennemi le plus blessé est cloué sur place.")
    elif k in ("Ahri", "Jhin"):
        tirs = [K["ahri_ulti"]] * 3 if k == "Ahri" else [K["jhin_tir"]] * 3 + [K["jhin_dernier"]]
        if k == "Ahri" and u["lr"]:
            tirs = [LR["ahri_ulti"]] * 3
        total = 0
        for pct in tirs:
            restants = [a for a in vivants(tous, 1 - u["camp"])]
            if not restants:
                break
            vise = min(restants, key=lambda a: a["pv"] / a["pvmax"])
            total += frapper(u, vise, pct / 100, journal, tous, True)
            if k == "Ahri" and u["lr"] and vise["pv"] <= 0 and len(tirs) < LR["ahri_max"]:
                tirs.append(pct)
        dire(f" : {len(tirs)} {'charges' if k == 'Ahri' else 'tirs'}, {total} dégâts.")
    elif k == "Kaisa":
        cible = min(visables(u, tous) or adverses, key=lambda a: a["pv"] / a["pvmax"])
        d = frapper(u, cible, K["kaisa_ulti"] / 100, journal, tous, True)
        u["bouclier"] += int(u["pvmax"] * K["kaisa_bouclier"] / 100)
        dire(f" sur {cible['nom']} : {d} dégâts, et elle se protège.")
    elif k == "Ezreal":
        total = zone(K["ezreal_zone"])
        dire(f" : {total} dégâts sur tous les ennemis.")
    elif k == "LeeSin":
        d = frapper(u, cible, K["leesin_ulti"] / 100, journal, tous, True)
        if cible["pv"] > 0:
            etourdir(cible)
        d += sum(frapper(u, a, K["leesin_eclat"] / 100, journal, tous, True) for a in vivants(tous, 1 - u["camp"]) if a is not cible)
        dire(f" sur {cible['nom']}, projeté sur ses alliés : {d} dégâts.")
    elif k == "Thresh":
        total = zone(K["thresh_zone"])
        for a in adverses:
            if a["pv"] > 0:
                ajouter_effet(a, "thresh", "vitesse", -K["thresh_lent"], 2)
        blesse = min(amis, key=lambda a: a["pv"] / a["pvmax"])
        blesse["bouclier"] += int(blesse["pvmax"] * K["thresh_bouclier"] / 100 * (1 + u["bonus"].get("soin", 0)))
        dire(f" : {total} dégâts, les ennemis sont ralentis et {blesse['nom']} est protégé.")
    elif k in ("Ambessa", "Nidalee"):
        cible = min(visables(u, tous) or adverses, key=lambda a: a["pv"] / a["pvmax"])
        d = frapper(u, cible, K["ambessa_ulti" if k == "Ambessa" else "nidalee_ulti"] / 100, journal, tous, True)
        if k == "Ambessa":
            if cible["pv"] > 0:
                etourdir(cible)
            dire(f" sur {cible['nom']} : {d} dégâts.")
        else:
            soin(u, u["pvmax"] * K["nidalee_soin"] / 100)
            dire(f" sur {cible['nom']} : {d} dégâts, et elle se soigne.")
    elif k == "Maokai":
        total = zone(K["maokai_zone"])
        pris = [a for a in vivants(tous, 1 - u["camp"]) if a["role"] != "boss"][:EV["maokai_racines"] if u.get("eveil") else K["maokai_racines"]]
        if u.get("eveil"):   # Maokai UR (13 octobre) : bouclier, et les ennemis sont forcés de l'attaquer
            u["bouclier"] += int(u["pvmax"] * EV["maokai_bouclier"] / 100)
            for a in adverses:
                if a["pv"] > 0:
                    a["provoque"] = u
        for a in pris:
            etourdir(a)
        dire(f" : {total} dégâts" + (f", {' et '.join(a['nom'] for a in pris)} sont enracinés." if pris else "."))
    elif k in ("Ziggs", "XinZhao", "Zeri"):
        total = zone(K["ziggs_zone" if k == "Ziggs" else "xin_zone" if k == "XinZhao" else "zeri_zone"])
        if k == "XinZhao":
            u["blocages"] += EV["xin_blocages"] if u.get("eveil") else K["xin_blocages"]
        elif k == "Zeri":
            ajouter_effet(u, "zeri", "vitesse", K["zeri_elan"], 4)
        dire(f" : {total} dégâts sur tous les ennemis.")
    elif k == "Varus":
        marques, cible["fletrissure"] = cible.get("fletrissure", 0), 0
        d = frapper(u, cible, (K["varus_ulti"] + K["varus_marque"] * marques) / 100, journal, tous, True)
        if cible["pv"] > 0:
            etourdir(cible)
        autres = [a for a in vivants(tous, 1 - u["camp"]) if a is not cible]
        if autres and marques >= K["varus_max"]:
            etourdir(random.choice(autres))
        dire(f" sur {cible['nom']} : {d} dégâts" + (", la corruption se propage." if autres and marques >= K["varus_max"] else "."))
    elif k == "Corki":
        total = 0
        for _ in range(3):
            restants = vivants(tous, 1 - u["camp"])
            if not restants:
                break
            total += frapper(u, random.choice(restants), K["corki_missile"] / 100, journal, tous, True)
        dire(f" : trois missiles, {total} dégâts.")
    elif k == "Graves":
        tank = u.get("joueur")   # 13 octobre : le Graves des joueurs est un tank (les pros gardent l'ancien)
        d = frapper(u, cible, K["graves_tank_ulti" if tank else "graves_ulti"] / 100, journal, tous, True)
        d += sum(frapper(u, a, K["graves_tank_eclat" if tank else "graves_eclat"] / 100, journal, tous, True) for a in vivants(tous, 1 - u["camp"]) if a is not cible)
        dire(f" sur {cible['nom']}, l'explosion touche les autres : {d} dégâts.")
    elif k == "Bard":
        total = zone(K["bard_zone"])
        debout = [a for a in adverses if a["pv"] > 0]
        figes = random.sample(debout, min(K["bard_stun"], len(debout)))
        if u.get("eveil") and debout:   # éveil : le plus menaçant est toujours figé
            menace = max(debout, key=lambda a: a["atk"])
            if menace not in figes:
                figes.append(menace)
        for a in figes:
            etourdir(a)
            if a["stun"]:
                a["gel"] = K["bard_tours"] - 1
        dire(f" : {total} dégâts, des ennemis sont figés dans le temps pour {K['bard_tours']} tours.")
    elif k == "Renata":
        tombes = [a for a in tous if a["camp"] == u["camp"] and a["pv"] <= 0]
        if tombes:
            ranimer(tombes[0])
            dire(f" : {tombes[0]['nom']} revient au combat !")
        else:
            for a in amis:
                a["bouclier"] += int(a["pvmax"] * K["renata_bouclier"] / 100 * (1 + u["bonus"].get("soin", 0)))
            dire(" : un bouclier protège toute son équipe.")
    elif k == "Azir":
        total = zone(LR["azir_zone"] if u["lr"] else K["azir_zone"])
        for a in adverses:
            a["jauge"] = max(0, a["jauge"] - 1) if a["role"] == "boss" else 0
        if u["lr"]:
            for a in vivants(tous, u["camp"]):
                a["bouclier"] += int(a["pvmax"] * LR["azir_bouclier"] / 100)
        dire(f" : {total} dégâts, sa phalange repousse tout le monde.")
    elif k == "Ryze":
        d = frapper(u, cible, (LR["ryze_ulti"] if u["lr"] else K["ryze_ulti"]) / 100, journal, tous, True)
        if cible["pv"] > 0:
            etourdir(cible)
            if u["lr"] and cible["role"] != "boss":
                cible["gel"] = LR["ryze_tours"] - 1
        d += sum(frapper(u, a, (LR["ryze_eclat"] if u["lr"] else K["ryze_eclat"]) / 100, journal, tous, True) for a in vivants(tous, 1 - u["camp"]) if a is not cible)
        dire(f" sur {cible['nom']}, puis la Surcharge se propage : {d} dégâts.")
    elif k == "Fiora":
        d = sum(frapper(u, cible, K["fiora_ulti"] / 100, journal, tous, True) for _ in range(4))
        if cible["pv"] <= 0:
            soigner(u, tous, K["fiora_equipe"] / 100)
            dire(f" sur {cible['nom']} : {d} dégâts. Défi remporté, son équipe est soignée.")
        else:
            dire(f" sur {cible['nom']} : {d} dégâts.")
    elif k == "Leblanc":
        d = frapper(u, cible, K["leblanc_ulti"] / 100, journal, tous, True)
        restants = vivants(tous, 1 - u["camp"])
        if restants:
            d += frapper(u, min(restants, key=lambda a: a["pv"] / a["pvmax"]), K["leblanc_echo"] / 100, journal, tous, True)
        dire(f" sur {cible['nom']}, et son reflet frappe à son tour : {d} dégâts.")
    elif k == "Syndra":
        spheres, u["spheres"] = u.get("spheres", 0), 0
        d = frapper(u, cible, (K["syndra_base"] + K["syndra_sphere"] * spheres) / 100, journal, tous, True)
        dire(f" sur {cible['nom']} : {spheres} sphères, {d} dégâts.")
    elif k == "Xayah":
        plumes, u["plumes"] = u.get("plumes", 0), 0
        total = zone(K["xayah_base"] + (EV["xayah_plume"] if u.get("eveil") else K["xayah_plume"]) * plumes)
        u["intouchable"] = 2
        dire(f" : elle s'envole et rappelle {plumes} plumes, {total} dégâts.")
    elif k == "Sylas" and u.get("urk"):
        cible = max(visables(u, tous) or adverses, key=lambda a: a["atk"])
        d = frapper(u, cible, UK["sylas_ulti"] / 100, journal, tous, True)
        dire(f" sur {cible['nom']} : {d} dégâts, et il lui vole son actif.")
        vole = cible.get("kit")
        if vole and vole not in ("Sylas", "Viego") and vivants(tous, 1 - u["camp"]):
            u["kit"], u["puissance"] = vole, UK["sylas_vole"] / 100
            try:
                lancer_ulti(u, tous, None, journal, "🔗")
            finally:
                u["kit"], u["puissance"] = "Sylas", 1.0
        u["suite"] = 2
    elif k == "Sylas":
        cible = max(visables(u, tous) or adverses, key=lambda a: a["atk"])
        d = frapper(u, cible, K["sylas_ulti"] / 100, journal, tous, True)
        if cible["pv"] > 0:
            ajouter_effet(cible, "sylas", "atk", -K["sylas_vol"], 3)
        ajouter_effet(u, "sylas_vol", "atk", K["sylas_vol"], 3)
        u["suite"] = 2
        dire(f" sur {cible['nom']} : {d} dégâts, et il lui vole sa force.")
    elif k == "Tristana":
        d = frapper(u, cible, K["tristana_ulti"] / 100, journal, tous, True)
        cible["jauge"] = max(0, cible["jauge"] - 1) if cible["role"] == "boss" else 0
        dire(f" sur {cible['nom']} : {d} dégâts, il est repoussé.")
    elif k == "KSante":
        d = frapper(u, cible, K["ksante_ulti"] / 100, journal, tous, True)
        if "azimuts" not in u["une_fois"]:
            u["une_fois"].append("azimuts")
            u["res_base"] = (u["res_base"][0] - K["ksante_res"], u["res_base"][1] - K["ksante_res"])
            u["atk_base"] = int(u["atk_base"] * (1 + K["ksante_atk"] / 100))
            maj(u)
        dire(f" sur {cible['nom']} : {d} dégâts. Il lâche ses défenses et passe à l'attaque.")
    elif k == "Ornn":
        total = zone(K["ornn_zone"])
        debout = [a for a in adverses if a["pv"] > 0]
        for a in debout:
            ajouter_effet(a, "ornn", "vitesse", -K["ornn_lent"], 2)
        if debout:
            etourdir(random.choice(debout))
        dire(f" : {total} dégâts, les ennemis sont ralentis et l'un d'eux est renversé.")
    elif k == "Jax":
        d = frapper(u, cible, K["jax_ulti"] / 100, journal, tous, True)
        if cible["pv"] > 0:
            etourdir(cible)
        u["blocages"] += K["jax_blocages"]
        dire(f" sur {cible['nom']} : {d} dégâts, et il esquivera les {K['jax_blocages']} prochaines attaques.")
    elif k == "Camille":
        d = frapper(u, cible, K["camille_ulti"] / 100, journal, tous, True)
        if cible["pv"] > 0:
            etourdir(cible)
            ajouter_effet(cible, "camille", "res", -K["camille_res"], 2)
        dire(f" sur {cible['nom']} : {d} dégâts, il est enfermé.")
    elif k == "Gwen":
        d = sum(frapper(u, cible, K["gwen_ulti"] / 100, journal, tous, True) for _ in range(3))
        soin(u, d * K["gwen_vol"] / 100)
        dire(f" trois fois sur {cible['nom']} : {d} dégâts, et elle se soigne.")
    elif k == "Aphelios":
        total = zone(K["aphelios_zone"])
        dire(f" : {total} dégâts sur tous les ennemis.")
    elif k == "Caitlyn":
        cible = min(visables(u, tous) or adverses, key=lambda a: a["pv"] / a["pvmax"])
        d = frapper(u, cible, K["caitlyn_ulti"] / 100, journal, tous, True)
        dire(f" sur {cible['nom']} : {d} dégâts.")
    elif k == "Vi":
        cible = max(visables(u, tous) or adverses, key=lambda a: a["atk"])
        u["bouclier"] += int(u["pvmax"] * K["vi_bouclier"] / 100)
        cible["blocages"] = 0
        d = frapper(u, cible, K["vi_ulti"] / 100, journal, tous, True)
        if cible["pv"] > 0:
            etourdir(cible)
        dire(f" sur {cible['nom']} : {d} dégâts" + (", et l'assomme." if cible["stun"] else "."))
    elif k == "Shaco":
        d = frapper(u, cible, K["shaco_ulti"] / 100, journal, tous, True)
        d += sum(frapper(u, a, K["shaco_zone"] / 100, journal, tous, True) for a in vivants(tous, 1 - u["camp"]))
        u["blocages"] += 1
        dire(f" : {d} dégâts en tout. Son clone encaissera la prochaine attaque.")
    elif k == "Morgana":
        total = zone(K["morgana_zone"])
        pris = [a for a in vivants(tous, 1 - u["camp"]) if a["pv"] < a["pvmax"] * K["morgana_seuil"] / 100]
        for a in pris:
            etourdir(a)
        dire(f" : {total} dégâts" + (f", et {len([a for a in pris if a['stun']])} ennemi(s) enchaîné(s)." if pris else "."))
    elif k == "Talon":
        total = zone(K["talon_zone"])
        u["blocages"] += K["talon_blocages"]   # 13 octobre : bloque une attaque au lieu de devenir intouchable
        dire(f" : {total} dégâts sur tous les ennemis, puis il se cache dans l'ombre.")
    elif k == "MissFortune":
        vagues, force_v = (K["mf_vagues"], K["mf_vague"]) if u.get("joueur") else (3, 55)   # 14 octobre : up réservé aux joueurs
        total = sum(sum(frapper(u, a, force_v / 100, journal, tous, True) for a in vivants(tous, 1 - u["camp"])) for _ in range(vagues))
        dire(f" : {vagues} vagues, {total} dégâts sur tous les ennemis.")
    elif k == "Orianna":
        total = zone(K["orianna_zone"])
        pris = random.sample(vivants(tous, 1 - u["camp"]), min(K["orianna_stun"], len(vivants(tous, 1 - u["camp"]))))
        for a in pris:
            etourdir(a)
        dire(f" : {total} dégâts" + (f", {', '.join(a['nom'] for a in pris if a['stun'])} projeté(s) en l'air." if any(a["stun"] for a in pris) else "."))
    elif k == "Akali":
        d = frapper(u, cible, K["akali"] / 100, journal, tous, True)
        if 0 < cible["pv"] < cible["pvmax"] * (EV["akali_seuil"] if u.get("eveil") else 40) / 100:
            d += frapper(u, cible, K["akali"] / 100, journal, tous, True)
            dire(f" deux fois sur {cible['nom']} : {d} dégâts.")
        else:
            dire(f" sur {cible['nom']} : {d} dégâts.")
    elif k == "Yasuo":
        d = frapper(u, cible, (K["yasuo_ulti"] if u.get("joueur") else 250) / 100, journal, tous, True)
        u["blocages"] += 1
        dire(f" sur {cible['nom']} : {d} dégâts. Son mur de vent bloquera la prochaine attaque.")
    elif k == "Darius":
        total, touches = 0, []
        while cible and len(touches) < 3:
            touches.append(cible["nom"])
            total += frapper(u, cible, 3.5 if cible["pv"] < cible["pvmax"] * 0.4 else 1.8, journal, tous, True)
            cible = choisir_cible(u, visables(u, tous)) if cible["pv"] <= 0 and visables(u, tous) and u["pv"] > 0 else None
        cumuler(u)
        dire(f" sur {', puis '.join(touches)} : {total} dégâts.")
    elif k == "Aatrox" and u.get("eveil"):   # Aatrox UR (13 octobre) : frappe tous les ennemis et se soigne sur chacun
        total = sum(frapper(u, a, EV["aatrox_zone"] / 100, journal, tous, True, vol=EV["aatrox_vol"] / 100) for a in adverses)
        dire(f" : {total} dégâts sur tous les ennemis, et il se soigne.")
    elif k == "Aatrox":
        d = frapper(u, cible, K["aatrox_ulti"] / 100, journal, tous, True, vol=(EV["aatrox_vol"] if u.get("eveil") else K["aatrox_ulti_vol"]) / 100)
        dire(f" sur {cible['nom']} : {d} dégâts, et il se soigne.")
    elif k == "Teemo":
        total = zone(K["teemo_zone"])
        for c in adverses:
            if c["pv"] > 0 and c["role"] != "boss":
                c["aveugle"] = True
        dire(f" : {total} dégâts, les ennemis sont aveuglés.")
    elif k == "Garen":
        d = frapper(u, cible, 1.8, journal, tous, True)
        if 0 < cible["pv"] < cible["pvmax"] * (EV["garen_execution"] if u.get("eveil") else K["execution"]) / 100 and cible["role"] != "boss":
            tuer(cible, journal, tous)
            if u.get("eveil") and cible["pv"] <= 0:
                u["jauge"] = u["cout"]   # éveil : l'exécution recharge son actif
            dire(f" sur {cible['nom']} : {d} dégâts, et l'exécute.")
        else:
            dire(f" sur {cible['nom']} : {d} dégâts.")
    elif k == "Sona":
        for c in adverses:
            ajouter_effet(c, "sona", "vitesse", -K["sona_lent"], 2)
        soigner(u, tous, K["sona_soin"] / 100)
        dire(" : les ennemis sont ralentis et son équipe est soignée.")
    elif k == "Leona":
        total = zone(K["leona_zone"])
        debout = [a for a in adverses if a["pv"] > 0]
        menace = max(debout, key=lambda a: a["atk"]) if debout else None
        if menace:
            etourdir(menace)
        ajouter_effet(u, "leona", "res", K["leona_res"], 2)
        dire(f" : {total} dégâts" + (f", {menace['nom']} est étourdi" if menace and menace["stun"] else "") + f", et elle gagne +{K['leona_res']} de résistances.")
    elif k == "Braum":
        for a in amis:
            a["blocages"] += 1
        dire(" : la prochaine attaque contre chaque allié sera bloquée.")
    elif k == "Annie":
        total = zone(130)
        u["tibbers"] = K["tibbers_actions"]
        dire(f" : {total} dégâts, et Tibbers entre en scène.")
    elif k == "Amumu":
        total = zone(130)
        for c in adverses:
            if c["pv"] > 0:
                c["provoque"] = u
        ajouter_effet(u, "amumu", "res", K["amumu_res"], 2)
        dire(f" : {total} dégâts, et les ennemis sont forcés de l'attaquer.")
    elif k == "Nasus":
        gain = int(u["pvmax"] * K["nasus_pv"] / 100)
        u["pvmax"] += gain
        u["pv"] += gain
        u["brulure"] = K["nasus_actions"]
        dire(" : il grandit et une tempête de sable brûle les ennemis.")
    elif e == "resurrection" and [a for a in tous if a["camp"] == u["camp"] and a["pv"] <= 0]:
        tombe = [a for a in tous if a["camp"] == u["camp"] and a["pv"] <= 0][0]
        ranimer(tombe)
        if u["kit"] == "Zilean" and u.get("joueur"):   # 14 octobre : Zilean des joueurs ranime avec moins de PV (Renata inchangée)
            tombe["pv"] = max(1, int(tombe["pvmax"] * K["zilean_ranime"] / 100))
        dire(f" : {tombe['nom']} revient au combat !")
    elif e in ("soin", "resurrection"):
        soigner(u, tous, K["zilean_soin"] / 100 if u["kit"] == "Zilean" and u.get("joueur") else 0.30)
        dire(" : son équipe est soignée.")
    elif e == "zone":
        total = zone(data.RAID_RYZE["zone"] if u["trait"] == "ryze" else data.CARTES.get(u["cid"], {}).get("zone", 130))
        dire(f" sur tous les ennemis : {total} dégâts.")
    else:
        mult = 2.5 if e == "degats" else 1.4 if e == "stun" else (3.5 if cible["pv"] < cible["pvmax"] * 0.4 else 1.8)
        if u["trait"] == "charge":
            mult = data.TRAITS_BOSS["charge"] / 100
        d = frapper(u, cible, mult, journal, tous, True)
        dire(f" sur {cible['nom']} : {d} dégâts.")
        if e == "stun" and cible["pv"] > 0:
            etourdir(cible)


def photo(tous):
    """État de toutes les unités à un instant donné, pour l'affichage."""
    return [{"nom": u["nom"], "pv": max(0, u["pv"]), "pvmax": u["pvmax"], "camp": u["camp"], "bouclier": u["bouclier"],
             "jauge": u["jauge"], "cout": u["cout"], "cid": u["cid"], "inflige": u.get("inflige", 0),
             "ligne": u.get("ligne", "avant")} for u in tous]


def simuler_detail(equipe, adversaires, hemorragie=False):
    """Joue le combat automatiquement. Renvoie (victoire, tours) : chaque tour regroupe autant d'actions qu'il y a d'unités
    debout, avec ses moments forts, les dégâts infligés par chaque camp et l'état des unités à la fin."""
    tous = equipe + adversaires
    for x in tous:
        x["hemorragie"] = hemorragie   # donjons et raid : les soins sont réduits
    tours = []
    en_cours = lambda: len({c["camp"] for c in tous if c["pv"] > 0}) == 2
    for numero in range(1, 41):
        journal, ultis = [], []
        avant = {camp: sum(x["inflige"] for x in tous if x["camp"] == camp) for camp in (0, 1)}
        for _ in range(len([x for x in tous if x["pv"] > 0])):
            if not en_cours():
                break
            u = suivant(tous)
            if not commencer_action(u, tous, journal) or not en_cours():
                continue
            blesses = [a for a in vivants(tous, u["camp"]) if a is not u and a["pv"] < a["pvmax"] * 0.5]
            if u["cout"] and u["jauge"] >= u["cout"]:
                if u["camp"] == 0:
                    ultis.append(u["cid"])
                lancer_ulti(u, tous, None, journal, "✨" if u["camp"] == 0 else "🔥")
            elif u["kit"] == "Soraka" and blesses and u["pv"] > u["pvmax"] * 0.25:
                soin_soraka(u, min(blesses, key=lambda a: a["pv"] / a["pvmax"]), journal)
            else:
                attaque_simple(u, choisir_cible(u, visables(u, tous)), tous, journal)
            finir_action(u)
        degats = {camp: sum(x["inflige"] for x in tous if x["camp"] == camp) - avant[camp] for camp in (0, 1)}
        tours.append({"numero": numero, "journal": journal, "degats": degats, "ultis": ultis, "etat": photo(tous)})
        if not en_cours():
            return bool(vivants(tous, 0)), tours
    tours[-1]["journal"].append("⏱️ Le combat s'éternise : ton équipe bat en retraite.")
    return False, tours


def simuler(equipe, adversaires):
    """Version courte : renvoie (victoire, moments forts de tout le combat)."""
    victoire, tours = simuler_detail(equipe, adversaires)
    return victoire, [ligne for t in tours for ligne in t["journal"]]


def barre_pv(pv, pvmax, taille=8):
    """Barre de vie colorée : verte, puis jaune sous 50 %, rouge sous 25 %."""
    if pv <= 0:
        return "⬛" * taille
    ratio = pv / pvmax
    plein = max(1, round(taille * ratio))
    couleur = "🟩" if ratio > 0.5 else "🟨" if ratio > 0.25 else "🟥"
    return couleur * plein + "⬛" * (taille - plein)


def barre(actuel, maximum, taille=10):
    plein = max(0, min(taille, round(taille * actuel / maximum)))
    return "🟩" * plein + "⬛" * (taille - plein)


def meilleure_equipe(possedees):
    """Les trois cartes les plus puissantes du joueur."""
    connues = [c for c in possedees if c in data.CARTES]
    return sorted(connues, key=lambda c: -puissance(c, possedees[c]["niveau"], possedees[c]["etoiles"]))[:3]


def puissance_equipe(ids, possedees):
    return sum(puissance(c, possedees[c]["niveau"], possedees[c]["etoiles"]) for c in ids)


def reflets(equipe, facteur):
    """Adversaires d'entraînement de l'arène : une copie de ton équipe, plus ou moins forte."""
    copies = copy.deepcopy(equipe)
    for r in copies:
        r["pv"] = r["pvmax"] = int(r["pvmax"] * facteur)
        r["atk_base"] = int(r["atk_base"] * facteur)
        r["bouclier"] = int(r["bouclier"] * facteur)
        r["camp"] = 1
        r["nom"] = f"Reflet de {r['nom']}"
        maj(r)
    return copies


def rang_arene(points):
    """Renvoie (index, nom, emoji) du rang correspondant aux points."""
    index = max(k for k, r in enumerate(data.ARENE_RANGS) if points >= r[0])
    return index, data.ARENE_RANGS[index][1], data.ARENE_RANGS[index][2]


# ------------------------------ Combat manuel --------------------------------
def cibles_possibles(u, tous):
    """Ennemis que cette unité peut viser : tant qu'un tank adverse est debout, il faut passer par lui."""
    cibles = visables(u, tous)
    tanks = [c for c in cibles if c["role"] == "tank"]
    return tanks or cibles


def ulti_cible(u):
    """True si l'ulti de cette unité vise un ennemi précis (sinon il touche tout le monde ou aide l'équipe)."""
    return u["effet"] in ("degats", "stun", "execution")


def jouer_action(u, tous, ulti, cible, journal, special=None):
    """Applique l'action choisie par un joueur : attaque simple, ulti si la jauge est pleine, ou action spéciale
    (Soraka : "soin" sur un allié, ou "passer")."""
    if special == "soin":
        soin_soraka(u, cible, journal)
    elif special == "passer":
        journal.append(f"⏭️ {u['nom']} passe son tour.")
    elif ulti:
        lancer_ulti(u, tous, cible, journal)
    else:
        attaque_simple(u, cible, tous, journal, detail=True)
    finir_action(u)
