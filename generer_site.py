"""
Fabrique la page index.html a partir de combats.json.

A lancer apres mma_tracker.py :
    python generer_site.py
Puis ouvre index.html dans ton navigateur.

Fichiers optionnels a cote du script :
- logos/       : logos des organisations (ufc.png, ksw.png...)
- fond.jpg     : photo d'ambiance en arriere-plan (tres assombrie)
- infos.json   : heure et chaine par evenement (cree automatiquement,
                 tu n'as qu'a remplir les champs vides)
"""

import json
import os
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

# Identite du site pour Google et pour les partages sur les reseaux.
# Le titre s'affiche dans les resultats de recherche : environ
# 60 caracteres, au-dela Google coupe. La description, environ 155.
SITE_URL = "https://mmaradar.fr"
SITE_TITRE = "Calendrier MMA francophone : prochains combats | MMA Radar"
SITE_DESC = ("Les prochains combats des combattants francophones en MMA : "
             "UFC, PFL, ARES, Hexagone, KSW. Dates, villes et diffusion, "
             "mis à jour chaque matin.")

MOIS_COURT = ["JANV", "FEVR", "MARS", "AVR", "MAI", "JUIN",
              "JUIL", "AOUT", "SEPT", "OCT", "NOV", "DEC"]

MOIS_LONG = ["JANVIER", "FÉVRIER", "MARS", "AVRIL", "MAI", "JUIN",
             "JUILLET", "AOÛT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DÉCEMBRE"]

# Pays tel qu'ecrit par Sherdog -> code drapeau
PAYS_ISO = {
    "france": "fr", "united states": "us", "canada": "ca", "belgium": "be",
    "switzerland": "ch", "morocco": "ma", "tunisia": "tn", "senegal": "sn",
    "cameroon": "cm", "guinea": "gn", "algeria": "dz", "united kingdom": "gb",
    "england": "gb", "scotland": "gb", "ireland": "ie", "poland": "pl",
    "germany": "de", "netherlands": "nl", "spain": "es", "italy": "it",
    "portugal": "pt", "sweden": "se", "norway": "no", "denmark": "dk",
    "austria": "at", "czech republic": "cz", "czechia": "cz", "slovakia": "sk",
    "serbia": "rs", "croatia": "hr", "georgia": "ge", "turkey": "tr",
    "russia": "ru", "ukraine": "ua", "kazakhstan": "kz", "azerbaijan": "az",
    "united arab emirates": "ae", "qatar": "qa", "saudi arabia": "sa",
    "bahrain": "bh", "japan": "jp", "china": "cn", "south korea": "kr",
    "singapore": "sg", "thailand": "th", "philippines": "ph", "india": "in",
    "australia": "au", "new zealand": "nz", "brazil": "br", "mexico": "mx",
    "argentina": "ar", "south africa": "za",
}

# (mot cherche dans le nom de l'evenement, fichier logo, libelle de secours)
ORGAS = [
    ("contender series", "dwcs", "Contender Series"),
    ("dana white", "dwcs", "Contender Series"),
    ("dwcs", "dwcs", "Contender Series"),
    ("road to ufc", "ufc", "ROAD TO UFC"),
    ("ufc", "ufc", "UFC"),
    ("ksw", "ksw", "KSW"),
    ("ares", "ares", "ARES"),
    ("hexagone", "hexagone", "HEXAGONE MMA"),
    ("hxmma", "hexagone", "HEXAGONE MMA"),
    ("hx mma", "hexagone", "HEXAGONE MMA"),
    ("oktagon", "oktagon", "OKTAGON"),
    ("cage warriors", "cagewarriors", "CAGE WARRIORS"),
    ("professional fighters", "pfl", "PFL"),
    ("pfl", "pfl", "PFL"),
    ("most valuable", "mvp", "MVP"),
    ("mvp", "mvp", "MVP"),
    ("bellator", "bellator", "BELLATOR"),
    ("rizin", "rizin", "RIZIN"),
    ("one championship", "one", "ONE"),
    ("one fc", "one", "ONE"),
    ("bkfc", "bkfc", "BKFC"),
    ("brave", "brave", "BRAVE CF"),
    ("uae warriors", "uaew", "UAE WARRIORS"),
    ("uaew", "uaew", "UAE WARRIORS"),
]

ICONE_AGENDA = (
    '<svg viewBox="0 0 20 20" width="15" height="15" fill="none" '
    'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
    'aria-hidden="true">'
    '<rect x="2.5" y="4" width="15" height="13.5" rx="2.5"/>'
    '<path d="M2.5 8.5h15"/><path d="M6.5 2.5v3"/><path d="M13.5 2.5v3"/>'
    '<path d="M10 11v4"/><path d="M8 13h4"/></svg>'
)

CEINTURE = (
    '<svg class="belt" viewBox="0 0 36 14" width="26" height="10" '
    'aria-hidden="true">'
    '<rect x="0" y="4" width="36" height="6" rx="3" fill="#f2c14e"/>'
    '<circle cx="18" cy="7" r="6.5" fill="#f2c14e" stroke="#0a0a0c" '
    'stroke-width="1.5"/>'
    '<circle cx="18" cy="7" r="3" fill="#fff3cf"/></svg>'
)


def charger_json(nom):
    if not os.path.exists(nom):
        return None
    with open(nom, encoding="utf-8") as f:
        contenu = f.read()
    try:
        return json.loads(contenu)
    except json.JSONDecodeError as erreur:
        print(f"\n!! {nom} contient une erreur de syntaxe :")
        print(f"   ligne {erreur.lineno}, colonne {erreur.colno} -> {erreur.msg}")
        lignes = contenu.splitlines()
        if 0 < erreur.lineno <= len(lignes):
            print(f"   {lignes[erreur.lineno - 1]}")
        print("   Rappel : chaque valeur doit etre entre guillemets droits,")
        print('   par exemple "chaine": "RMC Sport"\n')
        return "ERREUR"


# ---------------------------------------------------------------
# Noms raccourcis a l'affichage. La recherche sur Sherdog continue
# d'utiliser le nom complet, seul l'affichage change.
#     "Nom dans ma liste": "Nom affiche sur le site",
# ---------------------------------------------------------------
NOMS_AFFICHES = {
    "Baysangur Chamsoudinov": "Baki",
    "Paul Denis Navero": "Paul Dena",
}


def nom_affiche(nom):
    return NOMS_AFFICHES.get(nom, nom)


def normaliser(texte):
    """Minuscules, sans accents ni tirets. Sert a comparer les noms."""
    decompose = unicodedata.normalize("NFD", texte)
    sans_accent = "".join(c for c in decompose if unicodedata.category(c) != "Mn")
    for signe in "-'\u2019.":
        sans_accent = sans_accent.replace(signe, " ")
    return " ".join(sans_accent.lower().split())


def decalage_paris(jour):
    """Decalage horaire de Paris ce jour-la, en heures (1 en hiver, 2 en ete).

    L'heure d'ete court du dernier dimanche de mars au dernier dimanche
    d'octobre. On le calcule sans dependance exterieure.
    """
    def dernier_dimanche(annee, mois):
        j = date(annee, mois, 31)
        return j - timedelta(days=(j.weekday() + 1) % 7)

    debut = dernier_dimanche(jour.year, 3)
    fin = dernier_dimanche(jour.year, 10)
    return 2 if debut <= jour < fin else 1


def _ics_echapper(texte):
    return (texte.replace("\\", "\\\\").replace(";", "\\;")
                 .replace(",", "\\,").replace("\n", "\\n"))


def _ics_plier(ligne):
    """Le format calendrier limite les lignes a 75 octets."""
    octets = ligne.encode("utf-8")
    if len(octets) <= 75:
        return ligne
    morceaux, courant = [], b""
    for o in octets:
        octet = bytes([o])
        if len(courant) + 1 > 74:
            morceaux.append(courant)
            courant = b" "
        courant += octet
    morceaux.append(courant)
    return "\r\n".join(m.decode("utf-8", "ignore") for m in morceaux)


def fichier_agenda(ev, infos, fiches):
    """Ecrit un fichier calendrier pour un evenement, renvoie son chemin."""
    try:
        jour = datetime.strptime(ev["date"], "%Y-%m-%d").date()
    except ValueError:
        return ""

    lien = ev["combats"][0].get("lien_evenement", "")
    titre = nom_evenement(ev["evenement"], lien)

    diff = infos.get(ev["evenement"], {})
    heure = (diff.get("heure") or "").strip()

    lignes = ["BEGIN:VCALENDAR", "VERSION:2.0",
              "PRODID:-//MMA Radar//FR", "CALSCALE:GREGORIAN",
              "BEGIN:VEVENT"]

    cle = f"{ev['date']}-{normaliser(titre).replace(' ', '-')}"
    lignes.append(f"UID:{cle}@mmaradar.fr")
    lignes.append("DTSTAMP:" + datetime.now(timezone.utc)
                  .strftime("%Y%m%dT%H%M%SZ"))

    if re.fullmatch(r"\d{1,2}[:hH]\d{2}", heure):
        h, m = re.split(r"[:hH]", heure)
        depart = datetime(jour.year, jour.month, jour.day, int(h), int(m))
        depart -= timedelta(hours=decalage_paris(jour))   # vers l'heure UTC
        fin = depart + timedelta(hours=3)
        lignes.append("DTSTART:" + depart.strftime("%Y%m%dT%H%M%SZ"))
        lignes.append("DTEND:" + fin.strftime("%Y%m%dT%H%M%SZ"))
        rappel = "-PT1H"
        texte_rappel = "Le combat commence dans une heure"
    else:
        lignes.append("DTSTART;VALUE=DATE:" + jour.strftime("%Y%m%d"))
        lignes.append("DTEND;VALUE=DATE:"
                      + (jour + timedelta(days=1)).strftime("%Y%m%d"))
        rappel = "PT9H"
        texte_rappel = "C'est aujourd'hui"

    lignes.append("SUMMARY:" + _ics_echapper(titre))
    if ev.get("lieu"):
        lignes.append("LOCATION:" + _ics_echapper(ev["lieu"]))

    details = []
    for c in ev["combats"]:
        if c.get("annule"):
            continue
        adv = c.get("adversaire_suivi") or c.get("adversaire", "")
        details.append(f"{nom_affiche(c['combattant'])} vs {nom_affiche(adv)}")
    if diff.get("chaine"):
        details.append("Diffusion : " + diff["chaine"])
    if lien:
        details.append(lien)
    if details:
        lignes.append("DESCRIPTION:" + _ics_echapper("\n".join(details)))

    lignes += ["BEGIN:VALARM", "ACTION:DISPLAY",
               "DESCRIPTION:" + _ics_echapper(texte_rappel),
               "TRIGGER:" + rappel, "END:VALARM",
               "END:VEVENT", "END:VCALENDAR"]

    os.makedirs("agenda", exist_ok=True)
    nom_fichier = re.sub(r"[^a-z0-9]+", "-", cle.lower()).strip("-") + ".ics"
    chemin = os.path.join("agenda", nom_fichier)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(_ics_plier(l) for l in lignes) + "\r\n")
    return chemin.replace("\\", "/")


