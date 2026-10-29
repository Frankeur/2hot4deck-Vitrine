"""Tout le contenu du jeu : cartes, taux des packs, réglages. C'est le fichier à modifier."""

# --- Raretés ------------------------------------------------------------------
RARETES = ["N", "R", "SR", "SSR", "UR"]
COULEURS = {"N": 0x9AA0A6, "R": 0x3B82F6, "SR": 0xA855F7, "SSR": 0xF59E0B, "UR": 0xE11D48}
EMOJIS = {"N": "⚪", "R": "🔵", "SR": "🟣", "SSR": "🟡", "UR": "💎"}
#           PV   attaque  niveau max
# UR : niveau 100 dès la première copie et pas d'étoiles. Au niveau 100, un UR vaut 5 % de plus qu'une SSR à 5 étoiles.
BASE = {"N": (300, 40, 20), "R": (420, 55, 30), "SR": (600, 80, 40), "SSR": (850, 110, 50), "UR": (956, 124, 100)}

# --- Rôles : (multiplicateur PV, multiplicateur attaque, vitesse, actions pour charger l'ulti)
# La vitesse décide de qui joue : un champion deux fois plus rapide joue deux fois plus souvent.
ROLES = {
    "tank":       (1.40, 0.75, 85, 4),
    "combattant": (1.15, 1.00, 100, 3),
    "assassin":   (0.85, 1.30, 125, 3),
    "mage":       (0.90, 1.20, 105, 4),
    "tireur":     (0.85, 1.25, 115, 3),
    "support":    (1.00, 0.80, 95, 4),
    "sbire":      (1.00, 1.00, 90, 0),   # pas d'ulti
}

# --- Résistances par rôle : (physique, magique). Dégâts subis = dégâts x 100 / (100 + résistance).
RESISTANCES = {"tank": (60, 50), "combattant": (45, 35), "assassin": (30, 30), "mage": (20, 30),
               "tireur": (25, 25), "support": (30, 40), "sbire": (20, 20), "boss": (40, 40)}
# Pour donner des valeurs particulières à une carte : "Galio": {"res": (50, 80), "vitesse": 90}
# Éveil des UR (12 octobre) : chaque UR qui partageait le kit de sa version de base gagne un pouvoir en plus.
KITS_EVEIL = {"lux_rebouclier": 40, "lux_mort": 190, "luxur_feu": 220, "luxur_brulure": 40, "luxur_glace": 190, "luxur_lumiere": 500, "xayah_plumes": 4, "xayah_plume": 25, "aatrox_vol": 80, "aatrox_passif": 40, "aatrox_zone": 135, "varus_depart": 1, "varus_marques": 2,
              "bard_actions": 2, "maokai_racines": 1, "maokai_bouclier": 20, "garen_execution": 30, "tristana_coups": 3, "jayce_second": 50,
              "xin_blocages": 3, "senna_bouclier": 12, "vayne_pen": 30, "akali_seuil": 50, "zeri_cumuls": 1, "nidalee_seuil": 60,
              "yone_zone": 95, "jax_cumuls": 3}
# Kits propres à trois UR (12 octobre) : Viego et Sylas copient l'actif d'un autre champion, Gragas est un tank qui repousse.
KITS_UR = {"viego_soin": 25, "viego_ulti": 240, "viego_fort": 380, "viego_seuil": 40,
           "sylas_ulti": 170, "sylas_vole": 40, "sylas_bonus": 40, "sylas_soin": 10,
           "gragas_soin": 2, "gragas_seuil": 40, "gragas_res": 15, "gragas_zone": 80, "gragas_lent": 15}
# Kits propres aux cartes LR (12 octobre) : mêmes mécaniques que le champion, en plus fort.
KITS_LR = {"ahri_vol": 25, "ahri_coups": 3, "ahri_ulti": 120, "ahri_max": 5, "azir_soldat": 18, "azir_max": 4, "azir_zone": 130, "azir_bouclier": 10, "ryze_rebond": 70, "ryze_ulti": 260, "ryze_tours": 2, "ryze_eclat": 120}
# 12 octobre (soir) : les UR des Worlds sont plus fortes que les autres, d'autant plus que l'équipe qui les porte est loin.
# % de PV et d'ATQ en plus, sur les cartes des joueurs seulement (les pros des Worlds n'en profitent pas).
# BLG +4 · HLE +6 (et Sylas, la plus rare de la LEC) · Gen.G +8 · T1 +10 (Bard +16 et Viego +11, ils étaient en retard).
# 13 octobre (soir) : équilibrage carte par carte, en % de PV et d'attaque, pour les cartes des joueurs seulement (les pros ne changent pas).
AJUST_CARTES = {"Camille": -15, "Talon": -12, "Sejuani": -12, "Yone": -10, "Leona": -7, "LeeSin": -5, "LuxUR": -5, "Janna": -3, "Graves": -2,
                "Thresh": 50, "Karthus": 28, "Syndra": 26, "Ziggs": 20, "AatroxUR": 12, "Ambessa": 3, "Zeri": 3,
                "JayceUR": 18, "ZeriUR": 6, "YoneUR": 4}   # 14 octobre (soir) : buff discret de 3 UR (joueurs seulement, les pros ne bougent pas)
JOUEUR_TANK = {"Graves"}
PROS_NOUVEAUX_KITS = {"Gen.G", "T1"}   # 13 octobre (21 h) : ces équipes des Worlds jouent les nouveaux kits (Graves tank, Corki, Renata), Faker non   # champions dont la carte de joueur joue en tank (13 octobre)
UR_PALIERS = {"JaxUR": 4, "AkaliUR": 6, "JayceUR": 6, "VarusUR": 6, "SylasUR": 6, "NidaleeUR": 8, "XayahUR": 8, "YoneUR": 8,
              "ZeriUR": 10, "BardUR": 16, "ViegoUR": 11,
              "AzirLR": 22, "RyzeLR": 25, "AhriLR": 28}   # 14 octobre (soir) : +10 % pour chaque LR (avant 12, 15, 18, 15). 13 octobre : les LR de Faker restent les meilleures cartes du jeu (cartes des joueurs seulement)
PARTICULARITES = {"Karthus": {"cout": 5, "zone": 200}, "Malphite": {"cout": 5, "zone": 180}, "Maokai": {"res": (55, 45)}, "Gragas": {"pv": 0.85}, "Lux": {"cout": 3}}   # cout : actions pour charger l'ulti
# Cartes qui frappent en magique (toutes les autres frappent en physique)
MAGIQUES = {"Galio", "Lux", "Sejuani", "Ahri", "Akali", "Katarina", "Zilean", "Karthus", "Teemo", "Veigar", "Sona",
            "Braum", "Malphite", "Annie", "Amumu", "Soraka", "Blitzcrank", "gromp", "sentinelle", "sbire_mage",
            "Swain", "Ekko", "Ezreal", "Leona", "Thresh", "Mordekaiser", "Nami", "Morgana", "Janna", "Orianna", "Rumble", "Leblanc", "Syndra", "Sylas", "Gwen", "Azir", "Ryze",
            "Ziggs", "Corki", "Nidalee", "Bard", "Renata"}

# --- Passifs et actifs personnalisés : tous les chiffres sont ici (en % sauf mention contraire) -------------
KITS = {
    "cumuls_max": 10, "cumul_atk": 3,          # Senna, Veigar, Nasus : +3 % ATQ par attaque, 10 fois au plus
    "jinx_vitesse": 3,                         # Jinx : +3 % de vitesse par attaque
    "execution": 15,                           # Zed (passif) et Garen (ulti) achèvent sous 15 % de PV, sauf les boss
    "vayne_bonus": 60,                         # Vayne : une attaque sur trois fait +60 %
    "sejuani_pv": 6, "sejuani_res": 10, "malphite_res": 40, "leona_zone": 45, "leona_res": 10, "leona_soleil": 15,
    "yasuo_bouclier": 6, "yasuo_actions": 2, "yasuo_ulti": 180,   # 14 octobre : nerf (avant 10 %, 3 actions, 250 %)
    "darius_vol": 5, "darius_res": 8,          # par ulti lancé
    "aatrox_vol": 20, "aatrox_ulti": 220, "aatrox_ulti_vol": 50,
    "zilean_vitesse": 8, "zilean_ranime": 40, "zilean_soin": 25, "sona_atk": 12, "sona_lent": 25, "sona_soin": 12,
    "karthus_mort": 130, "garen_regen": 6, "ashe_lent": 15, "braum_coups": 4, "tryndamere_pv": 25,
    "yi_vitesse": 20, "yi_actions": 3, "tibbers": 60, "tibbers_actions": 3, "amumu_res": 30,
    "nasus_pv": 20, "nasus_feu": 40, "nasus_actions": 3, "soraka_soin": 20, "soraka_cout": 10, "blitz_passif": 30,
    "galio_zone": 100, "galio_res": 20, "lux_bouclier": 185, "lux_feu": 150, "lux_brulure": 35, "lux_lumiere": 420,
    "graves_tank_res": 5, "graves_cumul": 2, "graves_max": 8, "graves_tank_ulti": 200, "graves_tank_eclat": 30, "sejuani_ulti2": 100, "sejuani_lent": 25,
    "corki_coups": 3, "corki_eclat": 90, "corki_missiles": 4, "corki_gros": 45, "renata_passif": 5, "renata_equipe": 12, "renata_protege": 2, "senna_zone": 100, "senna_bouclier": 10,
    "akali": 180, "teemo_zone": 60, "veigar_atk": 5,
    # Vague du 11 octobre 2026
    "nami_soin": 18, "nami_vitesse": 10, "caitlyn_bonus": 100, "caitlyn_coups": 4, "caitlyn_ulti": 250,
    "vi_ulti": 180, "vi_bouclier": 12, "shaco_premier": 40, "shaco_ulti": 160, "shaco_zone": 50,
    "morgana_zone": 110, "morgana_vol": 25, "morgana_seuil": 50,
    "janna_bouclier": 6, "janna_soin": 25, "talon_saigne": 30, "talon_coups": 3, "talon_zone": 75, "talon_blocages": 1,
    # Tour des pros, palier Karmine Corp
    "rumble_brule": 20, "rumble_zone": 100, "rumble_ulti_brule": 35, "gnar_coups": 4, "gnar_bonus": 60, "gnar_zone": 100, "gnar_lent": 20,
    "jayce_canon": 30, "jayce_res": 12, "jayce_ulti": 260, "viego_soin": 20, "viego_atk": 15, "viego_ulti": 200, "viego_fort": 320, "viego_seuil": 40,
    "qiyana_premier": 40, "qiyana_zone": 90, "khazix_isole": 20, "khazix_ulti": 150, "draven_cumul": 14, "draven_max": 5, "draven_zone": 75,
    "kalista_lance": 80, "kalista_max": 6, "kalista_ulti": 200,
    # Worlds, phase suisse (Invictus Gaming, G2, BLG)
    "fiora_coups": 3, "fiora_bonus": 50, "fiora_soin": 8, "fiora_ulti": 70, "fiora_equipe": 15,
    "leblanc_bonus": 45, "leblanc_ulti": 160, "leblanc_echo": 90, "syndra_max": 7, "syndra_base": 110, "syndra_sphere": 50,
    "xayah_max": 5, "xayah_base": 40, "xayah_plume": 15, "sylas_ulti": 200, "sylas_vol": 15, "sylas_bonus": 40, "sylas_soin": 10,
    "tristana_coups": 4, "tristana_bonus": 80, "tristana_eclat": 40, "tristana_ulti": 220,
    "ksante_pv": 2, "ksante_ulti": 150, "ksante_atk": 60, "ksante_vol": 15, "ksante_res": 30,
    "ornn_pv": 5, "ornn_zone": 90, "ornn_lent": 25, "jax_ulti": 160, "jax_blocages": 2,
    "camille_bouclier": 12, "camille_actions": 3, "camille_ulti": 220, "camille_res": 20,
    "gwen_pv": 3, "gwen_ulti": 70, "gwen_vol": 40, "aphelios_vol": 25, "aphelios_bonus": 35, "aphelios_lent": 20, "aphelios_zone": 130,
    # Anciens champions remis en service pour les Worlds
    "yone_coups": 3, "yone_echo": 60, "yone_zone": 85, "ahri_vol": 15, "ahri_ulti": 90,
    "kaisa_coups": 4, "kaisa_bonus": 80, "kaisa_ulti": 180, "kaisa_bouclier": 20, "ezreal_cumul": 6, "ezreal_max": 5, "ezreal_zone": 140,
    "leesin_bouclier": 5, "leesin_ulti": 220, "leesin_eclat": 60, "jhin_coups": 4, "jhin_bonus": 120, "jhin_tir": 60, "jhin_dernier": 120,
    "thresh_ame": 15, "thresh_zone": 70, "thresh_lent": 30, "thresh_bouclier": 12,
    "azir_soldat": 15, "azir_max": 3, "azir_zone": 120, "ryze_coups": 3, "ryze_rebond": 70, "ryze_ulti": 200, "ryze_eclat": 60,
    # Worlds, phases finales (HLE, Gen.G, T1)
    "ambessa_coups": 3, "ambessa_echo": 50, "ambessa_bouclier": 6, "ambessa_ulti": 240, "ziggs_coups": 3, "ziggs_bonus": 70, "ziggs_zone": 160,
    "varus_max": 3, "varus_ulti": 110, "varus_marque": 30, "corki_pen": 30, "corki_missile": 80, "nidalee_seuil": 50, "nidalee_bonus": 30,
    "nidalee_ulti": 200, "nidalee_soin": 15, "graves_res": 15, "graves_ulti": 200, "graves_eclat": 70, "zeri_vitesse": 5, "zeri_zone": 110,
    "zeri_elan": 25, "maokai_coups": 3, "maokai_soin": 4, "maokai_zone": 60, "maokai_racines": 1, "xin_coups": 3, "xin_soin": 8, "xin_zone": 100, "xin_blocages": 2, "bard_actions": 3, "bard_soin": 10, "bard_zone": 60,
    "bard_stun": 2, "bard_tours": 2, "renata_atk": 8, "renata_bouclier": 15,
    "pv_max_plafond": 30,                      # dégâts en % des PV max de la cible : jamais plus que 30 % de l'attaque du lanceur contre un boss
    "mf_bonus": 30, "mf_vague": 60, "mf_vagues": 4, "orianna_cumul": 8, "orianna_max": 5, "orianna_zone": 140, "orianna_stun": 2,
}
HEMORRAGIE = 50               # % des soins conservés dans les donjons et le raid (règle « Hémorragie »)
_K = KITS
# Ce que les joueurs lisent sur la fiche de la carte : (passif, actif). None = pas de passif.
TEXTES_KITS = {
    "Galio": (None, f"Frappe tous les ennemis à {_K['galio_zone']} % et donne +{_K['galio_res']} de résistances à ses alliés pendant 2 actions."),
    "Lux": ("Quand Lux tombe, elle étourdit l'ennemi qui tape le plus fort.", f"Élémentaliste : ses actifs alternent le feu (tous les ennemis à {_K['lux_feu']} %, qui brûlent : {_K['lux_brulure']} % de son ATQ pendant 2 actions) et la lumière ({_K['lux_lumiere']} % sur l'ennemi le plus dangereux)."),
    "Vayne": (f"Une attaque sur trois inflige +{_K['vayne_bonus']} % de dégâts.", "Frappe un ennemi à 250 %."),
    "Leona": (f"Ses coups marquent l'ennemi de la lumière du soleil : le prochain coup d'un allié sur lui fait +{_K['leona_soleil']} %.",
              f"Frappe tous les ennemis à {_K['leona_zone']} %, étourdit celui qui tape le plus fort, et gagne +{_K['leona_res']} de résistances pendant 2 actions."),
    "Sejuani": ("Tank de première ligne (pas de bonus permanent depuis le 13 octobre).", f"Frappe un ennemi à {_K['sejuani_ulti2']} % et l'étourdit ; les autres ennemis sont ralentis de {_K['sejuani_lent']} % pendant 2 actions."),
    "Akali": ("Sous 50 % de PV, devient intouchable jusqu'à la fin de sa prochaine action (une fois par combat).",
              f"Frappe un ennemi à {_K['akali']} %, et une seconde fois s'il passe sous 40 % de PV."),
    "Yasuo": (f"Bouclier de {_K['yasuo_bouclier']} % de ses PV pendant ses {_K['yasuo_actions']} premières actions, rechargé s'il n'a pas été touché.",
              f"Frappe un ennemi à {_K['yasuo_ulti']} % et bloque la prochaine attaque qui le vise."),
    "Zed": (f"Achève un ennemi passé sous {_K['execution']} % de PV (une fois par combat, pas les boss).", "Frappe à 180 %, 350 % si la cible est sous 40 % de PV."),
    "Senna": (f"+{_K['cumul_atk']} % d'ATQ à chaque attaque ({_K['cumuls_max']} fois au plus).",
              f"Frappe tous les ennemis à {_K['senna_zone']} % et pose sur toute son équipe un bouclier de {_K['senna_bouclier']} % des PV."),
    "Darius": (f"Chaque ulti lui donne +{_K['darius_vol']} % de vol de vie et +{_K['darius_res']} de résistances.",
               "Frappe à 180 %, 350 % si la cible est sous 40 % de PV. S'il tue, il recommence sur un autre ennemi."),
    "Aatrox": (f"{_K['aatrox_vol']} % de vol de vie sur chaque attaque.", f"Frappe un ennemi à {_K['aatrox_ulti']} % et se soigne de {_K['aatrox_ulti_vol']} % des dégâts."),
    "Zilean": (f"+{_K['zilean_vitesse']} % de vitesse pour toute son équipe.", f"Ranime un allié K.O. avec {_K['zilean_ranime']} % de ses PV, sinon soigne l'équipe de {_K['zilean_soin']} %."),
    "Jinx": (f"+{_K['jinx_vitesse']} % de vitesse à chaque attaque ({_K['cumuls_max']} fois au plus).", "Frappe à 180 %, 350 % si la cible est sous 40 % de PV."),
    "Karthus": (f"À sa mort, frappe une dernière fois tous les ennemis à {_K['karthus_mort']} %.", "Frappe tous les ennemis à 200 %. Long à charger."),
    "Teemo": ("Impossible à cibler tant qu'aucun de ses alliés n'est tombé (les attaques de zone le touchent).",
              f"Frappe tous les ennemis à {_K['teemo_zone']} % et les aveugle : leur prochaine attaque normale rate."),
    "Veigar": (f"+{_K['veigar_atk']} % d'ATQ à chaque attaque ({_K['cumuls_max']} fois au plus).", "Frappe à 180 %, 350 % si la cible est sous 40 % de PV."),
    "Garen": (f"Récupère {_K['garen_regen']} % de ses PV à chacune de ses actions.", f"Frappe à 180 % et exécute la cible si elle passe sous {_K['execution']} % de PV (pas les boss)."),
    "Sona": (f"+{_K['sona_atk']} % d'ATQ pour toute son équipe.", f"Ralentit tous les ennemis de {_K['sona_lent']} % pendant 2 actions et soigne son équipe de {_K['sona_soin']} %."),
    "Ashe": (f"Ses attaques ralentissent la cible de {_K['ashe_lent']} % pendant 2 actions.", "Frappe un ennemi à 140 % et l'étourdit."),
    "Braum": (f"Marque l'ennemi qu'il frappe : au {_K['braum_coups']}e coup reçu, la cible passe son tour.", "Bloque la prochaine attaque contre chacun de ses alliés."),
    "Tryndamere": (f"Survit au coup fatal avec {_K['tryndamere_pv']} % de ses PV (une fois par combat).", "Frappe un ennemi à 250 %."),
    "MasterYi": (f"+{_K['yi_vitesse']} % de vitesse pendant ses {_K['yi_actions']} premières actions.", "Frappe un ennemi à 250 %."),
    "Malphite": (f"+{_K['malphite_res']} de résistance physique.", "Frappe tous les ennemis à 180 %. Long à charger."),
    "Annie": (None, f"Frappe tous les ennemis à 130 %, puis Tibbers frappe un ennemi à {_K['tibbers']} % pendant {_K['tibbers_actions']} actions."),
    "Amumu": (f"Après son ulti, +{_K['amumu_res']} de résistances jusqu'à sa prochaine action.", "Frappe tous les ennemis à 130 % et les force à l'attaquer à leur prochaine action."),
    "Nasus": (f"+{_K['cumul_atk']} % d'ATQ à chaque attaque réussie ({_K['cumuls_max']} fois au plus).",
              f"Gagne {_K['nasus_pv']} % de PV max et brûle tous les ennemis à {_K['nasus_feu']} % pendant {_K['nasus_actions']} actions."),
    "Soraka": (f"Au lieu d'attaquer, peut rendre {_K['soraka_soin']} % de PV à un allié contre {_K['soraka_cout']} % des siens. En combat automatique, elle le fait dès qu'un allié passe sous 50 %.",
               "Soigne toute son équipe de 30 % des PV max."),
    "Blitzcrank": (f"À chacune de ses actions, électrise un ennemi au hasard à {_K['blitz_passif']} %.", "Frappe tous les ennemis à 130 %."),
    "Nami": (f"Ses soins donnent +{_K['nami_vitesse']} % de vitesse à ses alliés pendant 2 actions.", f"Soigne toute son équipe de {_K['nami_soin']} % des PV max et étourdit l'ennemi qui frappe le plus fort."),
    "Caitlyn": (f"Une attaque sur {_K['caitlyn_coups']} est un tir en pleine tête : +{_K['caitlyn_bonus']} % de dégâts.", f"Frappe l'ennemi le plus blessé à {_K['caitlyn_ulti']} %."),
    "Vi": (f"Gagne un bouclier de {_K['vi_bouclier']} % de ses PV max quand elle lance son actif.", f"Fonce sur l'ennemi qui frappe le plus fort : {_K['vi_ulti']} % et étourdissement. Impossible à bloquer."),
    "Shaco": (f"Sa première attaque du combat inflige +{_K['shaco_premier']} % de dégâts.", f"Frappe un ennemi à {_K['shaco_ulti']} %, son clone explose sur tous les ennemis ({_K['shaco_zone']} %) et bloquera la prochaine attaque qui le vise."),
    "Morgana": (f"Se soigne de {_K['morgana_vol']} % des dégâts de son actif.", f"Frappe tous les ennemis à {_K['morgana_zone']} % et étourdit ceux qui sont sous {_K['morgana_seuil']} % de PV (pas les boss)."),
    "Janna": (f"À chacune de ses actions, pose un bouclier de {_K['janna_bouclier']} % de ses PV max sur l'allié le plus blessé.", f"Soigne toute son équipe de {_K['janna_soin']} % des PV max et vide la jauge d'actif des ennemis (les boss n'en perdent qu'un cran)."),
    "Rumble": (f"Ses attaques embrasent la cible : {_K['rumble_brule']} % de son attaque au début de ses 2 prochaines actions.", f"Frappe tous les ennemis à {_K['rumble_zone']} % et les embrase tous ({_K['rumble_ulti_brule']} % de son attaque, 2 actions)."),
    "Gnar": (f"Une attaque sur {_K['gnar_coups']} est portée en Méga Gnar : +{_K['gnar_bonus']} % de dégâts et étourdissement (pas les boss).", f"Frappe tous les ennemis à {_K['gnar_zone']} % et les ralentit de {_K['gnar_lent']} % pendant 2 actions."),
    "Jayce": (f"Alterne canon (+{_K['jayce_canon']} % de dégâts) et marteau (−{_K['jayce_res']} de résistances sur la cible pendant 2 actions).", f"Tire sur l'ennemi le plus blessé à {_K['jayce_ulti']} %."),
    "Viego": (f"Quand il tue un ennemi, il récupère {_K['viego_soin']} % de ses PV max et gagne +{_K['viego_atk']} % d'ATQ jusqu'à la fin du combat.", f"Frappe à {_K['viego_ulti']} %, ou à {_K['viego_fort']} % si la cible a moins de {_K['viego_seuil']} % de ses PV."),
    "Qiyana": (f"Son premier coup sur chaque ennemi inflige +{_K['qiyana_premier']} % de dégâts.", f"Frappe tous les ennemis à {_K['qiyana_zone']} % et étourdit l'un d'eux au hasard (pas les boss)."),
    "Khazix": (f"+{_K['khazix_isole']} % de dégâts quand il ne reste que deux ennemis ou moins.", f"Frappe l'ennemi le plus blessé à {_K['khazix_ulti']} % et devient intouchable jusqu'à la fin de sa prochaine action."),
    "Draven": (f"+{_K['draven_cumul']} % de dégâts par attaque ({_K['draven_max']} fois au plus) ; il perd tout dès qu'il est touché.", f"Ses haches traversent tous les ennemis deux fois, à {_K['draven_zone']} % chacune."),
    "Kalista": (f"Chaque attaque plante une lance dans la cible ({_K['kalista_max']} au plus).", f"Arrache toutes les lances : {_K['kalista_lance']} % par lance sur chaque ennemi transpercé. Sans lance, frappe à {_K['kalista_ulti']} %."),
    "Fiora": (f"Une attaque sur {_K['fiora_coups']} touche un point vital : +{_K['fiora_bonus']} % de dégâts, et elle récupère {_K['fiora_soin']} % de ses PV max.", f"Grand défi : frappe la cible 4 fois à {_K['fiora_ulti']} %. Si elle tombe, toute l'équipe récupère {_K['fiora_equipe']} % de ses PV."),
    "Leblanc": (f"Sa deuxième attaque d'affilée sur la même cible fait +{_K['leblanc_bonus']} % de dégâts.", f"Frappe la cible à {_K['leblanc_ulti']} %, puis son reflet frappe l'ennemi le plus blessé à {_K['leblanc_echo']} %."),
    "Syndra": (f"Chaque attaque crée une sphère ({_K['syndra_max']} au plus).", f"Projette toutes ses sphères sur une cible : {_K['syndra_base']} % + {_K['syndra_sphere']} % par sphère."),
    "Xayah": (f"Chaque attaque laisse une plume au sol ({_K['xayah_max']} au plus).", f"S'envole (intouchable jusqu'à la fin de sa prochaine action) et rappelle ses plumes : tous les ennemis à {_K['xayah_base']} % + {_K['xayah_plume']} % par plume."),
    "Sylas": (f"Après son actif, ses 2 attaques suivantes font +{_K['sylas_bonus']} % et lui rendent {_K['sylas_soin']} % de ses PV max.", f"Frappe l'ennemi qui tape le plus fort à {_K['sylas_ulti']} % et lui vole {_K['sylas_vol']} % de son attaque pendant 3 actions."),
    "Tristana": (f"Une attaque sur {_K['tristana_coups']} fait exploser sa charge : +{_K['tristana_bonus']} % de dégâts, et {_K['tristana_eclat']} % sur un autre ennemi.", f"Frappe à {_K['tristana_ulti']} % et repousse la cible : son actif en préparation est annulé."),
    "KSante": (f"Ses attaques infligent en plus {_K['ksante_pv']} % des PV max de la cible.", f"Tous azimuts : frappe à {_K['ksante_ulti']} %, puis échange {_K['ksante_res']} de résistances contre +{_K['ksante_atk']} % d'attaque et {_K['ksante_vol']} % de vol de vie jusqu'à la fin du combat (une fois)."),
    "Ornn": (f"Forgeron : toute son équipe commence avec +{_K['ornn_pv']} % de PV max.", f"Frappe tous les ennemis à {_K['ornn_zone']} %, les ralentit de {_K['ornn_lent']} % pendant 2 actions et en étourdit un."),
    "Jax": (f"+{_K['cumul_atk']} % d'attaque à chaque attaque ({_K['cumuls_max']} fois au plus).", f"Frappe à {_K['jax_ulti']} %, étourdit la cible et bloque les {_K['jax_blocages']} prochaines attaques qui le visent."),
    "Camille": (f"Gagne un bouclier de {_K['camille_bouclier']} % de ses PV max toutes les {_K['camille_actions']} actions.", f"Enferme la cible : {_K['camille_ulti']} %, étourdissement, et −{_K['camille_res']} de résistances pendant 2 actions."),
    "Gwen": (f"Ses attaques infligent en plus {_K['gwen_pv']} % des PV max de la cible.", f"Frappe la cible 3 fois à {_K['gwen_ulti']} % et récupère {_K['gwen_vol']} % des dégâts infligés."),
    "Aphelios": (f"Change d'arme à chaque attaque : vol de vie de {_K['aphelios_vol']} %, puis +{_K['aphelios_bonus']} % de dégâts, puis ralentissement de {_K['aphelios_lent']} %.", f"Frappe tous les ennemis à {_K['aphelios_zone']} %."),
    "Yone": (f"Une attaque sur {_K['yone_coups']} est doublée par son épée spirituelle ({_K['yone_echo']} % de plus).", f"Frappe tous les ennemis à {_K['yone_zone']} % et étourdit le plus blessé."),
    "Ahri": (f"{_K['ahri_vol']} % de vol de vie sur ses attaques.", f"Trois charges à {_K['ahri_ulti']} %, chacune sur l'ennemi le plus blessé."),
    "Kaisa": (f"Ses attaques marquent la cible : à la {_K['kaisa_coups']}e marque, le plasma éclate (+{_K['kaisa_bonus']} % de dégâts).", f"Fond sur l'ennemi le plus blessé à {_K['kaisa_ulti']} % et gagne un bouclier de {_K['kaisa_bouclier']} % de ses PV max."),
    "Ezreal": (f"+{_K['ezreal_cumul']} % de dégâts par attaque ({_K['ezreal_max']} fois au plus).", f"Frappe tous les ennemis à {_K['ezreal_zone']} %."),
    "LeeSin": (f"Gagne un bouclier de {_K['leesin_bouclier']} % de ses PV max à chacune de ses actions.", f"Frappe la cible à {_K['leesin_ulti']} % et l'étourdit ; elle est projetée sur les autres ennemis ({_K['leesin_eclat']} %)."),
    "Jhin": (f"Sa {_K['jhin_coups']}e balle est toujours un coup de grâce : +{_K['jhin_bonus']} % de dégâts.", f"Quatre tirs sur l'ennemi le plus blessé : trois à {_K['jhin_tir']} %, le dernier à {_K['jhin_dernier']} %."),
    "Thresh": (f"Récolte les âmes : gagne un bouclier de {_K['thresh_ame']} % de ses PV max à chaque ennemi K.O.", f"Frappe tous les ennemis à {_K['thresh_zone']} %, les ralentit de {_K['thresh_lent']} % pendant 2 actions et protège l'allié le plus blessé ({_K['thresh_bouclier']} % de ses PV max)."),
    "Azir": (f"Invoque un soldat de sable à chacune de ses actions ({_K['azir_max']} au plus) : +{_K['azir_soldat']} % de dégâts par soldat.", f"Sa phalange charge : tous les ennemis à {_K['azir_zone']} %, et les actifs qu'ils préparaient sont annulés."),
    "Ryze": (f"Une attaque sur {_K['ryze_coups']} rebondit sur un autre ennemi ({_K['ryze_rebond']} %).", f"Enferme la cible dans sa Prison runique : {_K['ryze_ulti']} % et étourdissement, puis la Surcharge frappe les autres ennemis ({_K['ryze_eclat']} %)."),
    "Ambessa": (f"Une attaque sur {_K['ambessa_coups']} est doublée ({_K['ambessa_echo']} % de plus) et lui donne un bouclier de {_K['ambessa_bouclier']} % de ses PV max.", f"Fond sur l'ennemi le plus blessé : {_K['ambessa_ulti']} % et étourdissement."),
    "Ziggs": (f"Une attaque sur {_K['ziggs_coups']} est une bombe : +{_K['ziggs_bonus']} % de dégâts.", f"Méga-bombe : tous les ennemis à {_K['ziggs_zone']} %."),
    "Varus": (f"Chaque attaque pose une marque de flétrissure sur la cible ({_K['varus_max']} au plus).", f"Enchaîne la cible : {_K['varus_ulti']} % + {_K['varus_marque']} % par marque, étourdissement. Avec {_K['varus_max']} marques, la corruption étourdit aussi un autre ennemi."),
    "Corki": (f"Ses attaques ignorent {_K['corki_pen']} % des résistances, et une attaque sur {_K['corki_coups']} envoie un missile à {_K['corki_eclat']} % sur un autre ennemi.", f"{_K['corki_missiles']} missiles à {_K['corki_missile']} % sur des ennemis au hasard, puis le gros missile sur tous les ennemis à {_K['corki_gros']} %."),
    "Nidalee": (f"+{_K['nidalee_bonus']} % de dégâts contre les ennemis sous {_K['nidalee_seuil']} % de PV.", f"Bondit en couguar sur l'ennemi le plus blessé : {_K['nidalee_ulti']} %, et elle récupère {_K['nidalee_soin']} % de ses PV max."),
    "Graves": (f"Joue en tank : +{_K['graves_tank_res']} de résistance physique, puis +{_K['graves_cumul']} de résistances à chaque attaque ({_K['graves_max']} fois au plus).", f"Tire sur la cible à {_K['graves_tank_ulti']} % ; l'explosion touche les autres ennemis ({_K['graves_tank_eclat']} %)."),
    "Zeri": (f"+{_K['zeri_vitesse']} % de vitesse à chaque attaque ({_K['cumuls_max']} fois au plus).", f"Frappe tous les ennemis à {_K['zeri_zone']} % et gagne +{_K['zeri_elan']} % de vitesse pendant 3 actions."),
    "Maokai": (f"Une attaque sur {_K['maokai_coups']} lui rend {_K['maokai_soin']} % de ses PV max.", f"Frappe tous les ennemis à {_K['maokai_zone']} % et enracine le premier : il passe son prochain tour."),
    "XinZhao": (f"Une attaque sur {_K['xin_coups']} lui rend {_K['xin_soin']} % de ses PV max.", f"Balaie tous les ennemis à {_K['xin_zone']} % et bloque les {_K['xin_blocages']} prochaines attaques qui le visent."),
    "Bard": (f"Toutes les {_K['bard_actions']} actions, un carillon soigne l'allié le plus blessé de {_K['bard_soin']} % de ses PV max.", f"Frappe tous les ennemis à {_K['bard_zone']} % et en fige {_K['bard_stun']} au hasard pendant {_K['bard_tours']} tours (pas les boss)."),
    "Renata": (f"Toute son équipe gagne +{_K['renata_atk']} % d'attaque, et à chaque action elle soigne l'allié le plus blessé de {_K['renata_passif']} % de ses PV max.", f"Ranime un allié K.O. avec la moitié de ses PV ; sinon, un bouclier de {_K['renata_equipe']} % de leurs PV max protège tous ses alliés, et le plus fragile ne peut pas tomber pendant {_K['renata_protege']} actions."),
    "Talon": (f"Une attaque sur {_K['talon_coups']} fait saigner la cible : {_K['talon_saigne']} % de son attaque au début de ses 2 prochaines actions.", f"Frappe tous les ennemis à {_K['talon_zone']} % et bloque la prochaine attaque qui le vise."),
    "MissFortune": (f"+{_K['mf_bonus']} % de dégâts quand elle change de cible.", f"Barrage de balles : {_K['mf_vagues']} vagues à {_K['mf_vague']} % sur tous les ennemis."),
    "Orianna": (f"+{_K['orianna_cumul']} % de dégâts par attaque d'affilée sur la même cible ({_K['orianna_max']} fois au plus).", f"Frappe tous les ennemis à {_K['orianna_zone']} % et étourdit {_K['orianna_stun']} d'entre eux au hasard (pas les boss)."),
}

