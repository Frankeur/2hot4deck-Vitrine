"""Fabrique l'image de chaque carte : l'illustration officielle glissée dans le cadre de sa rareté, avec son nom,
son rôle, son passif et l'emblème de sa région. Les cartes sont préparées une fois, au démarrage, dans images/c_<carte>.jpg.
Ce module a besoin de Pillow (installé par lancer.bat). Sans lui, le bot fonctionne comme avant, sans cadres."""
import os
import urllib.request

import data

try:
    from PIL import Image, ImageDraw, ImageFont
    PRET = True
except ImportError:   # Pillow absent : pas de cartes encadrées
    PRET = False

VERSION = "11"   # à changer pour refabriquer toutes les cartes (nouveaux cadres, nouvelle mise en page)
DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
CADRES, SOURCES, POLICES, EMBLEMES = (os.path.join(DOSSIER, d) for d in ("cadres", "sources", "polices", "emblemes"))
LARGEUR = 500       # largeur finale d'une carte, en pixels

# Mise en page de chaque cadre (en pixels du fichier images/cadres/cadre_<rareté>.png) :
# fenêtre de l'illustration, bandeau du nom (centre x, centre y, largeur), boîte de texte, emblème (centre x, centre y, taille).
MISE_EN_PAGE = {
    "N":   {"fenetre": (80, 193, 750, 1063), "nom": (415, 1143, 512), "boite": (100, 1253, 730, 1548), "embleme": (717, 368, 100), "accent": (198, 150, 98), "encre": (214, 170, 110)},
    "R":   {"fenetre": (78, 193, 763, 1063), "nom": (423, 1143, 537), "boite": (103, 1253, 743, 1548), "embleme": (725, 363, 100), "accent": (120, 170, 240), "encre": (226, 196, 120)},
    "SR":  {"fenetre": (95, 198, 765, 1068), "nom": (430, 1143, 512), "boite": (115, 1263, 745, 1578), "embleme": (740, 378, 100), "accent": (190, 140, 250), "encre": (232, 214, 240)},
    "SSR": {"fenetre": (135, 305, 1055, 1210), "nom": (590, 1285, 750), "boite": (185, 1430, 1000, 1740), "embleme": (1005, 465, 120), "accent": (240, 190, 90), "encre": (236, 196, 110)},
    "UR":  {"fenetre": (220, 330, 1085, 1255), "nom": (645, 1345, 750), "boite": (250, 1485, 1050, 1795), "embleme": (1077, 510, 120), "accent": (150, 200, 255), "encre": (40, 60, 120)},
}

# Illustrations officielles (Data Dragon de Riot). « centered » place le champion au milieu : idéal pour une fenêtre carrée.
ILLUSTRATIONS = ["https://ddragon.leagueoflegends.com/cdn/img/champion/centered/{}_0.jpg",
                 "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{}_0.jpg"]
# Emblèmes officiels des régions : plusieurs adresses essayées dans l'ordre. Sans emblème, la bannière reste unie.
_LOR = "https://dd.b.pvp.net/latest/core/en_us/img/regions/icon-{}.png"
_UNIVERS = "https://universe.leagueoflegends.com/images/{}_crest_icon.png"
EMBLEMES_REGIONS = {
    "Demacia": [_LOR.format("demacia"), _UNIVERS.format("demacia")],
    "Noxus": [_LOR.format("noxus"), _UNIVERS.format("noxus")],
    "Ionia": [_LOR.format("ionia"), _UNIVERS.format("ionia")],
    "Freljord": [_LOR.format("freljord"), _UNIVERS.format("freljord")],
    "Shurima": [_LOR.format("shurima"), _UNIVERS.format("shurima")],
    "Zaun": [_LOR.format("piltoverzaun"), _UNIVERS.format("zaun")],
    "Piltover": [_LOR.format("piltoverzaun"), _UNIVERS.format("piltover")],
    "Bandle": [_LOR.format("bandlecity"), _UNIVERS.format("bandle_city")],
    "Îles obscures": [_LOR.format("shadowisles"), _UNIVERS.format("shadow_isles")],
    "Targon": [_LOR.format("targon"), _UNIVERS.format("mt_targon")],
    "Ixtal": [_UNIVERS.format("ixtal")],
    "Bilgewater": [_LOR.format("bilgewater"), _UNIVERS.format("bilgewater")],
    "Néant": [_UNIVERS.format("void")],
    "Runeterra": [_LOR.format("runeterra"), _LOR.format("all")],
}
# Recadrage particulier d'une illustration : (horizontal, vertical) de 0 à 1. Par défaut (0.5, 0.3).
CADRAGES = {"GarenUR": (0.48, 0.5), "AzirLR": (0.80, 0.3), "AhriLR": (0.49, 0.12), "RyzeLR": (0.46, 0.2), "ZeriUR": (0.62, 0.0), "XinZhaoUR": (0.72, 0.05), "ViegoUR": (0.47, 0.05), "SylasUR": (0.46, 0.08), "GragasUR": (0.55, 0.05), "BardUR": (0.52, 0.1), "MaokaiUR": (0.5, 0.1), "XayahUR": (0.51, 0.0), "YoneUR": (0.5, 0.15), "NidaleeUR": (0.22, 0.3), "JayceUR": (0.47, 0.2), "VarusUR": (0.5, 0.12), "AkaliUR": (0.5, 0.08)}

DESCENTES = {}   # illustrations dont la tête touche le bord du haut : on les descend (part de leur hauteur)


def chemin_carte(cid):
    return os.path.join(DOSSIER, f"c_{cid}.png")


def _telecharger(adresses, destination):
    """Télécharge la première adresse qui répond. Renvoie True si le fichier existe à la fin."""
    if os.path.exists(destination):
        return True
    for adresse in adresses:
        try:
            requete = urllib.request.Request(adresse, headers={"User-Agent": "Mozilla/5.0 (bot de fans, non affilie a Riot Games)"})
            with urllib.request.urlopen(requete, timeout=20) as reponse:
                contenu = reponse.read()
            if len(contenu) > 500:
                with open(destination, "wb") as f:
                    f.write(contenu)
                return True
        except Exception:
            continue
    return False


SKINS_DDRAGON = {"GragasUR": "Gragas_6"}   # Gragas Oktoberfest


def _illustration(cid):
    """Chemin de l'illustration à mettre dans le cadre : image du dossier images, sinon illustration officielle téléchargée."""
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        if os.path.exists(os.path.join(DOSSIER, cid + ext)):
            return os.path.join(DOSSIER, cid + ext)
    carte = data.CARTES[cid]
    if cid in SKINS_DDRAGON:   # UR dont le skin officiel se télécharge directement (ex. Gragas Oktoberfest)
        destination = os.path.join(SOURCES, cid + "_skin.jpg")
        if _telecharger([u.replace("{}_0", SKINS_DDRAGON[cid]) for u in ILLUSTRATIONS], destination):
            return destination
    if carte["ulti"]:
        destination = os.path.join(SOURCES, cid + ".jpg")
        base = carte.get("base", cid)   # une UR sans illustration propre prend, en attendant, celle de son champion
        if _telecharger([u.format(cid) for u in ILLUSTRATIONS] + ([u.format(base) for u in ILLUSTRATIONS] if base != cid else []), destination):
            return destination
    generique = os.path.join(DOSSIER, f"carte_{carte['rarete']}.png")
    return generique if os.path.exists(generique) else None


def _embleme(region):
    if region not in EMBLEMES_REGIONS:
        return None
    destination = os.path.join(EMBLEMES, region.replace(" ", "_") + ".png")
    return destination if _telecharger(EMBLEMES_REGIONS[region], destination) else None


def _police(nom, taille):
    return ImageFont.truetype(os.path.join(POLICES, nom), max(8, int(taille)))


def _ecrire(d, texte, cx, cy, police, couleur, espacement=0):
    """Écrit un texte centré sur (cx, cy), avec une ombre."""
    largeur = sum(d.textlength(ch, font=police) for ch in texte) + espacement * (len(texte) - 1)
    boite = police.getbbox("Hg")
    x, y = cx - largeur / 2, cy - (boite[1] + boite[3]) / 2
    for ch in texte:
        d.text((x + 2, y + 2), ch, font=police, fill=(0, 0, 0))
        d.text((x, y), ch, font=police, fill=couleur)
        x += d.textlength(ch, font=police) + espacement


def _couper(d, texte, police, largeur):
    lignes = [""]
    for mot in texte.split():
        essai = (lignes[-1] + " " + mot).strip()
        if d.textlength(essai, font=police) <= largeur or not lignes[-1]:
            lignes[-1] = essai
        else:
            lignes.append(mot)
    return lignes


def texte_carte(cid):
    """Les deux textes de la boîte du bas : la ligne « rôle · région », et le passif (ou l'actif s'il n'y a pas de passif)."""
    carte = data.CARTES[cid]
    role = {"sbire": "Sbire" if carte["rarete"] == "N" else "Monstre"}.get(carte["role"], carte["role"].capitalize())
    entete = f"{role} · {carte['region']}".upper()
    passif, actif = data.TEXTES_KITS.get(cid, (None, None))
    if passif:
        return entete, "Passif", passif
    if actif:
        return entete, carte["ulti"], actif
    if carte["ulti"]:
        return entete, carte["ulti"], data.EFFETS[carte["effet"]].capitalize() + "."
    return entete, "", ""


