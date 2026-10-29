"""Import des joueurs pros depuis Leaguepedia (lol.fandom.com) : effectifs LPL / LCK / LEC / LCS par année, et photos.
Lancé tout seul par le bot quand ce fichier change. Résultat : pros.json et le dossier photos/. Journal : import.log.
Données : Leaguepedia (CC BY-SA 3.0)."""
import io, json, os, re, sys, time, traceback, urllib.parse, urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
CACHE, PHOTOS = os.path.join(ICI, "cache"), os.path.join(ICI, "photos")
os.makedirs(CACHE, exist_ok=True); os.makedirs(PHOTOS, exist_ok=True)
LOG = open(os.path.join(ICI, "import.log"), "a", encoding="utf-8")
MOI = str(os.getpid())
open(os.path.join(ICI, "pid.txt"), "w").write(MOI)
def seul():
    """Faux si un import plus récent a démarré : celui-ci doit alors s'arrêter."""
    try:
        return open(os.path.join(ICI, "pid.txt")).read() == MOI
    except OSError:
        return True
def log(*a):
    if not seul():
        sys.exit(0)
    LOG.write(time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a) + "\n"); LOG.flush()
UA = {"User-Agent": "2Hot4Deck-bot/1.0 (bot Discord de fans ; import ponctuel)"}
LIGUES = {"LPL/": "LPL", "LCK/": "LCK", "Champions/": "LCK", "LEC/": "LEC", "EU LCS/": "LEC", "LCS/": "LCS", "NA LCS/": "LCS", "LTA North/": "LCS"}
EXCLUS = ("Promotion", "Qualifier", "Expansion")
MIN_MATCHS = 10      # un joueur n'est gardé (et sa photo téléchargée) que s'il a commencé au moins autant de matchs

def lire(url, brut=False):
    for essai in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                d = r.read()
            return d if brut else json.loads(d.decode("utf-8", "replace"))
        except Exception as e:
            log("  erreur réseau", repr(e)[:150]); time.sleep(4 * (essai + 1))
    return None

NAVIGATEUR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
              "Referer": "https://lol.fandom.com/", "Accept": "image/avif,image/webp,image/png,image/*,*/*;q=0.8"}
def photo_brute(url):
    for entetes in (NAVIGATEUR, UA):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=entetes), timeout=40) as r:
                return r.read()
        except Exception as e:
            derniere = repr(e)[:120]
    log("  photo refusée", derniere, url[:120])
    return None

def api(**p):
    p["format"] = "json"
    return lire("https://lol.fandom.com/api.php?" + urllib.parse.urlencode(p)) or {}

def nom_fichier(titre):
    return re.sub(r"[^A-Za-z0-9]+", "_", titre).strip("_")

def pages_effectifs():
    chemin = os.path.join(CACHE, "_pages.json")
    if os.path.exists(chemin):
        return json.load(open(chemin, encoding="utf-8"))
    pages = []
    for prefixe in LIGUES:
        suite = {}
        while True:
            d = api(action="query", list="allpages", apprefix=prefixe, aplimit=500, **suite)
            pages += [p["title"] for p in d.get("query", {}).get("allpages", []) if p["title"].endswith("/Team Rosters")]
            if "continue" not in d:
                break
            suite = {"apcontinue": d["continue"]["apcontinue"]}; time.sleep(1.2)
    pages = [p for p in pages if not any(x in p for x in EXCLUS)]
    json.dump(pages, open(chemin, "w", encoding="utf-8"), ensure_ascii=False)
    return pages

def texte(page):
    chemin = os.path.join(CACHE, nom_fichier(page) + ".txt")
    if os.path.exists(chemin):
        return open(chemin, encoding="utf-8").read()
    d = api(action="parse", page=page, prop="wikitext")
    t = d.get("parse", {}).get("wikitext", {}).get("*")
    time.sleep(1.5)
    if t is None:
        log("  page illisible", page, json.dumps(d)[:200]); return ""
    open(chemin, "w", encoding="utf-8").write(t)
    return t