# --- Items : ils se fabriquent à la forge avec des composants gagnés en donjon. Un item s'équipe sur un champion.
# effet : atk, pv, vitesse, ulti, vol, pen (en %) · res_phys, res_mag (en points) · ange, zhonya, redemption, elan (voir texte)
# valeurs : une par niveau (refabriquer un item déjà possédé le fait monter d'un niveau)
ITEMS = {
    "lame_infini":  ("Lame d'infini", "⚔️", "atk", (15, 20, 25), "+{} % d'ATQ"),
    "rabadon":      ("Coiffe de Rabadon", "🎩", "ulti", (20, 28, 36), "+{} % de dégâts d'ulti"),
    "warmog":       ("Armure de Warmog", "💚", "pv", (20, 27, 34), "+{} % de PV"),
    "epineuse":     ("Cotte épineuse", "🌵", "res_phys", (30, 40, 50), "+{} de résistance physique"),
    "visage":       ("Visage spirituel", "👻", "res_mag", (30, 40, 50), "+{} de résistance magique"),
    "bottes":       ("Bottes de rapidité", "👟", "vitesse", (12, 16, 20), "+{} % de vitesse"),
    "soif_de_sang": ("Soif-de-sang", "🩸", "vol", (12, 16, 20), "{} % de vol de vie"),
    "ange":         ("Ange gardien", "😇", "ange", (30, 40, 50), "Se relève une fois par combat avec {} % de ses PV"),
    "zhonya":       ("Sablier de Zhonya", "⏳", "zhonya", (30, 40, 50), "Sous {} % de PV, devient intouchable jusqu'à la fin de sa prochaine action (une fois par combat)"),
    "danseur":      ("Danseur fantôme", "💨", "elan", (50, 75, 100), "Commence le combat avec sa jauge d'action remplie à {} %"),
    "rappel":       ("Rappel mortel", "🏹", "pen", (30, 38, 46), "Ignore {} % des résistances de la cible"),
    "redemption":   ("Rédemption", "✝️", "redemption", (10, 14, 18), "À sa mort, soigne ses alliés de {} % de leurs PV"),
}
ITEM_NIVEAU_MAX = 3
ITEM_ETAGE = 20                 # vaincre le boss de cet étage (le Héraut) offre un item au choix parmi trois, une seule fois

# Composants : (nom, emoji)
COMPOSANTS = {
    "epee": ("Épée longue", "🗡️"), "pioche": ("Pioche", "⛏️"), "dague": ("Dague", "🔪"),
    "cristal": ("Cristal de rubis", "♦️"), "cotte": ("Cotte de mailles", "🛡️"), "cape": ("Cape de négation", "🧥"),
    "baton": ("Bâton trop grand", "🪄"), "tome": ("Tome d'amplification", "📕"), "bottes": ("Bottes", "🥾"),
}
# Recette de chaque item : ses deux composants
RECETTES = {
    "lame_infini": ("epee", "pioche"), "rabadon": ("baton", "tome"), "warmog": ("cristal", "cotte"),
    "epineuse": ("cotte", "dague"), "visage": ("cape", "cristal"), "bottes": ("bottes", "dague"),
    "soif_de_sang": ("epee", "cristal"), "ange": ("pioche", "cotte"), "zhonya": ("baton", "cotte"),
    "danseur": ("dague", "pioche"), "rappel": ("epee", "dague"), "redemption": ("tome", "cape"),
}
RECETTE_QUANTITES = (3, 5, 8)   # exemplaires de CHAQUE composant pour fabriquer le niveau 1, 2, 3

# --- Donjons : le seul endroit où l'on gagne des composants. (nom, emoji, composants qu'on y trouve)
DONJONS = [
    ("Armurerie de Noxus", "⚔️", ("epee", "pioche", "dague")),
    ("Bastion de Demacia", "🏰", ("cristal", "cotte", "cape")),
    ("Académie de Piltover", "🔮", ("baton", "tome", "bottes")),
]
DONJON_ESSAIS = 3              # ancien réglage (3 victoires par jour), gardé pour les anciennes notes de mise à jour
DONJON_STOCK = 5               # victoires de donjon en réserve au maximum (12 octobre)
DONJON_DELAI = 5 * 3600        # une victoire de donjon revient toutes les 5 heures
DONJON_BUTIN = 2               # composants par victoire, +1 tous les DONJON_PALIER étages atteints dans la tour
DONJON_PALIER = 30
DONJON_ENSEMBLE = 0.7          # le gardien et le boss arrivent ensemble : leur force est ramenée à cette part de celle des descentes
DONJON_RETARD = 2              # les gardiens ont la force de ton étage moins 2
# Donjons défi : un combat très dur, à gagner une seule fois, qui donne un totem permanent au compte.
# (force des gardiens = étage de la tour équivalent, nouveau délai de recharge de l'énergie en minutes)
# (niveau de compte requis, force des gardiens = étage de la tour équivalent). Le dernier est le défi final, très dur.
DEFIS = [(10, 10), (20, 30), (30, 50), (40, 70), (50, 95)]
# Charges de Châtiment : une charge = une carte de jungle. Le stock dépend du niveau de compte, la recharge et la mise des défis gagnés.
CHARGES_PALIERS = [(1, 3), (10, 4), (20, 5), (30, 6), (40, 8), (50, 12)]   # (à partir de ce niveau de compte, charges maximum)
CHARGES_DELAI = [360, 330, 300, 270, 240, 180]    # minutes pour regagner une charge, selon le nombre de défis gagnés (0 à 5)
CHARGES_MISE = [1, 2, 2, 3, 4, 4]                  # charges jouables sur une seule carte, selon le nombre de défis gagnés
JUNGLE_BUTIN = 5                # butin d'un buisson, en nombre de chasses, pour une charge misée
CLEAR_RAPIDE = 50               # % du butin d'un clear complet donné par le clear rapide (instantané, sans jouer)
NIVEAU_COMPTE_MAX = 100         # dernier niveau de compte (50 jusqu'au 12 octobre)
NIVEAU_SANS_CHARGE = NIVEAU_COMPTE_MAX   # 14 octobre : chaque niveau donne une charge de jungle, jusqu'au dernier (avant : jusqu'au 50)
# Réserve d'XP : chaque doublon tiré la remplit (en nombre de chasses de jungle à ton étage). À dépenser sur la carte de ton choix.
RESERVE_XP = {"N": 3, "R": 6, "SR": 15, "SSR": 50, "UR": 200}
RESERVE_MAX = 40000             # XP gardée au maximum (de quoi monter une carte du niveau 1 au niveau 50)
# Clés de donjon : elles s'accumulent avec le temps et servent à ouvrir le coffre à la fin d'un donjon (une clé = un butin).
CLES_DELAI = 8 * 3600          # secondes pour gagner une clé
CLES_MAX = 6                   # clés gardées au maximum
CLES_DEPART = 3                # clés d'un nouveau compte
# Donjon de Noxus (nouvelle formule) : une descente en plusieurs salles, PV conservés, marché de Darius, boss, puis coffre.
NOXUS = {
    "force": 1.0,              # force des gardiens par rapport à un étage normal de la tour à la hauteur du joueur
    "legion_atk": 1.15,        # les légionnaires frappent fort (dégâts physiques)
    "elite": 1.2,              # (ancienne salle d'élite, plus utilisée)
    "darius": (3.5, 1.3),      # Darius : multiplicateurs de PV et d'attaque
    "boss": (2.8, 1.2),        # Swain : multiplicateurs de PV et d'attaque
    "butin_base": 0.35,        # coffre : cette part de ce que donnait une victoire de l'ancien donjon (2 + 1 par 10 étages), 1 au minimum
    "code": 4,                 # serrure : nombre de sceaux du code (tous différents, parmi 5)
    "vague": (2, 1.0),         # vague de gardes à chaque essai raté : nombre de légionnaires, force par rapport à un étage normal
}
# Les trois descentes. garde : (nom, PV, attaque) des soldats des vagues ; gardien et boss : (champion, nom affiché, PV, attaque, emoji, texte).
DESCENTES = [
    {"cle": "noxus", "fond": "noxus", "sceaux": ["⚔️", "🛡️", "🪓", "🩸", "🦅"], "garde": ("Légionnaire noxien", 1.0, 1.15),
     "gardien": ("Darius", "Darius, Main de Noxus", 3.5, 1.3, "🪓", "*« Ici, seule la force compte. »*"),
     "boss": ("Swain", "Swain, Grand Général", 2.8, 1.2, "👑", "Swain, Grand Général de Noxus, t'attend avec sa garde.")},
    {"cle": "demacia", "fond": "demacia", "sceaux": ["🛡️", "👑", "🕊️", "⚜️", "🌟"], "garde": ("Soldat demacien", 1.2, 0.95),
     "gardien": ("Garen", "Garen, Force de Demacia", 3.1, 1.2, "⚔️", "*« Demacia ! »*"),
     "boss": ("Galio", "Galio, le Colosse", 2.6, 1.1, "🗿", "Galio, le Colosse de pétricite, veille sur le trésor avec sa garde.")},
    {"cle": "piltover", "fond": "piltover", "sceaux": ["⚙️", "🔧", "💡", "🧪", "🔭"], "garde": ("Automate hextech", 0.9, 1.25),
     "gardien": ("Blitzcrank", "Blitzcrank, le Golem de vapeur", 3.5, 1.3, "🤖", "*Bip. Intrus détecté.*"),
     "boss": ("Ezreal", "Ezreal, l'Explorateur prodigue", 2.8, 1.2, "✨", "Ezreal garde la réserve de l'Académie avec ses automates.")},
]
# --- Runes : une rune par carte, gagnées en battant Ryze en raid. (nom, emoji, palier 0/1/2, effet)
RUNE = {  # chiffres des runes, en %
    "jambes_soin": 2, "gardien_seuil": 60, "gardien_bouclier": 4, "moisson_seuil": 50, "moisson_degats": 35, "moisson_plus": 10, "moisson_max": 80, "moisson_attente": 1,
    "tempo_vitesse": 4, "tempo_max": 6, "tempo_degats": 8, "premier_degats": 20, "premier_actions": 2, "poigne_degats": 3, "poigne_soin": 1.5,
    "glacial_lent": 25, "glacial_actions": 3, "comete_degats": 35, "comete_attaques": 3, "aery_degats": 4, "aery_bouclier": 2,
    "conquerant_atk": 3, "conquerant_max": 10, "conquerant_vol": 12, "conquerant_actions": 3,
}
RUNES = {
    "premier":    ("Premier coup", "💥", 0, f"+{RUNE['premier_degats']} % de dégâts sur ses {RUNE['premier_actions']} premières actions."),
    "comete":     ("Comète arcanique", "☄️", 0, f"Toutes les {RUNE['comete_attaques']} attaques, des dégâts magiques bonus ({RUNE['comete_degats']} % de son attaque)."),
    "glacial":    ("Optimisation glaciale", "🧊", 0, f"Toutes les {RUNE['glacial_actions']} actions, sa cible perd {RUNE['glacial_lent']} % de vitesse jusqu'à sa prochaine action."),
    "jambes":     ("Jeu de jambes", "👟", 0, f"Chaque attaque le soigne de {RUNE['jambes_soin']} % de ses PV max."),
    "poigne":     ("Poigne de l'immortel", "✊", 1, f"Une action sur deux : dégâts bonus ({RUNE['poigne_degats']} % de ses PV max) et soin de {RUNE['poigne_soin']} % de ses PV max."),
    "aery":       ("Aery", "🧚", 1, f"Chaque attaque : +{RUNE['aery_degats']} % de dégâts, et un bouclier ({RUNE['aery_bouclier']} % de ses PV max) sur l'allié le plus blessé."),
    "gardien":    ("Gardien", "🛡️", 1, f"Une fois par combat, sous {RUNE['gardien_seuil']} % de PV : un bouclier pour toute l'équipe ({RUNE['gardien_bouclier']} % de ses PV max, renforcé par ses résistances)."),
    "conquerant": ("Conquérant", "⚔️", 2, f"+{RUNE['conquerant_atk']} % d'attaque par attaque ({RUNE['conquerant_max']} fois au plus). Dès sa {RUNE['conquerant_actions']}e action, {RUNE['conquerant_vol']} % de vol de vie."),
    "tempo":      ("Tempo mortel", "🥁", 2, f"+{RUNE['tempo_vitesse']} % de vitesse par attaque ({RUNE['tempo_max']} fois au plus). Au maximum, +{RUNE['tempo_degats']} % de dégâts."),
    "moisson":    ("Moisson noire", "🌑", 2, f"Contre une cible sous {RUNE['moisson_seuil']} % de PV : +{RUNE['moisson_degats']} % de dégâts, puis {RUNE['moisson_attente']} actions d'attente. Chaque élimination annule l'attente et ajoute +{RUNE['moisson_plus']} % (jusqu'à +{RUNE['moisson_max']} %)."),
}
RUNE_ETAGES = [40, 60, 80]     # étage de la tour qui ouvre le raid de ce palier ET un emplacement de rune de plus (1, 2 puis 3 cartes)
# Raid contre Ryze : de RAID_JOUEURS[0] à RAID_JOUEURS[1] joueurs, une fois par jour. Ryze s'adapte au groupe.
SALON_RAID = "🔮・raid"
RAID_JOUEURS = (3, 5)
RAID_NOMS = ["Ryze I", "Ryze II", "Ryze III"]
RAID_NIVEAU = [35, 55, 78]     # niveau de référence des cartes pour chaque difficulté (la moitié de la force de Ryze en dépend, l'autre moitié du groupe)
# Par difficulté : multiplicateurs de PV et d'attaque de Ryze, et puissance de son Flux runique (coup ciblé sur le meilleur attaquant ; 0 = aucun).
# « rage » : part de vie (en %) sous laquelle il entre en rage. Réglé le 11 octobre 2026 sur les équipes réelles : Ryze I adouci, Ryze III renforcé.
RAID_DIFFICULTE = [{"pv": 0.85, "atk": 0.85, "flux": 0, "rage": 30}, {"pv": 1.0, "atk": 1.0, "flux": 0, "rage": 30},
                   {"pv": 1.3, "atk": 1.0, "flux": 0.7, "rage": 50}]