def identifiant_combat(c):
    """Cle stable d'un combat, qui survit a la regeneration du site.

    On s'appuie sur les adresses Sherdog des deux combattants : elles ne
    changent jamais, contrairement aux noms ou aux dates.
    """
    def bout(url):
        return url.rstrip("/").rsplit("/", 1)[-1] if url else ""

    a = bout(c.get("url_suivi", "")) or normaliser(c.get("combattant", ""))
    b = bout(c.get("url_adversaire", "")) or normaliser(c.get("adversaire", ""))
    return "|".join(sorted([a, b]))


def nettoyer_record(record):
    """'23-2-0 (WIN-LOSS-DRAW)' -> '23-2-0'"""
    return record.split("(")[0].strip()


def echapper(texte):
    return (texte.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;"))


# Sherdog utilise quelques codes qui ne sont pas des codes pays officiels,
# notamment pour les nations britanniques. Le service de drapeaux les
# connait sous une autre forme.
CODES_DRAPEAU = {
    "en": "gb-eng",   # Angleterre
    "wa": "gb-wls",   # pays de Galles
}


def drapeau_html(iso):
    if not iso:
        return ""
    code = CODES_DRAPEAU.get(iso, iso)
    return (f'<img class="flag" src="https://flagcdn.com/h20/{code}.png" '
            f'alt="" loading="lazy">')


def pays_depuis_lieu(lieu):
    morceaux = [m.strip() for m in lieu.split(",")]
    return morceaux[-1] if morceaux else ""


# Etats, provinces et leurs abreviations. Quand l'avant-dernier morceau du
# lieu est l'un d'eux, la ville est le morceau d'avant.
# "Tampa, Florida, United States" -> Tampa, FL
ETATS_FEDERES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT",
    "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME",
    "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO",
    "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND",
    "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
    "ontario": "ON", "quebec": "QC", "alberta": "AB",
    "british columbia": "BC", "manitoba": "MB", "saskatchewan": "SK",
    "nova scotia": "NS", "new brunswick": "NB",
    "new south wales": "NSW", "victoria": "VIC", "queensland": "QLD",
    "western australia": "WA", "south australia": "SA", "tasmania": "TAS",
}

# Mets ETAT_ABREGE = False si tu preferes "Tampa, Florida" en toutes lettres
ETAT_ABREGE = True


def ville_depuis_lieu(lieu):
    morceaux = [m.strip() for m in lieu.split(",")]
    if len(morceaux) >= 3 and morceaux[-2].lower() in ETATS_FEDERES:
        etat = morceaux[-2]
        if ETAT_ABREGE:
            etat = ETATS_FEDERES[etat.lower()]
        return f"{morceaux[-3]}, {etat}"
    if len(morceaux) >= 2:
        return morceaux[-2]
    return lieu


# Surface visuelle visee pour tous les logos, en pixels carres.
# Un logo tres allonge sera donc moins haut qu'un logo compact,
# pour qu'ils occupent tous la meme place a l'oeil.
SURFACE_LOGO = 900
HAUTEUR_MIN, HAUTEUR_MAX = 14, 28

# Ajustement manuel si un logo parait trop gros ou trop petit malgre tout
# (1.0 = pas de correction). Exemple : "brave": 0.9
CORRECTION_LOGO = {
    "ares": 1.1,   # beaucoup de vide interne : parait petit sinon
}

# Logos qui restent lisibles en couleur sur fond sombre : ils reprennent
# leurs couleurs d'origine quand l'evenement est deplie. Les autres restent
# en blanc, faute de quoi ils disparaitraient (versions entierement noires).
LOGOS_COULEUR = {"ufc", "oktagon", "pfl", "brave", "ksw", "ares", "hexagone"}

_cache_logos = {}


def _dimensions(chemin):
    """Largeur et hauteur d'une image, PNG, WEBP ou SVG, sans bibliotheque."""
    try:
        with open(chemin, "rb") as f:
            debut = f.read(4096)
    except OSError:
        return None

    if debut[:8] == b"\x89PNG\r\n\x1a\n":
        import struct
        largeur, hauteur = struct.unpack(">II", debut[16:24])
        return largeur, hauteur

    if debut[:4] == b"RIFF" and debut[8:12] == b"WEBP":
        forme = debut[12:16]
        try:
            if forme == b"VP8 ":
                largeur = int.from_bytes(debut[26:28], "little") & 0x3FFF
                hauteur = int.from_bytes(debut[28:30], "little") & 0x3FFF
                return largeur, hauteur
            if forme == b"VP8L":
                bits = int.from_bytes(debut[21:25], "little")
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
            if forme == b"VP8X":
                largeur = int.from_bytes(debut[24:27], "little") + 1
                hauteur = int.from_bytes(debut[27:30], "little") + 1
                return largeur, hauteur
        except (IndexError, ValueError):
            return None
        return None

    # SVG : viewBox, sinon attributs width et height
    texte = debut.decode("utf-8", "ignore")
    m = re.search(r'viewBox\s*=\s*"[\d.eE+-]+[ ,]+[\d.eE+-]+[ ,]+'
                  r'([\d.eE+-]+)[ ,]+([\d.eE+-]+)"', texte)
    if m:
        try:
            return float(m.group(1)), float(m.group(2))
        except ValueError:
            return None
    l = re.search(r'\bwidth\s*=\s*"([\d.]+)', texte)
    h = re.search(r'\bheight\s*=\s*"([\d.]+)', texte)
    if l and h:
        return float(l.group(1)), float(h.group(1))
    return None


def hauteur_logo(fichier, chemin):
    """Hauteur d'affichage pour que tous les logos aient la meme presence."""
    if fichier in _cache_logos:
        return _cache_logos[fichier]

    taille = _dimensions(chemin)
    if not taille or taille[1] <= 0:
        hauteur = 22
    else:
        largeur, haut = taille
        ratio = largeur / haut
        # surface = hauteur x (hauteur x ratio)  ->  hauteur = racine(S / ratio)
        hauteur = (SURFACE_LOGO / ratio) ** 0.5
        hauteur *= CORRECTION_LOGO.get(fichier, 1.0)
        hauteur = max(HAUTEUR_MIN, min(HAUTEUR_MAX, hauteur))

    _cache_logos[fichier] = round(hauteur, 1)
    return _cache_logos[fichier]


def orga_de(evenement):
    nom = evenement.lower()
    for mot, fichier, libelle in ORGAS:
        if mot in nom:
            return fichier, libelle
    return "mma", "MMA"


def logo_orga(evenement, classe="ev__logo"):
    fichier, libelle = orga_de(evenement)
    for ext in ("svg", "png", "webp"):
        chemin = f"logos/{fichier}.{ext}"
        if os.path.exists(chemin):
            h = hauteur_logo(fichier, chemin)
            if classe != "ev__logo":
                h = round(h * 0.62, 1)
            couleur = (' data-couleur="1"'
                       if classe == "ev__logo" and fichier in LOGOS_COULEUR
                       else "")
            return (f'<img class="{classe}" src="{chemin}" alt="{libelle}"'
                    f'{couleur} style="height:{h}px">')
    classe_badge = "ev__badge" if classe == "ev__logo" else "rl__sigle"
    return f'<span class="{classe_badge}">{libelle}</span>'


def chip_compte(date_iso):
    """'J-20', 'DEMAIN', 'CE SOIR' pour la pastille des barres."""
    try:
        jour = datetime.strptime(date_iso, "%Y-%m-%d").date()
    except ValueError:
        return ""
    ecart = (jour - date.today()).days
    if ecart < 0:
        return ""
    if ecart == 0:
        return "CE SOIR"
    if ecart == 1:
        return "DEMAIN"
    return f"J-{ecart}"


# Noms d'evenement trop longs pour la barre : le logo dit deja l'organisation
RACCOURCIS = {
    "professional fighters league": "PFL",
    "pfl challenger series": "PFL CHALLENGER SERIES",
    "dana white's contender series": "Contender Series",
    "brave combat federation": "BRAVE CF",
    "one fighting championship": "ONE",
    "one championship": "ONE",
    "most valuable promotions": "MVP",
    "absolute championship akhmat": "ACA",
    "extreme fighting championship worldwide": "EFC",
    "rizin fighting federation": "RIZIN",
}


def nom_depuis_lien(lien):
    """Deduit le nom de l'evenement de son adresse Sherdog.

    .../events/PFL-Brussels-Habirora-vs-Henderson-113189
        -> PFL Brussels : Habirora vs Henderson
    """
    if not lien or "/events/" not in lien:
        return ""

    slug = lien.rstrip("/").rsplit("/", 1)[-1]
    morceaux = slug.split("-")
    if morceaux and morceaux[-1].isdigit():
        morceaux = morceaux[:-1]
    if not morceaux:
        return ""

    # On ne garde que l'entete (sigle + numero ou ville), pas l'affiche :
    # "PFL-Brussels-Habirora-vs-Henderson" -> "PFL Brussels"
    if "vs" in morceaux:
        i = morceaux.index("vs")
        entete = morceaux[:max(i - 1, 1)]
        return " ".join(entete)

    return " ".join(morceaux)


