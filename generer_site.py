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
from urllib.parse import quote_plus

# Identite du site pour Google et pour les partages sur les reseaux.
# Le titre s'affiche dans les resultats de recherche : environ
# 60 caracteres, au-dela Google coupe. La description, environ 155.
SITE_URL = "https://mmaradar.fr"
SITE_TITRE = "Programme et calendrier MMA : prochains combats des Français"
SITE_DESC = ("Les prochains événements MMA avec des combattants français "
             "et francophones : UFC, PFL, ARES, Hexagone, KSW. Dates, "
             "villes, horaires et diffusion.")

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
    ("hexagone", "hexagone", "Hexagone MMA"),
    ("hxmma", "hexagone", "Hexagone MMA"),
    ("hx mma", "hexagone", "Hexagone MMA"),
    ("oktagon", "oktagon", "OKTAGON"),
    ("cage warriors", "cagewarriors", "CAGE WARRIORS"),
    ("professional fighters", "pfl", "PFL"),
    ("pfl", "pfl", "PFL"),
    ("most valuable", "mvp", "MVP"),
    ("mvp", "mvp", "MVP"),
    ("bellator", "bellator", "BELLATOR"),
    ("rizin", "rizin", "RIZIN"),
    ("one punch night", "opn", "OPN"),
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


# Dans infos.json, tu peux rendre cliquable une partie seulement du
# texte, ce qui permet de citer deux diffuseurs sur la meme ligne :
#     "chaine": "RMC Sport 1 et [RMC+](https://www.rmcplus.fr/)"
MOTIF_LIEN = re.compile(r"\[([^\[\]]+)\]\((https?://[^\s)]+)\)")


def texte_sans_liens(valeur):
    """'A et [B](https://b.fr)' -> 'A et B'. Pour l'agenda et Google."""
    return MOTIF_LIEN.sub(lambda m: m.group(1), (valeur or "").strip())


def lignes_diffusion(etiquette, texte, adresse="", heure=""):
    """Lignes de diffusion pour la description d'un agenda.

    Un agenda n'affiche que du texte : on y ecrit les adresses en entier,
    que Google Agenda et l'iPhone rendent cliquables.
    "[Twitch](https://...) et [YouTube](https://...)" ->
        Prelims (19:00) :
        Twitch https://...
        YouTube https://...
    """
    texte = (texte or "").strip()
    if not texte:
        return []
    moment = f" ({heure})" if heure else ""
    liens = MOTIF_LIEN.findall(texte)
    if not liens:
        lignes = [f"{etiquette} : {texte}{moment}"]
        adresse = (adresse or "").strip()
        if adresse.startswith("http"):
            lignes.append(adresse)
        return lignes
    reste = MOTIF_LIEN.sub("", texte)
    if re.fullmatch(r"(?:[\s,;&+/]|\bet\b)*", reste):
        lignes = [f"{etiquette}{moment} :"]       # que des liens
    else:
        lignes = [f"{etiquette} : {texte_sans_liens(texte)}{moment}"]
    return lignes + [f"{nom} {url}" for nom, url in liens]


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
    "Ugo-Antton Vidal": "Ugo Vidal",
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


# Une heure saisie avant HEURE_NUIT designe la nuit suivante. Sherdog
# date les cartes americaines au jour local : un gala du samedi soir a
# Las Vegas passe chez nous a 4h du matin, donc le dimanche. Tu ecris
# l'heure sur la ligne du samedi, comme dans un programme tele, et
# c'est ici qu'on retablit l'instant reel. Aucun gala ne commence a 4h
# du matin heure francaise le soir annonce : la regle est sans risque.
# Mets 0 pour la desactiver.
HEURE_NUIT = 9


def instant_utc(date_iso, heure):
    """Date et heure de Paris -> instant en temps universel.

    Ne sert qu'aux fichiers agenda, qui doivent declencher un rappel au
    bon moment. La date affichee sur le site, elle, ne bouge pas.
    """
    m = re.fullmatch(r"(\d{1,2})[:hH](\d{2})", (heure or "").strip())
    if not m:
        return None
    try:
        jour = datetime.strptime(date_iso, "%Y-%m-%d").date()
    except ValueError:
        return None

    h, mn = int(m.group(1)), int(m.group(2))
    depart = datetime(jour.year, jour.month, jour.day, h, mn)
    if h < HEURE_NUIT:
        depart += timedelta(days=1)
    # le decalage se lit sur le jour ou l'evenement a lieu, ce qui
    # couvre les deux nuits de changement d'heure de l'annee
    return depart - timedelta(hours=decalage_paris(depart.date()))


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

    diff = infos.get(cle_infos(ev), {})
    if not isinstance(diff, dict):
        diff = {}
    heure = (diff.get("heure") or "").strip()

    lignes = ["BEGIN:VCALENDAR", "VERSION:2.0",
              "PRODID:-//MMA Radar//FR", "CALSCALE:GREGORIAN",
              "BEGIN:VEVENT"]

    cle = f"{ev['date']}-{normaliser(titre).replace(' ', '-')}"
    lignes.append(f"UID:{cle}@mmaradar.fr")
    lignes.append("DTSTAMP:" + datetime.now(timezone.utc)
                  .strftime("%Y%m%dT%H%M%SZ"))

    depart = instant_utc(ev["date"], heure)
    if depart is not None:
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
    details += lignes_diffusion("Diffusion", diff.get("chaine"), diff.get("lien"))
    details += lignes_diffusion("Prelims", diff.get("prelim"), diff.get("lien_prelim"),
                                (diff.get("heure_prelim") or "").strip())
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


# Combattants qui ont leur fiche sur le site (rempli dans main, d'apres
# bios.json). Leur nom renvoie vers cette fiche plutot que vers Sherdog.
PAGES_COMBATTANTS = {}


def slug_combattant(nom):
    """'Nimo Djagbo' -> 'nimo-djagbo'"""
    return re.sub(r"[^a-z0-9]+", "-", normaliser(nom)).strip("-")


def attributs_lien(nom, url_sherdog, prefixe=""):
    """href (et ouverture dans un nouvel onglet pour Sherdog)."""
    page = PAGES_COMBATTANTS.get(nom)
    if page:
        return f'href="{prefixe}{page}"'
    return f'href="{url_sherdog}" target="_blank" rel="noopener"'


def drapeau_html(iso, titre=""):
    if not iso:
        return ""
    code = CODES_DRAPEAU.get(iso, iso)
    infobulle = f' title="{echapper(titre)}"' if titre else ""
    return (f'<img class="flag" src="https://flagcdn.com/h20/{code}.png" '
            f'alt="" loading="lazy"{infobulle}>')


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
    "one punch night - opn": "OPN",
    "hxmma": "Hexagone MMA",
    "hx mma": "Hexagone MMA",
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


# Noms qui se suffisent a eux-memes : contrairement a un sigle comme
# PFL, ils n'ont pas besoin qu'on aille chercher un complement dans
# l'adresse de la page, ce qui y collerait la ville et rallongerait.
NOMS_COMPLETS = {"hexagone mma"}


def nom_evenement(evenement, lien=""):
    """Nom court et lisible, quel que soit le format renvoye par Sherdog."""
    resultat = nettoyer_nom(evenement)

    # S'il ne reste que le sigle, le nom complet est dans l'adresse de la page,
    # qu'il faut nettoyer de la meme facon.
    sigles = {c.lower() for c in RACCOURCIS.values()} - NOMS_COMPLETS
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


def retirer_annules_remplaces(combats):
    """Un combat annule ne reste affiche que si le suivi n'a plus rien.

    Quand un suivi est reprogramme contre un autre adversaire sur la
    meme soiree, l'ancienne ligne barree ferait doublon : on la retire.
    Pour un duel entre deux suivis, elle ne part que si les deux ont
    un autre combat sur la soiree.
    """
    def soiree(c):
        return (c.get("date", ""), c.get("evenement", ""), c.get("lieu", ""))

    def suivis(c):
        return {normaliser(n) for n in (c.get("combattant"),
                                        c.get("adversaire_suivi")) if n}

    actifs = {}
    for c in combats:
        if not c.get("annule"):
            actifs.setdefault(soiree(c), set()).update(suivis(c))

    gardes = []
    for c in combats:
        if c.get("annule"):
            noms = suivis(c)
            if noms and noms <= actifs.get(soiree(c), set()):
                continue
        gardes.append(c)
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


# Champs de saisie de infos.json, dans l'ordre ou on les lit a l'ecran :
# la ligne principale, puis celle des prelims.
CHAMPS_INFOS = ("heure", "chaine", "lien",
                "heure_prelim", "prelim", "lien_prelim")

# _evenement est reecrit a chaque passage, il ne se saisit pas.
ORDRE_INFOS = ("_evenement",) + CHAMPS_INFOS


def id_evenement(lien):
    """Numero Sherdog d'une soiree, a la fin de son adresse.

    Sherdog renomme parfois une page (ex. Ares-45-... devenu ARES-45-...)
    sans changer ce numero : c'est lui qui identifie vraiment la soiree.
    """
    m = re.search(r"-(\d+)/?$", (lien or "").strip())
    return m.group(1) if m else ""


def aligner_soirees(combats):
    """Range les combats annules sous la soiree telle que Sherdog l'ecrit
    aujourd'hui.

    Un combat annule garde le nom et l'adresse de la soiree au moment de
    l'annulation. Si Sherdog les a modifies depuis, il formait une
    seconde soiree en double. On reprend ceux des combats encore prevus
    portant le meme numero Sherdog.
    """
    reference = {}
    for c in combats:
        if c.get("annule"):
            continue
        num = id_evenement(c.get("lien_evenement"))
        if num and num not in reference:
            reference[num] = c

    for c in combats:
        if not c.get("annule"):
            continue
        ref = reference.get(id_evenement(c.get("lien_evenement")))
        if ref is None:
            continue
        for champ in ("date", "evenement", "lieu", "lien_evenement"):
            if ref.get(champ):
                c[champ] = ref[champ]
    return combats