RAID_RYZE = {"flux_tous_les": 4, "pv": 2.3, "atk": 0.24, "zone": 50, "vitesse": 225, "prison": 3, "enrage_seuil": 30, "enrage_atk": 50, "epargne": 25}
SALON_DONJONS = "⚒️・donjons"
# « Qui est ce champion ? » : le même champion pour tout le monde chaque jour, à deviner sur une image de plus en plus dézoomée.
# Récompense des mini-jeux quotidiens : un pack ouvert tout de suite, d'autant meilleur que la réussite est belle.
# (nom affiché, taux) : [0] sans faute, [1] bonne réussite, [2] réussite simple. Rien trouvé : MINI_CONSOLATION golds.
MINI_PACKS = [("pack à taux doublés", {"R": 80, "SR": 16, "SSR": 4}),
              ("pack à taux améliorés", {"N": 55, "R": 30, "SR": 12, "SSR": 3}),
              ("pack normal", {"N": 60, "R": 30, "SR": 8, "SSR": 2})]
MINI_CONSOLATION = 5
SALON_QUIZ = "❓・qui-est-ce"
QUIZ_ZOOMS = [0.10, 0.17, 0.28, 0.45, 0.75]   # part de l'illustration montrée à chaque essai (0,10 = un tout petit morceau)
QUIZ_GOLDS = [80, 50, 35, 25, 15]             # golds gagnés selon l'essai où l'on trouve (1er, 2e…)
QUIZ_CONSOLATION = 5                          # golds si l'on ne trouve pas
# Boss de salon : un drake ou le Baron apparaît pour tout le serveur, on le combat ensemble, et le coup fatal le « vole ».
# Quiz des pros (données et photos : Leaguepedia). Deux jeux par jour, les mêmes pour tout le monde.
SALON_PROS = "🎤・quiz-des-pros"
PROS_VISAGE_GOLDS = [60, 40, 25, 15]          # « Qui est ce pro ? » : golds selon l'essai où l'on trouve
PROS_VISAGE_CONSOLATION = 5                   # golds si l'on ne trouve pas
PROS_VISAGE_MATCHS = 150                      # un pro n'est proposé que s'il a commencé au moins autant de matchs dans sa carrière
PROS_EQUIPE_ESSAIS = 3                        # « L'effectif du jour » : nombre d'essais
PROS_EQUIPE_GOLDS = 15                        # golds par joueur trouvé
PROS_EQUIPE_BONUS = 25                        # golds en plus si les cinq sont trouvés
PROS_EQUIPE_PART = 0.5                        # seules les équipes les plus connues sont proposées (cette part du total)
SALON_BOSS = "🐉・boss"
ROLE_BOSS = "Chasseur de boss"      # rôle que les joueurs prennent pour être mentionnés à chaque apparition
BOSS_HEURES = [13, 19, 22]          # heures d'apparition (heure de l'ordinateur qui fait tourner le bot)
BOSS_DUREE = 600                    # secondes avant que le boss s'enfuie
BOSS_ATTAQUES = 3                   # attaques par joueur et par boss
BOSS_PAUSE = 15                     # secondes entre deux attaques d'un même joueur
BOSS_SEUIL = 15                     # % de PV sous lequel le Châtiment devient utilisable
BOSS_CHATIMENT = 10                 # dégâts du Châtiment, en % des PV maximum du boss (un seul par joueur)
BOSS_BUTIN = 5                      # butin d'un participant, en camps de jungle (moitié garantie, moitié selon ses dégâts)
BOSS_BUFF_HEURES = 24               # durée du buff donné à tout le serveur quand le boss meurt
BOSS_NASHOR = 4                     # une apparition sur 4 est le Baron Nashor (50 % de PV en plus)
# (clé, nom, statistique du buff, valeur, texte du buff)
BOSS_MONDE = [
    ("infernal", "Drake infernal", "atk", 5, "+5 % d'attaque"),
    ("montagnes", "Drake des montagnes", "res", 5, "+5 de résistances"),
    ("nuages", "Drake des nuages", "vitesse", 5, "+5 % de vitesse"),
    ("oceans", "Drake des océans", "pv", 5, "+5 % de PV"),
    ("nashor", "Baron Nashor", "jungle", 10, "+10 % de butin en jungle"),
]
SALON_EXPEDITION = "🧭・expédition"
SALONS_RENOMMES = {"🏆・tour-des-pros": "🏆・worlds", "💰・coffre": SALON_EXPEDITION}   # ancien nom -> nouveau nom : le salon est renommé sur place

# --- Bêta : les joueurs peuvent effacer leur propre compte pour retester le début du jeu. Mettre False à la sortie.
RESET_COMPTE = True

# --- SSR ciblé : le joueur choisit un SSR ; quand un SSR tombe, il a cette chance (en %) que ce soit celui-là.
CIBLE_CHANCE = 25

# --- Niveau de compte : tout ce que tu fais rapporte de l'XP de compte.
TOUR_XP_COMPTE = (1.02, 5, 20) # XP de compte de la tour : +2 % par étage et boss comptés 5 fois, à partir de l'étage 20 (30 XP fixes avant)
XP_COMPTE = {"tour": 30, "jungle": 10, "donjon": 25, "arene_victoire": 15, "arene_defaite": 5, "duel_victoire": 15, "duel_defaite": 5}
XP_COMPTE_APRES_50 = [(50, 1.12), (70, 1.08), (85, 1.05)]   # au-delà du niveau 50 : hausse par niveau, par tranche (12 octobre)
XP_COMPTE_NIVEAU = (100, 1.10, 15, 1.05)  # XP pour passer un niveau : 100 au niveau 1, +10 % par niveau jusqu'au niveau 15, puis +5 % par niveau
NIVEAU_GOLDS = (30, 5)         # golds à chaque niveau : 30 + 5 par niveau
NIVEAU_PACK = 5                # un pack tous les 5 niveaux, à taux doublés tous les 10
# Rôles Discord de palier : (niveau de compte, nom, couleur). Un seul à la fois, le plus haut atteint.
ROLES_NIVEAU = [(10, "Aventurier", 0x2ECC71), (20, "Vétéran", 0x3498DB), (30, "Champion", 0x9B59B6), (40, "Légende", 0xE67E22), (50, "Ascendant", 0xF1C40F),
                (60, "Mythique", 0x1ABC9C), (75, "Immortel", 0xE74C3C), (100, "Éternel", 0xFFFFFF)]
# Niveau de compte nécessaire pour chaque mode (les autres sont ouverts dès le début)
DEBLOCAGES = {"jungle": 2, "arene": 6, "duels": 6, "donjons": 8}

# --- Bonus de leader : le premier champion de l'équipe donne le bonus de sa région à toute l'équipe.
# stat : pv, atk, vitesse, resistance (dégâts subis en moins), ulti (dégâts d'ulti), vol (vol de vie), soin. Valeur en %.
LEADERS = {
    "Demacia": ("pv", 12), "Freljord": ("resistance", 8), "Ionia": ("vitesse", 15), "Noxus": ("atk", 10),
    "Runeterra": ("atk", 6), "Zaun": ("ulti", 15), "Îles obscures": ("vol", 8), "Bandle": ("vitesse", 8),
    "Ixtal": ("pv", 10), "Shurima": ("atk", 8), "Targon": ("soin", 20),
    "Bilgewater": ("achever", 20), "Piltover": ("charge", 20),   # Bilgewater, 12 octobre : « À l'abordage » au lieu de +10 % de golds
}
BILGEWATER_NIVEAU = 100   # (ancien bonus de golds de Bilgewater, plus utilisé)
ACHEVER_SEUIL = 50        # leader Bilgewater : dégâts en plus sur les ennemis sous ce % de PV
NOMS_STATS = {"pv": "PV", "atk": "ATQ", "vitesse": "vitesse", "resistance": "résistance", "ulti": "dégâts d'ulti",
              "vol": "vol de vie", "soin": "soins", "golds": "de golds gagnés dans la tour et la jungle", "achever": "de dégâts sur les ennemis sous 50 % de PV (« À l'abordage »)",
              "charge": "de chances de charger son actif deux fois plus vite à chaque action"}

# --- Effets d'ulti ------------------------------------------------------------
# degats : gros coup sur une cible | zone : touche tous les ennemis | soin : soigne l'équipe
# stun : frappe et fait passer son tour à la cible | execution : bien plus fort sur une cible affaiblie
# resurrection : ranime un allié K.O. avec 50 % de ses PV, sinon soigne l'équipe
EFFETS = {"degats": "gros dégâts sur une cible", "zone": "touche tous les ennemis", "soin": "soigne toute l'équipe",
          "stun": "frappe et étourdit la cible", "execution": "achève les cibles affaiblies",
          "resurrection": "ranime un allié K.O., sinon soigne l'équipe"}


def c(nom, rarete, role, region, ulti=None, effet=None, image=None):
    return {"nom": nom, "rarete": rarete, "role": role, "region": region, "ulti": ulti, "effet": effet, "image": image}