def nettoyer_nom(texte):
    """Sigle a la place du nom a rallonge, pas de doublon, pas d'affiche."""
    resultat = " ".join(texte.split())
    # apostrophes courbes ramenees a la forme droite, pour que les
    # raccourcis ci-dessous s'appliquent quelle que soit la graphie
    resultat = resultat.replace("\u2019", "'")

    # 1. nom d'organisation a rallonge -> sigle, ou qu'il apparaisse
    for long, court in RACCOURCIS.items():
        motif = re.escape(long).replace("'", "['\u2019]?")
        resultat = re.sub(r"\b" + motif + r"\b", court,
                          resultat, flags=re.IGNORECASE)

    # 2. groupes de mots repetes cote a cote. Sherdog colle souvent le nom
    #    de l'organisation devant le nom de l'evenement, ce qui donne
    #    "Contender Series Contender Series 2026" ou "PFL PFL Tampa".
    mots = resultat.split()
    for longueur in range(4, 0, -1):
        i = 0
        while i + 2 * longueur <= len(mots):
            gauche = [m.lower().strip(":,") for m in mots[i:i + longueur]]
            droite = [m.lower().strip(":,")
                      for m in mots[i + longueur:i + 2 * longueur]]
            if gauche == droite:
                del mots[i:i + longueur]
            else:
                i += 1
    resultat = " ".join(mots).strip(" :-")

    # 3. on retire l'affiche ("... : Untel vs Untel"), redondante ici
    for sep in (" - ", ": ", " : "):
        if sep in resultat:
            gauche, droite = resultat.rsplit(sep, 1)
            if " vs" in droite.lower():
                resultat = gauche.strip(" :-")
                break

    return resultat


def nom_evenement_court(nom):
    """Version raccourcie pour les petits ecrans : on coupe a l'annee.

    "PFL MENA 11 2026 Semifinals" -> "PFL MENA 11"
    """
    mots = nom.split()
    for i, mot in enumerate(mots):
        if i > 0 and re.fullmatch(r"(19|20)\d{2}", mot.strip(":,-")):
            court = " ".join(mots[:i]).strip(" :-")
            if court:
                return court
            break
    return nom


def nom_evenement(evenement, lien=""):
    """Nom court et lisible, quel que soit le format renvoye par Sherdog."""
    resultat = nettoyer_nom(evenement)

    # S'il ne reste que le sigle, le nom complet est dans l'adresse de la page,
    # qu'il faut nettoyer de la meme facon.
    sigles = {c.lower() for c in RACCOURCIS.values()}
    if resultat.lower() in sigles:
        depuis_lien = nettoyer_nom(nom_depuis_lien(lien))
        if depuis_lien and depuis_lien.lower() not in sigles:
            return depuis_lien

    return resultat


def compte_a_rebours(date_iso):
    try:
        jour = datetime.strptime(date_iso, "%Y-%m-%d").date()
    except ValueError:
        return ""
    ecart = (jour - date.today()).days
    if ecart < 0:
        return "termine"
    if ecart == 0:
        return "ce soir"
    if ecart == 1:
        return "demain"
    return f"dans {ecart} jours"


def meme_duel(a, b):
    """Deux fiches decrivent-elles le meme combat entre deux suivis ?"""
    if a.get("date") != b.get("date") or a.get("evenement") != b.get("evenement"):
        return False

    # Methode fiable : les adresses des fiches Sherdog se croisent
    if a.get("url_suivi") and a.get("url_adversaire") \
            and b.get("url_suivi") and b.get("url_adversaire"):
        return ({a["url_suivi"], a["url_adversaire"]}
                == {b["url_suivi"], b["url_adversaire"]})

    # Repli : les noms de famille se croisent (l'orthographe du prenom
    # peut differer entre notre liste et Sherdog)
    def famille(nom):
        mots = normaliser(nom).split()
        return mots[-1] if mots else ""

    return (famille(a.get("adversaire", "")) == famille(b.get("combattant", ""))
            and famille(b.get("adversaire", "")) == famille(a.get("combattant", ""))
            and famille(a.get("combattant", "")) != "")


def fusionner_duels(combats):
    """Un duel entre deux suivis ne doit apparaitre qu'une fois."""
    gardes = []
    absorbes = set()

    for i, a in enumerate(combats):
        if i in absorbes:
            continue
        for j in range(i + 1, len(combats)):
            if j in absorbes:
                continue
            if meme_duel(a, combats[j]):
                absorbes.add(j)
                a = dict(a)
                a["adversaire_suivi"] = combats[j]["combattant"]
                a["drapeau_adversaire"] = (combats[j].get("drapeau")
                                           or a.get("drapeau_adversaire", ""))
                a["ordre"] = min(a.get("ordre", 500),
                                 combats[j].get("ordre", 500))
                break
        gardes.append(a)

    return gardes


def grouper(combats):
    evenements = {}
    for c in combats:
        cle = (c.get("date", ""), c.get("evenement", ""), c.get("lieu", ""))
        evenements.setdefault(cle, []).append(c)

    # dans un evenement, la tete d'affiche d'abord, puis la carte
    # de haut en bas ; a defaut on garde l'ordre de collecte
    for liste in evenements.values():
        liste.sort(key=lambda c: (c.get("ordre", 500), c.get("combattant", "")))

    mois = {}
    for (d, evenement, lieu), liste in sorted(evenements.items()):
        cle_mois = d[:7] if len(d) >= 7 else "9999-99"
        mois.setdefault(cle_mois, []).append({
            "date": d, "evenement": evenement, "lieu": lieu, "combats": liste,
        })
    return sorted(mois.items())


def libelle_mois(cle):
    if cle == "9999-99":
        return "DATE À CONFIRMER", ""
    annee, num = cle.split("-")
    return MOIS_LONG[int(num) - 1], annee


def assurer_infos(noms_evenements):
    """Charge infos.json et ajoute les evenements manquants a remplir."""
    infos = charger_json("infos.json")

    if infos == "ERREUR":
        # On ne reecrit surtout pas le fichier : tes saisies seraient perdues.
        print("infos.json ignore cette fois. Corrige-le puis relance.")
        return {}

    infos = infos or {}
    infos.setdefault(
        "_aide",
        "Remplis heure (ex: 21:00) et chaine (ex: RMC Sport) pour chaque "
        "evenement, puis relance generer_site.py. Laisse vide si inconnu.",
    )
    for nom in noms_evenements:
        infos.setdefault(nom, {"heure": "", "chaine": ""})

    with open("infos.json", "w", encoding="utf-8") as f:
        json.dump(infos, f, ensure_ascii=False, indent=2, sort_keys=True)
    return infos