def cle_repli(ev):
    """Cle de secours quand Sherdog ne donne pas l'adresse de la page."""
    return "|".join([ev.get("date", ""), ev.get("evenement", ""),
                     ev.get("lieu", "")])


def cle_infos(ev):
    """Cle unique d'un evenement dans infos.json.

    Le nom ne peut pas servir de cle : Sherdog appelle "Professional
    Fighters League" toutes les cartes PFL, si bien que l'heure saisie
    pour l'une se reportait sur toutes les autres. L'adresse de la page
    evenement, elle, est propre a chaque carte.
    """
    for c in ev.get("combats", []):
        lien = (c.get("lien_evenement") or "").strip()
        if lien:
            return lien.rstrip("/")
    return cle_repli(ev)


def etiquette_evenement(ev):
    """Libelle lisible, pose en tete de chaque entree de infos.json.

    Les cles sont des adresses : cette ligne est la pour que tu saches
    d'un coup d'oeil de quelle soiree il s'agit.
    """
    lien = ""
    for c in ev.get("combats", []):
        if c.get("lien_evenement"):
            lien = c["lien_evenement"]
            break

    nom = nom_evenement(ev.get("evenement", ""), lien)
    try:
        j = datetime.strptime(ev.get("date", ""), "%Y-%m-%d").date()
        jour = f"{j.day:02d}/{j.month:02d}/{j.year}"
    except ValueError:
        jour = "date a confirmer"

    ville = ville_depuis_lieu(ev.get("lieu", "")) if ev.get("lieu") else ""
    return f"{jour} - {nom}" + (f" ({ville})" if ville else "")


def _infos_remplies(entree):
    """Une entree ou tu as saisi quelque chose, par opposition a un gabarit."""
    if not isinstance(entree, dict):
        return False
    return any((entree.get(c) or "").strip() for c in CHAMPS_INFOS)