# --- Cartes. La clé d'un champion est son identifiant chez Riot (sert aussi pour l'image).
# Pour ajouter un champion : copie une ligne. Les noms d'ulti sont ceux du site officiel en français.
CARTES = {
    # N : les sbires
    "sbire_melee": c("Sbire de mêlée", "N", "sbire", "Faille"),
    "sbire_mage":  c("Sbire mage", "N", "sbire", "Faille"),
    "sbire_siege": c("Sbire de siège", "N", "sbire", "Faille"),
    "super_sbire": c("Super-sbire", "N", "sbire", "Faille"),
    # R : les monstres de la jungle
    "gromp":      c("Gromp", "R", "sbire", "Jungle"),
    "corbin":     c("Corbin écarlate", "R", "sbire", "Jungle"),
    "loup":       c("Loup des ténèbres", "R", "sbire", "Jungle"),
    "golem":      c("Golem ancien", "R", "sbire", "Jungle"),
    "sentinelle": c("Sentinelle bleue", "R", "sbire", "Jungle"),
    "roncier":    c("Roncier rouge", "R", "sbire", "Jungle"),
    # SR
    "Garen":      c("Garen", "SR", "combattant", "Demacia", "Justice de Demacia", "execution"),
    "Sona":       c("Sona", "SR", "support", "Demacia", "Crescendo", "soin"),
    "Annie":      c("Annie", "SR", "mage", "Noxus", "Invocation : Tibbers", "zone"),
    "Ashe":       c("Ashe", "SSR", "tireur", "Freljord", "Flèche de cristal enchantée", "stun"),
    "Tryndamere": c("Tryndamere", "SR", "combattant", "Freljord", "Rage inépuisable", "degats"),
    "Braum":      c("Braum", "SR", "tank", "Freljord", "Incassable", "soin"),
    "Malphite":   c("Malphite", "SR", "tank", "Ixtal", "Force indomptable", "zone"),
    "Amumu":      c("Amumu", "SR", "tank", "Shurima", "Malédiction d'Amumu", "zone"),
    "Nasus":      c("Nasus", "SR", "combattant", "Shurima", "Fureur des sables", "soin"),
    "Soraka":     c("Soraka", "SR", "support", "Targon", "Souhait", "soin"),
    "MasterYi":   c("Maître Yi", "SR", "assassin", "Ionia", "Highlander", "degats"),
    "Teemo":      c("Teemo", "SR", "tireur", "Bandle", "Piège nocif", "zone"),
    "Veigar":     c("Veigar", "SR", "mage", "Bandle", "Explosion primordiale", "execution"),
    "Blitzcrank": c("Blitzcrank", "SR", "tank", "Zaun", "Champ de stase", "zone"),
    # SSR
    "Lux":         c("Lux", "SSR", "mage", "Demacia", "Fureur des éléments", "zone"),
    "Vayne":       c("Vayne", "SSR", "tireur", "Demacia", "Combat ultime", "degats"),
    "Galio":       c("Galio", "SSR", "tank", "Demacia", "Entrée héroïque", "zone"),
    "Darius":      c("Darius", "SSR", "combattant", "Noxus", "Guillotine noxienne", "execution"),
    "Katarina":    c("Katarina", "SSR", "assassin", "Noxus", "Lotus mortel", "zone"),
    "Swain":       c("Swain", "SSR", "mage", "Noxus", "Incarnation démoniaque", "zone"),
    "Mordekaiser": c("Mordekaiser", "SSR", "combattant", "Noxus", "Royaume des morts", "degats"),
    "Yasuo":       c("Yasuo", "SSR", "combattant", "Ionia", "Dernier soupir", "degats"),
    "Yone":        c("Yone", "SSR", "assassin", "Ionia", "Destin scellé", "zone"),
    "Ahri":        c("Ahri", "SSR", "mage", "Ionia", "Assaut spirituel", "degats"),
    "Zed":         c("Zed", "SSR", "assassin", "Ionia", "Marque de la mort", "execution"),
    "LeeSin":      c("Lee Sin", "SSR", "combattant", "Ionia", "Rage du dragon", "stun"),
    "Jhin":        c("Jhin", "SSR", "tireur", "Ionia", "Rappel de rideau", "execution"),
    "Jinx":        c("Jinx", "SSR", "tireur", "Zaun", "Super roquette de la mort !", "execution"),
    "Ekko":        c("Ekko", "SSR", "assassin", "Zaun", "Chronofracture", "degats"),
    "Ezreal":      c("Ezreal", "SSR", "tireur", "Piltover", "Arc térébrant", "zone"),
    "Sejuani":     c("Sejuani", "SSR", "tank", "Freljord", "Prison de glace", "stun"),
    "Leona":       c("Leona", "SSR", "tank", "Targon", "Éruption solaire", "stun"),
    "Renekton":    c("Renekton", "SSR", "combattant", "Shurima", "Dominus", "zone"),
    "Kaisa":       c("Kai'Sa", "SSR", "tireur", "Néant", "Instinct meurtrier", "degats"),
    "Karthus":     c("Karthus", "SSR", "mage", "Îles obscures", "Requiem", "zone"),
    "Thresh":      c("Thresh", "SSR", "support", "Îles obscures", "La cage", "stun"),
    "Pyke":        c("Pyke", "SSR", "assassin", "Bilgewater", "Exécution abyssale", "execution"),
    "Gangplank":   c("Gangplank", "SSR", "combattant", "Bilgewater", "Tir de barrage", "zone"),
    "Senna":       c("Senna", "SSR", "tireur", "Îles obscures", "Ténèbres aveuglantes", "zone"),
    "Akali":       c("Akali", "SR", "assassin", "Ionia", "Maîtrise absolue", "execution"),
    "Zilean":      c("Zilean", "SSR", "support", "Runeterra", "Retour temporel", "resurrection"),
    "Aatrox":      c("Aatrox", "SSR", "combattant", "Runeterra", "Fossoyeur des mondes", "degats"),
    # Vague du 11 octobre 2026
    "Nami":        c("Nami", "SR", "support", "Bilgewater", "Raz-de-marée", "soin"),
    "Caitlyn":     c("Caitlyn", "SR", "tireur", "Piltover", "Un tir, une vie", "degats"),
    "Vi":          c("Vi", "SR", "combattant", "Piltover", "Assaut et batterie", "stun"),
    "Shaco":       c("Shaco", "SR", "assassin", "Runeterra", "Hallucination", "degats"),
    "Morgana":     c("Morgana", "SR", "mage", "Demacia", "Entraves de l'âme", "zone"),
    "Janna":       c("Janna", "SSR", "support", "Zaun", "Mousson", "soin"),
    "Talon":       c("Talon", "SSR", "assassin", "Noxus", "Assaut ténébreux", "zone"),
    # Tour des pros (exclusifs : voir TOUR_PROS_EXCLUSIFS)
    "Rumble":      c("Rumble", "SSR", "combattant", "Bandle", "L'Égalisateur", "zone"),
    "Gnar":        c("Gnar", "SR", "combattant", "Freljord", "GNAR !", "zone"),
    "Jayce":       c("Jayce", "SR", "combattant", "Piltover", "Orbe électrique", "degats"),
    "Viego":       c("Viego", "SR", "assassin", "Îles obscures", "Crève-cœur", "execution"),
    "Qiyana":      c("Qiyana", "SR", "assassin", "Ixtal", "Démonstration de talent", "zone"),
    "Khazix":      c("Kha'Zix", "SR", "assassin", "Runeterra", "Assaut du Néant", "degats"),
    "Draven":      c("Draven", "SSR", "tireur", "Noxus", "Lame tourbillonnante", "zone"),
    "Kalista":     c("Kalista", "SR", "tireur", "Îles obscures", "Extirpation", "degats"),
    "Fiora":       c("Fiora", "SSR", "combattant", "Demacia", "Grand défi", "degats"),
    "Leblanc":     c("LeBlanc", "SSR", "assassin", "Noxus", "Imitation", "degats"),
    "Syndra":      c("Syndra", "SSR", "mage", "Ionia", "Déchaînement de puissance", "degats"),
    "Xayah":       c("Xayah", "SR", "tireur", "Ionia", "Tempête de plumes", "zone"),
    "Sylas":       c("Sylas", "SR", "combattant", "Demacia", "Usurpation", "degats"),
    "Tristana":    c("Tristana", "SR", "tireur", "Bandle", "Tir à l'impact", "degats"),
    "KSante":      c("K'Sante", "SSR", "tank", "Shurima", "Tous azimuts", "degats"),
    "Ornn":        c("Ornn", "SR", "tank", "Freljord", "Appel du dieu de la forge", "zone"),
    "Jax":         c("Jax", "SR", "combattant", "Runeterra", "Contre-attaque", "stun"),
    "Camille":     c("Camille", "SSR", "combattant", "Piltover", "Ultimatum hextech", "stun"),
    "Gwen":        c("Gwen", "SSR", "combattant", "Îles obscures", "Couture", "degats"),
    "Aphelios":    c("Aphelios", "SSR", "tireur", "Targon", "Veille au clair de lune", "zone"),
    "Azir":        c("Azir", "SSR", "mage", "Shurima", "Partage de l'empereur", "zone"),
    "Ambessa":     c("Ambessa", "SSR", "combattant", "Noxus", "Exécution publique", "stun"),
    "Ziggs":       c("Ziggs", "SSR", "mage", "Zaun", "Méga-bombe infernale", "zone"),
    "Varus":       c("Varus", "SR", "tireur", "Ionia", "Chaîne de corruption", "stun"),
    "Corki":       c("Corki", "SSR", "tireur", "Bandle", "Barrage de missiles", "zone"),
    "Nidalee":     c("Nidalee", "SR", "assassin", "Ixtal", "Aspect du couguar", "degats"),
    "Graves":      c("Graves", "SSR", "tank", "Bilgewater", "Dégâts collatéraux", "degats"),   # 14 octobre : tank partout (carte, site, combats)
    "Zeri":        c("Zeri", "SSR", "tireur", "Zaun", "Éclair foudroyant", "zone"),
    "Maokai":      c("Maokai", "SSR", "tank", "Îles obscures", "Emprise de la nature", "zone"),   # n'existe qu'en UR (MaokaiUR, packs UR)
    "XinZhao":     c("Xin Zhao", "SSR", "combattant", "Demacia", "Garde du croissant", "zone"),
    "Bard":        c("Bard", "SSR", "support", "Runeterra", "Destin tempéré", "zone"),
    "Renata":      c("Renata Glasc", "SSR", "support", "Zaun", "Renflouage", "resurrection"),
    "Ryze":        c("Ryze", "SSR", "mage", "Runeterra", "Prison runique", "stun"),
    "MissFortune": c("Miss Fortune", "SSR", "tireur", "Bilgewater", "Barrage de balles", "zone"),
    "Orianna":     c("Orianna", "SR", "mage", "Piltover", "Onde de choc", "zone"),   # SSR jusqu'au 11 octobre 2026, puis SR réservée à la tour des pros
}
# UR : cinq versions de prestige. Mêmes passif et actif que le champion d'origine (« base »), avec les stats d'UR.
# Elles ne sortent que des packs UR. Leur illustration est le fichier images/<identifiant>.jpg.
for _id, _base, _nom in (("GarenUR", "Garen", "Garen, Dieu-Roi"), ("AatroxUR", "Aatrox", "Aatrox, Lune de sang"), ("VayneUR", "Vayne", "Vayne, Fleur spirituelle"),
                         ("SennaUR", "Senna", "Senna, True Damage"), ("LuxUR", "Lux", "Lux, Élémentaliste"), ("MaokaiUR", "Maokai", "Maokai, Totémique"),
                         ("TristanaUR", "Tristana", "Tristana, Légende immortalisée"),
                         ("AzirLR", "Azir", "Azir, Royaume en guerre"), ("AhriLR", "Ahri", "Ahri, Hall of Legends"), ("RyzeLR", "Ryze", "Ryze, Arcana"),
                         ("JayceUR", "Jayce", "Jayce, Prestige T1"), ("AkaliUR", "Akali", "Akali, K/DA Prestige"), ("VarusUR", "Varus", "Varus, T1"),
                         ("YoneUR", "Yone", "Yone, Fleur spirituelle"), ("NidaleeUR", "Nidalee", "Nidalee, DWG"), ("AsheUR", "Ashe", "Ashe de Ruler"), ("XayahUR", "Xayah", "Xayah, SSG"), ("ZeriUR", "Zeri", "Zeri, Rose fanée"), ("XinZhaoUR", "XinZhao", "Xin Zhao, Royaume en guerre"),
                         ("BardUR", "Bard", "Bard, T1"), ("JaxUR", "Jax", "Jax, Bâton divin")):   # les versions « de tel pro » sont réservées aux Worlds (TOUR_PROS_EXCLUSIFS)
    _o = CARTES[_base]
    CARTES[_id] = {**c(_nom, "UR", _o["role"], _o["region"], _o["ulti"], _o["effet"],
                       f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{_base}_0.jpg"), "base": _base}
    if _base in TEXTES_KITS:
        TEXTES_KITS[_id] = TEXTES_KITS[_base]
# Les trois UR à kit propre (12 octobre). Noms de skin provisoires, en attendant les illustrations.
CARTES["Gragas"] = c("Gragas", "SR", "tank", "Freljord", "Tonneau explosif", "zone")   # pas de carte à tirer : sert de base à l'UR
CARTES["Gragas"]["base"] = "Gragas"
for _id, _base, _nom in (("ViegoUR", "Viego", "Viego, Règne du revenant"), ("SylasUR", "Sylas", "Sylas, Freljord"), ("GragasUR", "Gragas", "Gragas, Oktoberfest")):
    _o = CARTES[_base]
    CARTES[_id] = {**c(_nom, "UR", _o["role"], _o["region"], _o["ulti"], _o["effet"],
                       f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{_base}_0.jpg"), "base": _base}
# Quatre champions de la LEC (12 octobre) : on ne les trouve que dans les packs de la LEC.
CARTES["Sion"] = c("Sion", "SR", "tank", "Noxus", "Assaut implacable", "stun")
CARTES["Chogath"] = c("Cho'Gath", "SSR", "tank", "Runeterra", "Festin", "execution")
CARTES["Sivir"] = c("Sivir", "SR", "tireur", "Shurima", "Course", "degats")
CARTES["Rakan"] = c("Rakan", "SSR", "support", "Ionia", "Entrée fracassante", "stun")
for _id in ("Sion", "Chogath", "Sivir", "Rakan"):
    CARTES[_id]["base"] = _id
KITS.update({"sion_pv": 20, "sion_ulti": 140, "chogath_pv": 8, "chogath_ulti": 300, "chogath_seuil": 25,
             "sivir_rebond": 40, "sivir_ulti": 120, "sivir_vitesse": 25, "rakan_bouclier": 8, "rakan_zone": 90, "rakan_charmes": 2})
_K = KITS
TEXTES_KITS["Sion"] = (f"Se relève une fois avec {_K['sion_pv']} % de ses PV quand il tombe.", f"Charge un ennemi : {_K['sion_ulti']} % et étourdissement.")
TEXTES_KITS["Chogath"] = (f"Chaque ennemi qu'il élimine lui donne +{_K['chogath_pv']} % de PV max.",
                          f"Festin : dévore un ennemi sous {_K['chogath_seuil']} % de PV (pas les boss), sinon le frappe à {_K['chogath_ulti']} %.")
TEXTES_KITS["Sivir"] = (f"Ses attaques rebondissent sur un autre ennemi ({_K['sivir_rebond']} %).",
                        f"Frappe un ennemi à {_K['sivir_ulti']} % et lance la course : +{_K['sivir_vitesse']} % de vitesse pour toute son équipe pendant 3 actions.")
TEXTES_KITS["Rakan"] = (f"À chacune de ses actions, pose un bouclier de {_K['rakan_bouclier']} % de ses PV max sur l'allié le plus blessé.",
                        f"Frappe tous les ennemis à {_K['rakan_zone']} % et charme {_K['rakan_charmes']} d'entre eux : ils passent leur prochain tour.")
_U = KITS_UR
_E = KITS_EVEIL
EVEILS = {
    "LuxUR": f"trois éléments au lieu de deux et plus de puissance : feu (tous les ennemis à {_E['luxur_feu']} %, brûlure {_E['luxur_brulure']} %), glace (tous à {_E['luxur_glace']} % et gel de l'ennemi le plus dangereux), lumière ({_E['luxur_lumiere']} % sur le plus dangereux) ; en tombant, elle frappe aussi l'ennemi étourdi à {_E['lux_mort']} % de son ATQ.",
    "XayahUR": f"commence avec {_E['xayah_plumes']} plumes, et chaque plume rappelée fait +{_E['xayah_plume']} % au lieu de {KITS['xayah_plume']} %.",
    "AatroxUR": f"{_E['aatrox_passif']} % de vol de vie au lieu de {KITS['aatrox_vol']} %, ne peut pas tomber tant que son actif est prêt (une fois par combat), et son actif frappe tous les ennemis à {_E['aatrox_zone']} % en le soignant de {_E['aatrox_vol']} % des dégâts.",
    "VarusUR": f"pose une marque sur chaque ennemi au début du combat, et {_E['varus_marques']} marques par attaque.",
    "BardUR": f"le carillon sonne toutes les {_E['bard_actions']} actions, et son actif fige toujours l'ennemi qui tape le plus fort.",
    "MaokaiUR": f"son actif force tous les ennemis à l'attaquer et lui donne un bouclier de {_E['maokai_bouclier']} % de ses PV max.",
    "GarenUR": f"exécute sous {_E['garen_execution']} % de PV, et chaque exécution recharge aussitôt son actif.",
    "TristanaUR": f"sa charge explose une attaque sur {_E['tristana_coups']}.",
    "JayceUR": f"son tir traverse jusqu'à un second ennemi ({_E['jayce_second']} %).",
    "XinZhaoUR": f"bloque {_E['xin_blocages']} attaques au lieu de {KITS['xin_blocages']}.",
    "SennaUR": f"son bouclier d'équipe passe à {_E['senna_bouclier']} % des PV.",
    "VayneUR": f"son coup sur trois ignore aussi {_E['vayne_pen']} % des résistances.",
    "AkaliUR": f"son actif frappe une seconde fois dès que la cible passe sous {_E['akali_seuil']} % de PV (au lieu de 40 %).",
    "ZeriUR": f"commence le combat avec {_E['zeri_cumuls']} cumul de vitesse.",
    "NidaleeUR": f"son bonus contre les blessés vaut sous {_E['nidalee_seuil']} % de PV.",
    "YoneUR": f"son actif frappe tous les ennemis à {_E['yone_zone']} % au lieu de {KITS['yone_zone']} %.",
    "JaxUR": f"commence le combat avec {_E['jax_cumuls']} cumuls d'attaque.",
}
for _id, _texte in EVEILS.items():
    _p, _a = TEXTES_KITS[_id]
    TEXTES_KITS[_id] = (((_p + " ") if _p else "") + "Éveil : " + _texte, _a)
TEXTES_KITS["Gragas"] = (f"Chaque action lui rend {_U['gragas_soin']} % de ses PV max. Sous {_U['gragas_seuil']} % de PV, il gagne +{_U['gragas_res']} de résistances.",
                         f"Tonneau explosif : tous les ennemis à {_U['gragas_zone']} %, leurs actifs en préparation sont annulés et ils sont ralentis de {_U['gragas_lent']} % pendant 2 actions.")
TEXTES_KITS["GragasUR"] = TEXTES_KITS["Gragas"]
TEXTES_KITS["ViegoUR"] = (f"Quand il tue un ennemi, il le possède : il récupère {_U['viego_soin']} % de ses PV, et son prochain actif devient celui du champion tué.",
                          f"Frappe à {_U['viego_ulti']} %, ou à {_U['viego_fort']} % si la cible a moins de {_U['viego_seuil']} % de PV. S'il tue, son actif se recharge aussitôt.")
TEXTES_KITS["SylasUR"] = (f"Après chaque actif, ses 2 attaques suivantes font +{_U['sylas_bonus']} % et lui rendent {_U['sylas_soin']} % de ses PV max.",
                          f"Frappe l'ennemi qui tape le plus fort à {_U['sylas_ulti']} % et lui vole son actif : il le relance aussitôt contre l'équipe adverse, à {_U['sylas_vole']} % de puissance.")
_L = KITS_LR
TEXTES_KITS["AhriLR"] = (f"{_L['ahri_vol']} % de vol de vie sur ses attaques. Une attaque sur {_L['ahri_coups']} charme la cible : elle passe son tour.",
                         f"Ruée spirituelle : trois charges à {_L['ahri_ulti']} %, chacune sur l'ennemi le plus blessé. Chaque ennemi tué redonne une charge ({_L['ahri_max']} au plus).")
TEXTES_KITS["AzirLR"] = (f"Commence avec un soldat de sable et en invoque un à chacune de ses actions ({_L['azir_max']} au plus) : +{_L['azir_soldat']} % de dégâts par soldat.",
                         f"Sa phalange charge : tous les ennemis à {_L['azir_zone']} %, les actifs qu'ils préparaient sont annulés, et toute son équipe reçoit un bouclier de {_L['azir_bouclier']} % de ses PV max.")
TEXTES_KITS["RyzeLR"] = (f"Chaque attaque rebondit sur un autre ennemi ({_L['ryze_rebond']} %).",
                         f"Prison runique : {_L['ryze_ulti']} % et étourdissement pendant {_L['ryze_tours']} tours, puis la Surcharge frappe les autres ennemis ({_L['ryze_eclat']} %).")

# Images officielles des champions (Data Dragon de Riot). Les sbires et monstres n'en ont pas.
for _id, _c in CARTES.items():
    if _c["ulti"] and not _c["image"]:
        _c["image"] = f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{_id}_0.jpg"

# Cartes retirées des packs : elles ne se tirent plus, mais les joueurs qui les possèdent les gardent et peuvent les jouer.
# (Liste alignée sur la feuille Google des admins : une carte absente de la feuille est retirée.)
RETIREES = {"Ahri", "Katarina", "Ekko", "Ezreal", "Jhin", "Kaisa", "LeeSin", "Mordekaiser", "Pyke", "Renekton",
            "Swain", "Thresh", "Yone"}
# Champions qu'on n'obtient que dans la tour des pros : jamais dans les packs normaux, jamais comme adversaires de la tour classique.
TOUR_PROS_EXCLUSIFS = {"Rumble", "Gnar", "Jayce", "Viego", "Qiyana", "Khazix", "Draven", "Kalista", "Orianna", "MissFortune",
                       "Fiora", "Leblanc", "Syndra", "Xayah", "Sylas", "Tristana", "KSante", "Ornn", "Jax", "Camille", "Gwen", "Aphelios",
                       "TristanaUR", "Azir", "Ryze", "Maokai", "AzirLR", "AhriLR", "RyzeLR",
                       "Ambessa", "Ziggs", "Varus", "Corki", "Nidalee", "Graves", "Zeri", "XinZhao", "Bard", "Renata",
                       "JayceUR", "AkaliUR", "VarusUR", "YoneUR", "NidaleeUR", "AsheUR", "BardUR", "JaxUR", "XayahUR", "ZeriUR", "XinZhaoUR"}
# SSR joués par les pros : sortis des packs normaux le 11 octobre 2026 (ceux qui les ont les gardent), ils reviendront par la tour des pros.
# Ils restent des adversaires possibles de la tour classique.
TOUR_PROS_HORS_PACKS = {"Akali", "Ashe", "Gragas", "ViegoUR", "SylasUR", "GragasUR", "Sion", "Chogath", "Sivir", "Rakan"}   # Ashe : SSR réservée aux Worlds depuis le 11 octobre (retirée des collections), encore adversaire de la tour
for _id, _c in CARTES.items():
    _b = _c.setdefault("base", _id)   # une carte UR reprend toutes les particularités de son champion d'origine
    _c["en_jeu"] = _id not in RETIREES and _id not in TOUR_PROS_EXCLUSIFS and _id not in TOUR_PROS_HORS_PACKS
    _c["type"] = "magique" if _b in MAGIQUES else "physique"
    _c["res"] = PARTICULARITES.get(_b, {}).get("res", RESISTANCES[_c["role"]])
    _c["vitesse"] = PARTICULARITES.get(_b, {}).get("vitesse", ROLES[_c["role"]][2])
    _c["cout"] = PARTICULARITES.get(_b, {}).get("cout", ROLES[_c["role"]][3])
    _c["zone"] = PARTICULARITES.get(_b, {}).get("zone", 130)

# Cartes que l'on peut obtenir dans les packs, par rareté
PAR_RARETE = {r: [k for k, v in CARTES.items() if v["rarete"] == r and v["en_jeu"]] for r in RARETES}
UR_PACK = PAR_RARETE["UR"] + ["TristanaUR"]   # UR du pack UR et de son garanti (13 octobre : Tristana en plus des 6 de base)

# --- Packs --------------------------------------------------------------------
TAUX = {"N": 60, "R": 30, "SR": 8, "SSR": 2}           # pack payant, en %
TAUX_NIVEAU = {"R": 70, "SR": 24, "SSR": 6}   # pack de niveau de compte : taux triplés, sans N (12 octobre)
TAUX_GRATUIT = {"N": 63, "R": 30, "SR": 6, "SSR": 1}   # pack gratuit
PRIX_PACK = 100
PRIX_PACK_10 = 900           # garantit au moins un SR
# Méga tirage (12 octobre, idée des joueurs) : MEGA_CARTES cartes pour MEGA_PRIX golds, au moins un SSR (au hasard), et un pack UR
# offert. Ces cartes ne font pas avancer le compteur « un pack UR tous les 50 packs » (le pack UR offert le remplace).
MEGA_PRIX = 4000
MEGA_CARTES = 50
PITIE = 80                   # SSR garanti après ce nombre de packs sans SSR
DELAI_GRATUIT = 6 * 3600     # secondes entre deux packs gratuits
ETOILES_MAX = 5              # un doublon donne une étoile (+10 % de stats)
GOLDS_DOUBLON = 20           # doublon d'une carte déjà à 5 étoiles

# --- Annonces publiques ------------------------------------------------------
SALON_TIRAGES = "📣・tirages"          # salon où les belles cartes sont annoncées à tout le serveur
SALON_DISCUSSION = "💬・discussion"    # salon libre pour parler du jeu
SALON_GUIDE = "📖・guide"              # règles et mode d'emploi du jeu
SALON_ANNONCES = "📢・annonces"          # les grandes annonces du jeu (ouverture d'un mode…), écrites par le bot
SALON_MAJ = "📰・mises-à-jour"         # le bot y annonce chaque mise à jour du jeu
RARETES_ANNONCEES = ("SSR", "UR")
# Packs UR : un pack UR gagné tous les UR_TOUS_LES packs ouverts (toutes origines confondues), à ouvrir dans le salon des packs.
UR_TOUS_LES = 50
UR_TAUX = {"UR": 1, "SSR": 29, "SR": 70}   # contenu d'un pack UR, en %
# --- Salon de test personnel du propriétaire (13 octobre) : un tournoi des Worlds de test qui démarre à BLG, avec les vraies
# cartes de trois joueurs (copiées, rien n'est enregistré) + quelques UR prêtées au hasard, tirées parmi les UR de tier S et A.
TEST_PERSO_SALON = "🧪・test-worlds"
TEST_PERSO_PROPRIO = 100000000000000001                                     # Joueur G : seul à voir et utiliser le salon
TEST_PERSO_JOUEURS = [100000000000000002, 100000000000000003, 100000000000000004]   # en haut Joueur A, au milieu Joueur C, en bas Joueur B
TEST_PERSO_DEPART = 5                                                        # 5 = Gen.G (3 = Bilibili Gaming)
TEST_PERSO_UR_NOMBRE = 3
TEST_COACH_VALEUR = 0.06   # 14 octobre : coach de test fixe à +6 % (comme un vrai coach), au lieu de grimper jusqu'à +20 % contre Faker
TEST_PERSO_FORCES = {}                                                           # salon de test seulement, par numéro d'équipe (vide : les réglages testés sont passés en live le 13 octobre au soir)
TEST_PERSO_BONUS = {}                                                       # salon de test seulement : bonus de pros (vide depuis le passage en live)
TEST_PERSO_UR = ["ViegoUR", "YoneUR", "JaxUR", "VarusUR", "NidaleeUR", "AkaliUR", "SylasUR",   # tier S (tier list des Worlds du 13 octobre)
                 "ZeriUR", "XinZhaoUR", "XayahUR", "JayceUR", "LuxUR", "VayneUR", "SennaUR", "BardUR"]   # tier A
UR_WORLDS_CHANCE = 1             # 13 octobre : % d'un pack UR de donner une UR des Worlds (équipes battues par le joueur, hors garanti)
MULTI_UR_LEC = {"GragasUR": 0.1, "XinZhaoUR": 0.1, "SylasUR": 0.05}   # % par tranche de 10 cartes (pack de 10, méga tirage) : UR de la LEC des équipes battues
UR_PITIE = 40                 # UR garanti après ce nombre de packs UR sans UR
# La prochaine UR tirée dans un pack UR (garantie ou naturelle) est choisie, pour ces joueurs, une seule fois (12 octobre).
UR_CHOISIES = {100000000000000003: "AatroxUR", 100000000000000001: "SennaUR"}   # Joueur C : Aatrox ; Joueur G : Senna (déjà données). Joueur F : Lux retirée le 13 octobre
UR_BOOST = {100000000000000005: ("LuxUR", 40)}   # Joueur F (13 octobre) : sa prochaine UR est Lux, et chaque pack UR a 40 % de la donner, jusqu'à ce qu'il l'ait
UR_DOUBLON_GOLDS = 500
# --- Boutique (12 octobre) : la même pour tout le serveur, renouvelée toute seule toutes les BOUTIQUE_DELAI secondes (pas de
# rafraîchissement payant). chance : % de présence à chaque renouvellement ; limite : achats par joueur et par boutique.
BOUTIQUE_DELAI = 6 * 3600
BOUTIQUE = {
    "composants": {"nom": "5 composants", "emoji": "🧪", "prix": 800, "limite": 2, "chance": 100, "quantite": 5},
    "ssr": {"nom": "Un SSR", "emoji": "🌟", "prix": 3000, "limite": 1, "chance": 100},
    "pack_lec": {"nom": "Pack LEC", "emoji": "🇪🇺", "prix": 2000, "limite": 1, "chance": 33},
    "pack_pro": {"nom": "Pack Worlds", "emoji": "🏆", "prix": 4000, "limite": 1, "chance": 10},
    "pack_ur": {"nom": "Pack UR", "emoji": "💎", "prix": 6000, "limite": 1, "chance": 10},
}
# Golds des modes de combat (12 octobre) : raid gagné (une fois par jour), par équipe battue à la LEC, par équipe éliminée aux Worlds.
GOLDS_RAID = 1000
GOLDS_LEC_EQUIPE = 100
GOLDS_WORLDS_EQUIPE = 200        # un UR déjà possédé : pas d'étoile, des golds (et de la réserve d'XP)

# --- Progression --------------------------------------------------------------
GOLDS_DEPART = 500
RARETE_DEPART = "SR"         # rareté du champion garanti dans le pack de départ
BONUS_NIVEAU = 0.06          # +6 % de stats par niveau
BONUS_ETOILE = 0.10
COFFRE_PACK_HEURES = 3       # un pack rapporté par tranche complète de ce nombre d'heures d'expédition
COFFRE_HEURES = 12           # durée maximale d'accumulation du farm passif
COFFRE_GOLDS = (10, 1)        # golds par heure : 3 + 0,2 par étage
COFFRE_XP = (60, 10)         # XP par carte et par heure : 6 + 0,5 par étage

# --- La tour : gratuite, mais chaque étage est un mur. Les récompenses ne se gagnent qu'une fois par étage.
TOUR_DIFFICILE_BOSS = (5, 1.5)   # tour difficile : multiplicateurs minimum de PV et d'attaque de tous les boss
TOUR_MAX = 200                # dernier étage de la tour
TOUR_BASE = (400, 56)         # PV et ATQ de référence d'un ennemi (modulés par son rôle et par la force de l'étage)
# Force des ennemis selon l'étage : des points (étage, force) reliés en ligne droite. Chaque étage ajoute donc une quantité fixe de force :
# la tour devient de plus en plus dure, sans mur. Étages 1 à 9 : la découverte. 10 à 20 : on apprend à monter ses cartes. 20 à 100 : montée régulière.
TOUR_COURBE = [(1, 0.55), (9, 0.78), (13, 1.30), (19, 3.30), (20, 2.40), (100, 10.24), (150, 20.0), (200, 32.0)]   # 14 octobre : tour difficile durcie (avant : 21 à l'étage 200)   # (le boss 20 a moins de force brute : ses multiplicateurs de boss font le reste)
# Doublons nécessaires pour chaque étoile (1re, 2e… 5e), par rareté. Les raretés absentes : un doublon par étoile.
ETOILE_DOUBLONS = {"SSR": [1, 1, 1, 2, 3]}
ETOILE_NIVEAUX = 10           # chaque étoile (doublon) relève aussi le niveau maximum de la carte d'autant
TOUR_GOLDS = (10, 2)          # golds par étage : 10 + 2 par étage
TOUR_XP = (100, 20)            # XP par carte : 15 + 2 par étage
TOUR_PACK_SR = 5              # tous les 5 étages : un pack à taux doublés (boss compris)
TAUX_BOSS = {"R": 80, "SR": 16, "SSR": 4}   # pack du boss, tous les 10 étages : taux doublés, jamais de carte N

# --- Énergie : elle ne sert qu'à la jungle.
# Lignes de combat : chaque carte se place devant ou derrière. Placée sur la ligne de son rôle, elle reçoit un petit bonus.
LIGNES = {"tank": "avant", "combattant": "avant", "assassin": "avant", "tireur": "arriere", "mage": "arriere", "support": "arriere"}
BONUS_LIGNE = 4          # % : PV et résistances (tank), attaque (combattant, tireur), vitesse (assassin), dégâts de l'actif (mage)
BONUS_LIGNE_SOIN = 5     # % : soins et boucliers d'un support placé derrière
CIBLE_AVANT = 67         # % de chances, dans les combats automatiques, de viser la ligne avant (les assassins visent qui ils veulent)
TEXTES_LIGNE = {"tank": f"+{BONUS_LIGNE} % PV et +{BONUS_LIGNE} de résistances", "combattant": f"+{BONUS_LIGNE} % d'attaque",
                "assassin": f"+{BONUS_LIGNE} % de vitesse", "tireur": f"+{BONUS_LIGNE} % d'attaque",
                "mage": f"+{BONUS_LIGNE} % de dégâts sur son actif", "support": f"+{BONUS_LIGNE_SOIN} % de soins et de boucliers"}
ENERGIE_MAX = 12              # énergie maximale au niveau de compte 1
ENERGIE_PAR_NIVEAU = 1        # énergie maximale gagnée à chaque niveau de compte
ENERGIE_DELAI = 2 * 3600      # secondes pour regagner 1 point

# --- La jungle : le farm. 1 énergie par victoire, de l'XP, quelques golds et une petite chance de pack gratuit.
# (nom, étage minimum dans la tour, retard sur ton étage, multiplicateur de récompenses)
JUNGLE = [("Chasse", 0, 2, 0.5)]   # chasse rapide : monstres un peu en dessous de ton étage ; dernier nombre = part du butin (0,5 = moitié de ce que rapporte un camp exploré)
JUNGLE_XP = (30, 2)           # XP par carte : 30 + 2 par étage atteint
JUNGLE_GOLDS = (3, 0.3)       # golds : 3 + 0,3 par étage atteint
JUNGLE_MULTI = [(5, 0), (10, 500)]     # chasse groupée : (nombre de chasses d'un coup, camps à avoir nettoyés pour la débloquer ; 0 = dès le début)
JUNGLE_CHANCE_PACK = 5        # % de chance de trouver un pack gratuit à chaque victoire
# Clear de jungle : le mini-jeu. On mise de l'énergie, puis on enchaîne les camps sans récupérer ses PV.
CLEAR_MISE_MIN = 3                       # énergie minimale à miser
CLEAR_FORCE = 0.08                       # chaque camp est plus fort que le précédent de ce pourcentage (0,12 = +12 %)
CLEAR_PARTS = [1, 1.5, 2, 2.5, 3, 4]     # poids du butin de chaque camp : pousser loin rapporte de plus en plus
CLEAR_BONUS = 1.2                        # un clear complet rapporte autant que mise × ce nombre de chasses rapides
CLEAR_CHATIMENT = 1.25                   # multiplicateur du butin si le Châtiment est réussi sur le dernier camp
CLEAR_PALIERS = [100, 80, 58, 34, 12]    # PV du dernier monstre affichés tour à tour pendant le Châtiment (en %)
CLEAR_FENETRE = 35                       # le Châtiment réussit si on appuie sous ce pourcentage de PV
CLEAR_RYTHME = 1.6                       # secondes entre deux paliers
CLEAR_DEFAITE = 0.5                      # part du butin gardée si l'équipe tombe en route
# Exploration de la jungle : une carte de 16 buissons à fouiller, 1 énergie par buisson.
# Contenu d'une carte : (clé, nombre de cases). Le reste des cases est vide.
EXPLO_CASES = [("camp", 6), ("bleu", 1), ("rouge", 1), ("tresor", 2), ("gank", 3), ("fruit", 1)]
COFFRE_HEXTECH_CHANCE = 3      # % de cartes de jungle qui cachent un coffre hextech (très rare)
COFFRE_HEXTECH_BUTIN = {"composants": 60, "pack": 30, "pack_pro": 10}   # ce qu'il contient, en %
COFFRE_HEXTECH_COMPOSANTS = 4  # composants donnés quand il en contient
EXPLO_VIES = 2                 # au 2e gank, la carte est réinitialisée (nouveaux buissons)
EXPLO_CLEAR = 20               # % du butin de la carte offert en plus quand il ne reste que des ganks cachés (clear complet)
EXPLO_BONUS = [(100, 10), (400, 25)]   # (camps nettoyés, % de butin en plus en exploration) · 26 octobre : 400 camps au lieu de 500
EXPLO_CAMP = 1.0               # butin d'un petit camp, en nombre de chasses rapides
EXPLO_GROS = (2.5, 1.0)        # butin d'un gros monstre : Châtiment réussi, Châtiment raté
EXPLO_TRESOR = 1.5             # golds d'un trésor, en nombre de chasses rapides (pas d'XP)
EXPLO_EMOJIS = {"camp": "🐺", "bleu": "🔵", "rouge": "🔴", "tresor": "💰", "gank": "⚔️", "balise": "👁️", "fruit": "🍯", "vide": "🍃", "coffre": "🧰"}
# Châtiment : PV du monstre affichés tour à tour (en %), puis secondes entre deux paliers. La bleue se soigne, le rouge s'effondre d'un coup.
EXPLO_CHATIMENT = {"bleu": ([100, 72, 44, 66, 38, 14], 1.5), "rouge": ([100, 92, 84, 76, 30, 10], 1.3)}
JUNGLE_MONSTRES = ["Gromp", "Loup des ténèbres", "Corbin écarlate", "Golem ancien", "Sentinelle bleue", "Roncier rouge"]
SALON_JUNGLE = "🌿・jungle"
SALON_PROFIL = "👤・profil"

# --- Ennemis de la tour -------------------------------------------------------
ENNEMIS = ["Sbire de mêlée", "Sbire mage", "Carapateur", "Loup des ténèbres", "Corbin écarlate",
           "Gromp", "Golem ancien", "Sentinelle bleue", "Roncier rouge", "Super-sbire"]
# Les boss, tous les 10 étages : (nom, trait, multiplicateur de PV, multiplicateur d'ATQ, description du trait)
# Les boss sont insensibles aux étourdissements, à l'aveuglement et aux exécutions.
BOSS = {
    10: ("Larves du Néant", "larves", 1.6, 0.9, "Trois larves au lieu d'un seul boss. Un combat d'échauffement."),
    20: ("Héraut de la Faille", "charge", 7, 2.2, "Sa charge frappe très fort une seule cible."),
    30: ("Drake des nuages", "vent", 4.2, 1.35, "Très rapide : il joue bien plus souvent que ton équipe."),
    40: ("Drake des montagnes", "terre", 6, 1.7, "Une carapace énorme, surtout contre le physique : apporte du magique ou de la pénétration."),
    50: ("Drake des océans", "eau", 5, 1.5, "Il se soigne à chacune de ses actions : il faut le tuer vite."),
    60: ("Drake infernal", "feu", 6, 1.6, "Il frappe de plus en plus fort au fil du combat."),
    70: ("Drake hextech", "hextech", 6, 1.8, "Ses attaques ralentissent ceux qu'il touche."),
    80: ("Drake chemtech", "chemtech", 6, 1.8, "Abattu une première fois, il se relève avec une partie de sa vie."),
    90: ("Baron Nashor", "nashor", 7, 2.0, "Ses coups rongent les résistances de ton équipe."),
    100: ("Dragon ancestral", "ancestral", 8, 2.2, "Il exécute tout champion passé sous 20 % de ses PV."),
}
TOUR_SSR_GARANTI = 30         # le boss de cet étage donne un pack avec un SSR garanti (une seule fois, à la première victoire)
TRAITS_BOSS = {"vent_vitesse": 130, "terre_res": (140, 60), "eau_soin": 4, "feu_atk": 8, "feu_max": 12, "hextech_lent": 25,
               "chemtech_pv": 35, "nashor_res": 15, "ancestral_seuil": 20, "charge": 280}

# --- Arène (PvP) --------------------------------------------------------------
# (points nécessaires, nom du rang et du rôle Discord, emoji, couleur du rôle)
ARENE_RANGS = [
    (0, "Fer", "⚫", 0x5E5E5E), (100, "Bronze", "🟤", 0xA0522D), (200, "Argent", "⚪", 0xB0BEC5),
    (300, "Or", "🟡", 0xF1C40F), (400, "Platine", "🔷", 0x1ABC9C), (500, "Émeraude", "🟢", 0x2ECC71),
    (600, "Diamant", "💎", 0x5DADE2), (700, "Maître", "🟣", 0x9B59B6), (850, "Grand Maître", "🔴", 0xE74C3C),
    (1000, "Challenger", "👑", 0xF39C12),
]
ARENE_COMBATS_PAR_JOUR = 5
ARENE_MAX_CONTRE_UN_JOUEUR = 2   # combats par jour contre le même joueur
ARENE_PERTES_DEFENSE_PAR_JOUR = 3  # au-delà, une défense perdue ne coûte plus de points ce jour-là
ARENE_DELAI_MESSAGE = 600        # secondes minimum entre deux messages privés d'arène au même joueur
ARENE_GAIN = 20              # points gagnés en battant un joueur (+ bonus s'il est mieux classé)
ARENE_PERTE = 10             # points perdus en perdant contre un joueur
ARENE_DEFENSE_PERDUE = 5     # points perdus par le défenseur battu
ARENE_DEFENSE_TENUE = 3      # points gagnés par le défenseur qui résiste
# Reflets : adversaires d'entraînement quand il n'y a pas assez de joueurs. facteur de puissance -> (gain, perte)
ARENE_REFLETS = {0.85: (8, 4), 1.0: (12, 5), 1.15: (16, 6)}

# --- Duels en direct ----------------------------------------------------------
# Les duels sont illimités, mais seuls les premiers de la journée comptent pour le classement (sinon deux amis
# pourraient s'échanger des points sans fin). Un seul duel classé par jour contre le même adversaire.
DUELS_CLASSES_PAR_JOUR = 3
DUEL_GAIN = 15               # points gagnés par le vainqueur d'un duel classé
DUEL_PERTE = 10              # points perdus par le perdant d'un duel classé
SALON_DUELS = "🤺・duels"

# --- Rangement du serveur -----------------------------------------------------
# Catégories créées par /installer, dans cet ordre, avec les salons qu'elles contiennent (clés des panneaux,
# ou "tirages" / "discussion" pour les salons sans boutons). Renomme ou réorganise librement, puis tape /installer.
# --- Tour des pros (en construction : salon privé et mode test tant que TOUR_PROS_OUVERTE est faux) ---
SALON_TOUR_PROS = "🏆・worlds"   # le mode s'appelle « Worlds » ; le code garde le nom tour_pros
TOUR_PROS_OUVERTE = True
WORLDS_BOUTONS_TEST = False
TOUR_PROS_UR = 1.2            # une carte UR jouée par un pro a ses PV et son attaque multipliés par ce nombre
# Coachs (cartes de pro) : bonus donné à toute l'équipe, selon l'équipe du pro (KC ... T1, puis Faker). Le coach Mid (ulti) vaut 1,5 fois plus.
WORLDS_COACHS = [0.06, 0.08, 0.10, 0.12, 0.14, 0.17, 0.20, 0.25]
WORLDS_COACH_ULTI = 1.5
WORLDS_COACH_AILLEURS = 0.5      # hors des Worlds et du raid, un coach ne donne que cette part de son bonus
WORLDS_POSTES = {"Top": "pv", "Jungle": "vitesse", "Mid": "ulti", "ADC": "atk", "Support": "soin"}   # ce que renforce un coach, selon son poste
# Ouverture de la LEC à tous : en même temps, le ticket Worlds devient obligatoire et le repos des Worlds passe de 8 h à 3 h.
LEC_OUVERTE = True
WORLDS_REPOS = 0                 # plus de repos des cartes aux Worlds depuis les tickets (12 octobre, 20h30)
WORLDS_TICKETS = LEC_OUVERTE     # vrai : il faut un ticket Worlds pour lancer un tournoi des Worlds (un ticket par joueur, rendu si l'inscription est annulée)
WORLDS_TICKETS_MAX = 5           # tickets Worlds qu'on peut garder au plus (on en gagne un en atteignant la finale de la LEC)
WORLDS_TICKETS_DEPART = 2        # tickets Worlds de chacun à l'ouverture de la LEC, et d'un nouveau compte
LEC_TICKETS_FINALE = 2           # tickets Worlds gagnés en atteignant la finale de la LEC (13 octobre : 2 au lieu de 1)
LEC_TICKETS_VICTOIRE = 1         # ticket Worlds en plus en remportant la LEC (battre Movistar KOI)
DEPART_VICTOIRES = 3             # 13 octobre : une équipe battue 3 fois par tout le groupe permet de commencer le tournoi à elle
DEPART_MINIMUM = 1                # 14 octobre : départ direct ouvert dès que l'équipe a été battue une fois (avant : DEPART_VICTOIRES)
WORLDS_DEPART = 3                 # 14 octobre : aux Worlds, le seul départ direct est BLG (LEC : LEC_DEPART, Team Vitality)
WORLDS_DEPARTS = [3, 5]           # 28 octobre : départs directs possibles aux Worlds, BLG et Gen.G (une fois l'équipe battue par tout le groupe)
WORLDS_DEPART_MAX = 4            # 13 octobre (18 h) : aux Worlds, le départ direct va au plus jusqu'à HLE (Gen.G, T1 et Faker se jouent toujours)
LEC_DEPART = 3                   # LEC : le départ direct se fait seulement à Team Vitality (demi-finale)
# Pack pro : gagné en éliminant des équipes (palier de la dernière équipe éliminée x WORLDS_PACKS_PAR_PALIER, une fois par jour,
# seul le meilleur tournoi du jour compte). Il ne contient que les cartes des équipes déjà éliminées par le joueur.
WORLDS_PACKS_PAR_PALIER = 2
TAUX_PRO = {"SR": 73, "SSR": 23, "UR": 2, "coach": 2}
WORLDS_LR = 0.5                  # % de LR de Faker, pris sur les SR, une fois Faker battu
PITIE_PRO_UR = 50                # UR garanti au bout de ce nombre de packs pro sans UR (dès qu'une équipe éliminée en possède une)
PITIE_PRO = 0                    # (garanti SSR des packs pro retiré le 12 octobre, depuis qu'un pack pro donne 3 cartes)
PRO_CARTES_BONUS = 2             # cartes bonus d'un pack pro (SR ou SSR, sans UR), en plus de la carte principale
WORLDS_COACH_POIDS = [10, 8, 6, 5, 4, 3, 2]   # poids d'un coach au tirage, selon son équipe (KC ... T1)
WORLDS_COACH_FAKER = 2           # % des tirages de coach qui donnent Faker, une fois qu'il est battu
# Mode test : le propriétaire joue les trois places avec une copie des équipes de ces trois joueurs (rien n'est modifié chez eux).
TOUR_PROS_TEST = [100000000000000002, 100000000000000006, 100000000000000003]
# Remplacements pour le mode test seulement : {joueur copié: {carte de son équipe: (carte à tester, niveau, étoiles)}}. Rien n'est changé chez le joueur.
# Deuxième équipe de test : les trois places disposent chacune de ces cartes au niveau 100, sans limite (aucune n'est grillée),
# avec un item au niveau maximum et une rune : {carte: (item, rune)}.
TOUR_PROS_TEST_UR = {"GarenUR": ("warmog", "poigne"), "AatroxUR": ("soif_de_sang", "conquerant"), "VayneUR": ("lame_infini", "tempo"),
                     "SennaUR": ("rappel", "conquerant"), "LuxUR": ("rabadon", "comete"), "MaokaiUR": ("warmog", "poigne")}
TOUR_PROS_TEST_REMPLACE = {100000000000000002: {"Karthus": ("GarenUR", 50, 0)}}
TOUR_PROS_TEST_NIVEAU = {100000000000000003: {"Yasuo": 100}}   # niveau forcé, uniquement dans le mode test des Worlds
# Phases prévues, dans l'ordre des Worlds : Play-In (Karmine Corp), Phase suisse 1 à 3 (Invictus Gaming, G2, BLG), Quart de finale (HLE),
# Demi-finale (Gen.G), Finale (T1), puis Faker seul en dernier match de la finale.
# Forces réglées le 11 octobre 2026 sur une équipe repère : trois UR différentes au niveau 100, item au maximum et rune, qui joue les trois
# matchs sans rien griller. Elle gagne en moyenne 89 % contre BLG, 66 % contre HLE, 59 % contre Gen.G, 51 % contre T1 et 49 % contre Faker.
# 13 octobre (discret) : Gen.G 165 → 169,5, T1 183 → 187,5, Faker 180 → 186. Calé sur le meilleur groupe réel du serveur : environ 70 % contre Gen.G, 50 % contre T1, 35 % contre Faker.
# À partir de HLE, la force baisse alors que la difficulté monte : ce sont les cartes UR adverses (×TOUR_PROS_UR) qui font la différence.
# Un palier = une équipe de trois pros, affrontés l'un après l'autre. « force » : étage de la tour dont ils ont la puissance.
# pros : (page du joueur dans pros/pros.json, poste affiché, ses trois champions).
TOUR_PROS = [
    {"equipe": "Karmine Corp", "phase": "Play-In", "logo": "logo_karmine.png", "entree": "fond_karmine.jpg", "fond": "fond_karmine.jpg", "couleur": (30, 130, 255), "clarte": 1.15, "force": 85, "pros": [
        ("Canna", "Top", ["Rumble", "Gnar", "Jayce"]),
        ("Yike", "Jungle", ["Viego", "Qiyana", "Khazix"]),
        ("Caliste", "ADC", ["Draven", "Kalista", "Caitlyn"])]},
    {"equipe": "Invictus Gaming", "phase": "Phase suisse · round 1", "logo": "logo_ig.png", "entree": "fond_ig.jpg", "fond": "fond_ig.jpg",
     "couleur": (225, 225, 240), "clarte": 0.95, "force": 110, "pros": [
        ("TheShy", "Top", ["Aatrox", "Fiora", "Jayce"]),
        ("Rookie", "Mid", ["Leblanc", "Syndra", "Orianna"]),
        ("JackeyLove", "ADC", ["Kaisa", "Xayah", "Ezreal"])]},
    # "bonus" : un pro plus fort que ses coéquipiers (multiplicateur de puissance). Une carte UR adverse est déjà plus forte d'elle-même.
    {"equipe": "G2 Esports", "phase": "Phase suisse · round 2", "logo": "logo_g2.png", "entree": "fond_g2.jpg", "fond": "fond_g2.jpg",
     "couleur": (235, 45, 45), "clarte": 0.95, "force": 120, "bonus": {"BrokenBlade": 0.93, "Caps": 1.04}, "pros": [
        ("BrokenBlade", "Top", ["KSante", "Ornn", "Yone"]),
        ("Hans Sama", "ADC", ["Draven", "MissFortune", "Kalista"]),
        ("Caps", "Mid", ["Sylas", "TristanaUR", "Syndra"])]},
    {"equipe": "Bilibili Gaming", "phase": "Phase suisse · round 3", "logo": "logo_blg.png", "entree": "fond_blg.jpg", "fond": "fond_blg.jpg",
     "couleur": (70, 195, 255), "clarte": 0.82, "force": 122, "bonus": {"Knight (Zhuo Ding)": 1.08, "Viper (Park Do-hyeon)": 1.18, "Bin (Chen Ze-Bin)": 1.13}, "pros": [
        ("Knight (Zhuo Ding)", "Mid", ["Ahri", "Syndra", "Sylas"]),
        ("Viper (Park Do-hyeon)", "ADC", ["Aphelios", "Ezreal", "Kaisa"]),
        ("Bin (Chen Ze-Bin)", "Top", ["JaxUR", "Camille", "Gwen"])]},
    {"equipe": "HLE", "phase": "Quart de finale", "logo": "logo_hle.png", "entree": "fond_hle.jpg", "fond": "fond_hle.jpg", "clarte": 0.85, "couleur": (255, 120, 20), "force": 129, "bonus": {"Gumayusi": 1.0, "Zeka (Kim Geon-woo)": 0.85, "Zeus": 0.98}, "pros": [
        ("Gumayusi", "ADC", ["Ziggs", "VarusUR", "Jhin"]),
        ("Zeka (Kim Geon-woo)", "Mid", ["AkaliUR", "Sylas", "Yone"]),
        ("Zeus", "Top", ["Ambessa", "Yone", "JayceUR"])]},
    {"equipe": "Gen.G", "phase": "Demi-finale", "logo": "logo_geng.png", "entree": "fond_geng.jpg", "fond": "fond_geng.jpg",
     "couleur": (200, 160, 60), "clarte": 1.12, "force": 137, "bonus": {"Canyon": 0.94, "Ruler": 1.01, "Chovy": 1.01}, "pros": [
        ("Canyon", "Jungle", ["NidaleeUR", "LeeSin", "Graves"]),
        ("Ruler", "ADC", ["Ashe", "Zeri", "XayahUR"]),
        ("Chovy", "Mid", ["Corki", "YoneUR", "Azir"])]},
    {"equipe": "T1", "phase": "Finale", "logo": "logo_t1.png", "entree": "fond_t1.jpg", "fond": "fond_t1.jpg",
     "couleur": (226, 1, 45), "clarte": 1.0, "force": 147, "bonus": {"Peyz": 0.92, "Oner": 1.05, "Keria": (1.09, 1.21)}, "pros": [
        ("Peyz", "ADC", ["ZeriUR", "Aphelios", "Kaisa"]),
        ("Oner", "Jungle", ["LeeSin", "ViegoUR", "XinZhao"]),   # 12 octobre : Xin Zhao T1 part chez Elyoya (LEC) ; Viego UR à venir
        ("Keria", "Support", ["BardUR", "Thresh", "Renata"])]},
    # Le boss final, seul, après la finale. Ses trois cartes deviendront des LR.
    {"equipe": "T1", "phase": "Grande finale · Faker", "da": "faker", "logo": "logo_t1.png", "entree": "fond_faker.jpg", "fond": "fond_faker.jpg", "clarte": 0.92, "couleur": (226, 1, 45), "force": 150, "bonus": {"Faker": 1.06}, "pros": [
        ("Faker", "Mid", ["AzirLR", "AhriLR", "RyzeLR"])]},
]

# Les coachs, calculés depuis TOUR_PROS : pseudo court -> ce que la carte de pro apporte.
COACHS = {}
for _k, _palier in enumerate(TOUR_PROS):
    for _pseudo, _poste, _champions in _palier["pros"]:
        _stat = WORLDS_POSTES.get(_poste, "pv")
        _valeur = WORLDS_COACHS[min(_k, len(WORLDS_COACHS) - 1)] * (WORLDS_COACH_ULTI if _stat == "ulti" else 1)
        COACHS[_pseudo.split(" (")[0]] = {"stat": _stat, "valeur": round(_valeur, 3), "equipe": _k, "poste": _poste, "page": _pseudo,
                                          "nom_equipe": "T1" if _k == len(TOUR_PROS) - 1 else _palier["equipe"], "champions": list(_champions)}
# Cartes d'un pack pro, par équipe : les champions de ses pros qui ne sortent pas des packs normaux (rempli plus bas, une fois « en_jeu » connu).
# Champions joués par un pro mais introuvables, même dans les packs pro : ils existent en LR (12 octobre).
WORLDS_SANS_CARTE = {"Ahri", "Azir", "Ryze"}
WORLDS_CARTES = [sorted({c for _p, _po, _ch in _pal["pros"] for c in _ch
                         if not CARTES[c]["en_jeu"] and not c.endswith("LR") and c not in WORLDS_SANS_CARTE}) for _pal in TOUR_PROS]
WORLDS_LRS = sorted(c for c in TOUR_PROS[-1]["pros"][0][2] if c.endswith("LR"))

# --- LEC (12 octobre, en construction : salon privé et mode test tant que LEC_OUVERTE est faux) ---
# Même moteur que les Worlds (3 joueurs, 3 cartes, une carte par pro et par équipe), sur 5 équipes, avec peu d'animation.
# Les champions des pros sont provisoires (cartes déjà dans le jeu), en attendant de choisir ceux de la région.
SALON_LEC = "🇪🇺・lec"
LEC_REPOS = 0                    # plus de repos des cartes à la LEC depuis le mode solo (12 octobre, 18h45)
LEC_ESSAIS = 1                   # 13 octobre : 1 au lieu de 2. LEC solo : tournois par jour et par joueur (un tournoi lancé compte, quel qu'en soit le résultat)
LEC_PALIERS = [
    {"equipe": "Los Ratones", "phase": "Semaine 1", "fond": "fond_ratones.jpg", "entree": "fond_ratones.jpg", "force": 50, "couleur": (230, 230, 230), "pros": [
        ("Baus", "Top", ["Sion", "GragasUR", "Chogath"]),
        ("Velja", "Jungle", ["MasterYi", "Shaco", "Viego"]),
        ("Rekkles", "Support", ["Janna", "Sivir", "Rakan"])]},
    {"equipe": "GIANTX", "phase": "Semaine 2", "fond": "fond_giantx.jpg", "entree": "fond_giantx.jpg", "force": 60, "couleur": (120, 200, 255), "pros": [
        ("Oscarinin", "Top", ["Renekton", "KSante", "Gnar"]),
        ("Jackies", "Mid", ["Akali", "Sylas", "Yone"]),
        ("Flakked", "ADC", ["Senna", "Kaisa", "Ezreal"])]},
    {"equipe": "NAVI", "phase": "Semaine 3", "fond": "fond_navi.jpg", "entree": "fond_navi.jpg", "force": 70, "couleur": (255, 230, 0), "pros": [
        ("Rhilech", "Jungle", ["Vi", "Khazix", "Nidalee"]),
        ("Poby", "Mid", ["Syndra", "Orianna", "Annie"]),
        ("Hans SamD", "ADC", ["Draven", "MissFortune", "Caitlyn"])]},
    {"equipe": "Team Vitality", "phase": "Demi-finale", "fond": "fond_vitality.jpg", "entree": "fond_vitality.jpg", "force": 85, "couleur": (250, 210, 0), "pros": [
        ("Naak Nako", "Top", ["Aatrox", "Gwen", "Jax"]),
        ("Lyncas", "Jungle", ["Amumu", "Khazix", "Zed"]),
        ("Carzzy", "ADC", ["Vayne", "Jhin", "Kaisa"])]},
    {"equipe": "Movistar KOI", "phase": "Finale", "fond": "fond_koi.jpg", "entree": "fond_koi.jpg", "force": 115, "bonus": {"Elyoya": 0.93}, "couleur": (0, 160, 255), "pros": [
        ("Supa", "ADC", ["Kalista", "Varus", "Jinx"]),
        ("Elyoya", "Jungle", ["XinZhaoUR", "LeeSin", "Sejuani"]),
        ("Jojopyun", "Mid", ["SylasUR", "Leblanc", "Orianna"])]},
]


# --- Récompenses de la LEC ---
# Packs LEC selon la dernière équipe battue (total du tournoi, chaque tournoi compte) : Los Ratones 1, GIANTX 2, NAVI 4, Vitality 6, KOI 12.
LEC_PACKS = [4, 8, 12, 16, 40]
# Contenu d'un pack LEC, en % : seulement les champions des équipes LEC battues par le joueur. Chaque UR a son propre taux ; une UR déjà
# possédée ne peut pas tomber (sa part revient aux SSR). Pas de garanti UR ; un SSR garanti au bout de LEC_PITIE packs sans SSR ni mieux.
LEC_TAUX = {"SR": 74, "SSR": 23.5, "coach": 1}
LEC_UR = {"GragasUR": 0.6, "XinZhaoUR": 0.6, "SylasUR": 0.3}
LEC_PITIE = 10
LEC_CARTES = [sorted({c for _p, _po, _ch in _pal["pros"] for c in _ch if not c.endswith("LR")}) for _pal in LEC_PALIERS]
# Coachs LEC : plus faibles que ceux des Worlds, et le même bonus partout (pas de bonus complet aux Worlds et au raid). Mid : x1,5 (ulti).
LEC_COACHS = [0.03, 0.04, 0.05, 0.06, 0.07]
LEC_COACH_POIDS = [10, 8, 6, 5, 4]
for _k, _palier in enumerate(LEC_PALIERS):
    for _pseudo, _poste, _champions in _palier["pros"]:
        _stat = WORLDS_POSTES.get(_poste, "pv")
        COACHS.setdefault(_pseudo, {"stat": _stat, "valeur": round(LEC_COACHS[_k] * (WORLDS_COACH_ULTI if _stat == "ulti" else 1), 3), "equipe": -1, "lec": _k,
                                    "poste": _poste, "page": _pseudo, "nom_equipe": _palier["equipe"], "champions": list(_champions), "partout": True})


def part_coach(pseudo, plein):
    """La part du bonus qu'un coach donne : tout aux Worlds et au raid (plein), WORLDS_COACH_AILLEURS ailleurs ; un coach LEC donne tout partout."""
    c = COACHS.get(pseudo) or {}
    return 1.0 if plein or c.get("partout") else WORLDS_COACH_AILLEURS


def texte_bonus_coach(pseudo, part=1.0):
    """« +14 % de PV » : le bonus d'un coach, en clair."""
    c = COACHS[pseudo]
    noms = {"pv": "de PV", "atk": "d'attaque", "vitesse": "de vitesse", "ulti": "de dégâts d'ulti", "soin": "de soins et boucliers"}
    return f"+{round(c['valeur'] * part * 100)} % {noms[c['stat']]}"

# Tant que c'est vrai, aucune note n'est publiée dans le salon des mises à jour (elles attendent, rien n'est perdu).
MAJ_EN_PAUSE = False

CATEGORIES = [
    ("🏠 2HOT4DECK", ["accueil", "annonces", "guide", "maj", "tirages", "discussion"]),
    ("🎒 INVENTAIRE", ["profil", "packs", "collection", "coffre"]),
    ("⚔️ PVE", ["tour", "jungle", "donjons", "boss", "raid"]),
    ("🎲 MINI-JEUX", ["quiz", "pros"]),
    ("🏆 PVP", ["arene", "duels"]),
]
ANCIENNE_CATEGORIE = "🏠 LA FAILLE"   # catégorie de l'ancien nom du jeu, supprimée une fois vide

# --- Règles de bonne conduite affichées dans le guide (modifie-les librement) --
# Rôle donné en appuyant sur Commencer : il débloque tous les salons du jeu. Sans lui, on ne voit que les salons publics.
ROLE_JOUEUR = "Invocateur"
COULEUR_ROLE_JOUEUR = 0x0AC8B9
SALONS_PUBLICS = ("accueil", "guide", "maj")

REGLES_SERVEUR = [
    "Un seul compte par personne.",
    "Un bug ? Signale-le dans le salon de discussion au lieu d'en profiter.",
    "Pas d'arrangement pour s'échanger des points de classement.",
    "On reste bon joueur, en victoire comme en défaite.",
]


# --- Notes de mise à jour ------------------------------------------------------
# Le bot publie chaque note une seule fois dans le salon des mises à jour, au démarrage.
# Pour annoncer une nouveauté : ajouter une entrée À LA FIN (clé unique, date, titre, texte). Ne jamais modifier une clé déjà publiée.
MISES_A_JOUR = [
    ("2026-10-10-alpha-2", "10 octobre 2026", "Alpha 2 · on repart de zéro", (
        "**🔄 Remise à zéro générale**\n"
        "Fin de la première alpha : tous les comptes repartent de zéro. Appuie sur **Commencer** dans l'accueil pour recevoir ton nouveau pack de départ.\n\n"
        "**🗼 La tour devient un mur**\n"
        "• Elle est gratuite et beaucoup plus dure : retente autant que tu veux.\n"
        "• Un pack avec **SR garanti** tous les 5 étages, un pack à **taux doublés** après chaque boss.\n\n"
        "**🌿 Nouveau : la jungle**\n"
        "• Le salon pour s'entraîner : XP, golds, et 3 % de chance de trouver un pack gratuit.\n"
        "• Chaque victoire coûte 1 ⚡. Tu as 12 ⚡ au maximum et tu en regagnes 1 toutes les 2 heures.\n\n"
        "**✨ Des champions uniques**\n"
        "• Chaque champion a maintenant son **passif** et son **actif** : lis leur fiche dans la collection.\n"
        "• **Vitesse** : un champion rapide joue plus souvent. **Physique et magique** : chacun a ses résistances.\n"
        "• **Leader** : le premier champion de ton équipe 👑 donne le bonus de sa région à tout le monde.\n"
        "• Nouvelle championne : **Senna**. Ahri et Katarina quittent les packs.\n\n"
        "**🎒 Les items**\n"
        "• Un item à choisir parmi 3 tous les 20 étages et tous les 2 rangs de classement, à équiper sur le champion de ton choix.\n\n"
        "**🎁 Les packs**\n"
        "• Les belles cartes sont plus rares : SSR 2 %, SR 8 %. Garantie SSR au bout de 80 packs.\n\n"
        "**🏟️ L'arène**\n"
        "• Tu n'affrontes plus que des joueurs proches de ton rang.\n\n"
        "**🔓 Le serveur**\n"
        "• Les salons du jeu se débloquent en appuyant sur Commencer, avec le rôle **Invocateur**.")),
    ("2026-10-10-donjons", "10 octobre 2026", "Donjons, forge et niveau de compte", (
        "**⚒️ Nouveau : les donjons et la forge**\n"
        "• Trois donjons, chacun avec ses **composants**. 3 victoires par jour, une défaite ne compte pas.\n"
        "• À **la forge**, assemble deux types de composants pour fabriquer un item, puis améliore-le jusqu'au niveau 3.\n"
        "• Les items ne se gagnent plus dans la tour ni au classement : tout passe par la forge.\n\n"
        "**🗼 La tour : des champions en face**\n"
        "• Chaque étage t'oppose à des champions adverses, avec leurs vrais passifs et leurs ultis. Un étage a toujours la même équipe : à toi de trouver la bonne réponse.\n"
        "• Les boss restent le Héraut, les drakes et Nashor.\n\n"
        "**🎯 Le SSR ciblé**\n"
        "• Dans le salon des packs, choisis le SSR que tu veux viser : quand un SSR tombe, une fois sur deux c'est lui.\n\n"
        "**⭐ Le niveau de compte**\n"
        "• Tout ce que tu fais rapporte de l'XP de compte. Chaque niveau donne des golds et recharge ton énergie.\n"
        "• Un pack tous les 5 niveaux, avec SR garanti tous les 10.\n"
        "• Les modes se débloquent peu à peu : jungle au niveau 2, donjons au niveau 4, arène et duels au niveau 6.\n"
        "• Ton profil est dans le salon du profil.")),
    ("2026-10-10-debut-facile", "10 octobre 2026", "Un début plus rapide, un premier boss redoutable", (
        "**🗼 La tour**\n"
        "• Les étages 1 à 9 sont maintenant faciles : de quoi découvrir le jeu et t'offrir tes 10 premiers packs.\n"
        "• Le **Héraut de l'étage 10** devient le premier vrai mur. Il te faudra trois champions solides.\n"
        "• Les boss ne peuvent plus être étourdis ni aveuglés.\n\n"
        "**🌿 La jungle**\n"
        "• Un seul niveau, un seul bouton **Chasser** : les monstres s'adaptent à ton étage.\n\n"
        "**🔓 Les déblocages**\n"
        "• Jungle au niveau 2, arène et duels au niveau 5, donjons au niveau 8.\n\n"
        "**🏅 Les rôles de niveau**\n"
        "• Un rôle Discord tous les 10 niveaux de compte : " + ", ".join(f"{nom} (niv. {n})" for n, nom, _ in ROLES_NIVEAU) + ".")),
    ("2026-10-10-profil", "10 octobre 2026", "Un salon pour ton profil", (
        "**👤 Nouveau salon : profil**\n"
        "• Le bouton **Mon profil** affiche tes golds, ton niveau de compte, ton énergie, ton étage, ton rang et tes donjons restants.\n"
        "• Le bouton **Classement des niveaux** montre les comptes les plus avancés du serveur.")),
    ("2026-10-10-tour-100", "10 octobre 2026", "Une tour de 100 étages et des boss uniques", (
        "**🗼 La tour passe à 100 étages**\n"
        "• Les 19 premiers étages sont faciles : le début du jeu va vite.\n"
        "• **Étage 10** : les larves du Néant, un boss d'échauffement.\n"
        "• **Étage 20** : le Héraut de la Faille, premier mur. Il se passe avec une vraie équipe.\n"
        "• **Étage 30** : le Drake des nuages, premier vrai mur. Puis un drake tous les 10 étages, le Baron Nashor au 90 et le Dragon ancestral au 100.\n\n"
        "**👹 Chaque boss a sa particularité**\n"
        "• Le drake des nuages est très rapide, celui des montagnes a une carapace, celui des océans se soigne, l'infernal frappe de plus en plus fort… "
        "Regarde **Voir l'étage** avant de l'affronter.\n"
        "• Les boss ne peuvent être ni étourdis, ni aveuglés, ni exécutés.\n\n"
        "**⚡ Énergie**\n"
        "• Monter de niveau de compte recharge ton énergie. Au début, vider tes 12 ⚡ dans la jungle suffit à passer un niveau : tu peux enchaîner.\n\n"
        "**🔓 Déblocages**\n"
        "• Jungle au niveau 2, arène et duels au niveau 6, donjons et forge au niveau 8.\n\n"
        "**🗑️ Bêta : réinitialiser son compte**\n"
        "• Dans le salon du profil, un bouton permet d'effacer ton compte pour retester le début. Autant de fois que tu veux.")),
    ("2026-10-10-2hot4deck", "10 octobre 2026", "Le jeu s'appelle 2Hot4Deck, et il change de look", (
        "**🔥 Nouveau nom : 2Hot4Deck**\n"
        "La Faille devient **2Hot4Deck**. Tes cartes, tes golds et ta progression ne bougent pas.\n\n"
        "**🃏 Des cartes encadrées**\n"
        "• Chaque carte a maintenant un cadre selon sa rareté, avec son rôle, sa région et l'emblème de sa région.\n\n"
        "**📦 Les packs s'ouvrent dans un coffre**\n"
        "• Un coffre s'ouvre à chaque pack, à la couleur de la rareté obtenue. Par dix, il prend la couleur de la meilleure carte.\n"
        "• Même chose pour le pack de départ et les packs gagnés aux paliers.\n\n"
        "**⚔️ Les combats en image**\n"
        "• Les deux équipes s'affichent face à face avec de grandes barres de vie. Les boss ont leur illustration.")),
    ("2026-10-10-energie-jungle", "10 octobre 2026", "Plus d'énergie en montant de niveau, et la chasse groupée", (
        "**⚡ Ta barre d'énergie grandit**\n"
        "• Chaque niveau de compte ajoute **+1 d'énergie maximale** (12 au niveau 1). Monter de niveau recharge toujours toute la barre.\n"
        "• En échange, les niveaux de compte demandent un peu plus d'XP à chaque fois (+10 % par niveau).\n\n"
        "**🌿 Chasse groupée dans la jungle**\n"
        "• Après **100 camps** nettoyés, tu peux chasser **×5** d'un coup. Après **500 camps**, **×10**.\n"
        "• Une chasse groupée coûte 5 ou 10 ⚡ et rapporte 5 ou 10 fois le butin, chance de pack comprise.")),
    ("2026-10-10-defis", "10 octobre 2026", "Les donjons défi et leurs totems", (
        "**🗿 Donjons défi** (idée d'un joueur, merci !)\n"
        "• Dans le salon des donjons, le bouton **Donjon défi** te fait affronter trois champions de la force d'un étage élevé de la tour.\n"
        "• Chaque défi se gagne une seule fois, les essais sont gratuits et illimités.\n"
        "• Chaque victoire donne un **totem** permanent qui accélère la recharge de ton énergie : "
        "1 h 45 → 1 h 30 → 1 h 15 → 1 h (au lieu de 2 h).\n"
        "• Les défis ont la force des étages 30, 50, 70, 90 de la tour.")),
    ("2026-10-10-expedition", "10 octobre 2026", "Le coffre devient l'expédition, et les vieux messages s'effacent", (
        "**🧭 L'expédition**\n"
        "• Le salon du coffre s'appelle maintenant **expédition** : ton équipe part en expédition quand tu n'es pas là, et tu récupères son butin. Rien d'autre ne change.\n\n"
        "**🧹 Moins de messages qui s'empilent**\n"
        "• Quand tu rappuies sur un bouton d'un panneau, ton ancien message privé de ce salon s'efface.\n"
        "• Un message privé resté sans clic disparaît tout seul au bout d'une douzaine de minutes.\n\n"
        "**🖼️ Nouvelles bannières** dans tous les salons.")),
    ("2026-10-10-lignes", "10 octobre 2026", "Ligne avant, ligne arrière, et une arène pour les combats", (
        "**🛡️ Deux lignes de combat**\n"
        "• Dans **Composer mon équipe**, chaque carte se place **devant** ou **derrière**, librement.\n"
        "• Placée sur la ligne de son rôle, elle gagne un petit bonus : tank devant " + TEXTES_LIGNE["tank"] + ", combattant devant " + TEXTES_LIGNE["combattant"]
        + ", assassin devant " + TEXTES_LIGNE["assassin"] + ", tireur derrière " + TEXTES_LIGNE["tireur"] + ", mage derrière " + TEXTES_LIGNE["mage"]
        + ", support derrière " + TEXTES_LIGNE["support"] + ".\n"
        f"• Dans les combats automatiques, les ennemis visent ta ligne avant {CIBLE_AVANT} fois sur 100 (sauf les assassins et les attaques de zone). "
        "La provocation reste la seule façon de forcer une cible, et en duel tu vises qui tu veux.\n"
        "• Ton équipe actuelle est déjà placée selon le rôle de ses cartes : tu n'as rien à faire pour avoir tes bonus.\n\n"
        "**🏟️ Nouvel écran de combat**\n"
        "• Les combats se déroulent dans une arène : ton équipe à gauche, l'adversaire à droite, la ligne avant vers le centre.")),
    ("2026-10-10-cible-20", "10 octobre 2026", "SSR ciblé : 20 %, et une nouvelle cible dès que tu l'obtiens", (
        "**🎯 SSR ciblé**\n"
        f"• Quand un SSR tombe, il a maintenant **{CIBLE_CHANCE} %** de chances d'être celui que tu vises (au lieu de 50 %).\n"
        "• Dès que tu obtiens ton SSR ciblé, tu peux **choisir une nouvelle cible tout de suite**, sans attendre le lendemain.")),
    ("2026-10-10-jungle-moins", "10 octobre 2026", "La jungle rapporte un peu moins au compte", (
        "**🌿 Jungle**\n"
        f"• Une chasse donne maintenant **{XP_COMPTE['jungle']} XP de compte** (au lieu de 15) et **{JUNGLE_GOLDS[0]} golds de base** (au lieu de 8).\n"
        "• L'XP gagnée par tes cartes ne change pas : la jungle reste le meilleur endroit pour les entraîner.\n"
        "• Le but : que chasser en boucle ne suffise plus à enchaîner les niveaux de compte et les packs sans jamais s'arrêter.")),
    ("2026-10-10-clear-jungle", "10 octobre 2026", "Le clear de jungle, l'item du Héraut et la fin des SR garantis", (
        "**🌿 Clear de jungle** (nouveau mini-jeu)\n"
        f"• Mise ton énergie ({CLEAR_MISE_MIN} au minimum, jusqu'à toute ta barre) : ton équipe enchaîne jusqu'à {len(CLEAR_PARTS)} camps, **sans récupérer ses PV**.\n"
        "• Après chaque camp : **Continuer** (le butin grossit de plus en plus) ou **Rentrer à la base** (tu gardes tout). Si ton équipe tombe, tu n'en gardes que la moitié.\n"
        f"• Sur le dernier camp, appuie sur **Châtiment** au bon moment pour +{round((CLEAR_CHATIMENT - 1) * 100)} % de butin.\n"
        "• La chasse simple existe toujours (**Chasse rapide**), mais un clear complet rapporte plus.\n\n"
        "**🎁 Le butin du Héraut**\n"
        f"• Vaincre le Héraut (étage {ITEM_ETAGE}) offre **un item au choix parmi trois**. Si tu l'as déjà battu, il t'attend au prochain combat de tour.\n\n"
        "**📦 Packs de palier**\n"
        "• Plus de SR garanti dans la tour ni aux niveaux de compte : à la place, des **packs à taux doublés** tous les 5 étages et tous les 10 niveaux.\n"
        "• Le pack de dix (au moins un SR) et le pack de départ ne changent pas.")),
    ("2026-10-10-exploration", "10 octobre 2026", "La jungle devient une carte à explorer", (
        "**🗺️ Exploration de la jungle** (remplace le clear de jungle)\n"
        "• Une carte de 16 buissons : en fouiller un coûte 1 ⚡. Derrière, un camp de monstres, un trésor, un fruit… ou un **gank** qui te coûte une vie.\n"
        "• Chaque buisson fouillé indique **combien de ganks se cachent autour de lui**, comme au démineur : à toi d'en déduire où ne pas aller.\n"
        f"• Tu as {EXPLO_VIES} vies. À zéro, l'exploration s'arrête. Tu peux aussi rentrer quand tu veux : le butin est gagné au fur et à mesure.\n"
        "• La **Sentinelle bleue** et le **Roncier rouge** se battent au **Châtiment** : appuie au bon moment pour un gros butin. Attention, la bleue se soigne et le rouge s'effondre d'un coup.\n"
        "• La **chasse rapide** reste disponible pour dépenser son énergie sans réfléchir, mais une carte bien jouée rapporte plus.")),
    ("2026-10-10-chasse-rapide", "10 octobre 2026", "Chasse rapide : ×5 pour tous, mais deux fois moins de butin", (
        "**🌿 Chasse rapide**\n"
        "• La chasse **×5** est disponible dès le début (la ×10 reste à débloquer après 500 camps).\n"
        "• En échange, une chasse rapide rapporte maintenant **la moitié** de l'XP et des golds d'avant.\n"
        "• Pour bien gagner, il faut **explorer la jungle** : une carte bien jouée rapporte plus du double pour la même énergie.")),
    ("2026-10-10-exploration-2", "10 octobre 2026", "Jungle : des buissons à prix variable, et plus de chasse rapide", (
        "**🗺️ Exploration**\n"
        "• Un camp, un trésor ou un gros monstre coûte maintenant **un nombre d'énergies tiré au hasard**, et rapporte d'autant plus : un buisson à 6 ⚡ donne six fois le butin. "
        "Plus ta barre d'énergie est grande, plus les buissons peuvent être gros : une barre pleine se dépense en une carte environ.\n"
        "• Un gank, un buisson vide, une balise ou un fruit coûtent toujours 1 ⚡. S'il te reste moins que le prix, tu paies ce que tu as.\n"
        f"• **Au {EXPLO_VIES}e gank, la carte est réinitialisée** : nouveaux buissons, et on repart. Un fruit de miel efface un gank.\n"
        "• " + " · ".join(f"{c} camps nettoyés : +{b} % de butin" for c, b in EXPLO_BONUS) + ".\n\n"
        "**🌿 La chasse rapide disparaît**, avec ses ×5 et ×10 : toute l'énergie se dépense en explorant.")),
    ("2026-10-10-qui-est-ce", "10 octobre 2026", "Nouveau salon : Qui est ce champion ?", (
        "**❓ Qui est ce champion ?**\n"
        "• Chaque jour, **le même champion mystère pour tout le monde**. Tu vois un tout petit morceau de son illustration et tu écris son nom.\n"
        f"• À chaque erreur, l'image se dévoile un peu plus. Tu as {len(QUIZ_ZOOMS)} essais, et un indice (rôle et région) à partir du troisième.\n"
        "• Moins il te faut d'essais, plus tu gagnes : " + " · ".join(f"{g} golds" for g in QUIZ_GOLDS) + ".\n"
        "• Un **classement du jour** départage les joueurs : d'abord le nombre d'essais, puis le temps mis à répondre.\n"
        "• Garde la réponse pour toi : tout le monde cherche le même champion !")),
    ("2026-10-10-boss-de-salon", "10 octobre 2026", "Les boss de salon : tout le serveur contre un drake", (
        "**🐉 Boss de salon** (nouveau salon)\n"
        "• Tous les jours à " + ", ".join(f"{h} h" for h in BOSS_HEURES) + ", un drake ou le Baron Nashor apparaît pour **tout le serveur**.\n"
        f"• Chaque joueur peut l'attaquer {BOSS_ATTAQUES} fois avec son équipe. Vous avez {BOSS_DUREE // 60} minutes pour le tuer ensemble.\n"
        f"• Sous {BOSS_SEUIL} % de PV, le **Châtiment** se débloque (un seul par joueur). Celui qui porte le **coup fatal** vole le boss : un pack à taux doublés.\n"
        f"• Si le boss meurt, **tout le serveur** gagne son buff pendant {BOSS_BUFF_HEURES} heures : "
        + " · ".join(f"{nom} : {texte}" for _, nom, _, _, texte in BOSS_MONDE) + ".\n"
        "• Tous les participants gagnent des golds et de l'XP, selon leurs dégâts.\n"
        f"• Dans le salon, le bouton **Me prévenir** te donne le rôle {ROLE_BOSS} : tu es mentionné à chaque apparition.")),
    ("2026-10-10-xp-tour", "10 octobre 2026", "La tour rapporte plus d'XP de compte en hauteur", (
        "**🗼 XP de compte de la tour**\n"
        "• Jusqu'à l'étage 19, un étage donne toujours 30 XP de compte. **À partir de l'étage 20**, il en donne 2 % de plus à chaque étage, et **un boss compte 5 fois**.\n"
        "• Exemples : étage 20 (Héraut) 150 XP · étage 30 (Drake) 183 · étage 50 (boss) 272 · étage 75 89 · étage 100 (boss) 731.\n"
        "• L'XP gagnée par tes cartes ne change pas. Les étages déjà passés ne sont pas recomptés.")),
    ("2026-10-10-niveaux-5", "10 octobre 2026", "Les niveaux de compte demandent moins d'XP après le niveau 15", (
        "**⭐ Niveaux de compte**\n"
        "• Jusqu'au niveau 15, rien ne change (+10 % d'XP par niveau). **À partir du niveau 15, la hausse passe à 5 % par niveau.**\n"
        "• Exemples : niveau 20, 485 XP au lieu de 612 · niveau 30, 790 au lieu de 1 586 · niveau 50, 2 095 au lieu de 10 672.\n"
        "• Ton niveau actuel ne change pas ; l'XP déjà gagnée dans ton niveau en cours est gardée.")),
    ("2026-10-10-ganks-mobiles", "10 octobre 2026", "Jungle : les ganks se déplacent, et le clear complet est récompensé", (
        "**🗺️ Exploration**\n"
        "• **Les ganks bougent** : après chaque buisson fouillé, chaque gank caché se glisse dans un buisson voisin. Les chiffres déjà affichés se mettent à jour, à toi de suivre leurs déplacements.\n"
        "• Un gank repéré par une balise ⚠️ reste suivi quand il bouge.\n"
        f"• **Clear complet** : si tu fouilles tout sauf les ganks, tu gagnes **+{EXPLO_CLEAR} % du butin de la carte**, puis une nouvelle carte commence.\n"
        "• Les chiffres ne comptent plus que les ganks encore cachés.")),
    ("2026-10-10-jungle-reglages", "10 octobre 2026", "Jungle : premier buisson sûr, une barre pleine = une carte, plus de balise", (
        "**🗺️ Exploration**\n"
        "• **Ton premier buisson n'est jamais un gank** : tu pars toujours avec un premier chiffre fiable.\n"
        "• Les ganks ne commencent à bouger qu'à partir de ton deuxième buisson.\n"
        "• **Une barre d'énergie pleine paie toujours une carte entière** : les prix des buissons se partagent ton énergie maximale. Le fruit et le buisson vide sont gratuits, un gank coûte 1 ⚡.\n"
        "• La **balise de vision** est retirée : il faut lire les chiffres.")),
    ("2026-10-10-noxus", "10 octobre 2026", "L'Armurerie de Noxus devient une vraie descente (essai)", (
        "**⚔️ Armurerie de Noxus, nouvelle formule**\n"
        "• Trois combats à la suite, **sans récupérer tes PV** : la garde noxienne, **Darius**, puis **Swain** et sa garde. Il faut les battre tous les trois.\n"
        "• Entre deux combats, **un mini-jeu à réussir** pour avancer : soulever la herse au bon moment, puis retenir l'ordre des sceaux. Un échec coûte des PV à toute ton équipe, et tu recommences.\n"
        f"• **Les clés** : entrer est gratuit et tu peux retenter autant que tu veux. Une clé ouvre le coffre ; en mettre plusieurs multiplie le butin. Tu gagnes une clé toutes les {CLES_DELAI // 3600} heures ({CLES_MAX} au maximum).\n"
        "• Les gardiens ont la force de ton étage de la tour : ce n'est plus gagné d'avance, et le coffre est moins rempli qu'avant.\n"
        "• Les deux autres donjons gardent l'ancienne formule pour l'instant.")),
    ("2026-10-10-noxus-code", "10 octobre 2026", "Armurerie de Noxus : le code de la serrure (essai)", (
        "**🔐 Armurerie de Noxus : un jeu de logique**\n"
        "• La descente commence devant une **serrure à 4 sceaux**, tous différents, parmi 5. Propose un code : la serrure te dit combien sont **bien placés** 🟢 et combien sont **mal placés** 🟡. À toi de déduire.\n"
        "• **Chaque essai raté alerte une vague de gardes**, et tes PV ne remontent pas. Mieux tu raisonnes, plus tu arrives frais.\n"
        "• Le code trouvé, il reste à vaincre **Darius**, puis **Swain** et sa garde, avant le coffre. Le code change à chaque descente.\n"
        "• La herse et le jeu de mémoire sont retirés. Les clés et le coffre ne changent pas.")),
    ("2026-10-10-descentes", "10 octobre 2026", "Les trois donjons passent au code et aux clés", (
        "**🔐 Bastion de Demacia et Académie de Piltover : même formule que Noxus**\n"
        "• Une serrure à 4 symboles à déduire, une vague de gardes à chaque essai raté, puis deux gardiens à vaincre : **Garen** et **Galio** à Demacia, **Blitzcrank** et **Ezreal** à Piltover.\n"
        "• **Fini la limite de 3 donjons par jour** : entrer est gratuit et illimité. Ce sont les **clés** qui ouvrent le coffre, et elles sont communes aux trois donjons.\n"
        "• Chaque donjon garde ses propres composants.")),
    ("2026-10-10-pros", "10 octobre 2026", "Nouveau salon : le quiz des pros", (
        "**🎤 Deux mini-jeux par jour sur la scène pro (LCK, LPL, LEC, LCS)**\n"
        "• **Qui est ce pro ?** Une photo, à toi d'écrire son pseudo. Un indice de plus à chaque erreur. Jusqu'à " + f"{PROS_VISAGE_GOLDS[0]} golds.\n"
        "• **L'effectif du jour** : une équipe et une année, par exemple « EDward Gaming 2021 ». Donne le top, le jungler, le mid, l'ADC et le support. "
        + f"{PROS_EQUIPE_GOLDS} golds par joueur trouvé, +{PROS_EQUIPE_BONUS} si tu as les cinq.\n"
        "• Les mêmes questions pour tout le monde, avec un classement du jour. Données : Leaguepedia.")),
    ("2026-10-10-boss-30-50", "10 octobre 2026", "Boss 30 et 50 adoucis, SSR garanti au boss 30", (
        "**🐉 Tour : deux boss moins durs**\n"
        "• **Drake des nuages (étage 30)** : moins de PV, frappe moins fort et un peu moins rapide.\n"
        "• **Drake des océans (étage 50)** : moins de PV, frappe moins fort et se soigne moins.\n"
        f"• **Nouveau** : battre le boss de l'étage {TOUR_SSR_GARANTI} pour la première fois donne un pack avec un **SSR garanti**.")),
    ("2026-10-10-mini-packs", "10 octobre 2026", "Mini-jeux : un pack à gagner, et leur propre catégorie", (
        "**🎲 Les mini-jeux quotidiens donnent maintenant un pack, ouvert tout de suite**\n"
        "• **Qui est ce champion ?** et **Qui est ce pro ?** : trouvé au 1er essai = pack à **taux doublés** · au 2e = pack à **taux améliorés** · ensuite = pack normal.\n"
        "• **L'effectif du jour** : les 5 joueurs = taux doublés · 3 ou 4 = taux améliorés · 1 ou 2 = pack normal.\n"
        "• Les golds de ces jeux sont remplacés par le pack (il reste une petite consolation si tu ne trouves rien).\n"
        "• Les deux salons passent dans une nouvelle catégorie **MINI-JEUX**.")),
    ("2026-10-10-tour-plate", "10 octobre 2026", "La tour est remise à plat, les étoiles débloquent des niveaux", (
        "**🗼 Une tour de plus en plus dure, mais sans mur**\n"
        "• La force des ennemis ne se multiplie plus d'étage en étage : **chaque étage ajoute la même quantité de force**. Le sommet reste très dur, mais on y monte régulièrement.\n"
        "• Les étages 10 à 19 demandent maintenant de monter un peu ses cartes, et le **Héraut (étage 20)** est moins brutal : on y arrive prêt.\n"
        "• À partir de l'étage 30, tout est nettement plus accessible qu'avant. Si tu étais bloqué, retente ta chance.\n\n"
        "**⭐ Les étoiles relèvent le niveau maximum**\n"
        f"• Chaque étoile (un doublon) donne toujours +10 % de stats, **et +{ETOILE_NIVEAUX} niveaux maximum**. Une carte SSR va de 50 (sans étoile) à 100 (5 étoiles).\n"
        "• Ouvrir des packs fait donc progresser même quand on tire un champion qu'on a déjà.")),
    ("2026-10-10-charges", "10 octobre 2026", "Jungle en charges, clear rapide, réserve d'XP, pack à chaque niveau", (
        "**🗺️ La jungle : fini l'énergie, place aux charges de Châtiment**\n"
        "• **Une charge = une carte complète.** Fouiller un buisson ne coûte plus rien, et chaque buisson rapporte bien plus qu'avant.\n"
        f"• Tu as **{CHARGES_PALIERS[0][1]} charges** au départ, et une charge revient toutes les **{CHARGES_DELAI[0] // 60} heures**. Le stock grandit tous les 10 niveaux de compte.\n"
        "• **Au 2e gank, ton équipe rentre** : tu gardes le butin ramassé, mais la carte est finie. Lis bien les chiffres.\n"
        f"• **Clear rapide** : pas envie de jouer ? Dépense une charge pour recevoir tout de suite **{CLEAR_RAPIDE} %** du butin d'un clear complet.\n\n"
        "**🗿 Cinq donjons défi, liés à ton niveau de compte**\n"
        "• Un défi se débloque aux niveaux " + ", ".join(str(n) for n, _ in DEFIS) + ". Chaque victoire **accélère la recharge** des charges (jusqu'à "
        + f"{CHARGES_DELAI[-1] // 60} heures) et permet de **miser plusieurs charges sur une seule carte** : butin doublé, triplé… mais tout est perdu si tu sors au 2e gank.\n\n"
        "**📚 La réserve d'XP**\n"
        "• Chaque **doublon** tiré dans un pack remplit ta réserve d'XP, en plus de son étoile. Dépense-la sur la carte de ton choix depuis sa fiche, dans la collection : "
        "pratique pour monter un champion que tu viens de tirer.\n\n"
        "**⭐ Niveau de compte**\n"
        f"• **Un pack à chaque niveau**, à ouvrir dans le salon des packs. Le niveau maximum est {NIVEAU_COMPTE_MAX}.\n"
        "• L'énergie n'existe plus.")),
    ("2026-10-10-etoiles-ssr", "10 octobre 2026", "SSR : les deux dernières étoiles demandent plus de doublons", (
        "**⭐ Étoiles des cartes SSR**\n"
        "• Les trois premières étoiles demandent toujours **un doublon** chacune.\n"
        "• La 4e étoile en demande **2**, la 5e en demande **3** : il faut 9 exemplaires en tout pour une SSR au maximum (niveau 100).\n"
        "• Un doublon qui ne donne pas encore d'étoile est compté sur la fiche de la carte, et remplit quand même ta réserve d'XP.\n"
        "• Les autres raretés ne changent pas : un doublon, une étoile.")),
    ("2026-10-10-ur", "10 octobre 2026", "Les cartes UR arrivent", (
        "**💎 Une nouvelle rareté : UR**\n"
        "• Cinq cartes de prestige : **Garen, Dieu-Roi** · **Aatrox, Lune de sang** · **Vayne, Fleur spirituelle** · **Senna, True Damage** · **Lux, Élémentaliste**.\n"
        "• Un UR monte jusqu'au **niveau 100 dès la première copie**, sans étoiles. Au maximum, il vaut un peu plus (5 %) qu'une SSR à 5 étoiles. Il a le passif et l'actif de son champion.\n\n"
        "**🎁 Les packs UR**\n"
        f"• **Tous les {UR_TOUS_LES} packs ouverts**, quelle que soit leur origine (achetés, gratuits, de niveau, de tour, de mini-jeu…), tu gagnes **un pack UR**, à ouvrir dans le salon des packs.\n"
        f"• Un pack UR contient {UR_TAUX['UR']} % d'UR, {UR_TAUX['SSR']} % de SSR et {UR_TAUX['SR']} % de SR. **Un UR est garanti au {UR_PITIE}e pack UR** sans en avoir eu.\n"
        "• Les packs que tu as déjà ouverts comptent : tes packs UR t'attendent.")),
    ("2026-10-10-runes-raid", "10 octobre 2026", "Les runes et le raid contre Ryze", (
        "**🔮 Un nouveau salon : le raid**\n"
        f"• De **{RAID_JOUEURS[0]} à {RAID_JOUEURS[1]} joueurs** unissent leurs équipes de 3 contre **Ryze**. Il s'adapte au groupe : il est aussi dur à 5 qu'à 3.\n"
        "• Trois difficultés, ouvertes aux étages " + ", ".join(str(e) for e in RUNE_ETAGES) + " de la tour. **Une victoire par jour** et par joueur (une défaite ne consomme rien).\n"
        "• Ryze enferme un champion dans sa Prison runique, frappe tout le monde avec sa Surcharge, et entre en rage quand il est presque vaincu.\n\n"
        "**✨ Les runes**\n"
        "• Chaque victoire donne **une rune au choix** du palier : " + ", ".join(v[0] for v in RUNES.values()) + ".\n"
        "• Une rune s'équipe sur une carte de ton équipe, en plus de son item, avec le bouton **Mes runes** (salon de la collection ou du raid).\n"
        f"• Étage {RUNE_ETAGES[0]} : une carte peut porter une rune. Étage {RUNE_ETAGES[1]} : deux cartes. Étage {RUNE_ETAGES[2]} : trois cartes.")),
    ("2026-10-10-debutants", "10 octobre 2026", "Monter dans la tour fait progresser, une charge par niveau", (
        "**🗼 La tour donne beaucoup plus d'XP à tes cartes**\n"
        f"• Chaque étage gagné rapporte maintenant **{TOUR_XP[0]} XP + {TOUR_XP[1]} par étage** à chaque carte de ton équipe (c'était 15 + 2). Grimper suffit pour faire monter ses cartes au début.\n\n"
        "**⚡ Une charge de Châtiment à chaque niveau de compte**\n"
        "• Chaque montée de niveau te rend **une charge de jungle**, en plus du pack. Elle peut dépasser ton stock maximum.\n\n"
        "**📚 La réserve d'XP a son bouton**\n"
        "• Dans le salon de la collection, le bouton **Réserve d'XP** montre ta réserve et te laisse la verser sur la carte de ton choix.\n"
        "• Après une défaite dans la tour, le bot te rappelle ce que tu peux encore utiliser : réserve d'XP, golds, charges, packs en attente.")),
    ("2026-10-10-expedition-packs", "10 octobre 2026", "L'expédition rapporte des packs", (
        "**🧭 Revenir fait plaisir**\n"
        f"• Ton expédition rapporte maintenant **un pack toutes les {COFFRE_PACK_HEURES} heures**, ouverts d'un coup à la récolte : jusqu'à {COFFRE_HEURES // COFFRE_PACK_HEURES} packs pour une expédition pleine ({COFFRE_HEURES} heures).\n"
        "• Elle rapporte aussi beaucoup plus de golds et d'XP qu'avant, surtout quand tu es haut dans la tour.\n"
        f"• Conseil : récolte par tranches de {COFFRE_PACK_HEURES} heures. Une tranche entamée n'est pas reportée sur l'expédition suivante.")),
    ("2026-10-11-vague-champions", "11 octobre 2026", "Onze champions arrivent, et la règle Hémorragie", (
        "**🆕 Neuf nouveaux champions**\n"
        "• SR : **Nami** (support, Bilgewater) · **Caitlyn** (tireur, Piltover) · **Vi** (combattant, Piltover) · **Shaco** (assassin, Runeterra) · **Morgana** (mage, Demacia).\n"
        "• SSR : **Janna** (support, Zaun) · **Talon** (assassin, Noxus) · **Miss Fortune** (tireur, Bilgewater) · **Orianna** (mage, Piltover).\n"
        "• **Leona** (Targon) et **Gangplank** (Bilgewater) reviennent dans les packs.\n"
        "• Chacun a son passif et son actif : ouvre sa fiche dans la collection.\n\n"
        "**👑 Deux nouveaux bonus de leader**\n"
        f"• **Bilgewater** : +10 % de golds gagnés dans la tour et la jungle. **Piltover** : {LEADERS['Piltover'][1]} % de chances de charger son actif deux fois plus vite à chaque action.\n\n"
        "**🩸 Hémorragie**\n"
        f"• Dans les **donjons** et le **raid**, tous les soins sont réduits à {HEMORRAGIE} % (les boucliers ne changent pas). Les équipes à soigneur n'y sont plus intouchables.\n\n"
        f"**🎯 SSR ciblé** : la chance d'obtenir le SSR visé passe à {CIBLE_CHANCE} %, pour compenser l'arrivée des nouveaux SSR.")),
    ("2026-10-11-tour-auto", "11 octobre 2026", "La tour en automatique", (
        "**🚀 Monter en automatique**\n"
        "• Dans le salon de la tour, le bouton **Monter en automatique** enchaîne les étages sans animation, jusqu'à la première défaite.\n"
        "• Il **s'arrête toujours avant un boss**, pour te laisser vérifier ton équipe et l'affronter toi-même.\n"
        "• Les packs de palier sont ouverts à la suite et listés dans le récapitulatif, avec les golds, l'XP et les niveaux gagnés.")),
    ("2026-10-11-tour-difficile", "11 octobre 2026", "La tour difficile : étages 101 à 200", (
        "**🗼 Après l'étage 100, la tour continue**\n"
        "• La **tour difficile** rejoue les 100 étages en version renforcée : mêmes boss, dans le même ordre, mais bien plus dangereux.\n"
        "• Les ennemis y sont plus forts à chaque étage, jusqu'à plus du double de l'étage 100 au sommet. Il faudra des cartes au niveau 100, des items au maximum et des runes pour voir le bout.\n"
        "• Les récompenses continuent de grandir avec l'étage : golds, XP, un pack à taux doublés tous les 5 étages et à chaque boss.")),
    ("2026-10-11-soir", "11 octobre 2026", "Worlds, donjons simplifiés, et trois idées des joueurs", (
        "**🏆 Les Worlds sont ouverts** : tout est expliqué dans le salon des annonces et dans le guide. "
        "Depuis l'ouverture : une carte ne joue **qu'une fois par équipe**, et le repos des cartes inscrites passe à **8 h**.\n\n"
        "**⚒️ Donjons simplifiés**\n"
        f"• Un seul combat contre les deux gardiens : plus de code, plus de clés. **{DONJON_ESSAIS} victoires par jour**, une défaite ne consomme rien.\n"
        f"• {DONJON_BUTIN} composants par victoire, +1 tous les {DONJON_PALIER} étages de la tour.\n\n"
        "**🔮 Raid**\n"
        "• Seule une **victoire** consomme le raid du jour. Après ta victoire, tu peux revenir **aider** d'autres groupes, sans récompense.\n\n"
        "**🎯 Entraînement** : dans le salon de la tour, rejoue n'importe quel étage déjà vaincu, sans limite et sans gain, pour essayer tes champions.\n\n"
        "**💎 Nouvelle UR** : **Maokai, Totémique**, le premier tank UR, dans les packs UR.\n\n"
        "**💡 Trois idées venues de vous** (merci !)\n"
        "• **L'XP ne se perd plus** : l'XP gagnée par une carte déjà au niveau maximum, et le surplus d'une réserve pleine, "
        "vont automatiquement à ta carte la plus haute qui n'est pas au maximum.\n"
        f"• **Tour difficile** : comme en donjon et en raid, les soins y sont réduits à {HEMORRAGIE} %. Les équipes à gros soins n'y sont plus intouchables.\n"
        "• **Coffre hextech** 🧰 : très rare, il se cache parfois dans un buisson de la jungle. Il contient des composants, un pack à taux doublés… "
        "ou, avec beaucoup de chance, **un pack pro**.\n\n"
        "Le salon des tirages n'annonce plus que les SSR et les UR.")),
    ("2026-10-12-matin", "12 octobre 2026", "Donjons à la carte et packs de niveau", (
        "**⚒️ Donjons : une réserve de victoires**\n"
        f"• Fini les {DONJON_ESSAIS} victoires par jour : tu as maintenant une **réserve de {DONJON_STOCK} victoires**, et une victoire revient toutes les **{DONJON_DELAI // 3600} heures**.\n"
        "• Si tu ne joues qu'une fois par jour, ta réserve t'attend pleine : tu ne perds rien.\n"
        f"• Pour fêter ça, tout le monde repart avec sa réserve pleine ({DONJON_STOCK} victoires).\n\n"
        "**🎁 Packs de niveau à taux triplés**\n"
        f"• Chaque niveau de compte donne maintenant un pack à **taux triplés** : R {TAUX_NIVEAU['R']} %, SR {TAUX_NIVEAU['SR']} %, SSR {TAUX_NIVEAU['SSR']} %, et plus aucune N.\n"
        "• Ça vaut aussi pour les packs de niveau que tu n'as pas encore ouverts.")),
    ("2026-10-12-niveaux", "12 octobre 2026", "Le niveau de compte passe à 100", (
        f"**👑 Le niveau maximum passe de 50 à {NIVEAU_COMPTE_MAX}.**\n"
        "• Chaque niveau au-delà de 50 est de plus en plus long à gagner : le 100 est un vrai défi.\n"
        "• Chaque niveau donne toujours des golds et un pack à taux triplés. Les charges de jungle offertes s'arrêtent au niveau 50.\n"
        "• Trois nouveaux rôles : **Mythique** au niveau 60, **Immortel** au 75 et **Éternel** au 100.")),
    ("2026-10-12-soir", "12 octobre 2026", "Les UR s'éveillent, et un compteur de packs", (
        f"**💎 Garanti UR** : un UR est maintenant garanti au **{UR_PITIE}e pack UR** sans en avoir eu (au lieu du 50e).\n\n"
        "**✨ Les éveils UR**\n"
        "Les UR qui avaient le même kit que leur version de base reçoivent un **éveil**, un bonus en plus écrit à la fin de leur passif :\n"
        + "\n".join(f"• **{CARTES[c]['nom']}** : {EVEILS[c]}" for c in ("GarenUR", "AatroxUR", "VayneUR", "SennaUR", "LuxUR", "MaokaiUR", "TristanaUR"))
        + "\n• …et d'autres UR à découvrir.\n\n"
        "**🏴‍☠️ Leader Bilgewater : « À l'abordage »**\n"
        f"• Le bonus de golds disparaît : il obligeait à jouer Bilgewater pour farmer. À la place, **+{LEADERS['Bilgewater'][1]} % de dégâts sur les ennemis sous {ACHEVER_SEUIL} % de PV**, pour toute l'équipe.\n\n"
        "**🛒 La boutique**\n"
        f"• Nouveau bouton **Boutique** dans le salon des packs. La même pour tout le serveur, elle se renouvelle toute seule toutes les {BOUTIQUE_DELAI // 3600} heures.\n"
        f"• Toujours : **5 composants** ({BOUTIQUE['composants']['prix']} golds, {BOUTIQUE['composants']['limite']} fois) et **un SSR** tiré au hasard, le même pour tous ({BOUTIQUE['ssr']['prix']} golds, 1 fois).\n"
        f"• Parfois : un **pack pro** ({BOUTIQUE['pack_pro']['prix']} golds) ou un **pack UR** ({BOUTIQUE['pack_ur']['prix']} golds). Une fois chacun.\n\n"
        "**💰 Des golds en combat**\n"
        f"• Le raid gagné rapporte **{GOLDS_RAID} golds** (une fois par jour), et chaque équipe éliminée aux Worlds **{GOLDS_WORLDS_EQUIPE} golds**.\n\n"
        "**🧮 Mes packs**\n"
        "• Nouveau bouton **Mes packs** dans le salon des packs : tout ce que tu as à ouvrir (gratuit, niveau, UR, pro…) et où l'ouvrir. Le même résumé est dans ton profil.")),
    ("2026-10-12-mega", "12 octobre 2026", "Le méga tirage", (
        f"**🎰 Le méga tirage** remplace le pack à {PRIX_PACK} golds dans le salon des packs.\n"
        f"• **{MEGA_CARTES} cartes pour {MEGA_PRIX} golds**, avec **au moins un SSR** et **un pack UR offert**.\n"
        f"• Ses {MEGA_CARTES} cartes ne font pas avancer le compteur des packs UR, puisqu'il en donne un directement. Le pack UR offert compte normalement pour l'UR garantie.\n"
        f"• Le pack à {PRIX_PACK} golds reste possible avec le bouton **Encore un**, après un pack gratuit.")),
    ("2026-10-12-packs-pro", "12 octobre 2026", "Les packs pro donnent 3 cartes", (
        f"**🏆 Un pack pro donne maintenant {1 + PRO_CARTES_BONUS} cartes.**\n"
        f"• Une carte principale, avec les mêmes chances qu'avant : {TAUX_PRO['UR']} % d'UR et {TAUX_PRO['coach']} % de carte de pro par pack.\n"
        f"• {PRO_CARTES_BONUS} cartes bonus, en SR ou SSR, parmi les champions des équipes que tu as éliminées.\n"
        "• Le SSR garanti des packs pro disparaît : avec 3 cartes par pack, les SSR tombent bien plus souvent.")),
    ("2026-10-12-leona", "12 octobre 2026", "Leona se réveille", (
        "**☀️ Leona reçoit un vrai kit.**\n"
        f"• **Passif, Lumière du soleil** : ses coups marquent l'ennemi. Le prochain coup d'un allié sur lui fait **+{KITS['leona_soleil']} %** de dégâts.\n"
        f"• **Actif, Éruption solaire** : frappe **tous les ennemis à {KITS['leona_zone']} %**, étourdit celui qui tape le plus fort, et Leona gagne **+{KITS['leona_res']} de résistances** pendant 2 actions.")),
    ("2026-10-12-lec-solo", "12 octobre 2026", "La LEC passe en solo", (
        "**🇪🇺 La LEC se joue maintenant seul.**\n"
        "• Tu inscris **9 cartes**, en 3 trios. Contre chaque pro, tu envoies un trio de 3 cartes ; chaque carte joue une fois par équipe.\n"
        f"• **{LEC_ESSAIS} tournois par jour**, et plus de repos des cartes.\n"
        "• **Plus de packs** : " + " · ".join(f"{t['equipe']} **{n}**" for t, n in zip(LEC_PALIERS, LEC_PACKS)) + " packs LEC au total, selon la dernière équipe battue.\n"
        f"• Atteindre la finale donne toujours un 🎟️ ticket Worlds ({WORLDS_TICKETS_MAX} au plus) : jusqu'à 2 par jour.\n"
        "• Les Worlds restent à 3 joueurs.")),
    ("2026-10-12-worlds-repos", "12 octobre 2026", "Plus de repos aux Worlds", (
        "**🏆 Les cartes ne se reposent plus aux Worlds.** Maintenant que chaque tournoi coûte un 🎟️ ticket, tu peux réinscrire tes meilleures cartes à chaque fois.\n"
        "• Les cartes qui étaient au repos sont libérées tout de suite.\n"
        "• Les messages de tournoi (Worlds et LEC) s'effacent 5 minutes après la fin, pour garder les salons propres.")),
    ("2026-10-12-worlds-packs", "12 octobre 2026", "Chaque tournoi des Worlds rapporte ses packs", (
        "**🏆 Fini la limite d'une récompense par jour aux Worlds.** Puisque chaque tournoi coûte un 🎟️ ticket, **chaque tournoi rapporte ses packs pro** : "
        + " · ".join(f"{n} {(k + 1) * WORLDS_PACKS_PAR_PALIER}" for k, n in enumerate(["Play-In", "Round 1", "Round 2", "Round 3", "Quart", "Demi", "Finale", "Grande finale"]))
        + " packs au total, selon la dernière équipe éliminée.")),
    ("2026-10-13-depart-direct", "13 octobre 2026", "Départ direct, LEC revue et tickets en plus", (
        f"**⏩ Départ direct.** Une équipe battue **{DEPART_VICTOIRES} fois** par tout le groupe peut servir de point de départ : "
        "le chef de groupe choisit le départ à l'inscription, et **les récompenses des équipes sautées sont données au départ** (packs et golds). "
        f"Aux Worlds, ça marche pour n'importe quelle équipe ; à la LEC, on peut commencer directement à **{LEC_PALIERS[LEC_DEPART]['equipe']}**.\n\n"
        f"**🇪🇺 La LEC.** **{LEC_ESSAIS} tournoi par jour**, mais **les packs sont doublés** : "
        + " · ".join(f"{t['equipe']} {n}" for t, n in zip(LEC_PALIERS, LEC_PACKS)) + " packs au total.\n\n"
        f"**🎟️ Les tickets Worlds.** Atteindre la finale de la LEC en donne **{LEC_TICKETS_FINALE}**, et la gagner **{LEC_TICKETS_VICTOIRE} de plus** "
        f"({WORLDS_TICKETS_MAX} au plus).\n\n"
        "**🛠️ Corrections.** Un tournoi de plus de 15 minutes ne se bloque plus. Les listes de cartes sont rangées par rareté puis par niveau, "
        "et la forge propose d'abord les cartes de ton équipe pour équiper un item.")),
    ("2026-10-13-kits", "13 octobre 2026", "Lux, Talon, Aatrox et Maokai changent", (
        f"**✨ Lux devient une vraie mage.** Plus de bouclier : ses dégâts ignorent **35 %** des résistances, une attaque sur 2 "
        f"touche aussi tous les autres ennemis à 50 %, et son actif **Rayon final** frappe tous les ennemis à **140 %**. "
        f"La SSR charge son actif en **3 actions** ; la UR garde 4 actions, mais son éveil étourdit l'ennemi qui tape le plus fort et son rebond monte à 70 %.\n\n"
        f"**🗡️ Talon** frappe toujours tous les ennemis à {KITS['talon_zone']} %, mais au lieu de devenir intouchable, il **bloque la prochaine attaque** qui le vise.\n\n"
        f"**🩸 Aatrox UR** : son actif frappe désormais **tous les ennemis à {KITS_EVEIL['aatrox_zone']} %** et le soigne de {KITS_EVEIL['aatrox_vol']} % des dégâts.\n\n"
        f"**🌳 Maokai UR** : son actif **force tous les ennemis à l'attaquer** et lui donne un bouclier de {KITS_EVEIL['maokai_bouclier']} % de ses PV ; "
        f"ses résistances remontent à {PARTICULARITES['Maokai']['res'][0]} / {PARTICULARITES['Maokai']['res'][1]}.")),
    ("2026-10-13-reglages", "13 octobre 2026", "Talon, tickets et nouvelles cartes dans les packs", (
        f"**🗡️ Talon** : son actif frappe maintenant tous les ennemis à **{KITS['talon_zone']} %** (au lieu de 120 %). Il bloque toujours la prochaine attaque qui le vise.\n\n"
        f"**🎟️ Tickets Worlds** : tu peux maintenant en garder **{WORLDS_TICKETS_MAX}** au lieu de 4.\n\n"
        "**🎉 Tes cartes débloquées dans les packs à golds.** Les packs de 10 et le méga tirage contiennent maintenant aussi les **SR et SSR des équipes "
        "que tu as battues** aux Worlds et à la LEC, et très rarement une **UR de la LEC**.\n\n"
        f"**💎 Pack UR** : **{UR_WORLDS_CHANCE} %** de chances d'une **UR des Worlds** des équipes que tu as éliminées. "
        "Le garanti donne toujours une UR du pack, et **Tristana** en fait maintenant partie.")),
    ("2026-10-13-lux-support", "13 octobre 2026", "Lux devient support", (
        "**✨ Lux change de rôle.** Après plusieurs essais en mage, Lux devient une **support** qui protège son équipe.\n\n"
        f"• **Barrière prismatique** (actif, en **3 actions**) : un bouclier de **{KITS['lux_bouclier']} % de son ATQ** sur toute son équipe, elle comprise.\n"
        "• **Passif** : quand elle tombe, elle **étourdit l'ennemi qui tape le plus fort**.\n"
        f"• **Lux UR** : au tour suivant, son bouclier revient à {KITS_EVEIL['lux_rebouclier']} % de son ATQ, et en tombant elle frappe aussi l'ennemi étourdi à **{KITS_EVEIL['lux_mort']} %** de son ATQ.")),
    ("2026-10-13-cible", "13 octobre 2026", "SSR ciblé : les SSR des pros et de la LEC", (
        "**🎯 Petit changement** : les packs de 10 et le méga tirage gardent leurs **SR et SSR habituels** (les UR de la LEC peuvent toujours y tomber, très rarement). "
        "À la place, le **SSR ciblé** du salon des packs propose maintenant aussi les **SSR des Worlds et de la LEC**, parmi les équipes que tu as battues.")),
    ("2026-10-13-equilibrage-soir", "13 octobre 2026", "Grosse mise à jour d'équilibrage", (
        "**✨ Lux devient élémentaliste.** Fini le bouclier : ses actifs alternent deux éléments.\n"
        f"• 🔥 **Feu** : tous les ennemis à **{KITS['lux_feu']} %**, et ils brûlent ({KITS['lux_brulure']} % de son ATQ pendant 2 actions).\n"
        f"• ✨ **Lumière** : un rayon à **{KITS['lux_lumiere']} %** sur l'ennemi le plus dangereux.\n"
        "• Son passif ne change pas : en tombant, elle étourdit l'ennemi qui tape le plus fort.\n\n"
        "**💎 Lux, Élémentaliste (UR)** maîtrise **trois éléments** : "
        f"feu ({KITS_EVEIL['luxur_feu']} % sur tous, brûlure {KITS_EVEIL['luxur_brulure']} %), "
        f"**glace** ({KITS_EVEIL['luxur_glace']} % sur tous, et l'ennemi le plus dangereux est gelé) et lumière ({KITS_EVEIL['luxur_lumiere']} %). "
        f"En échange, elle perd {-AJUST_CARTES['LuxUR']} % de PV et d'ATQ.\n\n"
        f"**❄️ Sejuani** perd ses PV et résistances bonus permanents, et {-AJUST_CARTES['Sejuani']} % de PV et d'ATQ. "
        f"Son actif frappe à {KITS['sejuani_ulti2']} %, étourdit la cible et **ralentit les autres ennemis** de {KITS['sejuani_lent']} %.\n\n"
        f"**📉 En baisse** (PV et ATQ) : 🗡️ Talon −{-AJUST_CARTES['Talon']} % · ☀️ Leona −{-AJUST_CARTES['Leona']} % · 🌬️ Janna −{-AJUST_CARTES['Janna']} %\n"
        f"**📈 En hausse** (PV et ATQ) : 💀 Karthus +{AJUST_CARTES['Karthus']} % · 🩸 Aatrox, Lune de sang (UR) +{AJUST_CARTES['AatroxUR']} %\n\n"
        "**🔧 Et 12 autres champions des packs pro et de la LEC ont été retravaillés** : nouveaux kits pour certains, chiffres revus pour d'autres. "
        "À vous de les découvrir !\n\n"
        "**🎯 Pensez à cibler !** Les SSR des pros et de la LEC ne sortent jamais des packs normaux : si l'un d'eux vous paraît fort, "
        "choisissez-le comme **SSR ciblé** dans le salon des packs. C'est le seul moyen de l'obtenir avec vos tirages.\n\n"
        "**🎁 Compensation** : tout le monde repart avec **au moins 2 🎟️ tickets Worlds** et **3 charges de jungle** offertes (détail en message privé).")),
    ("2026-10-14-tour", "14 octobre 2026", "La tour se durcit, départ direct simplifié", (
        "**🏰 La tour difficile se durcit !** Les cartes sont devenues bien plus fortes : tout le monde au-dessus de l'étage 100 y redescend, "
        "et les étages 101 à 200 sont plus durs. **Toutes les récompenses des étages se regagnent en remontant.**\n"
        "Contre les boss, un blocage ne pare plus que **la moitié du coup**.\n\n"
        "**⏩ Départ direct simplifié.** Dès que votre groupe a battu **Bilibili Gaming** (Worlds) ou **Team Vitality** (LEC), "
        "un bouton à l'inscription permet de commencer directement contre elle, avec les packs des équipes d'avant.\n\n"
        "**📦 Nouveau : Ouvrir x5** pour les packs pro et LEC.")),
    ("2026-10-14-objets", "14 octobre 2026", "Items et runes en plusieurs exemplaires", (
        "**⚒️ Un même item sur plusieurs champions !** Une fois un item au **niveau maximum**, la forge vous permet d'en fabriquer "
        "**un autre exemplaire**, à monter et à équiper sur un autre champion. Toujours un seul item par champion.\n\n"
        "**🔮 Les runes se regagnent.** En battant **Ryze**, vous pouvez maintenant reprendre une rune que vous avez déjà : "
        "chaque exemplaire s'équipe sur une carte différente (dans la limite de vos emplacements).\n\n"
        "**💎 Nouveau : Pack UR x5**, dans le salon des packs, pour ouvrir jusqu'à 5 packs UR d'un coup.\n\n"
        "**🏆 Packs pro** : une UR ou une LR que vous avez déjà ne retombe plus, tant qu'il en reste à avoir.\n"
        "**💎 Packs UR** : toute UR sortie d'un pack UR remet la garantie à zéro, y compris les UR des Worlds.")),
    ("2026-10-26-worlds-solo", "26 octobre 2026", "Les Worlds en solo, bonus de jungle plus tôt", (
        "**🏆 Les Worlds se jouent aussi en solo !** Nouveau bouton **Jouer en solo** dans le salon des Worlds.\n"
        "• Tu inscris **9 cartes**, en 3 trios. Contre chaque pro, tu envoies une carte de chaque trio, comme un groupe de 3 joueurs.\n"
        "• **Un seul 🎟️ ticket**, et les mêmes packs Worlds qu'en groupe.\n"
        "• Le mode à 3 joueurs reste là : bouton **Former un groupe**.\n\n"
        f"**🌿 Jungle** : le gros bonus d'exploration (**+{EXPLO_BONUS[-1][1]} % de butin**) arrive maintenant à **{EXPLO_BONUS[-1][0]} camps** nettoyés au lieu de 500.")),
    ("2026-10-28-depart-geng", "28 octobre 2026", "Départ direct à Gen.G", (
        f"**⏩ Nouveau départ direct aux Worlds : {TOUR_PROS[WORLDS_DEPARTS[-1]]['equipe']}.** Une fois {TOUR_PROS[WORLDS_DEPARTS[-1]]['equipe']} battue, "
        "tu peux commencer ton tournoi directement contre elle (en solo, ou en groupe si tout le monde l'a déjà battue).\n"
        "• À l'inscription, le bouton ⏩ passe du début à BLG, puis à Gen.G.\n"
        f"• Les packs Worlds des équipes sautées sont donnés au départ, comme pour BLG ({WORLDS_DEPARTS[-1] * WORLDS_PACKS_PAR_PALIER} packs).")),
]



# 14 octobre : contre un boss (tour, raid, boss de salon), un blocage (Xin Zhao, Jax, Talon…) ne pare que ce % du coup au lieu de tout.
BOSS_BLOCAGE = 50