CSS = """
  :root {
    color-scheme: dark;
    --noir: #0a0a0c;
    --bar: #1b1b21;
    --bar-clair: #232329;
    --bord: #34343d;
    --or: #f2c14e;
    --blanc: #f5f5f7;
    --gris: #9a9aa4;
    --sombre: #14140f;
  }

  * { box-sizing: border-box; }

  /* La couleur doit habiller aussi la zone reservee par le telephone
     (barre de navigation gestuelle en bas), sinon elle reste blanche. */
  html {
    background-color: var(--noir);
  }

  body {
    margin: 0;
    padding: 0 1.2rem 2.6rem;
    padding-left: calc(1.2rem + env(safe-area-inset-left));
    padding-right: calc(1.2rem + env(safe-area-inset-right));
    padding-bottom: calc(2.6rem + env(safe-area-inset-bottom));
    background-color: var(--noir);
    background-image: repeating-linear-gradient(
      135deg, rgba(255,255,255,0.016) 0 2px, transparent 2px 16px);
    color: var(--blanc);
    font-family: Inter, system-ui, sans-serif;
  }

  .wrap { max-width: 1080px; margin: 0 auto; }

  header.top { padding: 2.6rem 0 0.8rem; text-align: center; }

  h1 {
    font-family: Oswald, sans-serif;
    font-weight: 700;
    font-size: clamp(1.8rem, 4.5vw, 2.8rem);
    text-transform: uppercase;
    letter-spacing: 0.01em;
    margin: 0;
  }

  h1 em {
    color: var(--or);
    font-style: normal;
    /* insecable : la coupure tombe apres "combats", pas apres "des" */
    white-space: nowrap;
  }

  .sub { color: var(--gris); font-size: 0.85rem; margin: 0.7rem 0 0; }

  /* ---- bandeau de mois ---- */
  .mois {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    margin: 1.5rem 0 0.6rem;
  }

  .mois:first-of-type { margin-top: 0.6rem; }

  .mois__titre {
    font-family: Oswald, sans-serif;
    font-weight: 700;
    font-size: 0.92rem;
    letter-spacing: 0.12em;
    color: var(--blanc);
    white-space: nowrap;
  }

  .mois__titre .annee { color: var(--or); margin-left: 0.35rem; }

  .mois__filet {
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, var(--or), rgba(242, 193, 78, 0.06));
  }

  /* ---- ligne evenement ---- */
  details.ev { margin: 0 0 0.85rem; }

  summary.ev__bar {
    display: grid;
    grid-template-columns: 78px 110px minmax(0, 250px) minmax(0, 180px) minmax(0, 1fr) 58px 16px;
    align-items: center;
    gap: 1.1rem;
    background: linear-gradient(180deg, #17171c, #121216);
    border: 1px solid #2a2a33;
    border-radius: 12px;
    padding: 0.55rem 1.3rem;
    transform: skew(-8deg);
    cursor: pointer;
    list-style: none;
    transition: border-color 0.15s, background 0.15s;
    /* garde le bloc incline sur une couche stable : sans cela le texte
       penche est recalcule a chaque survol et semble trembler */
    will-change: transform;
    backface-visibility: hidden;
  }

  /* barre ouverte : plus claire, reliee a son panneau */
  details[open] > summary.ev__bar {
    background: linear-gradient(180deg, #2b2b34, #22222a);
    border-color: rgba(242, 193, 78, 0.55);
  }

  /* barre fermee : logo et date en retrait */
  details:not([open]) > summary.ev__bar .ev__logo { opacity: 0.62; }
  details:not([open]) > summary.ev__bar .ev__date { background: #3a3a42; }

  summary.ev__bar::-webkit-details-marker { display: none; }

  summary.ev__bar:hover { border-color: var(--or); }

  summary.ev__bar:focus-visible {
    outline: 2px solid var(--or);
    outline-offset: 2px;
  }

  .ck {
    transform: skew(8deg);
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
  }

  .ev__date {
    display: block;
    width: 100%;
    text-align: center;
    font-family: Oswald, sans-serif;
    font-weight: 700;
    font-size: 0.95rem;
    letter-spacing: 0.05em;
    background: #46464e;
    color: var(--blanc);
    border-radius: 7px;
    padding: 0.3rem 0.4rem;
    white-space: nowrap;
  }

  details[open] .ev__date { background: var(--or); color: var(--sombre); }

  summary.ev__bar > .ck:nth-child(2) { justify-content: center; }
  summary.ev__bar > .ck:nth-child(6) { justify-content: flex-end; }

  .ev__logo {
    width: auto;
    max-width: 106px;
    object-fit: contain;
    filter: brightness(0) invert(1);
    opacity: 0.92;
    transition: filter 0.18s, opacity 0.18s;
  }

  /* evenement deplie : les logos qui le supportent reprennent leurs couleurs */
  details[open] > summary.ev__bar .ev__logo[data-couleur="1"] {
    filter: none;
    opacity: 1;
  }

  .ev__badge {
    font-family: Oswald, sans-serif;
    font-size: 0.72rem;
    letter-spacing: 0.07em;
    color: #d6d6de;
    border: 1px solid #4c4c55;
    border-radius: 5px;
    padding: 0.18rem 0.5rem;
    white-space: nowrap;
  }

  .ev__nom {
    font-family: Oswald, sans-serif;
    font-weight: 500;
    font-size: 1.02rem;
    text-transform: uppercase;
    letter-spacing: 0.02em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .nom-court { display: none; }

  .ev__ville {
    font-family: Oswald, sans-serif;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--gris);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .ev__avec {
    justify-content: flex-start;
    text-align: left;
    font-size: 0.8rem;
    min-width: 0;
  }

  .ev__avec-txt {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    /* l'italique deborde de sa largeur theorique : on laisse de la marge */
    padding-right: 0.22em;
  }

  .ev__avec-label { color: var(--or); font-weight: 700; }

  /* surlignage des lettres tapees dans la recherche */
  mark.trouve {
    background: var(--or);
    color: var(--sombre);
    border-radius: 2px;
    padding: 0 0.1em;
  }

  .ev__avec-noms {
    color: var(--blanc);
    font-weight: 600;
    font-style: italic;
    text-transform: uppercase;
    padding-right: 0.12em;
  }

  .ev__chev {
    flex: none;
    color: var(--or);
    font-size: 0.95rem;
    line-height: 1;
    transition: transform 0.15s;
  }


  details[open] .ev__chev { transform: rotate(90deg); }

  /* ---- volet deplie ---- */
  .ev__body {
    margin: 0.45rem 1.6rem 0;
    padding: 0.8rem 1.1rem 0.45rem;
    background: #24242c;
    border: 1px solid #3a3a45;
    border-left: 3px solid var(--or);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
    border-radius: 10px;
  }

  .fight {
    display: grid;
    /* La categorie et la ceinture sont positionnees par-dessus la ligne :
       elles ne participent pas au calcul des largeurs, donc les deux
       colonnes de noms restent strictement egales et le VS est au centre. */
    position: relative;
    display: flex;
    align-items: center;
    background: #131318;
    border: 1px solid #3a3a45;
    border-radius: 10px;
    padding: 0.5rem 168px;
    margin: 0 0 0.55rem;
    transform: skew(-8deg);
    will-change: transform;
    backface-visibility: hidden;
  }

  .fight > .ck:nth-child(1),
  .fight > .ck:nth-child(2) {
    position: absolute;
    top: 50%;
    transform: skew(8deg) translateY(-50%);
  }

  .fight > .ck:nth-child(1) { left: 1.1rem; max-width: 108px; }
  .fight > .ck:nth-child(2) { left: 8.3rem; max-width: 34px; overflow: hidden; }

  .fight > .ck:nth-child(3) { flex: 1 1 0; min-width: 0; }
  .fight > .ck:nth-child(4) { flex: none; }
  .fight > .ck:nth-child(5) { flex: 1 1 0; min-width: 0; }

  .fight > .ck:nth-child(3) { justify-content: flex-end; text-align: right; }

  .fight__col {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    min-width: 0;
    max-width: 100%;
  }

  .fight .ck:nth-child(3) .fight__col { text-align: right; }

  .fight__nom {
    display: block;
    width: 100%;
    font-family: Oswald, sans-serif;
    font-weight: 500;
    font-size: 0.98rem;
    text-transform: uppercase;
    letter-spacing: 0.02em;
    color: var(--blanc);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }

  .fight__nom--suivi { font-weight: 700; }

  a.fight__nom--suivi {
    color: var(--blanc);
    text-decoration: none;
    border-bottom: 1px solid rgba(242, 193, 78, 0.55);
  }

  a.fight__nom--suivi:hover, a.fight__nom--suivi:focus {
    color: var(--or);
    border-bottom-color: var(--or);
  }

  .fight__rec {
    font-size: 0.68rem;
    color: #8a8a94;
    letter-spacing: 0.03em;
  }

  .fight__vs {
    font-family: Oswald, sans-serif;
    font-weight: 700;
    font-size: 0.68rem;
    color: var(--sombre);
    background: var(--or);
    border-radius: 999px;
    padding: 0.22rem 0.5rem;
    letter-spacing: 0.05em;
  }

  .belt { flex: none; }

  .fight__titre {
    font-family: Oswald, sans-serif;
    font-size: 0.6rem;
    letter-spacing: 0.09em;
    color: var(--or);
  }

  .fight__titre-bloc {
    justify-content: flex-start;
    gap: 0.35rem;
    min-width: 0;
    white-space: nowrap;
  }

  /* un peu d'air entre les noms et la pastille VS */
  .fight > .ck:nth-child(3) { padding-right: 0.55rem; }
  .fight > .ck:nth-child(5) { padding-left: 0.55rem; }

  .ev__foot {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    padding: 0.15rem 0.4rem 0.5rem;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6c6c76;
  }

  .ev__foot a { color: var(--gris); text-decoration: none; }
  .ev__foot a:hover, .ev__foot a:focus { color: var(--or); }

  .ev__actions { display: flex; gap: 1.1rem; align-items: center; }

  .ev__foot a.ev__ics {
    display: flex;
    align-items: center;
    color: var(--or);
    opacity: 0.72;
    transition: opacity 0.15s;
  }

  .ev__foot a.ev__ics:hover,
  .ev__foot a.ev__ics:focus { color: var(--or); opacity: 1; }

  .ev__diffusion { color: var(--gris); }

  .flag { height: 14px; border-radius: 2px; flex: none; }

  .empty { color: var(--gris); text-align: center; margin: 3rem 0; }

  /* ---- invitation a installer l'application ---- */
  .install {
    position: fixed;
    left: 50%;
    bottom: 1rem;
    bottom: calc(1rem + env(safe-area-inset-bottom));
    transform: translateX(-50%);
    z-index: 50;
    display: flex;
    align-items: center;
    gap: 0.9rem;
    max-width: calc(100% - 1.6rem);
    padding: 0.6rem 0.7rem 0.6rem 1.1rem;
    background: var(--bar-clair);
    border: 1px solid var(--or);
    border-radius: 999px;
    box-shadow: 0 8px 26px rgba(0, 0, 0, 0.55);
    font-size: 0.82rem;
  }

  .install[hidden] { display: none; }

  .install__txt { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .install__txt b { color: var(--or); }

  .install__oui {
    flex: none;
    font-family: Oswald, sans-serif;
    font-size: 0.75rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--sombre);
    background: var(--or);
    border: none;
    border-radius: 999px;
    padding: 0.4rem 0.9rem;
    cursor: pointer;
  }

  .install__non {
    flex: none;
    background: none;
    border: none;
    color: var(--gris);
    font-size: 1.2rem;
    line-height: 1;
    cursor: pointer;
    padding: 0 0.2rem;
  }

  .install__non:hover { color: var(--blanc); }

  @media (max-width: 560px) {
    .install { font-size: 0.74rem; gap: 0.6rem; padding-left: 0.9rem; }
    .install__oui { font-size: 0.68rem; padding: 0.35rem 0.7rem; }
  }

  footer p { margin: 0.35rem 0; }

  footer a {
    color: var(--gris);
    text-decoration: none;
    border-bottom: 1px solid rgba(242, 193, 78, 0.4);
  }

  footer a:hover, footer a:focus {
    color: var(--or);
    border-bottom-color: var(--or);
  }

  footer {
    margin-top: 1.6rem;
    padding-top: 1.4rem;
    border-top: 1px solid #24242c;
    color: #62626c;
    font-size: 0.75rem;
    text-align: center;
  }

  /* ---- petits ecrans ---- */
  @media (max-width: 860px) {
    summary.ev__bar, .fight { transform: none; }
    .ck { transform: none; }

    summary.ev__bar {
      grid-template-columns: auto auto 1fr auto;
      gap: 0.6rem 0.9rem;
      padding: 0.6rem 0.9rem;
    }

    .ev__nom { white-space: normal; }
    .ev__ville { grid-column: 1 / -2; }
    .ev__avec { grid-column: 1 / -1; justify-content: flex-start; text-align: left; }
    .ev__avec-txt { white-space: normal; }

    .ev__body { margin: 0.4rem 0 0; padding: 0.6rem 0.6rem 0.3rem; }

    .fight { grid-template-columns: 1fr; gap: 0.35rem; padding: 0.6rem 0.9rem; }
    .fight .ck:nth-child(2) { justify-content: flex-start; text-align: left; }
    .fight .ck:nth-child(2) .fight__col { text-align: left; }
    .fight__vs { justify-self: start; }
    .fight__cat { flex-direction: row; }
    .rl { grid-template-columns: 46px 18px 1fr; }
    .rl__meth, .rl__ev { display: none; }
    .outils { margin-top: 1.2rem; }
  }

  /* ---- pastille compte a rebours ---- */
  .jchip {
    font-family: Oswald, sans-serif;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: var(--gris);
    border: 1px solid #3a3a45;
    border-radius: 999px;
    padding: 0.16rem 0.55rem;
    white-space: nowrap;
  }

  .jchip--hot {
    color: var(--sombre);
    background: var(--or);
    border-color: var(--or);
  }

  /* ---- categorie de poids ---- */
  .fight__cat {
    justify-content: flex-start;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    display: block;
    font-family: Oswald, sans-serif;
    font-size: 0.66rem;
    letter-spacing: 0.08em;
    color: #8a8a94;
    text-transform: uppercase;
  }

  /* ---- annule / reporte ---- */
  .fight--annule { opacity: 0.6; }
  .fight--annule .fight__nom { text-decoration: line-through; }
  .fight__vs--annule { background: #e5484d; color: #fff; }

  .chip--reporte {
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.07em;
    color: #12120f;
    background: #e8933a;
    border-radius: 4px;
    padding: 0.1rem 0.35rem;
  }

  /* ---- barre d'outils ---- */
  .outils {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.7rem;
    margin: 1.6rem 0 0.4rem;
  }

  .outils__recherche {
    flex: 1 1 240px;
    background: #15151a;
    border: 1px solid var(--bord);
    border-radius: 999px;
    color: var(--blanc);
    font-family: Inter, sans-serif;
    font-size: 0.85rem;
    padding: 0.55rem 1.1rem;
    outline: none;
  }

  .outils__recherche:focus { border-color: var(--or); }
  .outils__recherche::placeholder { color: #6a6a74; }

  /* ---- derniers resultats ---- */
  details.recap { max-width: 800px; margin: 0.9rem auto 0; }

  summary.recap__bar {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.55rem;
    list-style: none;
    cursor: pointer;
    font-family: Oswald, sans-serif;
    font-size: 0.82rem;
    letter-spacing: 0.1em;
    color: var(--gris);
    border: 1px solid var(--bord);
    border-radius: 999px;
    padding: 0.45rem 1.2rem;
  }

  summary.recap__bar::-webkit-details-marker { display: none; }
  summary.recap__bar:hover { color: var(--blanc); border-color: var(--or); }

  .recap__chev { color: var(--or); font-size: 0.7rem; transition: transform 0.15s; }
  details[open] > .recap__bar .recap__chev { transform: rotate(90deg); }

  .recap__body {
    margin-top: 0.5rem;
    border: 1px solid #26262e;
    border-radius: 10px;
    padding: 0.3rem 0.9rem;
    background: rgba(21, 21, 26, 0.6);
  }

  .rl {
    display: grid;
    grid-template-columns: 52px 20px minmax(0, 1.25fr) minmax(0, 1fr) minmax(0, 1fr);
    align-items: center;
    gap: 0.6rem;
    padding: 0.42rem 0.2rem;
    font-size: 0.78rem;
    text-align: left;
  }

  .rl + .rl { border-top: 1px solid #222229; }

  .rl__date { color: #6a6a74; font-family: Oswald, sans-serif; font-size: 0.7rem; }

  .rl__badge {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 4px;
    font-family: Oswald, sans-serif;
    font-size: 0.66rem;
    font-weight: 700;
    color: #0d0d10;
  }

  .rl__badge--v { background: #46c07a; }
  .rl__badge--d { background: #e5484d; color: #fff; }
  .rl__badge--n { background: #6a6a74; color: #fff; }

  .rl__nom {
    font-family: Oswald, sans-serif;
    text-transform: uppercase;
    color: var(--blanc);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .rl__nom em {
    color: var(--gris);
    font-style: normal;
    font-family: Inter, sans-serif;
    font-size: 0.74rem;
    text-transform: none;
  }

  .rl__meth {
    color: #8a8a94;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .rl__ev {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    min-width: 0;
  }

  .rl__logo {
    width: auto;
    max-width: 66px;
    object-fit: contain;
    filter: brightness(0) invert(1);
    opacity: 0.55;
  }

  .rl__sigle {
    font-family: Oswald, sans-serif;
    font-size: 0.6rem;
    letter-spacing: 0.06em;
    color: #6a6a74;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  a.rl__lien {
    color: var(--blanc);
    text-decoration: none;
    border-bottom: 1px solid rgba(242, 193, 78, 0.55);
  }

  a.rl__lien:hover, a.rl__lien:focus {
    color: var(--or);
    border-bottom-color: var(--or);
  }

  /* ================= AFFINAGE MOBILE ================= */
  @media (max-width: 860px) {
    body {
      padding: 0 0.7rem 1.6rem;
      padding-left: calc(0.7rem + env(safe-area-inset-left));
      padding-right: calc(0.7rem + env(safe-area-inset-right));
      padding-bottom: calc(1.6rem + env(safe-area-inset-bottom));
    }

    header.top { padding: 1.6rem 0 0.5rem; }
    h1 { font-size: clamp(1.4rem, 6.5vw, 2rem); }
    .sub { font-size: 0.76rem; margin-top: 0.5rem; }

    .outils { margin: 1rem 0 0.3rem; }
    .outils__recherche { padding: 0.5rem 0.9rem; font-size: 0.82rem; }

    .mois { margin: 1.1rem 0 0.45rem; gap: 0.6rem; }
    footer { margin-top: 1rem; }
    .mois__titre { font-size: 0.78rem; letter-spacing: 0.1em; }

    /* --- barre evenement : 2 rangees --- */
    /* le logo disparait : le nom de l'evenement dit deja l'organisation */
    details.ev { margin-bottom: 0.5rem; }

    summary.ev__bar {
      grid-template-columns: 62px minmax(0, 1fr) auto auto 14px;
      gap: 0.3rem 0.55rem;
      padding: 0.5rem 0.7rem;
      border-radius: 9px;
    }

    summary.ev__bar > .ck:nth-child(1) { grid-area: 1 / 1 / 2 / 2; }
    summary.ev__bar > .ck:nth-child(3) { grid-area: 1 / 2 / 2 / 3; }
    summary.ev__bar > .ck:nth-child(2) { grid-area: 1 / 3 / 2 / 4;
                                         display: flex;
                                         justify-content: flex-start; }
    summary.ev__bar > .ck:nth-child(6) { grid-area: 1 / 4 / 2 / 5;
                                         display: flex; }
    summary.ev__bar > .ck:nth-child(7) { grid-area: 1 / 5 / 2 / 6; }
    summary.ev__bar > .ck:nth-child(4) { grid-area: 2 / 1 / 3 / 2; }
    summary.ev__bar > .ck:nth-child(5) { grid-area: 2 / 2 / 3 / 6; }

    /* max-height plafonne la hauteur fixee sur chaque logo */
    .ev__logo { max-height: 15px; max-width: 50px; }
    .ev__badge { font-size: 0.55rem; padding: 0.1rem 0.3rem; }

    .nom-long { display: none; }
    .nom-court { display: inline; }

    .jchip { display: inline-block; font-size: 0.6rem; padding: 0.12rem 0.4rem; }

    .ev__date { font-size: 0.78rem; padding: 0.24rem 0.3rem; border-radius: 6px; }

    .ev__nom {
      font-size: 0.92rem;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .ev__ville { font-size: 0.68rem; }
    .ev__chev { font-size: 0.8rem; }

    /* AVEC : une seule ligne, pointilles si trop long */
    .ev__avec { font-size: 0.7rem; }
    .ev__avec-txt {
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    /* --- volet deplie : les deux noms cote a cote --- */
    .ev__body { padding: 0.5rem 0.55rem 0.3rem; border-radius: 8px; }

    .duel { margin-bottom: 0.45rem; }

    .fight {
      padding: 1.85rem 0.6rem 0.55rem;
    }

    .vote { margin: 0 0.6rem 0.5rem; height: 18px; }
    .vote__cote { font-size: 0.6rem; }

    /* categorie a gauche, ceinture centree, toutes deux au-dessus des noms */
    .fight > .ck:nth-child(1) {
      top: 0.5rem;
      left: 0.6rem;
      transform: none;
      max-width: 45%;
    }

    .fight > .ck:nth-child(2) {
      top: 0.5rem;
      left: 50%;
      transform: translateX(-50%);
    }

    .fight > .ck:nth-child(3) { padding-right: 0.35rem; }
    .fight > .ck:nth-child(5) { padding-left: 0.35rem; }

    .fight__cat { font-size: 0.58rem; gap: 0.3rem; }
    .fight__titre { font-size: 0.53rem; }

    /* texte reduit pour que les deux noms tiennent chacun sur une ligne */
    .fight__nom {
      font-size: 0.76rem;
      letter-spacing: 0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 100%;
    }

    .fight__col { max-width: 100%; }
    .fight__rec { font-size: 0.6rem; }
    .fight__vs { font-size: 0.55rem; padding: 0.14rem 0.32rem; }
    .flag { height: 11px; }
    .belt { width: 20px; height: 8px; }

    .ev__foot {
      padding: 0.1rem 0.2rem 0.35rem;
      font-size: 0.62rem;
      gap: 0.6rem;
      flex-wrap: wrap;
    }

    .ev__actions { gap: 0.8rem; }

    /* --- derniers resultats --- */
    .recap { margin-top: 0.6rem; }
    summary.recap__bar { font-size: 0.74rem; padding: 0.4rem 1rem; }
    .recap__body { padding: 0.2rem 0.6rem; }

    .rl {
      grid-template-columns: 44px 18px minmax(0, 1fr) 46px;
      gap: 0.15rem 0.45rem;
      padding: 0.45rem 0.1rem;
      font-size: 0.74rem;
    }

    .rl > .rl__date { grid-area: 1 / 1 / 2 / 2; }
    .rl > .rl__badge { grid-area: 1 / 2 / 2 / 3; }
    .rl > .rl__nom { grid-area: 1 / 3 / 2 / 4; }
    .rl > .rl__meth { grid-area: 2 / 3 / 3 / 4; display: block; }
    .rl > .rl__ev { grid-area: 1 / 4 / 3 / 5; }

    .rl__nom { white-space: normal; font-size: 0.8rem; line-height: 1.2; }
    .rl__nom em { font-size: 0.7rem; }
    .rl__meth { font-size: 0.66rem; white-space: normal; }
    .rl__logo { max-width: 44px; }
  }

  /* tres petits ecrans : on serre encore un peu */
  @media (max-width: 400px) {
    .fight__nom { font-size: 0.7rem; }
    .fight__rec { font-size: 0.56rem; }
    .ev__nom { font-size: 0.86rem; }
  }
"""