def annee(page):
    m = re.search(r"/(\d{4}) Season", page)
    if m:
        return int(m.group(1))
    m = re.search(r"/Season (\d)", page)
    return 2010 + int(m.group(1)) if m else None

ROLES = {"t": "top", "top": "top", "j": "jungle", "jungle": "jungle", "jng": "jungle", "jungler": "jungle", "m": "mid", "mid": "mid", "middle": "mid", "ap": "mid",
         "b": "adc", "bot": "adc", "a": "adc", "ad": "adc", "adc": "adc", "s": "support", "support": "support", "sup": "support"}
def analyser(t):
    """Renvoie [(équipe, page du joueur, rôle, matchs commencés, drapeau)] d'une page d'effectifs (les deux mises en page du site)."""
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    sortie = []
    morceaux = re.split(r"=+\s*\{\{\s*[Tt]eam\s*\|\s*([^}|]+?)\s*(?:\|[^}]*)?\}\}\s*=+", t)
    for k in range(1, len(morceaux) - 1, 2):
        equipe, corps = morceaux[k].strip(), morceaux[k + 1]
        for ligne in re.findall(r"\{\{\s*ExtendedRoster/Line\s*\|(.*?)\}\}", corps, flags=re.S):
            champs = dict((a.strip().lower(), b.strip()) for a, _, b in (x.partition("=") for x in ligne.split("|")) if _)
            joueur = champs.get("player", "").replace("_", " ").strip()
            role = ROLES.get((champs.get("role") or champs.get("role1") or "").strip().lower())
            if not joueur or not role:
                continue
            r = "".join(v for c, v in champs.items() if re.fullmatch(r"r\d*", c))
            sortie.append((equipe, joueur, role, r.lower().count("y") if r else 1, champs.get("flag", "")))
        # ancienne mise en page : un tableau, une ligne {{player|…}} puis le nom puis le poste
        for pseudo, options, poste in re.findall(r"\{\{\s*[Pp]layer\s*\|\s*([^}|]+)([^}]*)\}\}\s*\n\|[^\n]*\n\|\s*([A-Za-z]+)", corps):
            role = ROLES.get(poste.strip().lower())
            lien = re.search(r"link\s*=\s*([^|}]+)", options)
            drapeau = re.search(r"flag\s*=\s*([^|}]+)", options)
            if role:
                sortie.append((equipe, (lien.group(1) if lien else pseudo).replace("_", " ").strip(), role, 12, drapeau.group(1).strip() if drapeau else ""))
    return sortie

def fusionner_equipes(lignes):
    """Une même équipe est parfois écrite en abrégé (« SKT », « GRF ») : on la rattache à son nom complet quand, la même année, au moins trois joueurs sont communs."""
    groupes = {}
    for (joueur, equipe, an, ligue, role), matchs in lignes.items():
        g = groupes.setdefault((an, ligue), {}).setdefault(equipe, [set(), 0])
        g[0].add(joueur); g[1] += matchs
    noms = {}
    for (an, ligue), equipes in groupes.items():
        ordre = sorted(equipes, key=lambda e: -equipes[e][1])
        for k, petit in enumerate(ordre):
            for grand in ordre[:k]:
                if len(equipes[petit][0] & equipes[grand][0]) >= 3:
                    noms[(an, ligue, petit)] = noms.get((an, ligue, grand), grand); break
    sortie = {}
    for (joueur, equipe, an, ligue, role), matchs in lignes.items():
        cle = (joueur, noms.get((an, ligue, equipe), equipe), an, ligue, role)
        sortie[cle] = sortie.get(cle, 0) + matchs
    log(len(noms), "noms d'équipe abrégés rattachés")
    return sortie