def assurer_infos(evenements):
    """Charge infos.json et ajoute les evenements manquants a remplir.

    Les entrees sont rangees par cle unique (voir cle_infos), et non plus
    par nom d'evenement. Les saisies faites sous l'ancienne organisation
    sont recuperees au premier passage.
    """
    infos = charger_json("infos.json")

    if infos == "ERREUR":
        # On ne reecrit surtout pas le fichier : tes saisies seraient perdues.
        print("infos.json ignore cette fois. Corrige-le puis relance.")
        return {}

    infos = infos or {}

    # Garde-fou : plus aucun evenement (panne de Sherdog, combats.json
    # tronque). On laisse le fichier intact plutot que de le vider.
    if not evenements:
        print("Aucun evenement : infos.json laisse en l'etat.")
        return {}

    aide = (
        "Une entree par evenement, rangee par adresse de sa page Sherdog : "
        "deux soirees differentes portent parfois le meme nom. Repere-toi "
        "a la ligne _evenement, reecrite a chaque passage, ne la remplis "
        "pas. A saisir : heure (ex: 21:00, garde ce format, il alimente "
        "aussi l'agenda et Google), chaine (ex: RMC Sport 1), lien "
        "(adresse de la page de diffusion, facultatif). Seconde ligne "
        "pour les prelims : heure_prelim (ex: 19:30), prelim (ex: "
        "Prelims Twitch) et lien_prelim. Laisse vide si inconnu, puis "
        "relance generer_site.py."
    )

    anciennes = {k: v for k, v in infos.items()
                 if k != "_aide" and isinstance(v, dict)}

    # Repere de secours : le libelle porte la date, le nom et la ville.
    # Il permet de retrouver une saisie si Sherdog cesse de donner
    # l'adresse de la page, et donc si la cle change.
    par_libelle = {}
    for k, v in anciennes.items():
        libelle = (v.get("_evenement") or "").strip()
        if libelle:
            par_libelle.setdefault(libelle, k)

    # Meme soiree dont Sherdog a modifie l'adresse : meme numero.
    par_numero = {}
    for k in anciennes:
        num = id_evenement(k)
        if num:
            par_numero.setdefault(num, k)

    prises = set()        # cles anciennes deja attribuees
    recuperes = []        # pour le compte rendu
    a_verifier = []       # homonymes : la saisie ne peut aller qu'a un seul

    sortie = {"_aide": aide}
    for ev in evenements:
        cle = cle_infos(ev)
        if cle in sortie:          # deux fois la meme carte
            continue

        libelle = etiquette_evenement(ev)
        source = None

        if cle in anciennes:
            source = cle
        # l'evenement a perdu son lien Sherdog, ou vient d'en gagner un
        elif cle_repli(ev) in anciennes:
            source = cle_repli(ev)
        elif par_numero.get(id_evenement(cle)) not in (None, *prises):
            source = par_numero[id_evenement(cle)]
        elif par_libelle.get(libelle) not in (None, *prises):
            source = par_libelle[libelle]
        else:
            # ancienne organisation : la saisie etait rangee sous le nom.
            # Le premier evenement de la liste (le plus proche) la
            # recupere, les homonymes suivants sont signales.
            nom = ev.get("evenement", "")
            if _infos_remplies(anciennes.get(nom)):
                if nom not in prises:
                    source = nom
                    recuperes.append(libelle)
                else:
                    a_verifier.append(libelle)

        if source is not None:
            prises.add(source)
        entree = anciennes.get(source) if source else None
        entree = dict(entree) if isinstance(entree, dict) else {}
        reste = {k: v for k, v in entree.items() if k not in ORDRE_INFOS}

        neuve = {"_evenement": libelle}
        for champ in CHAMPS_INFOS:
            neuve[champ] = entree.get(champ, "")
        neuve.update(reste)
        sortie[cle] = neuve

    if recuperes or a_verifier:
        try:
            with open("infos-ancien.json", "w", encoding="utf-8") as f:
                json.dump(infos, f, ensure_ascii=False, indent=2)
            print("\ninfos.json reorganise par cle unique.")
            print("   copie de securite : infos-ancien.json")
        except OSError:
            print("\ninfos.json reorganise par cle unique.")
        for e in recuperes:
            print(f"   saisie recuperee : {e}")
        for e in a_verifier:
            print(f"   A VERIFIER, meme nom Sherdog qu'un autre : {e}")

    with open("infos.json", "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=2)
    return sortie


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
    scrollbar-color: var(--bord) var(--noir);
  }

  body {
    margin: 0;
    padding: 0 1.2rem 2.6rem;
    padding-left: calc(1.2rem + env(safe-area-inset-left));
    padding-right: calc(1.2rem + env(safe-area-inset-right));
    padding-bottom: calc(2.6rem + env(safe-area-inset-bottom));
    background-color: transparent;
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
  /* icone agenda un peu plus grande, trait aussi fin qu'avant,
     et zone de clic elargie sans pousser le reste */
  .ev__foot a.ev__ics { padding: 0.35rem; margin: -0.35rem; }
  .ev__foot a.ev__ics svg { width: 19px; height: 19px; }
  .ev__foot a.ev__ics svg * { vector-effect: non-scaling-stroke;
                              stroke-width: 1.3px; }

  .ev__foot a.ev__ics:hover,
  .ev__foot a.ev__ics:focus { color: var(--or); opacity: 1; }

  .ev__gauche {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    min-width: 0;
  }

  .ev__diffusion { color: var(--blanc); }

  .ev__diffusion a {
    color: inherit;
    text-decoration: underline;
    text-decoration-color: rgba(242, 193, 78, 0.45);
    text-underline-offset: 2px;
  }

  .flag { height: 14px; border-radius: 2px; flex: none; }

  /* texte lu par les lecteurs d'ecran, invisible a l'ecran */
  .sr {
    position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
    overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
  }

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


def bloc_evenement(ev, fiches, infos, ouvert, prochaine_date, agenda="",
                   prefixe="", nom_courant=""):
    """prefixe : '../' quand la carte est affichee depuis une fiche.
    nom_courant : le combattant de cette fiche, dont le nom n'est pas
    un lien (on est deja sur sa page)."""
    try:
        jour = datetime.strptime(ev["date"], "%Y-%m-%d").date()
        date_txt = f"{jour.day:02d} {MOIS_COURT[jour.month - 1]}"
    except ValueError:
        date_txt = "--"

    ville = echapper(ville_depuis_lieu(ev["lieu"]))
    pays = pays_depuis_lieu(ev["lieu"])
    flag_event = drapeau_html(PAYS_ISO.get(pays.lower(), ""), ev["lieu"])

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
        if c["combattant"] != nom_courant and (
                url or c["combattant"] in PAGES_COMBATTANTS):
            lien_nom = (f'<a class="fight__nom fight__nom--suivi" '
                        f'{attributs_lien(c["combattant"], url, prefixe)} '
                        f'data-complet="{nom}">{nom}</a>')
        else:
            lien_nom = (f'<span class="fight__nom fight__nom--suivi" '
                        f'data-complet="{nom}">{nom}</span>')

        rec_suivi = echapper(nettoyer_record(c.get("record_suivi", "")))
        rec_adv = echapper(nettoyer_record(c.get("record_adversaire", "")))
        rec_suivi_html = f'<span class="fight__rec">{rec_suivi}</span>' if rec_suivi else ""
        rec_adv_html = f'<span class="fight__rec">{rec_adv}</span>' if rec_adv else ""

        annule = bool(c.get("annule"))
        belt = "" if annule else (
            CEINTURE + '<span class="sr">titre en jeu</span>'
            if c.get("titre") else "")
        titre_txt = ""   # l'icone ceinture parle d'elle-meme

        # Si l'adversaire fait aussi partie de la liste suivie, on affiche
        # son nom tel qu'on l'ecrit, son drapeau, et on le rend cliquable.
        nom_adv = (nom_affiche(c["adversaire_suivi"])
                   if c.get("adversaire_suivi") else c["adversaire"])
        suivi_adv = c.get("adversaire_suivi", "")
        url_adv = fiches.get(suivi_adv, "")
        if suivi_adv in PAGES_COMBATTANTS and not url_adv:
            url_adv = "#"
        flag_adv = drapeau_html(c.get("drapeau_adversaire", ""))
        classe_adv = "fight__nom fight__nom--suivi" if url_adv else "fight__nom"
        if url_adv and suivi_adv != nom_courant:
            bloc_adv = (f'<a class="{classe_adv}" '
                        f'{attributs_lien(suivi_adv, url_adv, prefixe)} '
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

    diff = infos.get(cle_infos(ev), {})
    if not isinstance(diff, dict):
        diff = {}

    def _lien(texte, adresse):
        """Rend le texte cliquable. Deux ecritures possibles :

        - "chaine": "RMC Sport 1" + "lien": "https://..."
          tout le texte est cliquable, comme avant ;
        - "chaine": "RMC Sport 1 et [RMC+](https://www.rmcplus.fr/)"
          seul RMC+ l'est, ce qui permet deux diffuseurs sur une ligne.
        """
        texte = echapper(texte)
        if MOTIF_LIEN.search(texte):
            # des liens imbriques seraient invalides : le champ lien
            # est ignore quand le texte porte deja ses propres adresses
            return MOTIF_LIEN.sub(
                lambda m: (f'<a href="{m.group(2)}" target="_blank" '
                           f'rel="noopener">{m.group(1)}</a>'), texte)
        adresse = (adresse or "").strip()
        if adresse.startswith("http"):
            return (f'<a href="{echapper(adresse)}" target="_blank" '
                    f'rel="noopener">{texte}</a>')
        return texte

    def _heure_affichee(valeur):
        """20:00 devient 20h, 20:30 devient 20h30."""
        valeur = (valeur or "").strip()
        if not valeur:
            return ""
        texte = valeur.replace(":", "h")
        return texte[:-2] if texte.endswith("h00") else texte

    def _ligne(heure_brute, texte, adresse):
        """Une ligne de diffusion : heure, puis chaine cliquable ou non."""
        texte = (texte or "").strip()
        if not texte:
            return ""
        corps = _lien(texte, adresse)
        moment = _heure_affichee(heure_brute)
        return f"{moment}&nbsp;: {corps}" if moment else corps

    ligne_principale = _ligne(diff.get("heure"), diff.get("chaine"),
                              diff.get("lien"))
    ligne_prelim = _ligne(diff.get("heure_prelim"), diff.get("prelim"),
                          diff.get("lien_prelim"))

    def _minutes(valeur):
        m = re.fullmatch(r"(\d{1,2})[:hH](\d{2})", (valeur or "").strip())
        return int(m.group(1)) * 60 + int(m.group(2)) if m else None

    # On lit la soiree dans l'ordre : les prelims commencent avant.
    # Si les deux horaires sont connus et disent le contraire, ils
    # priment sur cette regle.
    lignes_diff = [ligne_prelim, ligne_principale]
    debut_prelim = _minutes(diff.get("heure_prelim"))
    debut_chaine = _minutes(diff.get("heure"))
    if (debut_prelim is not None and debut_chaine is not None
            and debut_prelim > debut_chaine):
        lignes_diff = [ligne_principale, ligne_prelim]
    lignes_diff = [l for l in lignes_diff if l]

    diffusion = ""
    if lignes_diff:
        diffusion = (f'<span class="ev__diffusion">'
                     f'{"<br>".join(lignes_diff)}</span>')

    attr_ouvert = " open" if ouvert else ""

    return f"""
    <details class="ev"{attr_ouvert} data-orga="{orga_cle}" data-noms="{noms_data}">
      <summary class="ev__bar">
        <span class="ck"><span class="ev__date">{date_txt}</span></span>
        <span class="ck">{logo_orga(ev["evenement"]).replace('src="logos/', f'src="{prefixe}logos/')}</span>
        <span class="ck"><span class="ev__nom" data-complet="{nom_ev}">{bloc_nom}</span></span>
        <span class="ck">{flag_event}<span class="ev__ville" title="{echapper(ev["lieu"])}">{ville}</span></span>
        <span class="ck ev__avec"><span class="ev__avec-txt" data-complet="{noms_avec}">
          <span class="ev__avec-label">AVEC&nbsp;: </span>
          <span class="ev__avec-noms">{noms_avec}</span>
        </span></span>
        <span class="ck">{chip_html}</span>
        <span class="ck"><span class="ev__chev" aria-hidden="true">&#9656;</span></span>
      </summary>
      <div class="ev__body">{"".join(lignes)}
        <div class="ev__foot">
          <span class="ev__gauche">{lien_agenda}{diffusion}</span>
          <span class="ev__actions">{lien_html}</span>
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
        if r.get("combattant", "") in PAGES_COMBATTANTS and not url:
            url = "#"
        nom_html = (f'<a class="rl__lien" '
                    f'{attributs_lien(r.get("combattant", ""), url)}>{nom}</a>'
                    ) if url else nom

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
      <span class="recap__chev" aria-hidden="true">&#9656;</span></summary>
    <div class="recap__body">{"".join(lignes)}
    </div>
  </details>"""


def barre_outils():
    """Recherche seule : les filtres par orga alourdissaient pour rien."""
    return """
  <div class="outils">
    <input id="recherche" class="outils__recherche" type="search"
           placeholder="Rechercher un combattant..."
           aria-label="Rechercher un combattant">
  </div>"""


# Clics comptes par Umami (onglet Evenements de son tableau de bord).
# Seuls les gestes du visiteur sont comptes : l'ouverture automatique
# des volets par la recherche ne l'est pas. Sans Umami (bloqueur),
# rien ne se passe.
SUIVI_UMAMI = r"""
<script>
(function () {
  function compter(nom, infos) {
    if (window.umami && typeof window.umami.track === "function") {
      try { window.umami.track(nom, infos); } catch (e) {}
    }
  }
  function nomEvenement(el) {
    var ev = el.closest("details.ev");
    var n = ev && ev.querySelector(".ev__nom");
    return n ? (n.getAttribute("data-complet") || n.textContent).trim() : "";
  }
  document.addEventListener("click", function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    var bar = t.closest("summary.ev__bar");
    if (bar) {
      var ev = bar.parentElement;
      if (ev && !ev.open) compter("Ouverture evenement", { evenement: nomEvenement(bar) });
      return;
    }
    var recap = t.closest("summary.recap__bar");
    if (recap) {
      if (recap.parentElement && !recap.parentElement.open) compter("Ouverture resultats");
      return;
    }
    var a = t.closest("a");
    if (!a) return;
    if (a.classList.contains("ev__ics")) {
      compter("Ajout agenda", { evenement: nomEvenement(a) });
    } else if (a.classList.contains("fight__nom--suivi")) {
      compter("Fiche combattant", { combattant: a.textContent.trim() });
    } else if (a.closest(".ev__diffusion")) {
      compter("Lien diffusion", { evenement: nomEvenement(a) });
    } else if (a.closest(".ev__actions")) {
      compter("Carte complete", { evenement: nomEvenement(a) });
    }
  });
  var champ = document.getElementById("recherche");
  if (champ) {
    champ.addEventListener("change", function () {
      var q = champ.value.trim();
      if (q.length >= 2) compter("Recherche", { terme: q.toLowerCase() });
    });
  }
})();
</script>
"""


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

    // Sur iPhone et iPad, le navigateur ne propose rien : l'installation
    // passe par le bouton de partage. On explique au lieu d'un bouton
    // inutile. Depuis iPadOS 13, un iPad se declare comme un Mac : on le
    // reconnait a son ecran tactile, sinon il n'aurait aucune indication.
    var iOS = /iphone|ipad|ipod/i.test(navigator.userAgent)
      || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    if (iOS) {
      bandeau.querySelector(".install__txt").innerHTML =
        "<b>MMA Radar</b> sur ton écran d'accueil : "
        + "<svg viewBox=\"0 0 20 20\" width=\"13\" height=\"13\" fill=\"none\" "
        + "stroke=\"currentColor\" stroke-width=\"1.6\" stroke-linecap=\"round\" "
        + "stroke-linejoin=\"round\" aria-hidden=\"true\" "
        + "style=\"vertical-align:-2px\">"
        + "<path d=\"M10 2.6v9\"/><path d=\"M6.8 5.6 10 2.4l3.2 3.2\"/>"
        + "<path d=\"M5 9.2H3.6v8h12.8v-8H15\"/></svg>"
        + " puis <b>Sur l'écran d'accueil</b>";
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
      // compte dans Umami, onglet Evenements (installation confirmee)
      if (window.umami && typeof window.umami.track === "function") {
        try { window.umami.track("Installation"); } catch (e) {}
      }
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

            info = infos.get(cle_infos(ev), {})
            if not isinstance(info, dict):
                info = {}
            heure = (info.get("heure") or "").strip()
            debut = f"{jour}T{heure}:00" if re.fullmatch(r"\d\d:\d\d", heure) else jour

            noms = []
            for c in ev.get("combats", []):
                if c.get("annule"):
                    continue
                for n in (c.get("combattant"), c.get("adversaire")):
                    if n and n not in noms and n != ADVERSAIRE_INCONNU:
                        noms.append(n)

            interpretes = [{"@type": "Person", "name": n} for n in noms]
            _, libelle_orga = orga_de(ev.get("evenement", ""))

            bloc = {
                "@type": "SportsEvent",
                "name": ev.get("evenement", ""),
                "startDate": debut,
                "endDate": debut,
                "url": SITE_URL + "/",
                "image": SITE_URL + "/partage.jpg",
                "eventStatus": "https://schema.org/EventScheduled",
                "eventAttendanceMode":
                    "https://schema.org/OfflineEventAttendanceMode",
                "sport": "Mixed Martial Arts",
                "performer": interpretes,
                "competitor": interpretes,
            }

            if libelle_orga and libelle_orga != "MMA":
                bloc["organizer"] = {
                    "@type": "Organization",
                    "name": libelle_orga,
                }

            lieu = (ev.get("lieu") or "").strip()
            if lieu:
                bloc["location"] = {
                    "@type": "Place",
                    "name": lieu.split(",")[0].strip() or lieu,
                    "address": lieu,
                }
            chaine = texte_sans_liens(info.get("chaine"))
            if chaine:
                bloc["description"] = "Diffusion : " + chaine
                bloc["publication"] = {
                    "@type": "BroadcastEvent",
                    "name": f"{ev.get('evenement', '')} sur {chaine}",
                    "isLiveBroadcast": True,
                    "startDate": debut,
                    "publishedOn": {
                        "@type": "BroadcastService",
                        "name": chaine,
                    },
                }

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
<script defer src="https://cloud.umami.is/script.js" data-website-id="20e687c1-5629-4138-9b0d-3255669e6390"></script>
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
{SUIVI_UMAMI}
</body>
</html>
"""


# Barre de pronostics. En mode demonstration, les votes restent dans le
# navigateur du visiteur : rien n'est partage. A basculer sur un vrai
# service le jour ou on le mettra en place.
VOTES_ACTIFS = False
VOTES_DEMO = True

VERSION = 112


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


def ecrire_robots_et_sitemap(pages=()):
    """Autorise l'indexation et signale les pages aux moteurs."""
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
                "  </url>\n")
        for page in pages:
            f.write("  <url>\n"
                    f"    <loc>{SITE_URL}/{page}</loc>\n"
                    f"    <lastmod>{date.today().isoformat()}</lastmod>\n"
                    "    <changefreq>weekly</changefreq>\n"
                    "    <priority>0.6</priority>\n"
                    "  </url>\n")
        f.write("</urlset>\n")


# ---------------------------------------------------------------------
# Fiches combattants : une page par combattant qui a une bio dans
# bios.json. Infos lues sur Sherdog par profils.py (profils.json), ce
# qui est rempli a la main dans bios.json passe devant.
# ---------------------------------------------------------------------

NOMS_PAYS = {
    "fr": "France", "be": "Belgique", "ch": "Suisse", "lu": "Luxembourg",
    "ca": "Canada", "ma": "Maroc", "dz": "Algérie", "tn": "Tunisie",
    "sn": "Sénégal", "cm": "Cameroun", "ci": "Côte d'Ivoire",
    "cd": "RD Congo", "cg": "Congo", "ml": "Mali", "gn": "Guinée",
    "ht": "Haïti", "mg": "Madagascar", "ga": "Gabon", "bj": "Bénin",
    "tg": "Togo", "re": "La Réunion", "gp": "Guadeloupe", "mq": "Martinique",
    "gf": "Guyane", "yt": "Mayotte", "nc": "Nouvelle-Calédonie", "pf": "Polynésie française", "bf": "Burkina Faso", "ru": "Russie", "us": "États-Unis",
    "gb": "Royaume-Uni", "pt": "Portugal", "es": "Espagne", "it": "Italie",
    "de": "Allemagne", "pl": "Pologne", "br": "Brésil",
}

# Blocs "prochain combat" et "dernier combat" sur les fiches. Retires
# pour l'instant : passer a True pour les remettre.
FICHE_AVEC_COMBATS = False

RESULTATS_FR = {"win": "Victoire", "loss": "Défaite", "draw": "Match nul",
                "nc": "Sans décision", "no contest": "Sans décision"}

CSS_FICHE = """
  :root {
    color-scheme: dark;
    --noir: #0a0a0c;
    --bar: #1b1b21;
    --bord: #34343d;
    --or: #f2c14e;
    --blanc: #f5f5f7;
    --gris: #9a9aa4;
  }
  * { box-sizing: border-box; }
  html { background-color: var(--noir); scrollbar-color: var(--bord) var(--noir); }
  body {
    margin: 0;
    padding: 0 1.2rem 2.6rem;
    padding-left: calc(1.2rem + env(safe-area-inset-left));
    padding-right: calc(1.2rem + env(safe-area-inset-right));
    padding-bottom: calc(2.6rem + env(safe-area-inset-bottom));
    background-color: transparent;
    background-image: repeating-linear-gradient(
      135deg, rgba(255,255,255,0.016) 0 2px, transparent 2px 16px);
    color: var(--blanc);
    font-family: Inter, system-ui, sans-serif;
    line-height: 1.5;
  }
  .wrap { max-width: 960px; margin: 0 auto; }
  .haut { margin: 1.6rem 0 0; text-align: center; }
  a { color: var(--blanc); text-decoration-color: rgba(242,193,78,0.6);
      text-underline-offset: 3px; }
  .retour {
    display: inline-block; padding: 0.4rem 0;
    color: var(--gris); font-size: 0.85rem; text-decoration: none;
    letter-spacing: 0.04em;
  }
  .retour:hover { color: var(--or); }
  header.fiche { padding: 1.2rem 0 1.4rem; text-align: center; }
  h1 {
    font-family: Oswald, sans-serif; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.02em;
    font-size: clamp(2rem, 7vw, 2.8rem); line-height: 1.05; margin: 0;
  }
  h1 .flag { height: 0.62em; width: auto; margin-left: 0.4rem;
             vertical-align: 0.12em; border-radius: 2px; }
  .surnom { margin: 0.35rem 0 0; color: var(--or); font-style: italic;
            font-weight: 600; letter-spacing: 0.02em; }
  .bloc {
    background: var(--bar); border: 1px solid var(--bord);
    border-radius: 12px; padding: 1rem 1.15rem; margin: 0 0 1rem;
  }
  h2 {
    font-family: Oswald, sans-serif; font-weight: 500;
    text-transform: uppercase; letter-spacing: 0.08em;
    font-size: 0.82rem; color: var(--or); margin: 0 0 0.6rem;
    text-align: center;
  }
  .infos { display: grid; grid-template-columns: 1fr; gap: 0.75rem 0.8rem;
           margin: 0; text-align: center; }
  .infos dt { color: var(--gris); font-size: 0.72rem; text-transform: uppercase;
              letter-spacing: 0.07em; margin-bottom: 0.1rem; }
  .infos dd { margin: 0; font-size: 0.98rem; font-weight: 600; }
  .infos .age, .infos .coach { display: block; font-size: 0.76rem; font-weight: 400;
                               color: var(--gris); margin-top: 0.1rem; }
  /* l'info en blanc, son intitule en gris */
  .infos .age, .infos .coach__nom { color: var(--blanc); }
  .infos .info--large { grid-column: 1 / -1; }
  .surnom .record { font-style: normal; color: var(--blanc); }
  .surnom .sep { font-style: normal; color: var(--gris); margin: 0 0.35rem; }
  .nobr { white-space: nowrap; }
  @media (max-width: 799px) {
    /* fiche et bio l'une sous l'autre : la fiche passe sur deux colonnes */
    .infos { grid-template-columns: 1fr 1fr; }
  }
  .combat__ligne { font-family: Oswald, sans-serif; font-weight: 500;
                   text-transform: uppercase; font-size: 1.15rem;
                   letter-spacing: 0.02em; margin: 0; }
  .combat__ligne .vs { color: var(--or); font-size: 0.8rem;
                       margin: 0 0.45rem; vertical-align: 0.12em; }
  .combat__meta { margin: 0.25rem 0 0; color: var(--gris); font-size: 0.88rem; }
  .combat__res { font-weight: 700; }
  .combat__res--v { color: #3ecf8e; }
  .combat__res--d { color: #e5484d; }
  .chip {
    display: inline-block; margin-left: 0.5rem; padding: 0.05rem 0.5rem;
    border-radius: 999px; background: var(--or); color: #14140f;
    font-family: Oswald, sans-serif; font-size: 0.75rem; letter-spacing: 0.04em;
    vertical-align: 0.15em;
  }
  .vide { color: var(--gris); margin: 0; }
  .bio p { margin: 0; font-size: 1rem; line-height: 1.65; }
  .colonnes { display: grid; gap: 1rem; align-items: stretch; }
  .colonnes .bloc { margin: 0; }
  @media (min-width: 800px) {
    .colonnes { grid-template-columns: 300px 1fr; }
    .bio p { text-align: justify; }
  }
  .boutons { display: flex; flex-wrap: wrap; justify-content: center;
             gap: 0.6rem; margin: 0 0 1.4rem; }
  .bouton {
    display: inline-flex; align-items: center; gap: 0.4rem;
    padding: 0.6rem 1.1rem; border: 1px solid var(--or); border-radius: 999px;
    color: var(--or); text-decoration: none; font-family: Oswald, sans-serif;
    font-weight: 500; text-transform: uppercase; letter-spacing: 0.06em;
    font-size: 0.85rem;
  }
  .bouton:hover { background: var(--or); color: #14140f; }
  .liens { display: flex; flex-wrap: wrap; justify-content: center;
           gap: 0.6rem 1.4rem;
           margin: 1.4rem 0 0; font-size: 0.9rem; }
  footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--bord);
           color: var(--gris); font-size: 0.8rem; text-align: center; }
  footer p { margin: 0.3rem 0; }
  /* bouton Suivre : il prend la largeur de la petite phrase en dessous */
  .suivre { display: flex; justify-content: center; margin: -0.5rem 0 1.4rem; }
  .suivre__bloc { display: inline-flex; flex-direction: column;
                  align-items: stretch; gap: 0.35rem; }
  .suivre__btn {
    display: flex; align-items: center; justify-content: center; gap: 0.4rem;
    padding: 0.45rem 1rem; border-radius: 999px; background: var(--or);
    color: #14140f; text-decoration: none; font-family: Oswald, sans-serif;
    font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em;
    font-size: 0.8rem; white-space: nowrap; cursor: pointer;
  }
  .suivre__btn:hover { filter: brightness(1.08); }
  .suivre__btn svg { width: 13px; height: 13px; flex: none; }
  .suivre small { color: var(--gris); font-size: 0.74rem; text-align: center; }
  /* encadre d'explication, affiche apres le clic */
  .panneau {
    position: fixed; inset: 0; z-index: 60; display: flex;
    align-items: center; justify-content: center; padding: 1rem;
    background: rgba(0, 0, 0, 0.65);
  }
  .panneau[hidden] { display: none; }
  .panneau__boite {
    position: relative; max-width: 430px; width: 100%;
    background: var(--bar); border: 1px solid var(--or); border-radius: 12px;
    padding: 1.1rem 1.2rem 1rem; font-size: 0.9rem; line-height: 1.5;
  }
  .panneau__boite p { margin: 0 0 0.6rem; }
  .panneau__boite ol { margin: 0 0 0.6rem; padding-left: 1.2rem; }
  .panneau__boite li { margin-bottom: 0.25rem; }
  .panneau__boite b { color: var(--or); }
  .panneau__petit { color: var(--gris); font-size: 0.8rem; }
  .panneau__fermer {
    position: absolute; top: 0.4rem; right: 0.6rem; background: none;
    border: none; color: var(--gris); font-size: 1.4rem; line-height: 1;
    cursor: pointer;
  }
  .panneau__fermer:hover { color: var(--blanc); }
  .panneau__google {
    display: block; margin: 0.4rem 0 0.8rem; padding: 0.6rem 1rem;
    border-radius: 999px; background: var(--or); color: #14140f;
    text-align: center; text-decoration: none; font-family: Oswald, sans-serif;
    font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em;
    font-size: 0.85rem;
  }
  .panneau__google:hover { filter: brightness(1.08); }
  .panneau__secours { margin-top: 0.2rem; }
  .etapes { margin: 0.2rem 0 0.4rem; padding-left: 1.2rem; }
  .etapes li { margin-bottom: 0.7rem; }
  .etapes .panneau__google { margin: 0.3rem 0 0.4rem; }
  .panneau__secours .panneau__copier {
    margin: 0 0 0 0.3rem; background: none; border: 1px solid var(--bord);
    color: var(--blanc);
  }
  .panneau__copier {
    display: inline-block; margin: 0.2rem 0 0.4rem; padding: 0.35rem 0.9rem;
    border: none; border-radius: 999px; background: var(--or); color: #14140f;
    font-family: Oswald, sans-serif; text-transform: uppercase;
    letter-spacing: 0.05em; font-size: 0.75rem; cursor: pointer;
  }
  @media (max-width: 520px) {
    .boutons { gap: 0.4rem; margin-bottom: 1.1rem; }
    .bouton { padding: 0.36rem 0.6rem; font-size: 0.7rem;
              letter-spacing: 0.03em; gap: 0.25rem; }
    .suivre__btn { padding: 0.38rem 0.85rem; font-size: 0.74rem;
                   letter-spacing: 0.04em; }
    .suivre small { font-size: 0.72rem; }
  }
  @media (max-width: 400px) {
    .bouton .fleche { display: none; }
    .combat__ligne { font-size: 1.02rem; }
  }
"""

def css_carte(css, portee=".carte"):
    """Extrait du CSS de l'accueil les regles des cartes d'evenement et
    les limite a `portee` : la fiche reprend le meme rendu sans que le
    reste de l'accueil (corps, titres, outils...) ne deteigne dessus."""
    utile = re.compile(r"\.(ev|fight|duel|ck|jchip|chip|flag|belt|sr|"
                       r"nom-court|nom-long)(?:__|--|(?![\w-]))|details|summary")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    def traiter(texte):
        sortie, i = [], 0
        while True:
            a = texte.find("{", i)
            if a < 0:
                break
            tete = texte[i:a].strip()
            prof, b = 1, a + 1
            while prof:
                prof += {"{": 1, "}": -1}.get(texte[b], 0)
                b += 1
            corps = texte[a + 1:b - 1]
            if tete.startswith("@"):
                dedans = traiter(corps)
                if dedans:
                    sortie.append(f"{tete} {{{dedans}}}")
            else:
                parts = [f"{portee} {x.strip()}" for x in tete.split(",")
                         if utile.search(x)]
                if parts:
                    sortie.append(f"{', '.join(parts)} {{{corps}}}")
            i = b
        return "\n".join(sortie)

    return traiter(css) + f"""
  {portee} {{ --bar-clair: #232329; --sombre: #14140f; margin: 0 0 1rem; }}
  {portee} > h2 {{ margin-bottom: 0.5rem; }}
  /* moins d'air entre le texte sous Suivre et le titre */
  .suivre ~ {portee} {{ margin-top: -0.7rem; }}
  {portee} details.ev {{ margin: 0; }}
  /* sur la fiche on sait de qui et ou : ni ligne AVEC ni ville.
     Sur ordinateur on garde leur place, sinon la grille se decale. */
  {portee} .ev__avec, {portee} summary.ev__bar > .ck:nth-child(4) {{ visibility: hidden; }}
  @media (max-width: 860px) {{
    {portee} .ev__avec, {portee} summary.ev__bar > .ck:nth-child(4) {{ display: none; }}
  }}
"""


CSS_CARTE_FICHE = css_carte(CSS)



def taille_affichee(valeur):
    """'184', '1,84' ou '1.84' -> '1,84 m'"""
    try:
        v = float(str(valeur).replace(",", ".").replace("m", "").strip())
    except ValueError:
        return ""
    if v < 3:
        v *= 100
    if v < 120 or v > 230:
        return ""
    return f"{v / 100:.2f} m".replace(".", ",")


def lier_noms(texte, nom_courant):
    """Rend cliquable, dans une bio, le nom des autres combattants qui ont
    leur fiche (premiere mention seulement). Ne tient pas compte des
    accents : 'Marvin Capéran' renvoie bien vers 'Marvin Caperan'."""
    def sans_accent(t):
        return "".join(unicodedata.normalize("NFKD", ch)[0] if ch else ch
                       for ch in t).lower()

    plat = sans_accent(texte)
    reperes = []
    for nom, chemin in PAGES_COMBATTANTS.items():
        if nom == nom_courant:
            continue
        for forme in {nom, nom_affiche(nom)}:
            i = plat.find(sans_accent(forme))
            if i >= 0:
                reperes.append((i, i + len(forme), chemin))
                break
    reperes.sort()
    morceaux, pos = [], 0
    for debut, fin, chemin in reperes:
        if debut < pos:
            continue
        morceaux.append(echapper(texte[pos:debut]))
        cible = "../" + chemin
        morceaux.append(f'<a href="{cible}">{echapper(texte[debut:fin])}</a>')
        pos = fin
    morceaux.append(echapper(texte[pos:]))
    return "".join(morceaux)


def date_longue(iso):
    try:
        j = datetime.strptime(iso, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return ""
    jour = "1er" if j.day == 1 else str(j.day)
    return f"{jour} {MOIS_LONG[j.month - 1].lower()} {j.year}"


def age_depuis(iso):
    try:
        n = datetime.strptime(iso, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return ""
    t = date.today()
    return str(t.year - n.year - ((t.month, t.day) < (n.month, n.day)))


def prochain_combat_de(nom, combats):
    aujourd_hui = date.today().isoformat()
    candidats = []
    for c in combats:
        if c.get("annule") or (c.get("date") or "") < aujourd_hui:
            continue
        if c.get("combattant") == nom:
            adv = c.get("adversaire_suivi") or c.get("adversaire", "")
            rec_adv = c.get("record_adversaire", "")
            if c.get("adversaire_suivi"):
                rec_adv = ""
            candidats.append((c["date"], c, adv, rec_adv))
        elif c.get("adversaire_suivi") == nom:
            candidats.append((c["date"], c, c.get("combattant", ""), ""))
    if not candidats:
        return None
    candidats.sort(key=lambda x: x[0])
    return candidats[0]


def dernier_combat_de(nom, profil, resultats):
    dc = profil.get("dernier_combat") if isinstance(profil, dict) else None
    if isinstance(dc, dict) and dc.get("resultat"):
        return dc
    miens = [r for r in resultats if r.get("combattant") == nom]
    miens.sort(key=lambda r: r.get("date", ""), reverse=True)
    return miens[0] if miens else None


def page_fiche(nom, bio, profil, combats, resultats, url_sherdog, infos=None):
    affichage = nom_affiche(nom)
    profil = profil if isinstance(profil, dict) else {}
    prochain = prochain_combat_de(nom, combats)

    # infos : la saisie manuelle passe devant Sherdog ("?" = inconnu)
    def saisie(champ):
        v = str(bio.get(champ) or "").strip()
        return "" if v == "?" else v

    bio = dict(bio)
    for champ in ("surnom", "naissance", "taille", "tapology", "instagram",
                  "wikipedia", "nom_complet", "nationalite", "team", "coach"):
        bio[champ] = saisie(champ)
    surnom = (bio.get("surnom") or profil.get("surnom") or "").strip()
    titre_fiche = affichage
    if nom in NOMS_AFFICHES and bio.get("nom_complet"):
        # ex. Baki : nom complet en titre, nom raccourci en pseudo
        titre_fiche = bio["nom_complet"]
        surnom = affichage
    elif surnom.lower() == affichage.lower():
        surnom = ""
    naissance = (bio.get("naissance") or profil.get("naissance") or "").strip()
    drapeau = (profil.get("drapeau") or "").strip()
    categorie = (profil.get("categorie") or "").strip()
    record = nettoyer_record(profil.get("record") or "")
    if prochain:
        c = prochain[1]
        if not drapeau and c.get("combattant") == nom:
            drapeau = c.get("drapeau", "")
        if not categorie:
            categorie = c.get("categorie", "")
        if not record and c.get("combattant") == nom:
            record = nettoyer_record(c.get("record_suivi", ""))

    lignes_infos = []

    def info(etiquette, valeur):
        # une info inconnue reste affichee, avec un point d'interrogation
        lignes_infos.append(f'<div class="info"><dt>{etiquette}</dt>'
                            f'<dd>{valeur or "?"}</dd></div>')

    # ordre : la personne, puis le sportif
    # nationalite saisie a la main (codes pays, ex: "fr, tn") ou Sherdog
    pays = [p.strip().lower() for p in bio.get("nationalite", "").split(",")
            if p.strip()] or ([drapeau] if drapeau else [])
    info("Nationalité", " / ".join(
        f'<span class="nobr">{drapeau_html(p)} '
        f'{echapper(NOMS_PAYS.get(p, p.upper()))}</span>'
        for p in pays))
    if re.fullmatch(r"\d{4}", naissance):
        # annee seule : age approximatif
        age = date.today().year - int(naissance)
        info("Naissance", f'<span class="nobr">{naissance}</span>'
             f'<span class="age">env. {age} ans</span>')
    elif naissance:
        age = age_depuis(naissance)
        info("Naissance", f'<span class="nobr">{date_longue(naissance)}</span>'
             + (f'<span class="age">{age} ans</span>' if age else ""))
    else:
        info("Naissance", "")
    info("Taille", taille_affichee(bio.get("taille") or profil.get("taille_cm") or ""))
    info("Catégorie", echapper(categorie))
    # team sur toute la largeur, en dernier, avec le coach dessous s'il est connu
    coach = bio.get("coach", "")
    lignes_infos.append(
        '<div class="info info--large"><dt>Team</dt><dd>'
        + (echapper(bio.get("team") or profil.get("equipe", "")) or "?")
        + (f'<span class="coach">Coach : <span class="coach__nom">{echapper(coach)}</span></span>' if coach else "")
        + '</dd></div>')

    # prochain combat
    if prochain:
        _, c, adv, rec_adv = prochain
        lien_ev = c.get("lien_evenement", "")
        nom_ev = nom_evenement(c.get("evenement", ""), lien_ev)
        lieu = ville_depuis_lieu(c.get("lieu", ""))
        chip = chip_compte(c["date"])
        ceinture = " · titre en jeu" if c.get("titre") else ""
        adv_txt = echapper(nom_affiche(adv) if adv in PAGES_COMBATTANTS else adv)
        if adv in PAGES_COMBATTANTS:
            adv_txt = f'<a href="../{PAGES_COMBATTANTS[adv]}">{adv_txt}</a>'
        rec_txt = f" ({echapper(nettoyer_record(rec_adv))})" if rec_adv else ""
        bloc_prochain = f"""
    <p class="combat__ligne">{echapper(affichage)}<span class="vs">VS</span>{adv_txt}{rec_txt}</p>
    <p class="combat__meta">{echapper(nom_ev)} · {date_longue(c["date"])}{(" · " + echapper(lieu)) if lieu else ""}{ceinture}{f'<span class="chip">{chip}</span>' if chip else ""}</p>"""
    else:
        bloc_prochain = '\n    <p class="vide">Aucun combat annoncé pour le moment.</p>'

    # dernier combat
    dc = dernier_combat_de(nom, profil, resultats)
    if dc:
        res = (dc.get("resultat") or "").lower()
        classe = {"win": " combat__res--v", "loss": " combat__res--d"}.get(res, "")
        details = [echapper(dc.get("methode", ""))]
        if dc.get("round"):
            details.append(f'round {echapper(dc["round"])}')
        details = ", ".join(d for d in details if d)
        bloc_dernier = f"""
    <p class="combat__ligne"><span class="combat__res{classe}">{RESULTATS_FR.get(res, res.upper())}</span><span class="vs">VS</span>{echapper(dc.get("adversaire", ""))}</p>
    <p class="combat__meta">{details}{(" · " + echapper(nom_evenement(dc.get("evenement", "")))) if dc.get("evenement") else ""}{(" · " + date_longue(dc.get("date", ""))) if dc.get("date") else ""}</p>"""
    elif profil:
        bloc_dernier = '\n    <p class="vide">Pas encore de combat professionnel.</p>'
    else:
        bloc_dernier = ""   # pas de releve Sherdog : on ne sait pas

    section_dernier = ""
    if bloc_dernier:
        section_dernier = ('\n  <section class="bloc">\n'
                           '    <h2>Dernier combat</h2>' + bloc_dernier +
                           '\n  </section>')

    bloc_combats = ""
    if prochain:
        # meme carte que sur l'accueil, avec ce seul combat, repliee.
        # Les noms ne menent qu'aux fiches MMA Radar (pas a Sherdog).
        c = prochain[1]
        if c.get("adversaire_suivi") == nom:
            # le combattant de la fiche passe en premier nom
            c = dict(c)
            c["combattant"], c["adversaire_suivi"] = nom, c["combattant"]
            c["adversaire"] = c["adversaire_suivi"]
            for g, d in (("drapeau", "drapeau_adversaire"),
                         ("record_suivi", "record_adversaire"),
                         ("url_suivi", "url_adversaire")):
                c[g], c[d] = c.get(d, ""), c.get(g, "")
        ev = {"date": c["date"], "evenement": c.get("evenement", ""),
              "lieu": c.get("lieu", ""), "combats": [c]}
        bloc_combats = ('\n  <section class="carte" aria-label="Prochain combat">'
                        '\n    <h2>Prochain combat</h2>'
                        + bloc_evenement(ev, {}, infos or {}, False, c["date"],
                                         prefixe="../", nom_courant=nom)
                        + '\n  </section>\n')
    if FICHE_AVEC_COMBATS:
        bloc_combats = ('\n  <section class="bloc">\n'
                        '    <h2>Prochain combat</h2>' + bloc_prochain +
                        '\n  </section>\n' + section_dernier + '\n')

    texte_bio = lier_noms(bio.get("bio", "").strip(), nom)
    chemin = PAGES_COMBATTANTS[nom]
    url_page = f"{SITE_URL}/{chemin}"
    if FICHE_AVEC_COMBATS:
        titre = f"{affichage} : prochain combat, dernier résultat | MMA Radar"
    else:
        titre = f"{affichage} : fiche et parcours du combattant | MMA Radar"
    desc = f"{titre_fiche}"
    if surnom:
        desc += f" « {surnom} »"
    if FICHE_AVEC_COMBATS:
        desc += " : prochain combat, dernier résultat et parcours"
    else:
        desc += " : fiche et parcours du combattant de MMA"
    morceaux = [m for m in (categorie, f"palmarès pro {record}" if record else "") if m]
    if morceaux:
        desc += ". " + ", ".join(morceaux)
    desc += "."
    desc = echapper(desc).replace('"', "&quot;")
    titre_attr = echapper(titre).replace('"', "&quot;")

    personne = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": titre_fiche,
        "url": url_page,
        "jobTitle": "Combattant de MMA",
    }
    autres_noms = []
    for n in (surnom, affichage, (bio.get("nom_complet") or "").strip()):
        if n and n != titre_fiche and n not in autres_noms:
            autres_noms.append(n)
    if autres_noms:
        personne["alternateName"] = autres_noms
    if naissance:
        personne["birthDate"] = naissance
    if drapeau and drapeau in NOMS_PAYS:
        personne["nationality"] = {"@type": "Country", "name": NOMS_PAYS[drapeau]}
    if url_sherdog:
        personne["sameAs"] = [url_sherdog]
    jsonld = json.dumps(personne, ensure_ascii=False).replace("</", "<\\/")

    # sous le nom : surnom et palmares pro
    morceaux_titre = []
    if surnom:
        morceaux_titre.append(f"« {echapper(surnom)} »")
    if record:
        morceaux_titre.append(f'<span class="record">{echapper(record)}</span>')
    surnom_html = ('\n    <p class="surnom">'
                   + '<span class="sep">·</span>'.join(morceaux_titre) + "</p>"
                   if morceaux_titre else "")
    flag_titre = ""   # le drapeau figure deja sur la ligne Nationalite
    infos_html = "".join(lignes_infos)
    bloc_infos = (f"""
  <section class="bloc fiche-infos">
    <h2>Fiche</h2>
    <dl class="infos">{infos_html}</dl>
  </section>""" if infos_html else "")
    boutons = []
    if url_sherdog:
        boutons.append(
            f'<a class="bouton" href="{url_sherdog}" target="_blank" '
            f'rel="noopener" data-umami-event="Sherdog depuis fiche" '
            f'data-umami-event-combattant="{echapper(affichage)}">'
            f'Sherdog<span class="fleche"> &rarr;</span></a>')
    url_tapology = (bio.get("tapology") or "").strip()
    if url_tapology:
        personne.setdefault("sameAs", []).append(url_tapology)
        jsonld = json.dumps(personne, ensure_ascii=False).replace("</", "<\\/")
    else:
        # adresse exacte inconnue : on ouvre la recherche Tapology
        url_tapology = ("https://www.tapology.com/search?term="
                        + quote_plus(affichage) + "&mainSearchFilter=fighters")
    boutons.append(
        f'<a class="bouton" href="{echapper(url_tapology)}" target="_blank" '
        f'rel="noopener" data-umami-event="Tapology depuis fiche" '
        f'data-umami-event-combattant="{echapper(affichage)}">'
        f'Tapology<span class="fleche"> &rarr;</span></a>')
    url_insta = (bio.get("instagram") or "").strip().split("?")[0]
    if url_insta:
        boutons.append(
            f'<a class="bouton" href="{echapper(url_insta)}" target="_blank" '
            f'rel="noopener" data-umami-event="Instagram depuis fiche" '
            f'data-umami-event-combattant="{echapper(affichage)}">'
            f'Instagram<span class="fleche"> &rarr;</span></a>')
        personne.setdefault("sameAs", []).append(url_insta)
        jsonld = json.dumps(personne, ensure_ascii=False).replace("</", "<\\/")
    url_wiki = (bio.get("wikipedia") or "").strip()
    if url_wiki:
        boutons.append(
            f'<a class="bouton" href="{echapper(url_wiki)}" target="_blank" '
            f'rel="noopener" data-umami-event="Wikipedia depuis fiche" '
            f'data-umami-event-combattant="{echapper(affichage)}">'
            f'Wikipédia<span class="fleche"> &rarr;</span></a>')
        personne.setdefault("sameAs", []).append(url_wiki)
        jsonld = json.dumps(personne, ensure_ascii=False).replace("</", "<\\/")
    bloc_boutons = '\n  <p class="boutons">' + "".join(boutons) + '</p>\n'
    bloc_suivre = bloc_suivi(chemin, affichage)
    css_fond = (CSS_FOND.replace("url('fond.jpg')", "url('../fond.jpg')")
                if os.path.exists("fond.jpg") else "")

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{echapper(titre)}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url_page}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta property="og:type" content="profile">
<meta property="og:site_name" content="MMA Radar">
<meta property="og:locale" content="fr_FR">
<meta property="og:title" content="{titre_attr}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url_page}">
<meta property="og:image" content="{SITE_URL}/partage.jpg">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{titre_attr}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{SITE_URL}/partage.jpg">
<link rel="icon" href="../favicon.ico" sizes="any">
<link rel="icon" type="image/svg+xml" href="../icones/icone.svg">
<link rel="apple-touch-icon" sizes="180x180" href="../icones/icone-180.png">
<meta name="theme-color" content="#0f0f13">
<meta name="color-scheme" content="dark">
<script defer src="https://cloud.umami.is/script.js" data-website-id="20e687c1-5629-4138-9b0d-3255669e6390"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>{CSS_FICHE}{CSS_CARTE_FICHE}{css_fond}</style>
<script type="application/ld+json">{jsonld}</script>
</head>
<body>
<div class="wrap">
  <p class="haut"><a class="retour" href="../index.html">&larr; Tous les prochains combats</a></p>
  <header class="fiche">
    <h1>{echapper(titre_fiche)}{flag_titre}</h1>{surnom_html}
  </header>
{bloc_boutons}{bloc_suivre}{bloc_combats}
  <div class="colonnes">{bloc_infos}
  <section class="bloc bio">
    <h2>Parcours</h2>
    <p>{texte_bio}</p>
  </section>
  </div>

  <p class="liens"><a href="../index.html">Calendrier des combats des francophones</a></p>

  <footer>
    <p>Données issues de Sherdog. Les cartes évoluent, vérifie avant de bloquer ta soirée.</p>
    <p><a href="mailto:contact@mmaradar.fr">contact@mmaradar.fr</a></p>
  </footer>
</div>
{JS_SUIVI}
</body>
</html>
"""


# ---------------------------------------------------------------------
# Suivre un combattant : un calendrier par combattant, auquel on
# s'abonne. L'agenda du visiteur revient le lire tout seul, donc les
# nouveaux combats, l'heure et la chaine apparaissent sans rien faire.
# Le fichier garde la meme adresse pour toujours et n'est jamais
# supprime, sinon les abonnements casseraient.
# ---------------------------------------------------------------------
DOSSIER_SUIVI = "agenda/combattants"   # hors du nettoyage du dossier agenda
JOURS_HISTORIQUE = 365                 # combats passes gardes un an


def adresse_suivi(chemin_fiche):
    """combattants/jordan-zebo.html -> https://mmaradar.fr/agenda/combattants/jordan-zebo.ics"""
    slug = os.path.basename(chemin_fiche)[:-len(".html")]
    return f"{SITE_URL}/{DOSSIER_SUIVI}/{slug}.ics"


def bloc_suivi(chemin_fiche, affichage):
    https = adresse_suivi(chemin_fiche)
    webcal = "webcal://" + https.split("://", 1)[1]
    # Android et ordinateur : Google Agenda propose l'abonnement en un clic
    google = "https://calendar.google.com/calendar/r?cid=" + quote_plus(webcal)
    # Android : Google n'accepte plus l'abonnement en un clic sur telephone
    # (le lien ci-dessus affiche "ajoute" sans rien ajouter). Seule la page
    # "Ajouter a partir de l'URL" marche : on copie l'adresse et on ouvre
    # cette page dans Chrome, pour que l'appli Agenda ne l'intercepte pas.
    page_url = "https://calendar.google.com/calendar/u/0/r/settings/addbyurl"
    android = ("intent://" + page_url.split("://", 1)[1]
               + "#Intent;scheme=https;package=com.android.chrome;"
               + "S.browser_fallback_url=" + quote_plus(page_url) + ";end")
    nom = echapper(affichage)
    return f"""
  <div class="suivre"><div class="suivre__bloc">
    <a class="suivre__btn" href="{webcal}" data-https="{https}"
       data-umami-event="Suivre combattant" data-umami-event-combattant="{nom}">{ICONE_AGENDA}Suivre {nom}</a>
    <small>Ses prochains combats s'ajoutent tout seuls à ton agenda</small>
  </div></div>
  <div class="panneau" id="panneau-suivi" hidden>
    <div class="panneau__boite" role="dialog" aria-label="Suivre {nom}">
      <button class="panneau__fermer" type="button" aria-label="Fermer">&times;</button>
      <div class="panneau__apple" hidden>
        <p><b>Calendrier de {nom}</b></p>
        <p>Une fois l'abonnement accepté, ses combats apparaissent dans ton app
        Calendrier. L'heure et la chaîne s'ajoutent dès qu'elles sont connues.</p>
        <p><b>Pour recevoir un rappel</b> : laisse « Supprimer les alertes » désactivé.</p>
      </div>
      <div class="panneau__android" hidden>
        <p><b>Suivre {nom}</b></p>
        <ol class="etapes">
          <li><a class="panneau__google panneau__google--android" href="{page_url}" data-page="{android}">Ajouter à Google Agenda</a>
          L'adresse est copiée et Google Agenda s'ouvre.</li>
          <li>Colle l'adresse dans « URL de l'agenda », puis appuie sur « Ajouter l'agenda ».</li>
          <li>Dans l'appli Agenda : Paramètres, « {nom} · MMA Radar », active Synchroniser.
          Ajoute aussi une notification pour être prévenu.</li>
        </ol>
      </div>
      <div class="panneau__autre" hidden>
        <p><b>Suivre {nom}</b></p>
        <a class="panneau__google" href="{google}" target="_blank" rel="noopener">Ajouter à Google Agenda</a>
        <p class="panneau__petit">Pour être prévenu, ajoute une notification dans les paramètres
        de l'agenda. Sur Android, active aussi Synchroniser.</p>
        <p class="panneau__petit panneau__secours">Autre agenda (Outlook…) :
        <button class="panneau__copier" type="button">Copier l'adresse</button></p>
      </div>
    </div>
  </div>
"""


JS_SUIVI = r"""<script>
(function () {
  var btn = document.querySelector(".suivre__btn");
  var p = document.getElementById("panneau-suivi");
  if (!btn || !p) return;
  // iPhone, iPad et Mac savent s'abonner directement (lien webcal)
  var apple = /iPhone|iPad|iPod|Macintosh/.test(navigator.userAgent);
  var android = /Android/i.test(navigator.userAgent);
  btn.addEventListener("click", function (e) {
    if (!apple) e.preventDefault();
    p.querySelector(".panneau__apple").hidden = !apple;
    p.querySelector(".panneau__android").hidden = !android;
    p.querySelector(".panneau__autre").hidden = apple || android;
    p.hidden = false;
  });
  // Android : copie l'adresse, puis ouvre "Ajouter a partir de l'URL" dans Chrome
  var ga = p.querySelector(".panneau__google--android");
  if (ga) {
    ga.addEventListener("click", function (e) {
      e.preventDefault();
      var page = ga.dataset.page;
      function ouvrir() { window.location.href = page; }
      function secours() {
        var t = document.createElement("textarea");
        t.value = btn.dataset.https;
        document.body.appendChild(t);
        t.select();
        try { document.execCommand("copy"); } catch (err) {}
        document.body.removeChild(t);
        ouvrir();
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(btn.dataset.https).then(ouvrir, secours);
      } else {
        secours();
      }
    });
  }
  p.addEventListener("click", function (e) {
    if (e.target === p || e.target.closest(".panneau__fermer")) p.hidden = true;
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") p.hidden = true;
  });
  var copier = p.querySelector(".panneau__copier");
  copier.addEventListener("click", function () {
    function ok() { copier.textContent = "Adresse copiée ✓"; }
    function secours() {
      var t = document.createElement("textarea");
      t.value = btn.dataset.https;
      document.body.appendChild(t);
      t.select();
      try { document.execCommand("copy"); ok(); } catch (err) {}
      document.body.removeChild(t);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(btn.dataset.https).then(ok, secours);
    } else {
      secours();
    }
  });
})();
</script>"""


def _infos_combat(c, infos):
    """Heure et chaine saisies dans infos.json pour la soiree d'un combat."""
    lien = (c.get("lien_evenement") or "").strip()
    cle = (lien.rstrip("/") if lien else
           "|".join([c.get("date", ""), c.get("evenement", ""), c.get("lieu", "")]))
    d = infos.get(cle, {})
    return d if isinstance(d, dict) else {}


def _evenements_passes(chemin, limite):
    """Combats deja passes du fichier precedent, gardes en memoire un an."""
    try:
        with open(chemin, encoding="utf-8", newline="") as f:
            texte = f.read()
    except OSError:
        return []
    texte = texte.replace("\r\n ", "").replace("\r\n", "\n")
    aujourdhui = date.today().strftime("%Y%m%d")
    gardes = []
    for bloc in re.findall(r"BEGIN:VEVENT\n.*?END:VEVENT", texte, flags=re.S):
        m = re.search(r"^DTSTART[^:\n]*:(\d{8})", bloc, flags=re.M)
        if m and limite <= m.group(1) < aujourdhui:
            gardes.append(bloc.split("\n"))
    return gardes


def _evenement_suivi(nom, c, infos):
    """Lignes d'un combat a venir, pour le calendrier d'un combattant."""
    try:
        jour = datetime.strptime(c.get("date", ""), "%Y-%m-%d").date()
    except ValueError:
        return None
    if c.get("combattant") == nom:
        adv = c.get("adversaire_suivi") or c.get("adversaire", "")
    else:
        adv = c.get("combattant", "")
    soiree = nom_evenement(c.get("evenement", ""), c.get("lien_evenement", ""))
    diff = _infos_combat(c, infos)
    heure = (diff.get("heure") or "").strip()

    ident = re.sub(r"[^a-z0-9]+", "-", identifiant_combat(c).lower()).strip("-")
    lignes = ["BEGIN:VEVENT",
              f"UID:{ident}-{c['date']}@mmaradar.fr",
              "DTSTAMP:" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")]
    depart = instant_utc(c["date"], heure)
    if depart is not None:
        lignes.append("DTSTART:" + depart.strftime("%Y%m%dT%H%M%SZ"))
        lignes.append("DTEND:" + (depart + timedelta(hours=3))
                      .strftime("%Y%m%dT%H%M%SZ"))
        rappel, texte_rappel = "-PT1H", "Le combat commence dans une heure"
    else:
        lignes.append("DTSTART;VALUE=DATE:" + jour.strftime("%Y%m%d"))
        lignes.append("DTEND;VALUE=DATE:"
                      + (jour + timedelta(days=1)).strftime("%Y%m%d"))
        rappel, texte_rappel = "PT9H", "C'est aujourd'hui"
    lignes.append("SUMMARY:" + _ics_echapper(
        f"{nom_affiche(nom)} vs {nom_affiche(adv)} · {soiree}"))
    if c.get("lieu"):
        lignes.append("LOCATION:" + _ics_echapper(c["lieu"]))
    details = []
    details += lignes_diffusion("Diffusion", diff.get("chaine"), diff.get("lien"), heure)
    details += lignes_diffusion("Prelims", diff.get("prelim"), diff.get("lien_prelim"),
                                (diff.get("heure_prelim") or "").strip())
    details.append(f"Fiche du combattant : {SITE_URL}/{PAGES_COMBATTANTS[nom]}")
    lignes.append("DESCRIPTION:" + _ics_echapper("\n".join(details)))
    lignes += ["BEGIN:VALARM", "ACTION:DISPLAY",
               "DESCRIPTION:" + _ics_echapper(texte_rappel),
               "TRIGGER:" + rappel, "END:VALARM", "END:VEVENT"]
    return lignes


def ecrire_agendas_suivi(combats):
    """Un calendrier par combattant qui a une fiche (bouton Suivre)."""
    if not PAGES_COMBATTANTS:
        return
    infos = charger_json("infos.json")
    infos = infos if isinstance(infos, dict) else {}
    os.makedirs(DOSSIER_SUIVI, exist_ok=True)
    limite = (date.today() - timedelta(days=JOURS_HISTORIQUE)).strftime("%Y%m%d")
    aujourdhui = date.today().isoformat()

    for nom, chemin_fiche in PAGES_COMBATTANTS.items():
        fichier = os.path.join(DOSSIER_SUIVI,
                               os.path.basename(chemin_fiche)[:-len(".html")] + ".ics")
        evenements = _evenements_passes(fichier, limite)
        vus = {l for ev in evenements for l in ev if l.startswith("UID:")}
        for c in combats:
            if c.get("annule") or (c.get("date") or "") < aujourdhui:
                continue
            if nom not in (c.get("combattant"), c.get("adversaire_suivi")):
                continue
            ev = _evenement_suivi(nom, c, infos)
            if ev and ev[1] not in vus:
                vus.add(ev[1])
                evenements.append(ev)

        lignes = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//MMA Radar//FR",
                  "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
                  "X-WR-CALNAME:" + _ics_echapper(f"{nom_affiche(nom)} · MMA Radar"),
                  "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
                  "X-PUBLISHED-TTL:PT6H"]
        for ev in evenements:
            lignes += ev
        lignes.append("END:VCALENDAR")
        with open(fichier, "w", encoding="utf-8", newline="") as f:
            f.write("\r\n".join(_ics_plier(l) for l in lignes) + "\r\n")


def ecrire_fiches(combats, bios, profils, fiches, resultats):
    """Ecrit une page par combattant ayant une bio, et efface les autres."""
    if not PAGES_COMBATTANTS and not os.path.isdir("combattants"):
        return
    os.makedirs("combattants", exist_ok=True)
    voulues = {os.path.basename(p) for p in PAGES_COMBATTANTS.values()}
    for f in os.listdir("combattants"):
        if f.endswith(".html") and f not in voulues:
            os.remove(os.path.join("combattants", f))

    infos = charger_json("infos.json")
    infos = infos if isinstance(infos, dict) else {}
    for nom, chemin in PAGES_COMBATTANTS.items():
        html = page_fiche(nom, bios.get(nom, {}), profils.get(nom, {}),
                          combats, resultats, fiches.get(nom, ""), infos)
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(html)
    if PAGES_COMBATTANTS:
        print(f"{len(PAGES_COMBATTANTS)} fiche(s) combattant ecrite(s) "
              f"dans combattants/")
        sans_profil = [n for n in PAGES_COMBATTANTS if n not in profils]
        if sans_profil:
            print("   sans releve Sherdog (lance profils.py) : "
                  + ", ".join(sans_profil))


# Combats saisis a la main, pour les petites soirees que Sherdog tarde a
# remplir. Des que Sherdog affiche un combat pour le meme combattant a la
# meme date, l'entree manuelle est ignoree : pas de doublon, rien a
# supprimer. Les entrees dont la date est passee ne s'affichent plus.
ADVERSAIRE_INCONNU = "À déterminer"


def ajouter_combats_manuels(combats, fiches):
    donnees = charger_json("combats_manuels.json")
    if donnees in (None, "ERREUR"):
        return combats
    liste = donnees.get("combats", []) if isinstance(donnees, dict) else donnees

    aujourdhui = date.today().isoformat()
    deja = {(normaliser(c.get("combattant", "")), c.get("date", ""))
            for c in combats if not c.get("annule")}

    for m in liste:
        if not isinstance(m, dict):
            continue
        nom = (m.get("combattant") or "").strip()
        jour = (m.get("date") or "").strip()
        if not nom or len(jour) != 10 or jour < aujourdhui:
            continue
        if (normaliser(nom), jour) in deja:
            print(f"   {nom} : Sherdog a pris le relais, saisie manuelle ignoree")
            continue

        combat = {
            "combattant": nom,
            "url_suivi": fiches.get(nom, ""),
            "url_adversaire": "",
            "drapeau": (m.get("drapeau") or "").strip().lower(),
            "record_suivi": (m.get("record") or "").strip(),
            "titre": bool(m.get("titre")),
            "categorie": (m.get("categorie") or "").strip(),
            "ordre": 500,
            "drapeau_adversaire": (m.get("drapeau_adversaire") or "").strip().lower(),
            "adversaire": (m.get("adversaire") or "").strip() or ADVERSAIRE_INCONNU,
            "record_adversaire": "",
            "evenement": (m.get("evenement") or "").strip(),
            "date": jour,
            "lieu": (m.get("lieu") or "").strip(),
            "lien_evenement": (m.get("lien_evenement") or "").strip(),
        }
        combats.append(combat)
        deja.add((normaliser(nom), jour))
        print(f"   saisie manuelle : {nom}, {jour}")
    return combats


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

    bios = charger_json("bios.json")
    if bios == "ERREUR":
        print("bios.json illisible : fiches combattants non mises a jour.")
    bios = {} if bios in (None, "ERREUR") else bios
    profils = charger_json("profils.json")
    profils = {} if profils in (None, "ERREUR") else profils
    PAGES_COMBATTANTS.clear()
    for nom, b in bios.items():
        if (not nom.startswith("_") and isinstance(b, dict)
                and (b.get("bio") or "").strip()):
            PAGES_COMBATTANTS[nom] = f"combattants/{slug_combattant(nom)}.html"

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

    combats = aligner_soirees(combats)
    combats = ajouter_combats_manuels(combats, fiches)
    combats = fusionner_duels(combats)
    combats = retirer_annules_remplaces(combats)
    mois_groupes = grouper(combats)
    evenements = [ev for _, evs in mois_groupes for ev in evs]
    infos = assurer_infos(evenements)

    total = sum(1 for c in combats if not c.get("annule"))
    html = construire_html(mois_groupes, fiches, infos, total,
                           resultats_recents)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    ecrire_fiches(combats, bios, profils, fiches, resultats_recents)
    ecrire_agendas_suivi(combats)
    ecrire_robots_et_sitemap(sorted(PAGES_COMBATTANTS.values()))

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