CSS_FOND = """
  body::before {
    content: "";
    position: fixed;
    inset: 0;
    z-index: -1;
    background: url('fond.jpg') center / cover no-repeat;
    opacity: 0.14;
  }
"""


def bloc_evenement(ev, fiches, infos, ouvert, prochaine_date, agenda=""):
    try:
        jour = datetime.strptime(ev["date"], "%Y-%m-%d").date()
        date_txt = f"{jour.day:02d} {MOIS_COURT[jour.month - 1]}"
    except ValueError:
        date_txt = "--"

    ville = echapper(ville_depuis_lieu(ev["lieu"]))
    pays = pays_depuis_lieu(ev["lieu"])
    flag_event = drapeau_html(PAYS_ISO.get(pays.lower(), ""))

    noms = []
    for c in ev["combats"]:
        if c.get("annule"):
            continue
        noms.append(echapper(nom_affiche(c["combattant"])))
        if c.get("adversaire_suivi"):
            noms.append(echapper(nom_affiche(c["adversaire_suivi"])))
    noms_avec = ", ".join(noms)

    lien = ev["combats"][0].get("lien_evenement", "")

    nom_ev = echapper(nom_evenement(ev["evenement"], lien))
    nom_ev_court = echapper(nom_evenement_court(nom_evenement(ev["evenement"], lien)))
    if nom_ev_court != nom_ev:
        bloc_nom = (f'<span class="nom-long">{nom_ev}</span>'
                    f'<span class="nom-court">{nom_ev_court}</span>')
    else:
        bloc_nom = nom_ev

    orga_cle, _ = orga_de(ev["evenement"])
    tous_noms = []
    for c in ev["combats"]:
        tous_noms.append(normaliser(c["combattant"]))
        tous_noms.append(normaliser(nom_affiche(c["combattant"])))
        autre = c.get("adversaire_suivi") or c.get("adversaire", "")
        tous_noms.append(normaliser(autre))
        tous_noms.append(normaliser(nom_affiche(autre)))
    noms_data = "|".join(n for n in tous_noms if n)

    jtxt = chip_compte(ev["date"])
    classe_chip = "jchip jchip--hot" if ev["date"] == prochaine_date else "jchip"
    chip_html = f'<span class="{classe_chip}">{jtxt}</span>' if jtxt else ""

    lignes = []
    for c in ev["combats"]:
        nom = echapper(nom_affiche(c["combattant"]))
        flag = drapeau_html(c.get("drapeau", ""))
        url = fiches.get(c["combattant"], "")
        if url:
            lien_nom = (f'<a class="fight__nom fight__nom--suivi" href="{url}" '
                        f'target="_blank" rel="noopener" data-complet="{nom}">{nom}</a>')
        else:
            lien_nom = (f'<span class="fight__nom fight__nom--suivi" '
                        f'data-complet="{nom}">{nom}</span>')

        rec_suivi = echapper(nettoyer_record(c.get("record_suivi", "")))
        rec_adv = echapper(nettoyer_record(c.get("record_adversaire", "")))
        rec_suivi_html = f'<span class="fight__rec">{rec_suivi}</span>' if rec_suivi else ""
        rec_adv_html = f'<span class="fight__rec">{rec_adv}</span>' if rec_adv else ""

        annule = bool(c.get("annule"))
        belt = "" if annule else (CEINTURE if c.get("titre") else "")
        titre_txt = ""   # l'icone ceinture parle d'elle-meme

        # Si l'adversaire fait aussi partie de la liste suivie, on affiche
        # son nom tel qu'on l'ecrit, son drapeau, et on le rend cliquable.
        nom_adv = (nom_affiche(c["adversaire_suivi"])
                   if c.get("adversaire_suivi") else c["adversaire"])
        url_adv = fiches.get(c.get("adversaire_suivi", ""), "")
        flag_adv = drapeau_html(c.get("drapeau_adversaire", ""))
        classe_adv = "fight__nom fight__nom--suivi" if url_adv else "fight__nom"
        if url_adv:
            bloc_adv = (f'<a class="{classe_adv}" href="{url_adv}" '
                        f'target="_blank" rel="noopener" '
                        f'data-complet="{echapper(nom_adv)}">'
                        f'{echapper(nom_adv)}</a>')
        else:
            bloc_adv = (f'<span class="{classe_adv}" '
                        f'data-complet="{echapper(nom_adv)}">'
                        f'{echapper(nom_adv)}</span>')

        cat = echapper(c.get("categorie", ""))
        chip_rep = ""
        if c.get("reporte_depuis"):
            chip_rep = (f'<span class="chip--reporte" title="initialement '
                        f'le {echapper(c["reporte_depuis"])}">REPORTÉ</span>')

        classe_fight = "fight fight--annule" if annule else "fight"
        vs = ('<span class="fight__vs fight__vs--annule">ANNULÉ</span>'
              if annule else '<span class="fight__vs">VS</span>')

        barre = ""
        if VOTES_ACTIFS and not annule:
            barre = f"""
          <div class="vote" data-combat="{identifiant_combat(c)}">
            <button class="vote__cote vote__cote--g" data-cote="g" type="button"
                    aria-label="Voter pour {nom}"><span class="vote__pct"></span></button>
            <button class="vote__cote vote__cote--d" data-cote="d" type="button"
                    aria-label="Voter pour {echapper(nom_adv)}"><span class="vote__pct"></span></button>
          </div>"""

        lignes.append(f"""
        <div class="duel">
        <div class="{classe_fight}">
          <span class="ck fight__cat">{cat}{chip_rep}</span>
          <span class="ck fight__titre-bloc">{belt}{titre_txt}</span>
          <span class="ck">{flag}<span class="fight__col">{lien_nom}{rec_suivi_html}</span></span>
          <span class="ck">{vs}</span>
          <span class="ck"><span class="fight__col">{bloc_adv}{rec_adv_html}</span>{flag_adv}</span>
        </div>{barre}
        </div>""")

    lien_html = ""
    if lien:
        lien_html = (f'<a href="{lien}" target="_blank" rel="noopener">'
                     f'Carte complète &rarr;</a>')

    lien_agenda = ""
    if agenda:
        lien_agenda = (f'<a class="ev__ics" href="{agenda}" download '
                       f'title="Ajouter cet évènement à mon agenda" '
                       f'aria-label="Ajouter cet évènement à mon agenda">'
                       f'{ICONE_AGENDA}</a>')

    diff = infos.get(ev["evenement"], {})
    morceaux = []
    heure = diff.get("heure", "").strip()
    chaine = diff.get("chaine", "").strip()
    if heure:
        morceaux.append(echapper(heure.replace(":", "h")))
    if chaine:
        morceaux.append(echapper(chaine))
    gauche = (f'<span class="ev__diffusion">'
              f'{" &middot; ".join(m for m in morceaux if m)}</span>')

    attr_ouvert = " open" if ouvert else ""

    return f"""
    <details class="ev"{attr_ouvert} data-orga="{orga_cle}" data-noms="{noms_data}">
      <summary class="ev__bar">
        <span class="ck"><span class="ev__date">{date_txt}</span></span>
        <span class="ck">{logo_orga(ev["evenement"])}</span>
        <span class="ck"><span class="ev__nom" data-complet="{nom_ev}">{bloc_nom}</span></span>
        <span class="ck" title="{echapper(ev["lieu"])}">{flag_event}<span class="ev__ville">{ville}</span></span>
        <span class="ck ev__avec"><span class="ev__avec-txt" data-complet="{noms_avec}">
          <span class="ev__avec-label">AVEC&nbsp;: </span>
          <span class="ev__avec-noms">{noms_avec}</span>
        </span></span>
        <span class="ck">{chip_html}</span>
        <span class="ck"><span class="ev__chev">&#9656;</span></span>
      </summary>
      <div class="ev__body">{"".join(lignes)}
        <div class="ev__foot">
          {gauche}
          <span class="ev__actions">{lien_agenda}{lien_html}</span>
        </div>
      </div>
    </details>"""