def fabriquer(cid, rarete=None, destination=None):
    """Fabrique l'image d'une carte. Renvoie son chemin, ou None si l'illustration ou le cadre manque."""
    if cid.endswith("LR") and rarete is None:   # les cartes de Faker ont leur cadre rouge à elles
        return fabriquer_lr(cid, destination)
    carte = data.CARTES[cid]
    rarete = rarete or carte["rarete"]
    chemin_cadre = os.path.join(CADRES, f"cadre_{rarete}.png")
    source = _illustration(cid)
    if not source or not os.path.exists(chemin_cadre):
        return None
    m = MISE_EN_PAGE[rarete]
    cadre = Image.open(chemin_cadre).convert("RGBA")
    # 1. L'illustration : elle remplit la fenêtre et se prolonge, assombrie, derrière la boîte du bas
    x0, y0, x1, y1 = m["fenetre"]
    bx0, by0, bx1, by1 = m["boite"]
    # Les cadres ont une bande noire sous leur barre du haut : on l'ouvre pour que l'illustration monte jusqu'à l'or.
    marge = int(cadre.height * 0.027)
    bande = cadre.crop((x0 + 6, y0 - marge, x1 - 6, y0 + 8))
    pixels = bande.load()
    for yy in range(bande.height):
        for xx in range(bande.width):
            r_, v_, b_, a_ = pixels[xx, yy]
            if max(r_, v_, b_) < 46:
                pixels[xx, yy] = (r_, v_, b_, 0)
    cadre.paste(bande, (x0 + 6, y0 - marge))
    y0 -= marge
    gauche, droite, bas = min(x0, bx0) - 10, max(x1, bx1) + 10, by1 + 10
    fw, fh = droite - gauche, bas - y0
    art = Image.open(source).convert("RGB")
    if cid in DESCENTES:
        art = _descendre(art, DESCENTES[cid])
    echelle = max(fw / art.width, fh / art.height)
    art = art.resize((int(art.width * echelle) + 1, int(art.height * echelle) + 1), Image.LANCZOS)
    fx, fy = CADRAGES.get(cid, (0.5, 0.5))
    gx, gy = int((art.width - fw) * fx), int((art.height - fh) * fy)
    image = Image.new("RGBA", cadre.size, (3, 5, 13, 255))
    image.paste(art.crop((gx, gy, gx + fw, gy + fh)), (gauche, y0))
    voile = Image.new("RGBA", cadre.size, (0, 0, 0, 0))
    ImageDraw.Draw(voile).rectangle([bx0 - 20, by0 - 20, bx1 + 20, by1 + 20], fill=(6, 8, 14, 150))
    image.alpha_composite(voile)
    image.alpha_composite(cadre)
    # 2. L'emblème de la région, teinté pour avoir l'air brodé sur la bannière
    embleme = _embleme(carte["region"])
    if embleme:
        try:
            ex, ey, taille = m["embleme"]
            logo = Image.open(embleme).convert("RGBA")
            logo.thumbnail((taille, taille), Image.LANCZOS)
            alpha = logo.getchannel("A").point(lambda v: int(v * 0.88))
            teinte = Image.new("RGBA", logo.size, tuple(m["encre"]) + (255,))
            teinte.putalpha(alpha)
            image.alpha_composite(teinte, (ex - logo.width // 2, ey - logo.height // 2))
        except Exception:
            pass   # emblème illisible : la bannière reste unie
    # 3. Le texte
    d = ImageDraw.Draw(image)
    cx, cy, largeur = m["nom"]
    nom, taille = carte["nom"].upper(), 86
    while taille > 30:
        police = _police("LiberationSerif-Bold.ttf", taille)
        if sum(d.textlength(ch, font=police) for ch in nom) + 6 * (len(nom) - 1) <= largeur:
            break
        taille -= 3
    _ecrire(d, nom, cx, cy, police, (246, 234, 206), 6)
    entete = texte_carte(cid)[0]
    largeur_boite, taille = bx1 - bx0 - 60, 64
    while taille > 28:   # « RÔLE · RÉGION » en grand, sur une seule ligne
        police = _police("LiberationSerif-Bold.ttf", taille)
        if sum(d.textlength(ch, font=police) for ch in entete) + 5 * (len(entete) - 1) <= largeur_boite:
            break
        taille -= 3
    _ecrire(d, entete, (bx0 + bx1) // 2, (by0 + by1) // 2, police, tuple(m["accent"]), 5)
    destination = destination or chemin_carte(cid)
    # 4. Découpe au ras du cadre : le fond sombre autour devient transparent (plus de bord noir dans Discord)
    forme, boite, k = _silhouette(rarete)
    image.putalpha(forme.resize(image.size, Image.LANCZOS))
    final = image.crop((int(boite[0] * k), int(boite[1] * k), int(boite[2] * k), int(boite[3] * k)))
    final = final.resize((LARGEUR, int(final.height * LARGEUR / final.width)), Image.LANCZOS)
    final.save(destination, optimize=True)
    return destination


def _fond_flou(carte):
    """La carte posée sur elle-même, floutée et assombrie : plus de zone transparente (certaines applis Discord la montrent en noir)."""
    from PIL import ImageEnhance, ImageFilter
    base = Image.new("RGBA", carte.size, (8, 10, 20, 255))
    base.alpha_composite(carte)
    fond = ImageEnhance.Brightness(base.convert("RGB").filter(ImageFilter.GaussianBlur(30))).enhance(0.35).convert("RGBA")
    fond.alpha_composite(carte)
    return fond


def _descendre(art, part):
    """Descend l'illustration de « part » de sa hauteur (tête collée au bord du haut) : le haut ajouté prolonge le décor, flouté,
    avec un fondu pour qu'on ne voie pas la jointure."""
    from PIL import ImageFilter
    ajout = int(art.height * part)
    fondu = max(8, int(art.height * 0.08))
    nouvelle = art.resize((art.width, art.height + ajout), Image.LANCZOS).filter(ImageFilter.GaussianBlur(26))   # le décor, étiré et flouté
    masque = Image.new("L", art.size, 255)
    for y in range(fondu):
        masque.paste(int(255 * y / fondu), (0, y, art.width, y + 1))
    nouvelle.paste(art, (0, ajout), masque)
    return nouvelle


def preparer_tout(journal=print):
    """Fabrique les cartes qui manquent (toutes, si la version de la mise en page a changé). À lancer dans un fil à part."""
    if not PRET:
        journal("Cartes encadrées : module d'images absent (ferme la fenêtre et relance lancer.bat pour l'installer).")
        return 0
    for dossier in (SOURCES, EMBLEMES):
        os.makedirs(dossier, exist_ok=True)
    temoin = os.path.join(DOSSIER, "cartes_version.txt")
    ancienne = open(temoin).read().strip() if os.path.exists(temoin) else ""
    faites, ratees = 0, []
    for cid in data.CARTES:
        if ancienne == VERSION and os.path.exists(chemin_carte(cid)):
            continue
        try:
            if fabriquer(cid):
                faites += 1
            else:
                ratees.append(cid)
        except Exception as erreur:
            ratees.append(f"{cid} ({erreur})")
    if not ratees:
        with open(temoin, "w") as f:
            f.write(VERSION)
    if faites or ratees:
        journal(f"Cartes encadrées : {faites} fabriquée(s)" + (f", {len(ratees)} en échec : {', '.join(ratees[:8])}" if ratees else "") + ".")
    return faites


# ------------------------------ Scène de combat --------------------------------
import io
import re
import unicodedata

_vignettes = {}   # petites cartes déjà préparées, gardées en mémoire : (carte, largeur, hauteur) -> image


def _sans_emoji(texte):
    """Garde les lettres, chiffres et ponctuations que la police sait écrire (les emojis de Discord n'en font pas partie)."""
    texte = texte.replace("**", "").replace("~~", "").replace("*", "")
    garde = "".join(ch for ch in texte if ch.isascii() or 0xA0 <= ord(ch) <= 0x24F or ch in "’…«»·—–œŒ")
    return " ".join(garde.split()).strip(" ·")


def _cle_boss(nom):
    """Nom de fichier attendu pour l'illustration d'un boss : images/boss_<nom en minuscules sans accents>.jpg ou .png"""
    if nom.startswith("Larve"):
        nom = "Larves du Néant"
    brut = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()
    return "boss_" + re.sub(r"[^a-z0-9]+", "_", brut).strip("_")


def _image_boss(nom):
    for ext in (".jpg", ".png", ".jpeg", ".webp"):
        chemin = os.path.join(DOSSIER, _cle_boss(nom) + ext)
        if os.path.exists(chemin):
            return chemin
    return None


def _panneau(nom, largeur, hauteur, chemin=None):
    """Emplacement d'une unité sans carte (boss, larve) : son illustration si elle existe, sinon un panneau sobre à son nom."""
    cle = ("panneau", nom, largeur, hauteur, chemin)
    if cle not in _vignettes:
        image = Image.new("RGBA", (largeur, hauteur), (0, 0, 0, 0))
        d = ImageDraw.Draw(image)
        forme = Image.new("L", (largeur, hauteur), 0)
        ImageDraw.Draw(forme).rounded_rectangle([0, 0, largeur - 1, hauteur - 1], 22, fill=255)
        if chemin:
            art = Image.open(chemin).convert("RGB")
            echelle = max(largeur / art.width, hauteur / art.height)
            art = art.resize((int(art.width * echelle) + 1, int(art.height * echelle) + 1), Image.LANCZOS)
            gx, gy = (art.width - largeur) // 2, int((art.height - hauteur) * 0.3)
            image.paste(art.crop((gx, gy, gx + largeur, gy + hauteur)), (0, 0), forme)
        else:
            image.paste(Image.new("RGB", (largeur, hauteur), (28, 16, 22)), (0, 0), forme)
            _ecrire(d, "?", largeur // 2, hauteur // 2 - 30, _police("LiberationSerif-Bold.ttf", min(largeur, hauteur) // 2), (120, 50, 56))
        d.rounded_rectangle([0, 0, largeur - 1, hauteur - 1], 22, outline=(196, 70, 70, 255), width=5)
        bande = Image.new("RGBA", (largeur, 64), (8, 10, 18, 215))
        image.alpha_composite(bande, (0, hauteur - 70))
        taille = 34
        while taille > 11 and d.textlength(nom.upper(), font=_police("LiberationSerif-Bold.ttf", taille)) > largeur - 24:
            taille -= 2
        _ecrire(d, nom.upper(), largeur // 2, hauteur - 38, _police("LiberationSerif-Bold.ttf", taille), (246, 226, 206), 1)
        _vignettes[cle] = image
    return _vignettes[cle]


def _silhouette(rarete):
    """Forme exacte d'un cadre : (masque blanc = la carte / noir = le fond sombre autour, boîte utile, échelle par rapport au cadre)."""
    cle = ("silhouette", rarete)
    if cle not in _vignettes:
        from PIL import ImageChops, ImageFilter
        cadre = Image.open(os.path.join(CADRES, f"cadre_{rarete}.png")).convert("RGBA")
        l, h = 240, int(cadre.height * 240 / cadre.width)
        petit = cadre.resize((l, h), Image.BOX)
        sombre = ImageChops.multiply(petit.convert("L").point(lambda v: 255 if v < 28 else 0),
                                     petit.getchannel("A").point(lambda v: 255 if v > 200 else 0))
        grille = Image.new("L", (l + 2, h + 2), 255)   # on « verse » depuis le coin : tout le sombre relié au bord est du fond
        grille.paste(sombre, (1, 1))
        ImageDraw.floodfill(grille, (0, 0), 128)
        forme = grille.point(lambda v: 0 if v == 128 else 255).crop((1, 1, l + 1, h + 1))
        boite = forme.getbbox() or (0, 0, l, h)
        _vignettes[cle] = (forme.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.8)), boite, cadre.width / l)
    return _vignettes[cle]


def _vignette(cid, largeur, hauteur, buste=False):
    """La carte encadrée, réduite pour tenir dans (largeur, hauteur). buste : seulement le haut (illustration et nom), pour les combats."""
    cle = (cid, largeur, hauteur, buste)
    if cle not in _vignettes:
        chemin = chemin_carte(cid)
        if not os.path.exists(chemin):
            _vignettes[cle] = None
        else:
            carte = Image.open(chemin).convert("RGBA")
            if buste and not cid.endswith("LR"):
                try:
                    rarete = data.CARTES[cid]["rarete"]
                    _, boite, k = _silhouette(rarete)
                    part = (MISE_EN_PAGE[rarete]["boite"][1] - 22 - boite[1] * k) / ((boite[3] - boite[1]) * k)
                    carte = carte.crop((0, 0, carte.width, int(carte.height * part)))
                except Exception:
                    pass
            carte.thumbnail((largeur, hauteur), Image.LANCZOS)
            _vignettes[cle] = carte
    return _vignettes[cle]


def _fond(nom="combat"):
    """Le décor des combats (images/fond_<nom>.jpg), assombri pour que les cartes ressortent. Sans lui, le décor habituel ou un dégradé sobre."""
    cle = ("fond", nom)
    if cle not in _vignettes:
        from PIL import ImageEnhance, ImageFilter
        L, H = 1200, 800
        chemin = next((os.path.join(DOSSIER, f"fond_{n}.{ext}") for n in (nom, "combat") for ext in ("jpg", "png")
                       if os.path.exists(os.path.join(DOSSIER, f"fond_{n}.{ext}"))), None)
        try:
            art = Image.open(chemin).convert("RGB")
            echelle = max(L / art.width, H / art.height)
            art = art.resize((int(art.width * echelle) + 1, int(art.height * echelle) + 1), Image.LANCZOS)
            x, y = (art.width - L) // 2, (art.height - H) // 2
            fond = ImageEnhance.Brightness(art.crop((x, y, x + L, y + H))).enhance(0.5)
        except Exception:
            fond = Image.new("RGB", (L, H), (3, 5, 13))
            dl = ImageDraw.Draw(fond)
            dl.ellipse([-420, 100, 380, 700], fill=(22, 52, 112))
            dl.ellipse([820, 100, 1620, 700], fill=(112, 28, 34))
            fond = fond.filter(ImageFilter.GaussianBlur(140))
        fond = fond.convert("RGBA")
        fond.alpha_composite(Image.new("RGBA", (L, 92), (4, 5, 10, 205)), (0, H - 92))   # bandeau des dernières actions
        _vignettes[cle] = fond
    return _vignettes[cle].copy()


def scene(etat, gauche, droite, lignes=(), actif=None, fond="combat"):
    """Image d'un moment de combat, dans l'arène : ton équipe à gauche, l'adversaire à droite. Chaque camp a deux colonnes,
    la ligne arrière au bord et la ligne avant vers le centre. Grosses barres de vie, dernières actions en bas.
    etat : la liste renvoyée par combat.photo(). actif : rang de l'unité qui doit jouer (duels). Renvoie un fichier en mémoire, ou None."""
    if not PRET:
        return None
    from PIL import ImageEnhance, ImageFilter
    L, H = 1200, 800
    image = _fond(fond)
    d = ImageDraw.Draw(image)
    gras = lambda t: _police("LiberationSerif-Bold.ttf", t)
    centres = {(0, "arriere"): 135, (0, "avant"): 400, (1, "avant"): 800, (1, "arriere"): 1065}
    colonnes = {cle: [] for cle in centres}
    for k, u in enumerate(etat):
        colonnes[(u["camp"], u.get("ligne") if u.get("ligne") in ("avant", "arriere") else "avant")].append((k, u))
    # Un camp dont toutes les cartes sont sur la même ligne les aligne côte à côte, pour qu'elles restent grandes.
    en_rang = {camp for camp in (0, 1) if sum(1 for l in ("avant", "arriere") if colonnes[(camp, l)]) == 1
               and max(len(colonnes[(camp, "avant")]), len(colonnes[(camp, "arriere")])) >= 2}
    plus = max([len(c) for (camp, _), c in colonnes.items() if camp not in en_rang] or [1])
    haut_carte, eb, losange, reste = {0: (330, 42, 12, 84), 1: (330, 42, 12, 84), 2: (250, 40, 11, 84)}.get(plus, (165, 30, 8, 58))
    haut_zone = H - 92 - 30
    for (camp, ligne), unites in colonnes.items():
        if not unites:
            continue
        cx = centres[(camp, ligne)]
        du_camp = [u for u in etat if u["camp"] == camp]
        seul_sans_carte = len(du_camp) == 1 and not (du_camp[0]["cid"] and os.path.exists(chemin_carte(du_camp[0]["cid"])))
        if seul_sans_carte:   # un boss : grand panneau illustré à cheval sur les deux colonnes
            cx = 268 if camp == 0 else 932
        if camp not in en_rang:
            _ecrire(d, "LIGNE AVANT" if ligne == "avant" else "LIGNE ARRIÈRE", cx, 15, gras(17), (150, 186, 255) if camp == 0 else (255, 160, 150), 2)
        haut, extra = (380, 84) if seul_sans_carte else (haut_carte, reste)
        y = 30 + (haut_zone - len(unites) * (haut + extra)) // 2
        rang = camp in en_rang
        if rang:
            cx_camp, large = (268 if camp == 0 else 932), 524 // len(unites)
            haut, extra = (300, 84) if len(unites) == 2 else (210, 84)
            y = 30 + (haut_zone - (haut + extra)) // 2
            _ecrire(d, "LIGNE AVANT" if ligne == "avant" else "LIGNE ARRIÈRE", cx_camp, 15, gras(17), (150, 186, 255) if camp == 0 else (255, 160, 150), 2)
        for place, (k, u) in enumerate(unites):
            if rang:
                cx = cx_camp + int((place - (len(unites) - 1) / 2) * large)
            if seul_sans_carte:
                vignette = _panneau(u["nom"], 500, haut, _image_boss(u["nom"]))
            else:
                vignette = _vignette(u["cid"], (large - 14) if rang else 250, haut, True) if u["cid"] else None
                if vignette is None:
                    vignette = _panneau(u["nom"], min(236, int(haut * 0.95), (large - 14) if rang else 236), haut, _image_boss(u["nom"]))
            if u["pv"] <= 0:   # K.O. : la carte passe en gris sombre
                alpha = vignette.getchannel("A")
                grise = ImageEnhance.Brightness(ImageEnhance.Color(vignette.convert("RGB")).enhance(0)).enhance(0.32).convert("RGBA")
                grise.putalpha(alpha)
                vignette = grise
            x, bas = cx - vignette.width // 2, y + haut
            barre_l = 480 if seul_sans_carte else (large - 12) if rang else max(vignette.width + 16, 150)
            bx, by = cx - barre_l // 2, bas + (extra - eb) - 12
            if actif == k and u["pv"] > 0:   # celui qui doit jouer : halo doré
                halo = Image.new("RGBA", image.size, (0, 0, 0, 0))
                ImageDraw.Draw(halo).rounded_rectangle([x - 12, bas - vignette.height - 12, x + vignette.width + 12, by + eb + 10], 26, fill=(255, 214, 110, 190))
                image.alpha_composite(halo.filter(ImageFilter.GaussianBlur(16)))
            image.alpha_composite(vignette, (x, bas - vignette.height))
            d = ImageDraw.Draw(image)
            if u["cout"] and u["pv"] > 0:   # jauge d'ulti : un losange par action à charger
                n, pas, r = u["cout"], losange * 3, losange
                for j in range(n):
                    px, py = cx - (n - 1) * pas // 2 + j * pas, bas + (by - bas) // 2
                    plein = j < min(u["jauge"], n)
                    d.polygon([(px, py - r), (px + r, py), (px, py + r), (px - r, py)], fill=(255, 214, 110) if plein else (20, 22, 32), outline=(255, 214, 110), width=2)
            # barre de vie avec le chiffre dedans, et le bouclier en liseré bleu
            d.rounded_rectangle([bx - 3, by - 3, bx + barre_l + 3, by + eb + 3], 13, fill=(8, 10, 18), outline=(110, 116, 140), width=2)
            part = max(0.0, min(1.0, u["pv"] / max(1, u["pvmax"])))
            if part > 0:
                couleur = (46, 160, 84) if part > 0.5 else (204, 150, 30) if part > 0.25 else (204, 56, 56)
                d.rounded_rectangle([bx, by, bx + max(22, int(barre_l * part)), by + eb], 10, fill=couleur)
            if u.get("bouclier"):
                fin = min(barre_l, int(barre_l * u["bouclier"] / max(1, u["pvmax"])) + 16)
                d.rounded_rectangle([bx, by, bx + fin, by + 8], 4, fill=(150, 210, 255))
            texte = "K.O." if u["pv"] <= 0 else f"{u['pv']} / {u['pvmax']}"
            taille = eb - 6
            while taille > 16 and d.textlength(texte, font=gras(taille)) > barre_l - 14:
                taille -= 2
            lt = d.textlength(texte, font=gras(taille))
            d.text((cx - lt / 2, by + eb / 2), texte, font=gras(taille), fill=(255, 255, 255), anchor="lm", stroke_width=3, stroke_fill=(0, 0, 0))
            if not rang:
                y += haut + extra
    # en bas : les dernières actions (ou « VS » au début)
    utiles = [t for t in (_sans_emoji(l) for l in lignes) if t][-2:]
    milieu = H - 46
    if not utiles:
        _ecrire(d, f"{_sans_emoji(gauche)[:22]}   VS   {_sans_emoji(droite)[:22]}".upper(), L // 2, milieu, gras(34), (246, 234, 206), 1)
    for j, t in enumerate(utiles):
        taille = 34
        while taille > 18 and d.textlength(t, font=gras(taille)) > L - 50:
            taille -= 2
        _ecrire(d, t, L // 2, milieu + (j - (len(utiles) - 1) / 2) * 38, gras(taille), (246, 234, 206))
    tampon = io.BytesIO()
    image.convert("RGB").save(tampon, "JPEG", quality=86)
    tampon.seek(0)
    return tampon


def apercu_equipe(cartes, pied=()):
    """Prévisualisation d'une équipe sur ses deux lignes, côté gauche de l'arène.
    cartes : liste de (identifiant, "avant" ou "arriere", est_leader, texte du bonus de ligne, bonus actif).
    pied : une ou deux lignes de texte en bas (bonus de leader, puissance). Renvoie un fichier en mémoire, ou None."""
    if not PRET or not cartes:
        return None
    L, H = 900, 640
    fond = _fond()
    image = fond.crop((0, 0, 708, fond.height - 92)).resize((L, H), Image.LANCZOS)   # la moitié bleue de l'arène, sans le bandeau
    image.alpha_composite(Image.new("RGBA", (L, 84), (4, 5, 10, 205)), (0, H - 84))
    d = ImageDraw.Draw(image)
    gras = lambda t: _police("LiberationSerif-Bold.ttf", t)
    centres = {"arriere": 235, "avant": 665}
    colonnes = {"arriere": [c for c in cartes if c[1] == "arriere"], "avant": [c for c in cartes if c[1] != "arriere"]}
    plus = max(len(c) for c in colonnes.values())
    haut = {1: 330, 2: 198}.get(plus, 122)
    extra = 62 if plus < 3 else 44
    for ligne, liste in colonnes.items():
        cx = centres[ligne]
        _ecrire(d, "LIGNE AVANT" if ligne == "avant" else "LIGNE ARRIÈRE", cx, 22, gras(24), (170, 200, 255), 3)
        if not liste:
            _ecrire(d, "(vide)", cx, (H - 84) // 2 + 20, _police("LiberationSerif-Italic.ttf", 26), (150, 156, 176))
            continue
        y = 66 + (H - 84 - 66 - len(liste) * (haut + extra)) // 2
        for cid, _, chef, bonus, actif in liste:
            vignette = _vignette(cid, 300, haut, True)
            if vignette is None:
                vignette = _panneau(data.CARTES[cid]["nom"], int(haut * 0.9), haut)
            x = cx - vignette.width // 2
            if chef:   # le leader : liseré doré et étiquette
                from PIL import ImageFilter
                halo = Image.new("RGBA", image.size, (0, 0, 0, 0))
                ImageDraw.Draw(halo).rounded_rectangle([x - 10, y - 10, x + vignette.width + 10, y + haut + 10], 24, fill=(255, 214, 110, 200))
                image.alpha_composite(halo.filter(ImageFilter.GaussianBlur(14)))
                d = ImageDraw.Draw(image)
            image.alpha_composite(vignette, (x, y + haut - vignette.height))
            d = ImageDraw.Draw(image)
            if chef:
                lt = d.textlength("LEADER", font=gras(20)) + 22
                d.rounded_rectangle([cx - lt / 2, y - 6, cx + lt / 2, y + 22], 10, fill=(40, 30, 8), outline=(255, 214, 110), width=2)
                _ecrire(d, "LEADER", cx, y + 8, gras(20), (255, 224, 140), 1)
            taille = 24 if plus < 3 else 19
            texte = bonus or "pas de bonus de ligne"
            while taille > 13 and d.textlength(texte, font=gras(taille)) > 400:
                taille -= 1
            lt = d.textlength(texte, font=gras(taille)) + 26
            by = y + haut + 8
            d.rounded_rectangle([cx - lt / 2, by, cx + lt / 2, by + taille + 14], 12, fill=(10, 34, 20) if actif else (22, 24, 34),
                                outline=(70, 200, 120) if actif else (96, 100, 120), width=2)
            _ecrire(d, texte, cx, by + (taille + 14) // 2, gras(taille), (150, 240, 180) if actif else (170, 174, 190))
            y += haut + extra
    utiles = [_sans_emoji(t) for t in pied if t][:2]
    for j, t in enumerate(utiles):
        taille = 28
        while taille > 15 and d.textlength(t, font=gras(taille)) > L - 40:
            taille -= 1
        _ecrire(d, t, L // 2, H - 42 + (j - (len(utiles) - 1) / 2) * 34, gras(taille), (246, 234, 206))
    tampon = io.BytesIO()
    image.convert("RGB").save(tampon, "JPEG", quality=85)
    tampon.seek(0)
    return tampon


def mystere(cid, essai, graine):
    """Un morceau de l'illustration d'un champion pour « Qui est ce champion ? ». essai : 0 = très zoomé, puis de plus en plus large.
    graine : la date du jour, pour que tout le monde voie le même morceau. Renvoie un fichier en mémoire, ou None."""
    if not PRET:
        return None
    import random
    source = _illustration(cid)
    if not source:
        return None
    art = Image.open(source).convert("RGB")
    hasard = random.Random(f"{graine}-{cid}")
    cx, cy = art.width * hasard.uniform(0.36, 0.64), art.height * hasard.uniform(0.28, 0.55)
    part = data.QUIZ_ZOOMS[min(essai, len(data.QUIZ_ZOOMS) - 1)]
    cote = max(24, int(min(art.width, art.height) * part))
    x = int(min(max(0, cx - cote / 2), art.width - cote))
    y = int(min(max(0, cy - cote / 2), art.height - cote))
    morceau = art.crop((x, y, x + cote, y + cote)).resize((640, 640), Image.LANCZOS)
    tampon = io.BytesIO()
    morceau.save(tampon, "JPEG", quality=88)
    tampon.seek(0)
    return tampon


def effectif(joueurs, titre):
    """Image d'un effectif : cinq portraits côte à côte. joueurs : [(chemin de la photo ou None, pseudo, poste, trouvé ?)]. Renvoie un fichier en mémoire."""
    import io
    L, H, cote, marge = 1200, 400, 208, 26
    img = Image.new("RGB", (L, H), (20, 22, 28))
    d = ImageDraw.Draw(img)
    _ecrire(d, titre, L // 2, 34, _police("LiberationSerif-Bold.ttf", 34), (236, 214, 150))
    for k, (chemin, pseudo, poste, trouve) in enumerate(joueurs[:5]):
        x, y = marge + k * (cote + marge), 70
        try:
            photo = Image.open(chemin).convert("RGB")
            e = max(cote / photo.width, cote / photo.height)
            photo = photo.resize((int(photo.width * e) + 1, int(photo.height * e) + 1), Image.LANCZOS)
            gx = (photo.width - cote) // 2
            img.paste(photo.crop((gx, 0, gx + cote, cote)), (x, y))
        except Exception:
            d.rectangle((x, y, x + cote, y + cote), fill=(38, 42, 52))
            _ecrire(d, "?", x + cote // 2, y + cote // 2, _police("LiberationSerif-Bold.ttf", 90), (90, 96, 110))
        d.rectangle((x, y, x + cote, y + cote), outline=(72, 187, 120) if trouve else (197, 48, 48), width=4)
        _ecrire(d, pseudo, x + cote // 2, y + cote + 30, _police("LiberationSerif-Bold.ttf", 28), (240, 240, 240))
        _ecrire(d, poste.upper(), x + cote // 2, y + cote + 64, _police("LiberationSerif-Regular.ttf", 20), (160, 166, 180))
    tampon = io.BytesIO()
    img.save(tampon, "JPEG", quality=88)
    tampon.seek(0)
    return tampon



def raid(groupes, boss, titre, lignes=(), secousse=(0, 0), impact=0.0, eclair=0.0, tremble=0, brut=False):
    """Image d'un raid : à gauche une rangée par joueur (son pseudo et ses trois cartes avec leur vie), à droite le boss en grand
    avec son immense barre de vie. groupes : [(pseudo, [unités de combat.photo()])]. boss : unité de combat.photo().
    Effets (pour l'animation) : secousse du boss en pixels, impact = éclat blanc sur le boss (0 à 1), eclair = décharge violette sur
    les joueurs (0 à 1), tremble = décalage des rangées des joueurs. Renvoie un fichier en mémoire (ou l'image elle-même si brut), ou None."""
    if not PRET:
        return None
    import io
    from PIL import ImageEnhance, ImageFilter
    L, H = 1200, 800
    image = _fond("raid")
    gras = lambda t: _police("LiberationSerif-Bold.ttf", t)
    # -- le boss, à droite : halo runique, portrait, éclat quand il est touché --
    art = _image_boss("Ryze")
    if art is None:   # sans image fournie, l'illustration officielle est récupérée une fois
        cible = os.path.join(DOSSIER, "boss_ryze.jpg")
        if _telecharger(["https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Ryze_0.jpg"], cible):
            art = cible
    bl, bh = 500, 500
    bx, by = 670 + secousse[0], 62 + secousse[1]
    rage = 0 < boss["pv"] < boss["pvmax"] * 0.3
    halo = Image.new("RGBA", (L, H), (0, 0, 0, 0))
    ImageDraw.Draw(halo).rounded_rectangle([bx - 26, by - 26, bx + bl + 26, by + bh + 26], 40, fill=(255, 70, 70, 190) if rage else (130, 90, 255, 170))
    image.alpha_composite(halo.filter(ImageFilter.GaussianBlur(30)))
    panneau = _panneau("Ryze", bl, bh, art)
    if boss["pv"] <= 0:
        alpha = panneau.getchannel("A")
        panneau = ImageEnhance.Brightness(ImageEnhance.Color(panneau.convert("RGB")).enhance(0)).enhance(0.35).convert("RGBA")
        panneau.putalpha(alpha)
    image.alpha_composite(panneau, (bx, by))
    if impact > 0:
        eclat = Image.new("RGBA", (bl, bh), (255, 255, 255, int(170 * impact)))
        masque = Image.new("L", (bl, bh), 0)
        ImageDraw.Draw(masque).rounded_rectangle([0, 0, bl - 1, bh - 1], 22, fill=255)
        image.paste(Image.alpha_composite(image.crop((bx, by, bx + bl, by + bh)), eclat), (bx, by), masque)
    d = ImageDraw.Draw(image)
    _ecrire(d, titre.upper(), L // 2, 26, gras(30), (236, 214, 150), 2)
    part = max(0.0, min(1.0, boss["pv"] / max(1, boss["pvmax"])))
    fx, y = 670, 62 + bh + 22
    d.rounded_rectangle([fx - 4, y - 4, fx + bl + 4, y + 58], 16, fill=(8, 10, 18), outline=(255, 120, 110) if rage else (150, 120, 220), width=3)
    if part > 0:
        d.rounded_rectangle([fx, y, fx + max(26, int(bl * part)), y + 54], 13, fill=(204, 56, 56) if rage else (124, 78, 200))
    _ecrire(d, f"{max(0, boss['pv']):,} / {boss['pvmax']:,} PV".replace(",", " "), fx + bl // 2, y + 27, gras(30), (255, 255, 255))
    _ecrire(d, f"{round(100 * part)} %" + ("  ·  EN RAGE" if rage else "  ·  VAINCU" if boss["pv"] <= 0 else ""), fx + bl // 2, y + 84, gras(24),
            (255, 150, 140) if rage else (220, 200, 255))
    # -- les joueurs, à gauche : une rangée chacun, sur un voile à peine teinté --
    n = max(1, len(groupes))
    haut_zone, x0, large = H - 62 - (96 if lignes else 24), 22, 620
    rang = haut_zone // n
    carte_h = min(150, rang - 62)
    carte_l = min(170, (large - 150) // 3 - 12)
    voile = Image.new("RGBA", (L, H), (0, 0, 0, 0))
    dv = ImageDraw.Draw(voile)
    for k in range(len(groupes)):
        dec = tremble if k % 2 == 0 else -tremble
        dv.rounded_rectangle([x0 + dec, 62 + k * rang + 4, x0 + large + dec, 62 + k * rang + rang - 6], 16, fill=(6, 6, 14, 96), outline=(170, 150, 255, 120), width=2)
    image.alpha_composite(voile)
    d = ImageDraw.Draw(image)
    for k, (pseudo, unites) in enumerate(groupes):
        dec = tremble if k % 2 == 0 else -tremble
        y0 = 62 + k * rang
        nom = "".join(ch for ch in pseudo if ch.isprintable() and ord(ch) < 0x2000 and not unicodedata.category(ch).startswith("M")).strip() or "Joueur"
        taille = 22
        while taille > 13 and d.textlength(nom, font=gras(taille)) > 136:
            taille -= 1
        if d.textlength(nom, font=gras(taille)) > 136:
            nom = nom[:12] + "…"
        _ecrire(d, nom, x0 + 72 + dec, y0 + rang // 2 - 14, gras(taille), (214, 222, 255))
        total = sum(u.get("inflige", 0) for u in unites)
        _ecrire(d, f"{total:,}".replace(",", " ") + " dégâts", x0 + 72 + dec, y0 + rang // 2 + 16, _police("LiberationSerif-Regular.ttf", 17), (200, 204, 222))
        for j, u in enumerate(unites[:3]):
            cx = x0 + 150 + j * (carte_l + 12) + carte_l // 2 + dec
            vignette = _vignette(u["cid"], carte_l, carte_h, True) if u["cid"] else None
            if vignette is None:
                vignette = _panneau(u["nom"], min(carte_l, int(carte_h * 0.95)), carte_h, None)
            if u["pv"] <= 0:
                alpha = vignette.getchannel("A")
                grise = ImageEnhance.Brightness(ImageEnhance.Color(vignette.convert("RGB")).enhance(0)).enhance(0.32).convert("RGBA")
                grise.putalpha(alpha)
                vignette = grise
            haut = y0 + 12
            image.alpha_composite(vignette, (cx - vignette.width // 2, haut))
            d = ImageDraw.Draw(image)
            py, pl = haut + carte_h + 8, carte_l - 8
            d.rounded_rectangle([cx - pl // 2 - 2, py - 2, cx + pl // 2 + 2, py + 26], 9, fill=(8, 10, 18), outline=(110, 116, 140), width=2)
            p = max(0.0, min(1.0, u["pv"] / max(1, u["pvmax"])))
            if p > 0:
                couleur = (46, 160, 84) if p > 0.5 else (204, 150, 30) if p > 0.25 else (204, 56, 56)
                d.rounded_rectangle([cx - pl // 2, py, cx - pl // 2 + max(14, int(pl * p)), py + 24], 7, fill=couleur)
            _ecrire(d, str(max(0, u["pv"])) if p > 0 else "K.O.", cx, py + 12, gras(17), (255, 255, 255))
    if eclair > 0:   # la Surcharge de Ryze : une décharge violette balaie le côté des joueurs
        decharge = Image.new("RGBA", (L, H), (0, 0, 0, 0))
        dd = ImageDraw.Draw(decharge)
        dd.rectangle([0, 50, 660, H - 100], fill=(150, 110, 255, int(110 * eclair)))
        hasard = __import__("random").Random(int(eclair * 1000) + len(groupes))
        for _ in range(4):   # quelques arcs partis du boss
            x, yy = 690, hasard.randint(160, 520)
            points = [(x, yy)]
            while x > 40:
                x -= hasard.randint(50, 110)
                yy += hasard.randint(-60, 60)
                points.append((x, yy))
            dd.line(points, fill=(235, 225, 255, int(255 * eclair)), width=5)
        image.alpha_composite(decharge.filter(ImageFilter.GaussianBlur(2)))
        d = ImageDraw.Draw(image)
    if lignes:
        for k, ligne in enumerate(list(lignes)[-2:]):
            texte = _sans_emoji(ligne).replace("**", "")
            _ecrire(d, _couper(d, texte, _police("LiberationSerif-Regular.ttf", 22), L - 80)[0], L // 2, H - 66 + k * 32, _police("LiberationSerif-Regular.ttf", 22), (226, 228, 240))
    if brut:
        return image
    tampon = io.BytesIO()
    image.convert("RGB").save(tampon, "JPEG", quality=88)
    tampon.seek(0)
    return tampon


def raid_anime(etapes, titre):
    """Animation d'un raid (GIF joué une seule fois) : pour chaque étape, Ryze encaisse et tremble, puis sa Surcharge balaie les joueurs.
    etapes : [(groupes, boss, lignes)] dans l'ordre du combat. Renvoie (fichier en mémoire, durée en secondes), ou (None, 0)."""
    if not PRET or not etapes:
        return None, 0
    import io
    images, durees = [], []
    def poser(durée, groupes, boss, lignes, **effets):
        vue = raid(groupes, boss, titre, lignes, brut=True, **effets).convert("RGB").resize((480, 320), Image.LANCZOS)
        images.append(vue.quantize(colors=56, method=Image.MEDIANCUT, dither=Image.Dither.NONE))
        durees.append(durée)
    pv_boss, pv_joueurs = None, None
    for rang_etape, (groupes, boss, lignes) in enumerate(etapes):
        joueurs = sum(max(0, u["pv"]) for _, unites in groupes for u in unites)
        if pv_boss is None:   # l'entrée dans la salle
            poser(1100, groupes, boss, lignes)
        else:
            if boss["pv"] < pv_boss:
                poser(90, groupes, boss, lignes, secousse=(14, -8), impact=0.9)
                poser(100, groupes, boss, lignes, secousse=(-12, 7), impact=0.4)
            if joueurs < pv_joueurs and boss["pv"] > 0:
                poser(110, groupes, boss, lignes, eclair=1.0, tremble=9)
                poser(100, groupes, boss, lignes, eclair=0.5, tremble=-7)
            poser(1500 if rang_etape == len(etapes) - 1 else 620, groupes, boss, lignes)
        pv_boss, pv_joueurs = boss["pv"], joueurs
    tampon = io.BytesIO()
    images[0].save(tampon, "GIF", save_all=True, append_images=images[1:], duration=durees, optimize=True, disposal=1)   # sans « loop » : joué une fois
    tampon.seek(0)
    return tampon, sum(durees) / 1000


def _fond_pros(clarte=0.85, fichier=None, ancre=0.5, zoom=1.0, ancre_y=0.5):
    """Le décor des Worlds : l'arène de l'équipe affrontée (fichier du dossier images), sinon images/fond_pros.jpg, sinon celui du raid."""
    cle = ("fond_pros", clarte, fichier, ancre, zoom, ancre_y)
    if cle not in _vignettes:
        from PIL import ImageEnhance
        L, H = 1200, 800
        chemin = next((os.path.join(DOSSIER, n) for n in (fichier, "fond_pros.jpg", "fond_raid.jpg", "fond_combat.jpg") if n and os.path.exists(os.path.join(DOSSIER, n))), None)
        try:
            art = Image.open(chemin).convert("RGB")
            e = max(L / art.width, H / art.height) * zoom
            art = art.resize((int(art.width * e) + 1, int(art.height * e) + 1), Image.LANCZOS)
            x, y = int((art.width - L) * ancre), int((art.height - H) * ancre_y)   # ancre : 0 = bord gauche, 1 = bord droit
            fond = ImageEnhance.Brightness(art.crop((x, y, x + L, y + H))).enhance(clarte).convert("RGBA")
        except Exception:
            fond = Image.new("RGBA", (L, H), (24, 20, 48, 255))
        _vignettes[cle] = fond
    return _vignettes[cle].copy()


def _lueur(image, boite, couleur, flou=16, marge=8):
    """Un halo coloré derrière une carte, pour la détacher du décor."""
    from PIL import ImageFilter
    x1, y1, x2, y2 = boite
    halo = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(halo).rounded_rectangle([x1 - marge, y1 - marge, x2 + marge, y2 + marge], 18, fill=couleur)
    image.alpha_composite(halo.filter(ImageFilter.GaussianBlur(flou)))


def duel_pro(groupes, pro, titre, sous_titre="", score=(), lignes=(), brut=False):
    """Écran d'un match de la tour des pros. À gauche le champion que chaque joueur envoie dans ce match (les autres ne sont pas montrés).
    À droite le pro (photo, pseudo, équipe) et ses trois champions.
    groupes : [(pseudo, [{"cid", "nom", "pv", "pvmax", "etat": "joue" | "grille" | "reserve"}], photo de profil en octets ou None)].
    pro : {"nom", "detail", "photo": chemin ou None, "unites": [unités de combat.photo()]}. score : résultats des matchs joués (True/False)."""
    if pro.get("da") == "faker":   # Faker a sa propre mise en scène
        return duel_faker(groupes, pro, titre, sous_titre, score, lignes, brut)
    if not PRET:
        return None
    import io
    from PIL import ImageEnhance, ImageFilter
    L, H = 1200, 800
    image = _fond_pros(pro.get("clarte", 0.85), pro.get("fond"))
    image.alpha_composite(Image.new("RGBA", (L, 70), (4, 5, 10, 150)))
    if lignes:
        image.alpha_composite(Image.new("RGBA", (L, 88), (4, 5, 10, 190)), (0, H - 88))
    gras = lambda t: _police("LiberationSerif-Bold.ttf", t)
    fin = lambda t: _police("LiberationSerif-Regular.ttf", t)
    d = ImageDraw.Draw(image)
    _ecrire(d, titre.upper(), L // 2, 24, gras(28), (236, 214, 150), 2)
    if sous_titre:
        _ecrire(d, sous_titre.upper(), L // 2, 54, gras(18), (200, 204, 222), 2)

    def griser(vignette, clarte):
        alpha = vignette.getchannel("A")
        grise = ImageEnhance.Brightness(ImageEnhance.Color(vignette.convert("RGB")).enhance(0)).enhance(clarte).convert("RGBA")
        grise.putalpha(alpha)
        return grise

    def barre(cx, y, largeur, u):
        d.rounded_rectangle([cx - largeur // 2 - 2, y - 2, cx + largeur // 2 + 2, y + 26], 9, fill=(8, 10, 18), outline=(110, 116, 140), width=2)
        p = max(0.0, min(1.0, u["pv"] / max(1, u["pvmax"])))
        if p > 0:
            couleur = (46, 160, 84) if p > 0.5 else (204, 150, 30) if p > 0.25 else (204, 56, 56)
            d.rounded_rectangle([cx - largeur // 2, y, cx - largeur // 2 + max(14, int(largeur * p)), y + 24], 7, fill=couleur)
        _ecrire(d, str(max(0, u["pv"])) if p > 0 else "K.O.", cx, y + 12, gras(17), (255, 255, 255))

    def carte(u, largeur, hauteur):
        vignette = _vignette(u["cid"], largeur, hauteur, True) if u.get("cid") else None
        return vignette if vignette is not None else _panneau(u["nom"].replace(" adverse", ""), largeur, min(hauteur, int(largeur * 1.25)), None)

    # -- le pro, à droite : sa photo en haut, et surtout ses trois champions, grands et éclairés --
    px, pl = 660, 520
    pw, ph = 300, 226
    ox, oy = px + 16, 82
    _lueur(image, (ox + 36, oy + 30, ox + pw - 36, oy + ph - 10), tuple(pro.get("couleur", (236, 190, 90))) + (125,), 46)
    image.alpha_composite(_portrait(pro.get("photo"), pw, ph, 18), (ox, oy))
    d = ImageDraw.Draw(image)
    tx = ox + pw + (px + pl - ox - pw) // 2
    nom_pro, taille = pro["nom"].upper(), 44
    while taille > 22 and d.textlength(nom_pro, font=gras(taille)) + 3 * len(nom_pro) > 196:
        taille -= 2
    plaque = Image.new("RGBA", (L, H), (0, 0, 0, 0))   # une plaque sombre derrière le nom : il reste lisible sur une arène claire
    ImageDraw.Draw(plaque).rounded_rectangle([tx - 104, oy + 40, tx + 104, oy + 226], 16, fill=(4, 5, 12, 120))
    image.alpha_composite(plaque)
    d = ImageDraw.Draw(image)
    _ecrire(d, nom_pro, tx, oy + 78, gras(taille), (255, 240, 200), 3)
    for n, morceau in enumerate(pro.get("detail", "").split(" · ")):
        _ecrire(d, morceau, tx, oy + 124 + n * 28, fin(21), (226, 230, 244))
    for k in range(3):   # trois pastilles : les matchs gagnés, perdus, à venir
        cx = tx + (k - 1) * 40
        etat = score[k] if k < len(score) else None
        d.ellipse([cx - 11, oy + 190, cx + 11, oy + 212], fill=(46, 160, 84) if etat else (197, 48, 48) if etat is False else (30, 32, 44), outline=(236, 214, 150), width=2)
    unites = pro["unites"][:3]
    vedettes = [data.CARTES.get(u.get("cid"), {}).get("rarete") in ("UR", "LR") for u in unites]   # une carte UR est plus grande que les autres
    largeurs = [(204 if v else 148) if any(vedettes) else 164 for v in vedettes]
    gauche = px + (pl - sum(largeurs) - 10 * (len(unites) - 1)) // 2
    for j, u in enumerate(unites):
        cl = largeurs[j]
        cx = gauche + sum(largeurs[:j]) + 10 * j + cl // 2
        vignette = carte(u, cl, 330)
        y = 596 - vignette.height   # toutes les cartes posées sur la même ligne, quelle que soit leur taille
        if u["pv"] <= 0:
            vignette = griser(vignette, 0.38)
        else:
            _lueur(image, (cx - vignette.width // 2, y, cx + vignette.width // 2, y + vignette.height),
                   (120, 190, 255, 230) if vedettes[j] else (255, 96, 86, 190), 20 if vedettes[j] else 14, 8 if vedettes[j] else 5)
        image.alpha_composite(vignette, (cx - vignette.width // 2, y))
        d = ImageDraw.Draw(image)
        barre(cx, 608, cl - 8, u)

    # -- les joueurs, à gauche : seulement le champion que chacun envoie dans ce match, en grand --
    x0, large = 22, 620
    choisis = [(g[0], next((u for u in g[1] if u.get("etat", "joue") == "joue"), g[1][0]), g[2] if len(g) > 2 else None) for g in groupes][:3]
    rang, carte_l, carte_h = 206, 170, 178
    voile = Image.new("RGBA", (L, H), (0, 0, 0, 0))
    dv = ImageDraw.Draw(voile)
    for k in range(len(choisis)):
        dv.rounded_rectangle([x0, 80 + k * rang, x0 + large, 80 + k * rang + rang - 10], 16, fill=(6, 6, 14, 92), outline=(190, 175, 255, 170), width=2)
    image.alpha_composite(voile)
    d = ImageDraw.Draw(image)
    for k, (pseudo, u, avatar) in enumerate(choisis):
        y0 = 80 + k * rang
        milieu = y0 + (rang - 10) // 2
        nom = "".join(c for c in pseudo if c.isprintable() and ord(c) < 0x2000 and not unicodedata.category(c).startswith("M")).strip() or "Joueur"
        taille = 28
        while taille > 14 and d.textlength(nom, font=gras(taille)) > 180:
            taille -= 1
        try:   # la photo de profil Discord du joueur, en médaillon ; sans elle, son pseudo
            cote = 132
            pp = Image.open(io.BytesIO(avatar) if isinstance(avatar, (bytes, bytearray)) else avatar).convert("RGB").resize((cote, cote), Image.LANCZOS)
            rond = Image.new("L", (cote * 3, cote * 3), 0)
            ImageDraw.Draw(rond).ellipse([0, 0, cote * 3 - 1, cote * 3 - 1], fill=255)
            image.paste(pp, (x0 + 112 - cote // 2, milieu - cote // 2), rond.resize((cote, cote), Image.LANCZOS))
            d = ImageDraw.Draw(image)
            d.ellipse([x0 + 112 - cote // 2 - 3, milieu - cote // 2 - 3, x0 + 112 + cote // 2 + 2, milieu + cote // 2 + 2], outline=(170, 150, 255), width=4)
        except Exception:
            _ecrire(d, nom, x0 + 112, milieu, gras(taille), (214, 222, 255))
        vignette = carte(u, carte_l, carte_h)
        if u["pv"] <= 0:
            vignette = griser(vignette, 0.32)
        cx = x0 + 312
        if u["pv"] > 0:
            _lueur(image, (cx - vignette.width // 2, milieu - vignette.height // 2, cx + vignette.width // 2, milieu + vignette.height // 2), (120, 170, 255, 150), 14, 4)
        image.alpha_composite(vignette, (cx - vignette.width // 2, milieu - vignette.height // 2))
        d = ImageDraw.Draw(image)
        _ecrire(d, u["nom"], x0 + 508, milieu - 26, gras(22), (236, 214, 150))
        barre(x0 + 508, milieu, 190, u)
    for k, ligne in enumerate(list(lignes)[-2:]):
        _ecrire(d, _couper(d, _sans_emoji(ligne).replace("**", ""), fin(22), L - 80)[0], L // 2, H - 66 + k * 32, fin(22), (226, 228, 240))
    if brut:
        return image
    tampon = io.BytesIO()
    image.convert("RGB").save(tampon, "JPEG", quality=88)
    tampon.seek(0)
    return tampon


def _gif(images, durees, taille=(480, 320), couleurs=64):
    """Assemble un GIF joué une seule fois. Renvoie (fichier en mémoire, durée en secondes)."""
    import io
    vues = [im.convert("RGB").resize(taille, Image.LANCZOS).quantize(colors=couleurs, method=Image.MEDIANCUT, dither=Image.Dither.NONE) for im in images]
    tampon = io.BytesIO()
    vues[0].save(tampon, "GIF", save_all=True, append_images=vues[1:], duration=durees, optimize=True, disposal=1)
    tampon.seek(0)
    return tampon, sum(durees) / 1000


def _portrait(chemin, largeur, hauteur, rayon=18):
    """La photo d'un pro, recadrée et arrondie, avec son liseré doré. Sans photo : un cadre sombre avec un point d'interrogation."""
    try:   # une photo détourée (fond transparent) est posée telle quelle, sans cadre : le pro se fond dans le décor
        brute = Image.open(chemin)
        if brute.mode == "RGBA" and brute.getchannel("A").getextrema()[0] < 40:
            e = min(largeur / brute.width, hauteur / brute.height)
            brute = brute.resize((max(1, int(brute.width * e)), max(1, int(brute.height * e))), Image.LANCZOS)
            alpha = brute.getchannel("A")
            bas = max(1, int(brute.height * 0.14))   # le bas du buste s'efface en douceur
            fondu = Image.new("L", brute.size, 255)
            df = ImageDraw.Draw(fondu)
            for y in range(bas):
                df.line([(0, brute.height - 1 - y), (brute.width, brute.height - 1 - y)], fill=int(255 * y / bas))
            from PIL import ImageChops
            brute.putalpha(ImageChops.multiply(alpha, fondu))
            toile = Image.new("RGBA", (largeur, hauteur), (0, 0, 0, 0))
            toile.alpha_composite(brute, ((largeur - brute.width) // 2, hauteur - brute.height))
            return toile
    except Exception:
        pass
    cadre = Image.new("RGBA", (largeur, hauteur), (18, 20, 30, 255))
    try:
        photo = Image.open(chemin).convert("RGB")
        e = max(largeur / photo.width, hauteur / photo.height)
        photo = photo.resize((int(photo.width * e) + 1, int(photo.height * e) + 1), Image.LANCZOS)
        gx = (photo.width - largeur) // 2
        cadre.paste(photo.crop((gx, 0, gx + largeur, hauteur)))
    except Exception:
        _ecrire(ImageDraw.Draw(cadre), "?", largeur // 2, hauteur // 2, _police("LiberationSerif-Bold.ttf", hauteur // 2), (90, 96, 110))
    masque = Image.new("L", (largeur, hauteur), 0)
    ImageDraw.Draw(masque).rounded_rectangle([0, 0, largeur - 1, hauteur - 1], rayon, fill=255)
    cadre.putalpha(masque)
    ImageDraw.Draw(cadre).rounded_rectangle([1, 1, largeur - 2, hauteur - 2], rayon, outline=(236, 200, 110), width=4)
    return cadre


def entree_equipe(equipe, palier, logo=None, image=None, couleur=(236, 200, 110), clarte=0.85):
    """Animation d'entrée d'une équipe des Worlds. Avec une image d'ambiance (fichier du dossier images) : la salle est plongée dans la
    couleur de l'équipe, des fumigènes montent, l'image s'embrase puis le nom claque. Sans elle : son logo (ou son nom) claque à l'écran.
    Renvoie (GIF en mémoire, durée en secondes), ou (None, 0)."""
    if not PRET:
        return None, 0
    from PIL import ImageEnhance, ImageFilter
    L, H = 1200, 800
    gras = lambda t: _police("LiberationSerif-Bold.ttf", t)
    images, durees = [], []
    try:
        ambiance = Image.open(os.path.join(DOSSIER, image)).convert("RGB") if image else None
    except Exception:
        ambiance = None
    lumiere = clarte   # réglage de l'équipe : une arène très claire est assombrie pour que les textes restent lisibles
    if ambiance is not None:
        r, v, b = couleur
        plein = ambiance.width > ambiance.height   # une arène, large : elle remplit l'écran ; une affiche, haute : elle flotte au milieu
        if plein:
            e = max(L / ambiance.width, H / ambiance.height)
            ambiance = ambiance.resize((int(ambiance.width * e) + 1, int(ambiance.height * e) + 1), Image.LANCZOS)
            gx, gy = (ambiance.width - L) // 2, (ambiance.height - H) // 2
            ambiance = ambiance.crop((gx, gy, gx + L, gy + H))
            fondu = Image.new("L", ambiance.size, 255)
        else:
            hauteur = 660
            ambiance = ambiance.resize((int(ambiance.width * hauteur / ambiance.height), hauteur), Image.LANCZOS)
            fondu = Image.new("L", ambiance.size, 0)   # bords fondus : l'image se perd dans la fumée
            ImageDraw.Draw(fondu).rounded_rectangle([46, 46, ambiance.width - 46, ambiance.height - 46], 60, fill=255)
            fondu = fondu.filter(ImageFilter.GaussianBlur(34))
        hasard = __import__("random").Random(7)
        volutes = [(hasard.randint(0, L), hasard.randint(200, H + 300), hasard.randint(120, 300), hasard.uniform(0.6, 1.6)) for _ in range(34)]

        def poser(duree, temps, clarte=0.0, eclat=0.0, nom=0, secousse=(0, 0)):
            im = Image.new("RGBA", (L, H), (r // 14, v // 12, b // 7, 255))
            fumee = Image.new("RGBA", (L, H), (0, 0, 0, 0))
            df = ImageDraw.Draw(fumee)
            for x, y, rayon, vitesse in volutes:   # les fumigènes montent et s'étalent
                yy = y - int(temps * 46 * vitesse)
                rr = rayon + int(temps * 9)
                df.ellipse([x - rr, yy - rr, x + rr, yy + rr], fill=(min(255, r + 70), min(255, v + 60), min(255, b + 30), 62))
            im.alpha_composite(fumee.filter(ImageFilter.GaussianBlur(46)))
            if clarte > 0:
                halo = Image.new("RGBA", (L, H), (0, 0, 0, 0))
                ImageDraw.Draw(halo).ellipse([L // 2 - 380, 40, L // 2 + 380, H - 20], fill=(r, v, b, int(150 * clarte)))
                im.alpha_composite(halo.filter(ImageFilter.GaussianBlur(70)))
                vue = ImageEnhance.Brightness(ambiance).enhance((0.25 + 0.85 * clarte) * min(1.0, (lumiere + 0.25) / 0.85)).convert("RGBA")
                vue.putalpha(fondu.point(lambda a: int(a * min(1.0, clarte * 1.3))))
                im.alpha_composite(vue, (max(-12, L // 2 - vue.width // 2) + (0 if plein else secousse[0]), (0 if plein else 76 + secousse[1])))
                devant = Image.new("RGBA", (L, H), (0, 0, 0, 0))   # un peu de fumée passe devant l'image
                dd = ImageDraw.Draw(devant)
                for x, y, rayon, vitesse in volutes[::4]:
                    yy = y + 160 - int(temps * 60 * vitesse)
                    dd.ellipse([x - rayon, yy - rayon // 2, x + rayon, yy + rayon // 2], fill=(min(255, r + 110), min(255, v + 90), 255, 44))
                im.alpha_composite(devant.filter(ImageFilter.GaussianBlur(40)))
            im.alpha_composite(Image.new("RGBA", (L, 84), (0, 0, 0, 110)))
            d = ImageDraw.Draw(im)
            _ecrire(d, "WORLDS", L // 2, 44, gras(40), (236, 214, 150), 14)
            if nom:
                im.alpha_composite(Image.new("RGBA", (L, 150), (0, 0, 0, 150)), (0, H - 150))
                d = ImageDraw.Draw(im)
                _ecrire(d, equipe.upper(), L // 2 + secousse[0], H - 92 + secousse[1], gras(nom), (255, 255, 255), 6)
                _ecrire(d, str(palier).upper(), L // 2, H - 34, gras(28), (min(255, r + 120), min(255, v + 90), 255), 8)
            if eclat:
                im.alpha_composite(Image.new("RGBA", (L, H), (min(255, r + 160), min(255, v + 110), 255, int(215 * eclat))))
            images.append(im)
            durees.append(duree)

        for t in range(4):
            poser(110, t)
        for t, clarte in enumerate((0.15, 0.35, 0.6, 0.85)):
            poser(100, 4 + t, clarte=clarte)
        poser(70, 8, clarte=1, eclat=0.95)
        poser(70, 9, clarte=1, eclat=0.45, nom=132, secousse=(12, -8))
        poser(70, 10, clarte=1, eclat=0.15, nom=108, secousse=(-9, 6))
        for t in range(11, 17):
            poser(170, t, clarte=1, nom=96)
        durees[-1] = 1400
        return _gif(images, durees, couleurs=80)

    fond = _fond_pros(0.7)
    try:
        embleme = Image.open(os.path.join(DOSSIER, logo)).convert("RGBA")
        embleme.thumbnail((460, 460), Image.LANCZOS)
    except Exception:
        embleme = None

    def poser(duree, ligne=0.0, taille=0.0, eclat=0.0, secousse=(0, 0), nom=False):
        im = fond.copy()
        d = ImageDraw.Draw(im)
        _ecrire(d, "WORLDS", L // 2, 70, gras(40), (236, 214, 150), 14)
        if ligne:
            d.rectangle([L // 2 - int(520 * ligne), 118, L // 2 + int(520 * ligne), 122], fill=(236, 200, 110))
            d.rectangle([L // 2 - int(520 * ligne), 678, L // 2 + int(520 * ligne), 682], fill=(236, 200, 110))
        if taille:
            if embleme is not None:
                e = embleme.resize((max(1, int(embleme.width * taille)), max(1, int(embleme.height * taille))), Image.LANCZOS)
                im.alpha_composite(e, (L // 2 - e.width // 2 + secousse[0], 370 - e.height // 2 + secousse[1]))
                d = ImageDraw.Draw(im)
            else:
                _ecrire(d, equipe.upper(), L // 2 + secousse[0], 370 + secousse[1], gras(int(110 * taille)), (255, 232, 170), 4)
        if nom:
            _ecrire(d, (equipe if embleme is not None else str(palier)).upper(), L // 2, 630, gras(40), (255, 240, 200), 6)
            if embleme is not None:
                _ecrire(d, str(palier).upper(), L // 2, 726, gras(26), (200, 204, 222), 6)
        if eclat:
            im.alpha_composite(Image.new("RGBA", (L, H), (255, 244, 210, int(210 * eclat))))
        images.append(im)
        durees.append(duree)

    for l in (0.2, 0.6, 1.0):
        poser(70, ligne=l)
    poser(70, ligne=1, taille=1.5, eclat=0.95, secousse=(12, -8))
    poser(70, ligne=1, taille=1.2, eclat=0.5, secousse=(-9, 6))
    poser(70, ligne=1, taille=1.05, eclat=0.15, secousse=(4, -2))
    poser(300, ligne=1, taille=1.0)
    poser(60, ligne=1, taille=1.0, nom=True, eclat=0.25)
    poser(1700, ligne=1, taille=1.0, nom=True)
    return _gif(images, durees)


def duel_anime(etapes, pro, titre, sous_titre="", score=()):
    """Animation d'un match de la tour des pros (GIF joué une fois) : à chaque étape, le camp qui encaisse tremble sous un éclat.
    etapes : [(groupes, unités du pro, lignes)] dans l'ordre du combat. Renvoie (GIF en mémoire, durée en secondes), ou (None, 0)."""
    if not PRET or not etapes:
        return None, 0
    from PIL import ImageChops
    images, durees = [], []
    avant = None
    for rang_etape, (groupes, unites, lignes) in enumerate(etapes):
        base = duel_pro(groupes, dict(pro, unites=unites), titre, sous_titre, score, lignes, brut=True)
        pv_pro = sum(max(0, u["pv"]) for u in unites)
        pv_joueurs = sum(max(0, u["pv"]) for g in groupes for u in g[1] if u.get("etat", "joue") == "joue")
        if avant is None:
            images.append(base)
            durees.append(1000)
        else:
            for cote, touche, couleur in ((1, pv_pro < avant[0], (255, 255, 255)), (0, pv_joueurs < avant[1], (255, 90, 90))):
                if not touche:
                    continue
                for dx, dy, force_eclat in ((12, -7, 0.75), (-10, 6, 0.35)):
                    im = ImageChops.offset(base, dx, dy)
                    eclat = Image.new("RGBA", base.size, (0, 0, 0, 0))
                    limite = ((780 if pro.get("solo") else 840), 500) if pro.get("da") == "faker" else (650, 650)
                    ImageDraw.Draw(eclat).rectangle([limite[0] if cote else 0, 70, 1200 if cote else limite[1], 740], fill=couleur + (int(150 * force_eclat),))
                    im.alpha_composite(eclat)
                    images.append(im)
                    durees.append(90)
            images.append(base)
            durees.append(1500 if rang_etape == len(etapes) - 1 else 650)
        avant = (pv_pro, pv_joueurs)
    return _gif(images, durees, couleurs=72)


def entree_pro(pro, numero, champions):
    """Animation d'avant-match : le pro entre en scène, son nom claque, puis ses trois champions arrivent un par un, d'abord en très grand.
    pro : {"nom", "detail", "photo"}. champions : [{"cid", "nom"}]. Renvoie (GIF en mémoire, durée en secondes), ou (None, 0)."""
    if pro.get("da") == "faker":
        return entree_champions_faker(pro, numero, champions)
    if not PRET:
        return None, 0
    L, H = 1200, 800
    gras = lambda t: _police("LiberationSerif-Bold.ttf", t)
    fond = _fond_pros(pro.get("clarte", 0.85) - 0.04, pro.get("fond"))
    portrait = _portrait(pro["photo"], 380, 290, 22)
    cl, ch = 300, 420

    vedettes = [data.CARTES.get(c.get("cid"), {}).get("rarete") in ("UR", "LR") for c in champions[:3]]
    tailles = [(1.22 if v else 0.86) if any(vedettes) else 1.0 for v in vedettes]

    def carte(c, echelle=1.0):
        l, h = int(cl * echelle), int(ch * echelle)
        v = _vignette(c["cid"], l, h, True) if c.get("cid") else None
        return v if v is not None else _panneau(c["nom"], l, min(h, int(l * 1.25)), None)

    images, durees = [], []

    def vue(glisse=1.0, nom_taille=0, eclat=0.0, secousse=(0, 0), montres=0, vedette=None, traits=False):
        im = fond.copy()
        im.alpha_composite(Image.new("RGBA", (L, 76), (4, 5, 10, 150)))
        d = ImageDraw.Draw(im)
        if traits:   # des traits de vitesse pendant qu'il arrive
            hasard = __import__("random").Random(int(glisse * 100))
            for _ in range(26):
                y, x = hasard.randint(90, 380), hasard.randint(0, L)
                d.line([(x, y), (x + hasard.randint(120, 380), y)], fill=(236, 214, 150), width=hasard.randint(2, 5))
        _ecrire(d, numero.upper() if isinstance(numero, str) else f"MATCH {numero} SUR 3", L // 2, 40, gras(30), (236, 214, 150), 6)
        im.alpha_composite(portrait, (70 + int((1 - glisse) * 1300) + secousse[0], 92 + secousse[1]))
        d = ImageDraw.Draw(im)
        if nom_taille:
            plaque = Image.new("RGBA", (L, H), (0, 0, 0, 0))
            ImageDraw.Draw(plaque).rounded_rectangle([510, 120, 1130, 330], 22, fill=(4, 5, 12, 115))
            im.alpha_composite(plaque)
            d = ImageDraw.Draw(im)
            _ecrire(d, pro["nom"].upper(), 820 + secousse[0], 200 + secousse[1], gras(nom_taille), (255, 232, 170), 4)
            _ecrire(d, pro.get("detail", ""), 820, 288, _police("LiberationSerif-Regular.ttf", 32), (232, 236, 248))
        for k in range(montres):
            v = carte(champions[k], tailles[k])
            x, y = 600 + (k - 1) * (cl + 60) - v.width // 2, 404 + (ch - v.height) // 2 - 20
            _lueur(im, (x, y, x + v.width, y + v.height), (120, 190, 255, 235) if vedettes[k] else (255, 96, 86, 200), 26 if vedettes[k] else 18, 10 if vedettes[k] else 6)
            im.alpha_composite(v, (x, y))
        if vedette is not None:   # le champion qui arrive, en très grand au milieu de l'écran
            k, echelle = vedette
            v = carte(champions[k], echelle * (1.12 if vedettes[k] else 1.0))
            x, y = 600 - v.width // 2 + int((k - 1) * (cl + 60) * (1.9 - echelle)), 400 - v.height // 2 + int(180 * (1.9 - echelle))
            _lueur(im, (x, y, x + v.width, y + v.height), (255, 220, 130, 230), 26, 12)
            im.alpha_composite(v, (x, y))
            _ecrire(ImageDraw.Draw(im), champions[k]["nom"].upper(), 600, 742, gras(46), (255, 240, 200), 4)
        if eclat:
            im.alpha_composite(Image.new("RGBA", (L, H), (255, 244, 210, int(200 * eclat))))
        return im

    def poser(duree, **k):
        images.append(vue(**k))
        durees.append(duree)

    for g in (0.25, 0.6, 0.9):
        poser(60, glisse=g, traits=True)
    poser(70, nom_taille=130, eclat=0.9, secousse=(12, -6))
    poser(70, nom_taille=100, eclat=0.35, secousse=(-8, 4))
    poser(420, nom_taille=88)
    for k in range(len(champions[:3])):
        poser(70, nom_taille=88, montres=k, vedette=(k, 1.7), eclat=0.55)
        poser(520, nom_taille=88, montres=k, vedette=(k, 1.6))
        poser(70, nom_taille=88, montres=k, vedette=(k, 1.25))
        poser(160, nom_taille=88, montres=k + 1)
    durees[-1] = 1800
    return _gif(images, durees, couleurs=64)


def presentation_pros(equipe, pros, fond=None, clarte=0.85, couleur=(236, 200, 110)):
    """Animation de présentation de l'effectif, entre l'entrée de l'équipe et le premier match : les trois pros arrivent un par un,
    chacun en grand au centre avec son nom qui claque, puis il va se ranger. Leurs champions ne sont pas montrés.
    pros : [(pseudo, poste, chemin de la photo ou None)]. Renvoie (GIF en mémoire, durée en secondes), ou (None, 0)."""
    if not PRET or not pros:
        return None, 0
    L, H = 1200, 800
    gras = lambda t: _police("LiberationSerif-Bold.ttf", t)
    fin = lambda t: _police("LiberationSerif-Regular.ttf", t)
    decor = _fond_pros(max(0.3, clarte - 0.12), fond)
    r, v, b = couleur
    teinte = (min(255, r + 60), min(255, v + 60), min(255, b + 60))
    pros = pros[:3]
    grands = [_portrait(p[2], 560, 430, 26) for p in pros]
    petits = [_portrait(p[2], 320, 246, 18) for p in pros]
    places = [(L // 2 + int((k - (len(pros) - 1) / 2) * 372) - 160, 250) for k in range(len(pros))]
    images, durees = [], []

    def vue(ranges=0, vedette=None, echelle=1.0, glisse=0.0, eclat=0.0, secousse=(0, 0), nom=0):
        im = decor.copy()
        im.alpha_composite(Image.new("RGBA", (L, 96), (0, 0, 0, 100)))
        d = ImageDraw.Draw(im)
        _ecrire(d, equipe.upper(), L // 2, 34, gras(38), (255, 240, 200), 8)
        _ecrire(d, "L'EFFECTIF", L // 2, 74, gras(20), teinte, 10)
        for k in range(ranges):   # ceux qui sont déjà présentés, rangés côte à côte
            x, y = places[k]
            _lueur(im, (x, y, x + 320, y + 246), (r, v, b, 150), 18, 6)
            im.alpha_composite(petits[k], (x, y))
            d = ImageDraw.Draw(im)
            im.alpha_composite(Image.new("RGBA", (320, 92), (0, 0, 0, 120)), (x, y + 258))
            d = ImageDraw.Draw(im)
            _ecrire(d, pros[k][0].upper(), x + 160, y + 290, gras(38), (255, 255, 255), 2)
            _ecrire(d, pros[k][1], x + 160, y + 328, fin(24), teinte)
        if vedette is not None:
            k = vedette
            if glisse:   # il quitte le centre pour aller à sa place
                x0, y0 = L // 2 - 280, 150
                x1, y1 = places[k]
                l, h = int(560 - 240 * glisse), int(430 - 184 * glisse)
                portrait = _portrait(pros[k][2], l, h, 22)
                x, y = int(x0 + (x1 - x0) * glisse), int(y0 + (y1 - y0) * glisse)
            else:
                l, h = int(560 * echelle), int(430 * echelle)
                portrait = grands[k] if echelle == 1.0 else grands[k].resize((l, h), Image.LANCZOS)
                x, y = L // 2 - l // 2 + secousse[0], 150 + (430 - h) // 2 + secousse[1]
            _lueur(im, (x, y, x + portrait.width, y + portrait.height), (r, v, b, 210), 30, 14)
            im.alpha_composite(portrait, (x, y))
            if nom:
                im.alpha_composite(Image.new("RGBA", (L, 170), (0, 0, 0, 140)), (0, 606))
                d = ImageDraw.Draw(im)
                _ecrire(d, pros[k][0].upper(), L // 2 + secousse[0], 668 + secousse[1], gras(nom), (255, 255, 255), 6)
                _ecrire(d, pros[k][1].upper(), L // 2, 742, gras(30), teinte, 10)
        if eclat:
            im.alpha_composite(Image.new("RGBA", (L, H), (min(255, r + 160), min(255, v + 150), min(255, b + 150), int(215 * eclat))))
        return im

    def poser(duree, **k):
        images.append(vue(**k))
        durees.append(duree)

    poser(350)
    for k in range(len(pros)):
        poser(70, ranges=k, vedette=k, echelle=1.25, eclat=0.9, secousse=(10, -6))
        poser(70, ranges=k, vedette=k, echelle=1.1, eclat=0.4, nom=120, secousse=(-8, 5))
        poser(620, ranges=k, vedette=k, nom=96)
        poser(70, ranges=k, vedette=k, glisse=0.5)
        poser(180, ranges=k + 1, eclat=0.15)
    durees[-1] = 1700
    return _gif(images, durees, couleurs=80)


# ============================ FAKER : une mise en scène à part ============================
# Grande finale des Worlds : titre « The Unkillable Demon King », Faker qui apparaît avec le chut, puis un écran de match
# tout en rouge où ses trois champions sont à la verticale (son visage est déjà dans l'arène, pas besoin de sa photo).
def _fumee_rouge(graine, temps=0, force=70):
    from PIL import ImageFilter
    h = __import__("random").Random(graine)
    f = Image.new("RGBA", (1200, 800), (0, 0, 0, 0))
    d = ImageDraw.Draw(f)
    for _ in range(30):
        x, y, r = h.randint(0, 1200), h.randint(150, 1050) - temps * 40, h.randint(120, 300)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(210, 20, 30, force))
    return f.filter(ImageFilter.GaussianBlur(50))


def _eclairs_rouges(graine, x0, x1, nombre=4):
    from PIL import ImageFilter
    h = __import__("random").Random(graine)
    f = Image.new("RGBA", (1200, 800), (0, 0, 0, 0))
    d = ImageDraw.Draw(f)
    for _ in range(nombre):
        x, y = h.randint(x0, x1), h.randint(60, 200)
        points = [(x, y)]
        while y < 740:
            x += h.randint(-26, 26)
            y += h.randint(14, 34)
            points.append((x, y))
        d.line(points, fill=(255, 170, 175, 235), width=2)
    lueur = f.filter(ImageFilter.GaussianBlur(10))
    tout = Image.new("RGBA", (1200, 800), (0, 0, 0, 0))
    for couche in (lueur, lueur, f):
        tout.alpha_composite(couche)
    return tout


def _image_faker(nom, largeur, hauteur):
    """Une image du dossier images réduite pour tenir dans (largeur, hauteur), gardée en mémoire. None si elle manque."""
    cle = ("faker", nom, largeur, hauteur)
    if cle not in _vignettes:
        try:
            im = Image.open(os.path.join(DOSSIER, nom)).convert("RGBA")
            im.thumbnail((largeur, hauteur), Image.LANCZOS)
            _vignettes[cle] = im
        except Exception:
            _vignettes[cle] = None
    return _vignettes[cle]


def entree_faker(nom="Faker", phase="Grande finale"):
    """L'entrée de Faker : le titre claque dans la fumée rouge, puis Faker apparaît en fondu devant, avec le chut.
    Renvoie (GIF en mémoire, durée en secondes), ou (None, 0)."""
    if not PRET:
        return None, 0
    from PIL import ImageChops, ImageEnhance, ImageFilter
    L, H = 1200, 800
    gras = lambda t: _police("LiberationSerif-Bold.ttf", t)
    titre = _image_faker("titre_faker.png", 1120, 460)
    try:
        photo = Image.open(os.path.join(DOSSIER, "faker_chut.jpg")).convert("RGB")
        photo = ImageEnhance.Contrast(photo.resize((int(photo.width * 700 / photo.height), 700), Image.LANCZOS)).enhance(1.08)
        masque = Image.new("L", photo.size, 0)
        ImageDraw.Draw(masque).ellipse([photo.width * 0.24, 90, photo.width * 0.82, photo.height * 1.3], fill=255)
        masque = masque.filter(ImageFilter.GaussianBlur(60))
        photo = Image.blend(photo, ImageChops.multiply(photo, Image.new("RGB", photo.size, (200, 10, 25))), 0.28).convert("RGBA")
    except Exception:
        photo, masque = None, None
    images, durees = [], []

    def poser(duree, temps, taille=0.0, sombre=1.0, haut=0, visage=0.0, texte=False, eclat=0.0, secousse=(0, 0)):
        im = Image.new("RGBA", (L, H), (14, 2, 4, 255))
        im.alpha_composite(_fumee_rouge(3, temps))
        if taille and titre is not None:
            halo = Image.new("RGBA", (L, H), (0, 0, 0, 0))
            ImageDraw.Draw(halo).ellipse([120, 180 - haut, 1080, 620 - haut], fill=(255, 20, 40, int(120 * sombre)))
            im.alpha_composite(halo.filter(ImageFilter.GaussianBlur(90)))
            t = titre.resize((max(1, int(titre.width * taille)), max(1, int(titre.height * taille))), Image.LANCZOS)
            if sombre < 1:
                t = ImageEnhance.Brightness(t).enhance(0.35 + 0.65 * sombre)
                t.putalpha(t.getchannel("A").point(lambda v: int(v * (0.45 + 0.55 * sombre))))
            im.alpha_composite(t, (L // 2 - t.width // 2 + secousse[0], H // 2 - haut - t.height // 2 + secousse[1]))
        if visage and photo is not None:
            p = photo.copy()
            p.putalpha(masque.point(lambda v: int(v * visage)))
            im.alpha_composite(p, (L // 2 - int(p.width * 0.53), H - p.height + 10))
            im.alpha_composite(_fumee_rouge(9, temps, 46))
        if texte:
            bas = Image.new("RGBA", (L, 170), (0, 0, 0, 0))
            db = ImageDraw.Draw(bas)
            for y in range(170):
                db.line([(0, y), (L, y)], fill=(6, 0, 2, int(230 * y / 170)))
            im.alpha_composite(bas, (0, H - 170))
            d = ImageDraw.Draw(im)
            _ecrire(d, nom.upper(), L // 2 + secousse[0], H - 86 + secousse[1], gras(96), (255, 255, 255), 18)
            _ecrire(d, str(phase).upper(), L // 2, H - 30, gras(26), (255, 90, 100), 10)
        if eclat:
            im.alpha_composite(Image.new("RGBA", (L, H), (255, 70, 80, int(215 * eclat))))
        images.append(im)
        durees.append(duree)

    for t in range(3):
        poser(140, t)
    poser(70, 3, taille=1.35, eclat=0.95, secousse=(14, -8))
    poser(70, 4, taille=1.12, eclat=0.4, secousse=(-10, 6))
    poser(70, 5, taille=1.03, eclat=0.12, secousse=(4, -2))
    poser(1300, 6, taille=1.0)
    for k, v in enumerate((0.25, 0.5, 0.75, 1.0)):   # le titre recule vers le haut, Faker apparaît devant
        poser(120, 7 + k, taille=1.0, sombre=1 - 0.8 * v, haut=int(150 * v), visage=v)
    poser(80, 11, taille=1.0, sombre=0.2, haut=150, visage=1, texte=True, eclat=0.5, secousse=(10, -6))
    poser(80, 12, taille=1.0, sombre=0.2, haut=150, visage=1, texte=True, eclat=0.15, secousse=(-6, 4))
    poser(2200, 13, taille=1.0, sombre=0.2, haut=150, visage=1, texte=True)
    return _gif(images, durees, couleurs=96)


def duel_faker(groupes, pro, titre, sous_titre="", score=(), lignes=(), brut=False, montres=3, vedette=None, eclat=0.0):
    """Écran de match contre Faker : l'arène (avec son visage) en plein écran, ses trois champions à la verticale à droite dans un
    halo rouge, les joueurs à la verticale à gauche. montres : combien de ses champions sont déjà posés ; vedette : (rang, échelle)
    du champion en train d'arriver, en grand au centre."""
    if not PRET:
        return None
    import io
    from PIL import ImageEnhance, ImageFilter
    L, H = 1200, 800
    image = _fond_pros(pro.get("clarte", 0.92), pro.get("fond"), pro.get("ancre", 0.5), pro.get("zoom", 1.0), pro.get("ancre_y", 0.5))
    image.alpha_composite(Image.new("RGBA", (L, 70), (6, 0, 2, 170)))
    if lignes:
        image.alpha_composite(Image.new("RGBA", (L, 62), (6, 0, 2, 200)), (0, H - 62))
    gras = lambda t: _police("LiberationSerif-Bold.ttf", t)
    fin = lambda t: _police("LiberationSerif-Regular.ttf", t)
    d = ImageDraw.Draw(image)
    _ecrire(d, titre.upper(), L // 2, 24, gras(28), (255, 225, 225), 2)
    if sous_titre:
        _ecrire(d, sous_titre.upper(), L // 2, 54, gras(18), (255, 120, 125), 2)
    rang = 222 if lignes else 236

    def griser(vignette, clarte):
        alpha = vignette.getchannel("A")
        grise = ImageEnhance.Brightness(ImageEnhance.Color(vignette.convert("RGB")).enhance(0)).enhance(clarte).convert("RGBA")
        grise.putalpha(alpha)
        return grise

    def barre(cx, y, largeur, u):
        d.rounded_rectangle([cx - largeur // 2 - 2, y - 2, cx + largeur // 2 + 2, y + 26], 9, fill=(8, 10, 18), outline=(110, 116, 140), width=2)
        p = max(0.0, min(1.0, u["pv"] / max(1, u["pvmax"])))
        if p > 0:
            couleur = (46, 160, 84) if p > 0.5 else (204, 150, 30) if p > 0.25 else (204, 56, 56)
            d.rounded_rectangle([cx - largeur // 2, y, cx - largeur // 2 + max(14, int(largeur * p)), y + 24], 7, fill=couleur)
        _ecrire(d, str(max(0, u["pv"])) if p > 0 else "K.O.", cx, y + 12, gras(17), (255, 255, 255))

    def carte(u, largeur, hauteur):
        vignette = _vignette(u["cid"], largeur, hauteur, True) if u.get("cid") else None
        return vignette if vignette is not None else _panneau(u["nom"].replace(" adverse", ""), largeur, min(hauteur, int(largeur * 1.25)), None)

    unites = pro["unites"][:3]
    if pro.get("solo") and unites:   # le duel final : le pro fait partie de l'arène, en apparition géante
        u = unites[0]
        rage = 0 < u["pv"] < u["pvmax"] * 0.3
        zone = (560, 40, 1190, 560)   # où se trouve l'apparition dans le décor
        voile = Image.new("RGBA", (L, H), (0, 0, 0, 0))
        dv = ImageDraw.Draw(voile)
        dv.rectangle([0, 0, 520, H], fill=(0, 0, 0, 110))   # le côté des joueurs un peu assombri
        dv.ellipse([zone[0] - 40, zone[1] - 20, zone[2] + 60, zone[3] + 40], fill=(255, 10, 30, 90 if rage else 40))
        image.alpha_composite(voile.filter(ImageFilter.GaussianBlur(70)))
        if u["pv"] <= 0:   # vaincu : l'apparition s'éteint
            eteint = image.crop(zone)
            eteint = ImageEnhance.Brightness(ImageEnhance.Color(eteint.convert("RGB")).enhance(0.1)).enhance(0.5).convert("RGBA")
            masque = Image.new("L", eteint.size, 0)
            ImageDraw.Draw(masque).ellipse([20, 0, eteint.width, eteint.height], fill=255)
            image.paste(eteint, zone[:2], masque.filter(ImageFilter.GaussianBlur(40)))
        else:
            image.alpha_composite(_eclairs_rouges(11, 600, 1180, 5 if rage else 3))
        d = ImageDraw.Draw(image)
        part = max(0.0, min(1.0, u["pv"] / max(1, u["pvmax"])))
        bx, bl, fy = 590, 580, 684   # 14 octobre : barre plus basse, pour laisser voir le trône au fond
        _ecrire(d, u["nom"].replace(" adverse", "").upper(), bx + bl // 2, fy - 30, gras(44), (255, 235, 235), 6)
        if not u.get("intro"):
            d.rounded_rectangle([bx - 4, fy - 4, bx + bl + 4, fy + 42], 14, fill=(8, 4, 6), outline=(255, 70, 80) if rage else (255, 140, 140), width=3)
            if part > 0:
                d.rounded_rectangle([bx, fy, bx + max(26, int(bl * part)), fy + 38], 11, fill=(235, 20, 40) if rage else (190, 18, 36))
            _ecrire(d, f"{max(0, u['pv']):,} / {u['pvmax']:,} PV".replace(",", " ") + (f"  ·  {round(100 * part)} %" if part > 0 else "  ·  VAINCU"),
                    bx + bl // 2, fy + 19, gras(24), (255, 255, 255))
            if rage:
                _ecrire(d, "EN RAGE", bx + bl // 2, 92, gras(30), (255, 210, 210), 6)
    else:
        # -- à droite : la colonne rouge de Faker --
        voile = Image.new("RGBA", (L, H), (0, 0, 0, 0))
        ImageDraw.Draw(voile).rectangle([840, 70, L, H], fill=(40, 0, 6, 150))
        image.alpha_composite(voile.filter(ImageFilter.GaussianBlur(30)))
        image.alpha_composite(_eclairs_rouges(5, 1010, 1190, 4))
        image.alpha_composite(_eclairs_rouges(8, 845, 870, 2))
        d = ImageDraw.Draw(image)
        for k, u in enumerate(unites[:montres]):
            y0, cx = 84 + k * rang, 930
            v = carte(u, 190, rang - 26)
            if u["pv"] <= 0:
                v = griser(v, 0.36)
            else:
                _lueur(image, (cx - v.width // 2, y0, cx + v.width // 2, y0 + v.height), (255, 30, 45, 255), 30, 14)
                _lueur(image, (cx - v.width // 2, y0, cx + v.width // 2, y0 + v.height), (255, 150, 150, 200), 8, 3)
            image.alpha_composite(v, (cx - v.width // 2, y0))
            d = ImageDraw.Draw(image)
            nom = u["nom"].replace(" adverse", "").split(" de ")[0].split(",")[0].upper()
            taille = 30
            while taille > 16 and d.textlength(nom, font=gras(taille)) + 3 * len(nom) > 176:
                taille -= 2
            _ecrire(d, nom, 1096, y0 + (100 if u.get("intro") else 76), gras(taille), (255, 235, 235), 3)
            if not u.get("intro"):
                barre(1096, y0 + 106, 170, u)

    # -- à gauche : le champion que chaque joueur envoie --
    x0, large = 18, 470
    choisis = [(g[0], next((u for u in g[1] if u.get("etat", "joue") == "joue"), g[1][0]), g[2] if len(g) > 2 else None) for g in groupes][:3]
    voile = Image.new("RGBA", (L, H), (0, 0, 0, 0))
    dv = ImageDraw.Draw(voile)
    for k in range(len(choisis)):
        dv.rounded_rectangle([x0, 84 + k * rang, x0 + large, 84 + k * rang + rang - 12], 16, fill=(6, 6, 14, 120), outline=(255, 90, 100, 170), width=2)
    image.alpha_composite(voile)
    d = ImageDraw.Draw(image)
    for k, (pseudo, u, avatar) in enumerate(choisis):
        y0 = 84 + k * rang
        milieu = y0 + (rang - 12) // 2
        try:
            cote = 112
            pp = Image.open(io.BytesIO(avatar) if isinstance(avatar, (bytes, bytearray)) else avatar).convert("RGB").resize((cote, cote), Image.LANCZOS)
            rond = Image.new("L", (cote * 3, cote * 3), 0)
            ImageDraw.Draw(rond).ellipse([0, 0, cote * 3 - 1, cote * 3 - 1], fill=255)
            image.paste(pp, (x0 + 78 - cote // 2, milieu - cote // 2), rond.resize((cote, cote), Image.LANCZOS))
            d = ImageDraw.Draw(image)
            d.ellipse([x0 + 78 - cote // 2 - 3, milieu - cote // 2 - 3, x0 + 78 + cote // 2 + 2, milieu + cote // 2 + 2], outline=(255, 120, 130), width=4)
        except Exception:
            nom = "".join(c for c in pseudo if c.isprintable() and ord(c) < 0x2000 and not unicodedata.category(c).startswith("M")).strip() or "Joueur"
            _ecrire(d, nom[:10], x0 + 78, milieu, gras(20), (214, 222, 255))
        v = carte(u, 170, rang - 46)
        if u["pv"] <= 0:
            v = griser(v, 0.32)
        cx = x0 + 232
        if u["pv"] > 0:
            _lueur(image, (cx - v.width // 2, milieu - v.height // 2, cx + v.width // 2, milieu + v.height // 2), (120, 170, 255, 150), 14, 4)
        image.alpha_composite(v, (cx - v.width // 2, milieu - v.height // 2))
        d = ImageDraw.Draw(image)
        nom_carte = u["nom"].split(",")[0]
        taille = 20
        while taille > 13 and d.textlength(nom_carte, font=gras(taille)) > 150:
            taille -= 1
        _ecrire(d, nom_carte, x0 + 388, milieu - 26, gras(taille), (236, 214, 150))
        barre(x0 + 388, milieu, 150, u)
    if vedette is not None and vedette[0] < len(unites):   # le champion de Faker qui arrive, en grand au centre
        k, echelle = vedette
        v = carte(unites[k], int(300 * echelle), int(420 * echelle))
        x, y = 600 - v.width // 2 + int(330 * (1.6 - echelle) / 0.5), 400 - v.height // 2 + int((84 + k * rang + 100 - 400) * (1.6 - echelle) / 0.5)
        _lueur(image, (x, y, x + v.width, y + v.height), (255, 30, 45, 255), 40, 18)
        image.alpha_composite(v, (x, y))
        _ecrire(ImageDraw.Draw(image), unites[k]["nom"].replace(" adverse", "").upper(), 600, 748, gras(44), (255, 235, 235), 4)
    d = ImageDraw.Draw(image)
    for k, ligne in enumerate(list(lignes)[-1:]):
        _ecrire(d, _couper(d, _sans_emoji(ligne).replace("**", ""), fin(22), L - 80)[0], L // 2, H - 32, fin(22), (240, 228, 230))
    if eclat:
        image.alpha_composite(Image.new("RGBA", (L, H), (255, 70, 80, int(210 * eclat))))
    if brut:
        return image
    tampon = io.BytesIO()
    image.convert("RGB").save(tampon, "JPEG", quality=88)
    tampon.seek(0)
    return tampon


def entree_champions_faker(pro, numero, champions):
    """Avant le match contre Faker : ses trois champions arrivent un par un, en grand, puis vont se ranger à la verticale à droite."""
    if not PRET:
        return None, 0
    unites = [{"cid": c.get("cid"), "nom": c["nom"], "pv": 1, "pvmax": 1, "intro": True} for c in champions[:3]]
    titre = numero.upper() if isinstance(numero, str) else "GRANDE FINALE"
    images, durees = [], []

    def poser(duree, **k):
        images.append(duel_faker([], dict(pro, unites=unites), "Worlds · Grande finale · " + pro["nom"], titre, brut=True, **k))
        durees.append(duree)

    poser(500, montres=0)
    for k in range(len(unites)):
        poser(70, montres=k, vedette=(k, 1.6), eclat=0.6)
        poser(560, montres=k, vedette=(k, 1.6))
        poser(70, montres=k, vedette=(k, 1.3))
        poser(180, montres=k + 1)
    durees[-1] = 1800
    return _gif(images, durees, couleurs=72)


# ============================ CARTES LR (Faker) ET CARTES DE PRO ============================
# Deux cadres à part, déjà détourés dans images/cadres : cadre_LR.png (rouge, « Faker · The Unkillable Demon King » gravé dans le
# bandeau) et cadre_PRO.png (or et argent). Ils n'ont pas de boîte de texte : le nom du champion s'écrit en bas de l'illustration.
CADRES_SPECIAUX = {
    "LR":  {"fichier": "cadre_LR.png", "fenetre": (203, 296, 824, 1152), "accent": (255, 70, 80)},
    "PRO": {"fichier": "cadre_PRO.png", "fenetre": (196, 262, 830, 1098), "nom": (512, 1192, 520), "accent": (236, 200, 110)},
}


def _poser_cadre(art, genre, cadrage=(0.5, 0.3), descente=0):
    """Remplit la fenêtre d'un cadre spécial avec une image (recadrée), pose le cadre par-dessus. Renvoie (image, mise en page)."""
    m = CADRES_SPECIAUX[genre]
    cadre = Image.open(os.path.join(CADRES, m["fichier"])).convert("RGBA")
    x0, y0, x1, y1 = m["fenetre"]
    x0, y0, x1, y1 = x0 - 14, y0 - 60, x1 + 14, y1 + 14   # un peu plus large que la fenêtre : rien ne manque derrière les ornements
    fw, fh = x1 - x0, y1 - y0
    echelle = max(fw / art.width, fh / art.height)
    art = art.resize((int(art.width * echelle) + 1, int(art.height * echelle) + 1), Image.LANCZOS)
    gx, gy = int((art.width - fw) * cadrage[0]), int((art.height - fh) * cadrage[1])
    image = Image.new("RGBA", cadre.size, (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle([x0, y0, x1, y1], fill=(8, 2, 4, 255))
    image.paste(art.crop((gx, gy, gx + fw, gy + fh - descente)).convert("RGBA"), (x0, y0 + descente))   # descente : l'image commence plus bas, sous l'ornement du haut
    return image, cadre, m


def _finir_speciale(image, destination):
    boite = image.getchannel("A").point(lambda v: 255 if v > 60 else 0).getbbox() or (0, 0) + image.size
    final = image.crop(boite)
    final = final.resize((LARGEUR, int(final.height * LARGEUR / final.width)), Image.LANCZOS)
    final.save(destination, optimize=True)
    return destination


def fabriquer_lr(cid, destination=None):
    """Une carte LR de Faker : l'illustration du champion dans le cadre rouge, son nom en bas de l'image."""
    source = _illustration(cid)
    if not source or not os.path.exists(os.path.join(CADRES, CADRES_SPECIAUX["LR"]["fichier"])):
        return None
    image, cadre, m = _poser_cadre(Image.open(source).convert("RGB"), "LR", CADRAGES.get(cid, (0.5, 0.3)), 48)
    x0, y0, x1, y1 = m["fenetre"]
    ombre = Image.new("RGBA", image.size, (0, 0, 0, 0))   # un dégradé sombre au bas de l'illustration, pour y lire le nom
    do = ImageDraw.Draw(ombre)
    for y in range(230):
        do.line([(x0, y1 - 230 + y), (x1, y1 - 230 + y)], fill=(10, 0, 2, int(215 * (y / 230) ** 1.4)))
    image.alpha_composite(ombre)
    image.alpha_composite(cadre)
    d = ImageDraw.Draw(image)
    nom = data.CARTES[data.CARTES[cid].get("base", cid)]["nom"].upper()
    taille = 104
    while taille > 40 and d.textlength(nom, font=_police("LiberationSerif-Bold.ttf", taille)) + 10 * len(nom) > x1 - x0 - 90:
        taille -= 4
    _ecrire(d, nom, (x0 + x1) // 2, y1 - 92, _police("LiberationSerif-Bold.ttf", taille), (255, 236, 236), 10)
    return _finir_speciale(image, destination or chemin_carte(cid))


def carte_pro(pseudo, poste, equipe, photo, destination, fond=None, couleur=(236, 200, 110), clarte=0.62, taille=1.0):
    """La carte d'un joueur pro (futur coach) : sa photo détourée devant l'arène de son équipe, dans le cadre or et argent."""
    from PIL import ImageEnhance, ImageFilter
    if not os.path.exists(os.path.join(CADRES, CADRES_SPECIAUX["PRO"]["fichier"])):
        return None
    try:
        decor = Image.open(os.path.join(DOSSIER, fond)).convert("RGB")
        decor = ImageEnhance.Brightness(decor.filter(ImageFilter.GaussianBlur(7))).enhance(clarte)
    except Exception:
        decor = Image.new("RGB", (800, 1000), (18, 16, 26))
    image, cadre, m = _poser_cadre(decor, "PRO", (0.5, 0.35))
    x0, y0, x1, y1 = m["fenetre"]
    halo = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse([x0 + 40, y0 + 160, x1 - 40, y1 + 120], fill=tuple(couleur) + (120,))
    halo = halo.filter(ImageFilter.GaussianBlur(70))
    masque = Image.new("L", image.size, 0)
    ImageDraw.Draw(masque).rectangle([x0 - 14, y0 - 60, x1 + 14, y1 + 14], fill=255)
    halo.putalpha(ImageChops_multiply(halo.getchannel("A"), masque))
    image.alpha_composite(halo)
    try:
        p = Image.open(photo).convert("RGBA")
        p = p.crop(p.getchannel("A").point(lambda v: 255 if v > 30 else 0).getbbox() or (0, 0) + p.size)   # sans les marges vides
        plein = p.getchannel("A").getextrema()[0] > 200   # une photo avec son décor (pas détourée) remplit toute la fenêtre
        e = max((x1 - x0 + 30) / p.width, (y1 - y0 + 80) / p.height) if plein else min((x1 - x0 + 70) / p.width, (y1 - y0 - 40) / p.height) * taille
        p = p.resize((int(p.width * e), int(p.height * e)), Image.LANCZOS)
        px, py = (x0 + x1) // 2 - p.width // 2, y1 + 14 - p.height
        calque = Image.new("RGBA", image.size, (0, 0, 0, 0))
        calque.alpha_composite(p, (px, py))
        calque.putalpha(ImageChops_multiply(calque.getchannel("A"), masque))
        image.alpha_composite(calque)
    except Exception:
        pass
    bas = Image.new("RGBA", image.size, (0, 0, 0, 0))
    db = ImageDraw.Draw(bas)
    for y in range(150):
        db.line([(x0, y1 - 150 + y), (x1, y1 - 150 + y)], fill=(4, 4, 8, int(240 * (y / 150) ** 1.1)))
    image.alpha_composite(bas)
    image.alpha_composite(cadre)
    d = ImageDraw.Draw(image)
    court = {"Karmine Corp": "KC", "Invictus Gaming": "IG", "G2 Esports": "G2", "Bilibili Gaming": "BLG"}.get(equipe, equipe)
    plaque = Image.new("RGBA", image.size, (0, 0, 0, 0))   # un petit bandeau sombre : la ligne reste lisible sur un maillot clair
    ImageDraw.Draw(plaque).rounded_rectangle([(x0 + x1) // 2 - 190, y1 - 84, (x0 + x1) // 2 + 190, y1 - 18], 30, fill=(6, 6, 10, 185))
    image.alpha_composite(plaque)
    d = ImageDraw.Draw(image)
    _ecrire(d, f"{poste} · {court}".upper(), (x0 + x1) // 2, y1 - 52, _police("LiberationSerif-Bold.ttf", 50), (255, 244, 214), 6)
    cx, cy, largeur = m["nom"]
    nom, taille = pseudo.upper(), 84
    while taille > 34 and d.textlength(nom, font=_police("LiberationSerif-Bold.ttf", taille)) + 8 * len(nom) > largeur:
        taille -= 4
    _ecrire(d, nom, cx, cy, _police("LiberationSerif-Bold.ttf", taille), (255, 244, 214), 8)
    return _finir_speciale(image, destination)


def ImageChops_multiply(a, b):
    from PIL import ImageChops
    return ImageChops.multiply(a, b)


# ---- Ouvertures de pack à part : une carte LR de Faker (rouge) et une carte de pro (or et argent)
def ouverture_lr(cid):
    """Un pack pro qui donne une LR : fumée rouge, le titre claque, puis la carte se révèle. Renvoie (GIF, durée) ou (None, 0)."""
    if not PRET:
        return None, 0
    from PIL import ImageFilter
    L, H = 1200, 800
    titre = _image_faker("titre_faker.png", 1000, 400)
    carte = _vignette(cid, 520, 700)
    images, durees = [], []

    def poser(duree, temps, taille=0.0, haut=0, montre=0.0, eclat=0.0, secousse=(0, 0)):
        im = Image.new("RGBA", (L, H), (14, 2, 4, 255))
        im.alpha_composite(_fumee_rouge(3, temps))
        if taille and titre is not None:
            t = titre.resize((max(1, int(titre.width * taille)), max(1, int(titre.height * taille))), Image.LANCZOS)
            if montre:
                t.putalpha(t.getchannel("A").point(lambda v: int(v * (1 - 0.75 * montre))))
            im.alpha_composite(t, (L // 2 - t.width // 2 + secousse[0], H // 2 - haut - t.height // 2 + secousse[1]))
        if montre and carte is not None:
            c = carte.resize((max(1, int(carte.width * (0.6 + 0.4 * montre))), max(1, int(carte.height * (0.6 + 0.4 * montre)))), Image.LANCZOS)
            x, y = L // 2 - c.width // 2, H // 2 - c.height // 2 + 20
            _lueur(im, (x + 60, y + 60, x + c.width - 60, y + c.height - 60), (255, 30, 45, int(255 * montre)), 60, 20)
            c.putalpha(c.getchannel("A").point(lambda v: int(v * montre)))
            im.alpha_composite(c, (x, y))
        if eclat:
            im.alpha_composite(Image.new("RGBA", (L, H), (255, 70, 80, int(215 * eclat))))
        images.append(im)
        durees.append(duree)

    for t in range(3):
        poser(150, t)
    poser(70, 3, taille=1.3, eclat=0.95, secousse=(14, -8))
    poser(70, 4, taille=1.1, eclat=0.4, secousse=(-10, 6))
    poser(900, 5, taille=1.0)
    poser(80, 6, taille=1.0, haut=40, montre=0.35, eclat=0.7)
    poser(80, 7, taille=1.0, haut=40, montre=0.7, eclat=0.3)
    poser(2500, 8, taille=1.0, haut=40, montre=1.0)
    return _gif(images, durees, couleurs=96)


def ouverture_pro(chemin_carte_pro):
    """Un pack pro qui donne une carte de pro : faisceaux or et argent, éclair, puis la carte. Renvoie (GIF, durée) ou (None, 0)."""
    if not PRET:
        return None, 0
    from PIL import ImageFilter
    L, H = 1200, 800
    try:
        carte = Image.open(chemin_carte_pro).convert("RGBA")
        carte.thumbnail((520, 700), Image.LANCZOS)
    except Exception:
        return None, 0
    hasard = __import__("random").Random(11)
    rayons = [(hasard.uniform(0, 6.283), hasard.randint(6, 26), hasard.random() > 0.5) for _ in range(26)]
    images, durees = [], []
    import math

    def poser(duree, force, montre=0.0, eclat=0.0):
        im = Image.new("RGBA", (L, H), (10, 9, 14, 255))
        f = Image.new("RGBA", (L, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(f)
        for angle, largeur, argent in rayons:
            x, y = L // 2 + math.cos(angle) * 900, H // 2 + math.sin(angle) * 900
            d.line([(L // 2, H // 2), (x, y)], fill=((225, 230, 245) if argent else (240, 196, 96)) + (int(150 * force),), width=largeur)
        im.alpha_composite(f.filter(ImageFilter.GaussianBlur(14)))
        halo = Image.new("RGBA", (L, H), (0, 0, 0, 0))
        ImageDraw.Draw(halo).ellipse([L // 2 - 300, H // 2 - 330, L // 2 + 300, H // 2 + 330], fill=(255, 226, 150, int(140 * force)))
        im.alpha_composite(halo.filter(ImageFilter.GaussianBlur(80)))
        if montre:
            c = carte.resize((max(1, int(carte.width * (0.6 + 0.4 * montre))), max(1, int(carte.height * (0.6 + 0.4 * montre)))), Image.LANCZOS)
            c.putalpha(c.getchannel("A").point(lambda v: int(v * montre)))
            im.alpha_composite(c, (L // 2 - c.width // 2, H // 2 - c.height // 2))
        if eclat:
            im.alpha_composite(Image.new("RGBA", (L, H), (255, 244, 214, int(220 * eclat))))
        images.append(im)
        durees.append(duree)

    for force in (0.15, 0.35, 0.6, 0.85):
        poser(170, force)
    poser(70, 1, eclat=0.95)
    poser(80, 1, montre=0.4, eclat=0.5)
    poser(80, 1, montre=0.8, eclat=0.2)
    poser(2500, 1, montre=1.0)
    return _gif(images, durees, couleurs=96)