def resoudre(titres):
    """Suit les redirections du wiki : {titre demandé: vrai titre de la page}. Sert aux abréviations d'équipe (C9 → Cloud9) et aux pseudos écrits de plusieurs façons."""
    chemin = os.path.join(CACHE, "_redirections.json")
    connus = json.load(open(chemin, encoding="utf-8")) if os.path.exists(chemin) else {}
    a_faire = [t for t in titres if t not in connus]
    for k in range(0, len(a_faire), 50):
        lot = a_faire[k:k + 50]
        q = api(action="query", titles="|".join(lot), redirects=1).get("query")
        if q is None:
            log("  redirections illisibles"); break
        pas = {}
        for x in q.get("normalized", []) + q.get("redirects", []):
            pas[x["from"]] = x["to"]
        absents = {p["title"] for p in q.get("pages", {}).values() if "missing" in p}
        for t in lot:
            fin = t
            for _ in range(4):
                fin = pas.get(fin, fin)
            connus[t] = t if fin in absents else fin.split("#")[0]
        json.dump(connus, open(chemin, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(1.2)
    return {t: connus.get(t, t) for t in titres}

def renommer(lignes, equipes=None, joueurs=None):
    sortie = {}
    for (joueur, equipe, an, ligue, role), matchs in lignes.items():
        cle = ((joueurs or {}).get(joueur, joueur), (equipes or {}).get(equipe, equipe), an, ligue, role)
        sortie[cle] = sortie.get(cle, 0) + matchs
    return sortie

# Abréviations que le wiki renvoie vers le nom actuel du club (ou vers rien) : on garde le nom de l'époque.
NOMS_EQUIPES = {"AFs": "Afreeca Freecs", "DN SOOPers": "Afreeca Freecs", "DRX": "DRX", "Kiwoom DRX": "DRX", "DWG": "DAMWON Gaming", "Dplus Kia": "DAMWON Gaming",
                "UOL": "Unicorns of Love", "Unicorns of Love.CIS": "Unicorns of Love", "KZ": "KING-ZONE DragonX", "Kz": "KING-ZONE DragonX", "TOP": "Top Esports", "Top": "Top Esports",
                "VIT": "Team Vitality", "Vit": "Team Vitality", "tip": "Team Impulse", "Tip": "Team Impulse", "DIG": "Dignitas", "FLY": "FlyQuest", "ROG": "Rogue", "SPY": "Splyce",
                "KT": "KT Rolster", "ROC": "Team ROCCAT", "clg": "Counter Logic Gaming", "we": "Team WE", "lmq": "LMQ", "EdwarD Gaming": "EDward Gaming", "tsm": "TSM",
                "Team SoloMid": "TSM", "FC Schalke 04": "FC Schalke 04 Esports", "NRG eSports": "NRG", "SinoDragon": "SinoDragon Gaming", "KSV": "KSV eSports"}

def principal():
    log("===== nouvel import, processus", MOI)
    pages = pages_effectifs()
    log(len(pages), "pages d'effectifs à lire")
    lignes, vides = {}, []
    for n, page in enumerate(pages):
        ligue, an = next(v for k, v in LIGUES.items() if page.startswith(k)), annee(page)
        trouve = analyser(texte(page)) if an else []
        if not trouve:
            vides.append(page)
        for equipe, joueur, role, matchs, drapeau in trouve:
            cle = (joueur, equipe, an, ligue, role)
            lignes[cle] = lignes.get(cle, 0) + matchs
            PAYS.setdefault(joueur, drapeau)
        if n % 20 == 0:
            log("  lu", n + 1, "/", len(pages), page)
    log("pages sans effectif reconnu :", len(vides), json.dumps(vides, ensure_ascii=False)[:3000])
    lignes = fusionner_equipes(lignes)
    lignes = fusionner_equipes(renommer(lignes, equipes=NOMS_EQUIPES))
    courts = sorted({e for (_, e, _, _, _) in lignes if e == e.lower() or len(e) <= 4})
    vrais = resoudre(courts)
    log(len(courts), "abréviations d'équipe ·", sum(1 for a, b in vrais.items() if a != b), "résolues :", json.dumps({a: b for a, b in vrais.items() if a != b}, ensure_ascii=False)[:1500])
    vrais = {a: NOMS_EQUIPES.get(b, b) for a, b in vrais.items()}
    lignes = fusionner_equipes(renommer(lignes, equipes=vrais))
    propres = {e: re.sub(r"\s*\((?:[^)]*Team|[^)]*team)\)$", "", e) for (_, e, _, _, _) in lignes}
    lignes = fusionner_equipes(renommer(lignes, equipes=propres))
    pseudos = resoudre(sorted({j for (j, _, _, _, _) in lignes}))
    log(sum(1 for a, b in pseudos.items() if a != b), "pseudos rattachés à leur page")
    lignes = renommer(lignes, joueurs=pseudos)
    for ancien, nouveau in pseudos.items():
        PAYS.setdefault(nouveau, PAYS.get(ancien, ""))
    joueurs = {}
    for (joueur, equipe, an, ligue, role), matchs in lignes.items():
        joueurs.setdefault(joueur, []).append([an, ligue, equipe, role, matchs])
    joueurs = {j: sorted(c) for j, c in joueurs.items() if sum(x[4] for x in c) >= MIN_MATCHS}
    log(len(lignes), "lignes ·", len(joueurs), "joueurs gardés")
    sauver(joueurs, {})
    photos = telecharger_photos(sorted(joueurs), lambda ph: sauver(joueurs, ph))
    sauver(joueurs, photos)
    log("TERMINÉ :", len(joueurs), "joueurs,", sum(1 for p in photos.values() if p), "photos")

PAYS = {}
def sauver(joueurs, photos):
    donnees = {"source": "Leaguepedia (lol.fandom.com), CC BY-SA 3.0", "date": time.strftime("%Y-%m-%d"),
               "joueurs": {j: {"nom": re.sub(r"\s*\(.*\)$", "", j), "pays": PAYS.get(j, ""), "photo": photos.get(j), "carriere": c} for j, c in joueurs.items()}}
    tmp = os.path.join(ICI, "pros.tmp")
    json.dump(donnees, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, os.path.join(ICI, "pros.json"))

def telecharger_photos(titres, point=None):
    try:
        from PIL import Image
    except ImportError:
        log("Pillow absent : pas de photos"); return {}
    photos, urls = {}, {}
    connus = os.path.join(CACHE, "_photos.json")
    if os.path.exists(connus):
        urls = json.load(open(connus, encoding="utf-8"))
    a_chercher = [t for t in titres if t not in urls]
    for k in range(0, len(a_chercher), 50):
        lot = a_chercher[k:k + 50]
        d = api(action="query", titles="|".join(lot), prop="pageimages", piprop="thumbnail|name", pithumbsize=260, pilimit=50, redirects=1)
        q = d.get("query", {})
        retour = {}
        for x in q.get("normalized", []) + q.get("redirects", []):
            retour[x["to"]] = retour.get(x["from"], x["from"])
        for p in q.get("pages", {}).values():
            origine = retour.get(p.get("title"), p.get("title"))
            urls[origine] = p.get("thumbnail", {}).get("source")
        for t in lot:
            urls.setdefault(t, None)
        json.dump(urls, open(connus, "w", encoding="utf-8"), ensure_ascii=False)
        if k % 500 == 0:
            log("  adresses des photos", k, "/", len(a_chercher))
        time.sleep(1.2)
    faits = rates = 0
    for n, t in enumerate(titres):
        if n % 10 == 0 and not seul():
            sys.exit(0)
        url = urls.get(t)
        if not url:
            continue
        fichier = nom_fichier(t) + ".jpg"
        chemin = os.path.join(PHOTOS, fichier)
        if not os.path.exists(chemin):
            brut = photo_brute(url)
            time.sleep(0.25)
            if not brut:
                rates += 1
                if rates >= 8 and not faits:
                    log("  les photos sont refusées par le site : abandon des photos"); break
                continue
            try:
                im = Image.open(io.BytesIO(brut)).convert("RGBA")
                fond = Image.new("RGBA", im.size, (24, 26, 32, 255)); fond.alpha_composite(im)
                fond.convert("RGB").save(chemin, "JPEG", quality=85)
            except Exception as e:
                log("  photo illisible", t, repr(e)[:100]); continue
        photos[t] = fichier; faits += 1
        if n % 100 == 0:
            log("  photos", n, "/", len(titres), "·", faits, "prêtes")
            if point:
                point(photos)
    return photos

if __name__ == "__main__":
    try:
        principal()
    except Exception:
        log(traceback.format_exc())
    log("FIN")