def module_resultats(resultats, fiches):
    """Bandeau replie des resultats des 30 derniers jours."""
    if not resultats:
        return ""
    limite = (date.today() - timedelta(days=30)).isoformat()
    recents = [r for r in resultats if r.get("date", "") >= limite]
    recents.sort(key=lambda r: r.get("date", ""), reverse=True)
    recents = recents[:12]
    if not recents:
        return ""

    lignes = []
    for r in recents:
        res = r.get("resultat", "")
        if res == "win":
            badge = '<span class="rl__badge rl__badge--v">V</span>'
        elif res == "loss":
            badge = '<span class="rl__badge rl__badge--d">D</span>'
        else:
            badge = '<span class="rl__badge rl__badge--n">N</span>'
        try:
            j = datetime.strptime(r.get("date", ""), "%Y-%m-%d").date()
            dtxt = f"{j.day:02d} {MOIS_COURT[j.month - 1]}"
        except ValueError:
            dtxt = ""
        nom = echapper(nom_affiche(r.get("combattant", "")))
        url = fiches.get(r.get("combattant", ""), "")
        nom_html = (f'<a class="rl__lien" href="{url}" target="_blank" '
                    f'rel="noopener">{nom}</a>') if url else nom

        lignes.append(f"""
      <div class="rl">
        <span class="rl__date">{dtxt}</span>
        {badge}
        <span class="rl__nom" data-complet="{nom} vs {echapper(r.get("adversaire", ""))}">{nom_html} <em>vs {echapper(r.get("adversaire", ""))}</em></span>
        <span class="rl__meth" data-complet="{echapper(r.get("methode", ""))}">{echapper(r.get("methode", ""))}</span>
        <span class="rl__ev" title="{echapper(nom_evenement(r.get("evenement", "")))}">{logo_orga(r.get("evenement", ""), "rl__logo")}</span>
      </div>""")

    return f"""
  <details class="recap">
    <summary class="recap__bar">DERNIERS RÉSULTATS
      <span class="recap__chev">&#9656;</span></summary>
    <div class="recap__body">{"".join(lignes)}
    </div>
  </details>"""


def barre_outils():
    """Recherche seule : les filtres par orga alourdissaient pour rien."""
    return """
  <div class="outils">
    <input id="recherche" class="outils__recherche" type="search"
           placeholder="Rechercher un combattant...">
  </div>"""


JS = r"""
<script>
(function () {
  function norm(t) {
    return t.toLowerCase().normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/[-'.]/g, " ").replace(/\s+/g, " ").trim();
  }
  var champ = document.getElementById("recherche");

  // Infobulle seulement sur les textes reellement coupes.
  // On mesure au moment ou la souris arrive dessus : a cet instant les
  // polices sont chargees, le volet est ouvert, la mesure est fiable.
  document.addEventListener("mouseover", function (ev) {
    var el = ev.target.closest ? ev.target.closest("[data-complet]") : null;
    if (!el) return;
    var deborde = el.scrollWidth > el.clientWidth + 1;
    if (!deborde && el.parentElement) {
      deborde = el.scrollWidth > el.parentElement.clientWidth + 1;
    }
    if (deborde) {
      el.setAttribute("title", el.dataset.complet);
    } else {
      el.removeAttribute("title");
    }
  }, true);

  if (!champ) return;

  // Normalise caractere par caractere, en gardant la correspondance avec
  // le texte d'origine : indispensable pour surligner au bon endroit
  // quand la recherche ignore les accents.
  function normAvecIndex(texte) {
    var sortie = "", index = [];
    for (var i = 0; i < texte.length; i++) {
      var c = texte[i].toLowerCase()
                      .normalize("NFD")
                      .replace(/[\u0300-\u036f]/g, "")
                      .replace(/[-'.\u2019]/g, " ");
      for (var j = 0; j < c.length; j++) {
        sortie += c[j];
        index.push(i);
      }
    }
    return { texte: sortie, index: index };
  }

  // ---------- installation sur l'ecran d'accueil ----------
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("sw.js").catch(function () {});
    });
  }

  (function () {
    var bandeau = document.getElementById("install");
    if (!bandeau) return;

    var refuse = false;
    try { refuse = localStorage.getItem("install-refuse") === "1"; } catch (e) {}

    // deja installe : on ne propose rien
    var installe = window.matchMedia("(display-mode: standalone)").matches
      || window.navigator.standalone === true;
    if (installe || refuse) return;

    // L'installation n'a d'interet que sur telephone : sur ordinateur
    // le bandeau encombre pour rien.
    var tactile = window.matchMedia("(pointer: coarse)").matches
      || /android|iphone|ipad|ipod/i.test(navigator.userAgent);
    if (!tactile) return;

    var invite = null;

    window.addEventListener("beforeinstallprompt", function (ev) {
      ev.preventDefault();
      invite = ev;
      bandeau.hidden = false;
    });

    // Sur iPhone, le navigateur ne propose rien : l'installation passe
    // par le bouton de partage. On explique au lieu d'un bouton inutile.
    var iOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
    if (iOS) {
      bandeau.querySelector(".install__txt").innerHTML =
        "<b>MMA Radar</b> : Partager, puis Sur l'écran d'accueil";
      bandeau.querySelector(".install__oui").hidden = true;
      bandeau.hidden = false;
    }

    document.getElementById("install-oui").addEventListener("click", function () {
      if (!invite) return;
      invite.prompt();
      invite = null;
      bandeau.hidden = true;
    });

    document.getElementById("install-non").addEventListener("click", function () {
      bandeau.hidden = true;
      try { localStorage.setItem("install-refuse", "1"); } catch (e) {}
    });

    window.addEventListener("appinstalled", function () {
      bandeau.hidden = true;
    });
  })();

  // ---------- pronostics (mode demonstration) ----------
  // Les votes restent dans le navigateur du visiteur. Les compteurs de
  // depart sont simules a partir de l'identifiant du combat, pour que la
  // barre ait l'air vivante pendant les essais.
  var VOTES_MINI = 10;   // sous ce total, on n'affiche pas de pourcentage

  function graine(texte) {
    var h = 0;
    for (var i = 0; i < texte.length; i++) {
      h = (h * 31 + texte.charCodeAt(i)) % 100000;
    }
    return h;
  }

  function comptes(id) {
    var enregistre = null;
    try { enregistre = localStorage.getItem("pronostic:" + id); } catch (e) {}
    if (enregistre) {
      try { return JSON.parse(enregistre); } catch (e) {}
    }
    var g = graine(id);
    return { g: 6 + (g % 47), d: 6 + ((g >> 3) % 41), moi: null };
  }

  function enregistrer(id, etat) {
    try { localStorage.setItem("pronostic:" + id, JSON.stringify(etat)); }
    catch (e) {}
  }

  function afficher(bloc, etat) {
    var total = etat.g + etat.d;
    var gauche = bloc.querySelector(".vote__cote--g");
    var droite = bloc.querySelector(".vote__cote--d");
    var pg = total ? Math.round((etat.g / total) * 100) : 50;
    var pd = 100 - pg;

    gauche.style.width = pg + "%";
    droite.style.width = pd + "%";

    var assez = total >= VOTES_MINI;
    gauche.querySelector(".vote__pct").textContent = assez ? pg + "%" : "";
    droite.querySelector(".vote__pct").textContent = assez ? pd + "%" : "";

    bloc.classList.toggle("vote--fait", !!etat.moi);
    gauche.classList.toggle("vote__cote--choisi", etat.moi === "g");
    droite.classList.toggle("vote__cote--choisi", etat.moi === "d");

    bloc.title = etat.moi
      ? "Ton pronostic est enregistre"
      : (assez ? total + " pronostics" : "Sois le premier a pronostiquer");
  }

  document.querySelectorAll(".vote").forEach(function (bloc) {
    var id = bloc.dataset.combat;
    afficher(bloc, comptes(id));

    bloc.addEventListener("click", function (ev) {
      var bouton = ev.target.closest(".vote__cote");
      if (!bouton) return;
      var cote = bouton.dataset.cote;
      var etat = comptes(id);
      if (etat.moi === cote) return;          // deja vote de ce cote
      if (etat.moi) { etat[etat.moi] -= 1; }  // changement d'avis
      etat[cote] += 1;
      etat.moi = cote;
      enregistrer(id, etat);
      afficher(bloc, etat);
    });
  });

  var A_SURLIGNER = ".ev__avec-noms, .fight__nom, .rl__nom";

  function surligner(q) {
    document.querySelectorAll(A_SURLIGNER).forEach(function (el) {
      if (el.dataset.brut === undefined) {
        el.dataset.brut = el.innerHTML;
      }
      if (!q) {
        el.innerHTML = el.dataset.brut;
        return;
      }

      // on travaille sur le texte seul, puis on reinjecte le balisage
      var brut = el.dataset.brut;
      var sansBalises = document.createElement("div");
      sansBalises.innerHTML = brut;

      var noeuds = [];
      (function parcourir(n) {
        for (var i = 0; i < n.childNodes.length; i++) {
          var enfant = n.childNodes[i];
          if (enfant.nodeType === 3) { noeuds.push(enfant); }
          else { parcourir(enfant); }
        }
      })(sansBalises);

      noeuds.forEach(function (noeud) {
        var t = noeud.nodeValue;
        var n = normAvecIndex(t);
        var pos = n.texte.indexOf(q);
        if (pos === -1) return;

        var morceaux = document.createDocumentFragment();
        var curseur = 0;
        while (pos !== -1) {
          var debut = n.index[pos];
          var fin = n.index[pos + q.length - 1] + 1;
          morceaux.appendChild(
            document.createTextNode(t.slice(curseur, debut)));
          var m = document.createElement("mark");
          m.className = "trouve";
          m.textContent = t.slice(debut, fin);
          morceaux.appendChild(m);
          curseur = fin;
          pos = n.texte.indexOf(q, pos + q.length);
        }
        morceaux.appendChild(document.createTextNode(t.slice(curseur)));
        noeud.parentNode.replaceChild(morceaux, noeud);
      });

      el.innerHTML = sansBalises.innerHTML;
    });
  }

  // Une recherche est une vue temporaire : en vidant le champ, on rend
  // la page telle qu'elle etait, y compris les volets deja ouverts.
  var etatAvant = null;

  champ.addEventListener("input", function () {
    var q = norm(champ.value || "");
    var volets = document.querySelectorAll("details.ev");

    if (q && etatAvant === null) {
      etatAvant = new Map();
      volets.forEach(function (ev) { etatAvant.set(ev, ev.open); });
    }

    volets.forEach(function (ev) {
      var visible = !q || norm(ev.dataset.noms || "").indexOf(q) !== -1;
      ev.style.display = visible ? "" : "none";
      if (q) ev.open = visible;
    });

    if (!q && etatAvant) {
      volets.forEach(function (ev) { ev.open = etatAvant.get(ev) === true; });
      etatAvant = null;
    }
    document.querySelectorAll("main section").forEach(function (sec) {
      var un = sec.querySelector("details.ev:not([style*='display: none'])");
      sec.style.display = un ? "" : "none";
    });
    surligner(q);
  });
})();
</script>"""


def donnees_structurees(mois_groupes, infos):
    """Decrit les evenements dans le langage que Google comprend.

    Invisible sur la page. C'est ce qui permet aux moteurs de savoir
    qu'il s'agit d'evenements sportifs avec une date et un lieu, et non
    d'un simple texte.
    """
    aujourdhui = date.today().isoformat()
    blocs = [{
        "@type": "WebSite",
        "name": "MMA Radar",
        "url": SITE_URL + "/",
        "description": SITE_DESC,
        "inLanguage": "fr",
    }]

    for _, evs in mois_groupes:
        for ev in evs:
            jour = ev.get("date", "")
            if len(jour) != 10 or jour < aujourdhui:
                continue

            info = infos.get(ev.get("evenement", ""), {})
            if not isinstance(info, dict):
                info = {}
            heure = (info.get("heure") or "").strip()
            debut = f"{jour}T{heure}:00" if re.fullmatch(r"\d\d:\d\d", heure) else jour

            noms = []
            for c in ev.get("combats", []):
                if c.get("annule"):
                    continue
                for n in (c.get("combattant"), c.get("adversaire")):
                    if n and n not in noms:
                        noms.append(n)

            bloc = {
                "@type": "SportsEvent",
                "name": ev.get("evenement", ""),
                "startDate": debut,
                "url": SITE_URL + "/",
                "eventStatus": "https://schema.org/EventScheduled",
                "sport": "Mixed Martial Arts",
                "competitor": [{"@type": "Person", "name": n} for n in noms],
            }

            lieu = (ev.get("lieu") or "").strip()
            if lieu:
                bloc["location"] = {
                    "@type": "Place",
                    "name": lieu.split(",")[0].strip() or lieu,
                    "address": lieu,
                }
            if (info.get("chaine") or "").strip():
                bloc["description"] = "Diffusion : " + info["chaine"].strip()

            blocs.append(bloc)

    donnees = {"@context": "https://schema.org", "@graph": blocs}
    texte = json.dumps(donnees, ensure_ascii=False).replace("</", "<\\/")
    return '\n<script type="application/ld+json">' + texte + "</script>"


def construire_html(mois_groupes, fiches, infos, total, resultats):
    maj = date.today()
    date_maj = f"{maj.day} {MOIS_LONG[maj.month - 1].lower()} {maj.year}"
    pluriel = "s" if total > 1 else ""

    aujourd_hui = date.today().isoformat()
    dates_futures = sorted({ev["date"] for _, evs in mois_groupes
                            for ev in evs if ev["date"] >= aujourd_hui})
    prochaine_date = dates_futures[0] if dates_futures else ""

    sections = []
    for cle, evenements in mois_groupes:
        nom_mois, annee = libelle_mois(cle)
        blocs = []
        for ev in evenements:
            chemin = fichier_agenda(ev, infos, fiches)
            blocs.append(bloc_evenement(ev, fiches, infos, False,
                                        prochaine_date, chemin))
        sections.append(f"""
  <section>
    <div class="mois">
      <span class="mois__titre">{nom_mois}<span class="annee">{annee}</span></span>
      <span class="mois__filet"></span>
    </div>
    {"".join(blocs)}
  </section>""")

    if not sections:
        sections.append("""
  <p class="empty">Aucun combat annoncé pour le moment.<br>
  Relance le script quand de nouvelles cartes sortent.</p>""")

    css_fond = CSS_FOND if os.path.exists("fond.jpg") else ""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{SITE_TITRE}</title>
<meta name="description" content="{SITE_DESC}">
<link rel="canonical" href="{SITE_URL}/">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta property="og:type" content="website">
<meta property="og:site_name" content="MMA Radar">
<meta property="og:locale" content="fr_FR">
<meta property="og:title" content="{SITE_TITRE}">
<meta property="og:description" content="{SITE_DESC}">
<meta property="og:url" content="{SITE_URL}/">
<meta property="og:image" content="{SITE_URL}/partage.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="MMA Radar, le calendrier des combats des francophones">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{SITE_TITRE}">
<meta name="twitter:description" content="{SITE_DESC}">
<meta name="twitter:image" content="{SITE_URL}/partage.jpg">
<link rel="manifest" href="manifest.webmanifest">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="MMA Radar">
<link rel="icon" href="favicon.ico" sizes="any">
<link rel="icon" type="image/svg+xml" href="icones/icone.svg">
<link rel="icon" type="image/png" sizes="32x32" href="icones/icone-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="icones/icone-180.png">
<meta name="theme-color" content="#0f0f13">
<meta name="color-scheme" content="dark">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>{CSS}{css_fond}</style>{donnees_structurees(mois_groupes, infos)}
</head>
<body>
<div class="wrap">

  <header class="top">
    <h1>Prochains combats <em>des francophones</em></h1>
    <p class="sub">{total} combat{pluriel} annoncé{pluriel} &middot; mis à jour le {date_maj}</p>
  </header>
{module_resultats(resultats, fiches)}
{barre_outils()}
  <main>{"".join(sections)}
  </main>

  <div class="install" id="install" hidden>
    <span class="install__txt"><b>MMA Radar</b> sur ton écran d'accueil</span>
    <button class="install__oui" id="install-oui" type="button">Installer</button>
    <button class="install__non" id="install-non" type="button"
            aria-label="Fermer">&times;</button>
  </div>

  <footer>
    <p>Données issues de Sherdog. Les cartes évoluent, vérifie avant de bloquer ta soirée.</p>
    <p><a href="mailto:contact@mmaradar.fr">contact@mmaradar.fr</a></p>
  </footer>

</div>
{JS}
</body>
</html>
"""


# Barre de pronostics. En mode demonstration, les votes restent dans le
# navigateur du visiteur : rien n'est partage. A basculer sur un vrai
# service le jour ou on le mettra en place.
VOTES_ACTIFS = False
VOTES_DEMO = True

VERSION = 64


def ecrire_manifeste():
    """Decrit l'application pour les telephones."""
    manifeste = {
        "name": "MMA Radar",
        "short_name": "MMA Radar",
        "description": "Les prochains combats des combattants francophones.",
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "orientation": "portrait",
        "lang": "fr",
        "background_color": "#0a0a0c",
        "theme_color": "#0f0f13",
        "icons": [
            {"src": "icones/icone-192.png", "sizes": "192x192",
             "type": "image/png", "purpose": "any"},
            {"src": "icones/icone-512.png", "sizes": "512x512",
             "type": "image/png", "purpose": "any"},
            {"src": "icones/icone-512.png", "sizes": "512x512",
             "type": "image/png", "purpose": "maskable"},
        ],
    }
    with open("manifest.webmanifest", "w", encoding="utf-8") as f:
        json.dump(manifeste, f, ensure_ascii=False, indent=2)


def ecrire_service_worker():
    """Cache hors ligne. Le numero de version force le renouvellement.

    Regle d'or : la page et les donnees passent d'abord par le reseau,
    pour ne jamais afficher un calendrier perime. Seules les images et
    les polices sont servies depuis le cache.
    """
    contenu = """// Genere automatiquement par generer_site.py
const CACHE = "mmaradar-vVERSION_ICI";
const SOCLE = ["./", "./index.html", "./fond.jpg",
               "./icones/icone-192.png", "./icones/icone-512.png"];

self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(CACHE)
      .then(function (c) { return c.addAll(SOCLE).catch(function () {}); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (cles) {
      return Promise.all(cles.map(function (k) {
        if (k !== CACHE) { return caches.delete(k); }
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (e) {
  const req = e.request;
  if (req.method !== "GET") { return; }

  const url = new URL(req.url);
  const donnee = req.mode === "navigate"
    || url.pathname.endsWith(".html")
    || url.pathname.endsWith(".json")
    || url.pathname.endsWith(".ics");

  if (donnee) {
    // reseau d'abord : le calendrier doit toujours etre a jour
    e.respondWith(
      fetch(req).then(function (rep) {
        const copie = rep.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copie); });
        return rep;
      }).catch(function () { return caches.match(req); })
    );
    return;
  }

  // images, icones, polices : cache d'abord, mise a jour en arriere-plan
  e.respondWith(
    caches.match(req).then(function (garde) {
      const reseau = fetch(req).then(function (rep) {
        const copie = rep.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copie); });
        return rep;
      }).catch(function () { return garde; });
      return garde || reseau;
    })
  );
});
""".replace("VERSION_ICI", str(VERSION))
    with open("sw.js", "w", encoding="utf-8") as f:
        f.write(contenu)


def ecrire_robots_et_sitemap():
    """Autorise l'indexation et signale la page aux moteurs."""
    with open("robots.txt", "w", encoding="utf-8") as f:
        f.write("User-agent: *\n"
                "Allow: /\n"
                "\n"
                f"Sitemap: {SITE_URL}/sitemap.xml\n")

    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                "  <url>\n"
                f"    <loc>{SITE_URL}/</loc>\n"
                f"    <lastmod>{date.today().isoformat()}</lastmod>\n"
                "    <changefreq>daily</changefreq>\n"
                "    <priority>1.0</priority>\n"
                "  </url>\n"
                "</urlset>\n")


def main():
    print(f"generer_site v{VERSION}")
    ecrire_manifeste()
    ecrire_service_worker()
    ecrire_robots_et_sitemap()
    combats = charger_json("combats.json")
    if combats is None:
        print("combats.json introuvable. Lance d'abord mma_tracker.py")
        return
    if combats == "ERREUR":
        print("combats.json illisible. Relance mma_tracker.py")
        return

    fiches = charger_json("fighters.json")
    fiches = {} if fiches in (None, "ERREUR") else fiches

    # on repart d'un dossier agenda propre : les evenements passes
    # ou renommes ne doivent pas y trainer
    if os.path.isdir("agenda"):
        for f in os.listdir("agenda"):
            if f.endswith(".ics"):
                os.remove(os.path.join("agenda", f))

    resultats_recents = charger_json("resultats.json")
    if resultats_recents in (None, "ERREUR"):
        resultats_recents = []

    annotations = charger_json("annulations.json")
    if annotations in (None, "ERREUR"):
        annotations = []

    for m in annotations:
        if m.get("type") == "annule":
            copie = dict(m)
            copie["annule"] = True
            combats.append(copie)
        elif m.get("type") == "reporte":
            for c in combats:
                if (normaliser(c.get("combattant", ""))
                        == normaliser(m.get("combattant", ""))
                        and c.get("date") == m.get("nouvelle_date")):
                    c["reporte_depuis"] = m.get("ancienne_date", "")

    combats = fusionner_duels(combats)
    mois_groupes = grouper(combats)
    noms_evenements = [ev["evenement"] for _, evs in mois_groupes for ev in evs]
    infos = assurer_infos(noms_evenements)

    total = sum(1 for c in combats if not c.get("annule"))
    html = construire_html(mois_groupes, fiches, infos, total,
                           resultats_recents)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    nb_ev = sum(len(evs) for _, evs in mois_groupes)
    print(f"index.html cree : {len(mois_groupes)} mois, {nb_ev} evenement(s), "
          f"{len(combats)} combat(s)")
    print("infos.json mis a jour : remplis heure et chaine puis relance-moi.")
    if not os.path.isdir("logos"):
        print("Dossier logos/ absent : badges texte utilises en attendant.")
    else:
        # deux fichiers pour un meme logo : le svg gagne, ce qui peut
        # laisser une vieille version en place sans qu'on le remarque
        vus = {}
        for f in sorted(os.listdir("logos")):
            base, _, ext = f.rpartition(".")
            if ext in ("svg", "png", "webp"):
                vus.setdefault(base, []).append(f)
        ordre = {"svg": 0, "png": 1, "webp": 2}
        for base, fichiers in vus.items():
            if len(fichiers) > 1:
                gagnant = min(fichiers, key=lambda f: ordre[f.rpartition(".")[2]])
                print(f"ATTENTION : plusieurs fichiers pour {base} "
                      f"({', '.join(fichiers)}). C'est {gagnant} qui est "
                      f"utilise, supprime les autres.")
    if not os.path.exists("fond.jpg"):
        print("fond.jpg absent : fond texture simple utilise.")


if __name__ == "__main__":
    main()
