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
from datetime import date, datetime, timedelta

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
    ("contender series", "dwcs", "CONTENDER SERIES"),
    ("dana white", "dwcs", "CONTENDER SERIES"),
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
]

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


def normaliser(texte):
    """Minuscules, sans accents ni tirets. Sert a comparer les noms."""
    decompose = unicodedata.normalize("NFD", texte)
    sans_accent = "".join(c for c in decompose if unicodedata.category(c) != "Mn")
    for signe in "-'\u2019.":
        sans_accent = sans_accent.replace(signe, " ")
    return " ".join(sans_accent.lower().split())


def nettoyer_record(record):
    """'23-2-0 (WIN-LOSS-DRAW)' -> '23-2-0'"""
    return record.split("(")[0].strip()


def echapper(texte):
    return (texte.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;"))


def drapeau_html(iso):
    if not iso:
        return ""
    return (f'<img class="flag" src="https://flagcdn.com/h20/{iso}.png" '
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


def orga_de(evenement):
    nom = evenement.lower()
    for mot, fichier, libelle in ORGAS:
        if mot in nom:
            return fichier, libelle
    return "mma", "MMA"


def logo_orga(evenement):
    fichier, libelle = orga_de(evenement)
    for ext in ("svg", "png", "webp"):
        chemin = f"logos/{fichier}.{ext}"
        if os.path.exists(chemin):
            return f'<img class="ev__logo" src="{chemin}" alt="{libelle}">'
    return f'<span class="ev__badge">{libelle}</span>'


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
    "dana white's contender series": "CONTENDER SERIES",
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

    # 1. nom d'organisation a rallonge -> sigle, ou qu'il apparaisse
    for long, court in RACCOURCIS.items():
        resultat = re.sub(r"\b" + re.escape(long) + r"\b", court,
                          resultat, flags=re.IGNORECASE)

    # 2. mots doubles ("PFL PFL Tampa" quand l'organisation precede son sigle)
    mots = []
    for m in resultat.split():
        if mots and mots[-1].lower().strip(":") == m.lower().strip(":"):
            continue
        mots.append(m)
    resultat = " ".join(mots).strip(" :-")

    # 3. on retire l'affiche ("... : Untel vs Untel"), redondante ici
    for sep in (" - ", ": ", " : "):
        if sep in resultat:
            gauche, droite = resultat.rsplit(sep, 1)
            if " vs" in droite.lower():
                resultat = gauche.strip(" :-")
                break

    return resultat


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
                a["drapeau_adversaire"] = combats[j].get("drapeau", "")
                break
        gardes.append(a)

    return gardes


def grouper(combats):
    evenements = {}
    for c in combats:
        cle = (c.get("date", ""), c.get("evenement", ""), c.get("lieu", ""))
        evenements.setdefault(cle, []).append(c)

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

  body {
    margin: 0;
    padding: 0 1.2rem 4rem;
    background-color: var(--noir);
    background-image: repeating-linear-gradient(
      135deg, rgba(255,255,255,0.016) 0 2px, transparent 2px 16px);
    color: var(--blanc);
    font-family: Inter, system-ui, sans-serif;
  }

  .wrap { max-width: 1080px; margin: 0 auto; }

  header.top { padding: 2.6rem 0 1.6rem; text-align: center; }

  h1 {
    font-family: Oswald, sans-serif;
    font-weight: 700;
    font-size: clamp(1.8rem, 4.5vw, 2.8rem);
    text-transform: uppercase;
    letter-spacing: 0.01em;
    margin: 0;
  }

  h1 em { color: var(--or); font-style: normal; }

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
    height: 24px;
    width: auto;
    max-width: 106px;
    object-fit: contain;
    filter: brightness(0) invert(1);
    opacity: 0.92;
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

  summary.ev__bar:hover .ev__chev { transform: scale(1.25); }
  details[open] > summary.ev__bar:hover .ev__chev { transform: rotate(90deg) scale(1.25); }

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
    grid-template-columns: 92px 1fr auto 1fr;
    align-items: center;
    gap: 0.9rem;
    background: #131318;
    border: 1px solid #3a3a45;
    border-radius: 10px;
    padding: 0.5rem 1.2rem;
    margin: 0 0 0.55rem;
    transform: skew(-8deg);
  }

  .fight .ck:nth-child(2) { justify-content: flex-end; text-align: right; }

  .fight__col { display: flex; flex-direction: column; min-width: 0; }

  .fight .ck:nth-child(2) .fight__col { align-items: flex-end; }

  .fight__nom {
    font-family: Oswald, sans-serif;
    font-weight: 500;
    font-size: 0.98rem;
    text-transform: uppercase;
    letter-spacing: 0.02em;
    color: var(--blanc);
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

  .ev__diffusion { color: var(--gris); }

  .flag { height: 14px; border-radius: 2px; flex: none; }

  .empty { color: var(--gris); text-align: center; margin: 3rem 0; }

  footer {
    margin-top: 3.5rem;
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
    .fight .ck:nth-child(2) .fight__col { align-items: flex-start; }
    .fight__vs { justify-self: start; }
    .fight__cat { flex-direction: row; }
    .jchip { display: none; }
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
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    gap: 0.25rem;
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
  details.recap { max-width: 800px; margin: 1.8rem auto 0; }

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

  .recap__nb { color: var(--or); font-weight: 700; }
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
    color: #6a6a74;
    font-size: 0.72rem;
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


def bloc_evenement(ev, fiches, infos, ouvert, prochaine_date):
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
        noms.append(echapper(c["combattant"]))
        if c.get("adversaire_suivi"):
            noms.append(echapper(c["adversaire_suivi"]))
    noms_avec = ", ".join(noms)

    lien = ev["combats"][0].get("lien_evenement", "")
    orga_cle, _ = orga_de(ev["evenement"])
    tous_noms = []
    for c in ev["combats"]:
        tous_noms.append(normaliser(c["combattant"]))
        tous_noms.append(normaliser(c.get("adversaire_suivi")
                                    or c.get("adversaire", "")))
    noms_data = "|".join(n for n in tous_noms if n)

    jtxt = chip_compte(ev["date"])
    classe_chip = "jchip jchip--hot" if ev["date"] == prochaine_date else "jchip"
    chip_html = f'<span class="{classe_chip}">{jtxt}</span>' if jtxt else ""

    lignes = []
    for c in ev["combats"]:
        nom = echapper(c["combattant"])
        flag = drapeau_html(c.get("drapeau", ""))
        url = fiches.get(c["combattant"], "")
        if url:
            lien_nom = (f'<a class="fight__nom fight__nom--suivi" href="{url}" '
                        f'target="_blank" rel="noopener">{nom}</a>')
        else:
            lien_nom = f'<span class="fight__nom fight__nom--suivi">{nom}</span>'

        rec_suivi = echapper(nettoyer_record(c.get("record_suivi", "")))
        rec_adv = echapper(nettoyer_record(c.get("record_adversaire", "")))
        rec_suivi_html = f'<span class="fight__rec">{rec_suivi}</span>' if rec_suivi else ""
        rec_adv_html = f'<span class="fight__rec">{rec_adv}</span>' if rec_adv else ""

        annule = bool(c.get("annule"))
        belt = "" if annule else (CEINTURE if c.get("titre") else "")

        # Si l'adversaire fait aussi partie de la liste suivie, on affiche
        # son nom tel qu'on l'ecrit, son drapeau, et on le rend cliquable.
        nom_adv = c.get("adversaire_suivi") or c["adversaire"]
        url_adv = fiches.get(c.get("adversaire_suivi", ""), "")
        flag_adv = drapeau_html(c.get("drapeau_adversaire", ""))
        classe_adv = "fight__nom fight__nom--suivi" if url_adv else "fight__nom"
        if url_adv:
            bloc_adv = (f'<a class="{classe_adv}" href="{url_adv}" '
                        f'target="_blank" rel="noopener">{echapper(nom_adv)}</a>')
        else:
            bloc_adv = f'<span class="{classe_adv}">{echapper(nom_adv)}</span>'

        cat = echapper(c.get("categorie", ""))
        chip_rep = ""
        if c.get("reporte_depuis"):
            chip_rep = (f'<span class="chip--reporte" title="initialement '
                        f'le {echapper(c["reporte_depuis"])}">REPORTÉ</span>')

        classe_fight = "fight fight--annule" if annule else "fight"
        vs = ('<span class="fight__vs fight__vs--annule">ANNULÉ</span>'
              if annule else '<span class="fight__vs">VS</span>')

        lignes.append(f"""
        <div class="{classe_fight}">
          <span class="ck fight__cat">{cat}{chip_rep}</span>
          <span class="ck">{belt}{flag}<span class="fight__col">{lien_nom}{rec_suivi_html}</span></span>
          <span class="ck">{vs}</span>
          <span class="ck"><span class="fight__col">{bloc_adv}{rec_adv_html}</span>{flag_adv}{belt}</span>
        </div>""")

    lien_html = ""
    if lien:
        lien_html = (f'<a href="{lien}" target="_blank" rel="noopener">'
                     f'Carte complète &rarr;</a>')

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
        <span class="ck"><span class="ev__nom">{echapper(nom_evenement(ev["evenement"], lien))}</span></span>
        <span class="ck">{flag_event}<span class="ev__ville">{ville}</span></span>
        <span class="ck ev__avec"><span class="ev__avec-txt">
          <span class="ev__avec-label">AVEC&nbsp;: </span>
          <span class="ev__avec-noms">{noms_avec}</span>
        </span></span>
        <span class="ck">{chip_html}</span>
        <span class="ck"><span class="ev__chev">&#9656;</span></span>
      </summary>
      <div class="ev__body">{"".join(lignes)}
        <div class="ev__foot">
          {gauche}
          {lien_html}
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
        nom = echapper(r.get("combattant", ""))
        url = fiches.get(r.get("combattant", ""), "")
        nom_html = (f'<a class="rl__lien" href="{url}" target="_blank" '
                    f'rel="noopener">{nom}</a>') if url else nom

        lignes.append(f"""
      <div class="rl">
        <span class="rl__date">{dtxt}</span>
        {badge}
        <span class="rl__nom">{nom_html} <em>vs {echapper(r.get("adversaire", ""))}</em></span>
        <span class="rl__meth">{echapper(r.get("methode", ""))}</span>
        <span class="rl__ev">{echapper(nom_evenement(r.get("evenement", "")))}</span>
      </div>""")

    return f"""
  <details class="recap">
    <summary class="recap__bar">DERNIERS RÉSULTATS
      <span class="recap__nb">{len(recents)}</span>
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
  if (!champ) return;

  champ.addEventListener("input", function () {
    var q = norm(champ.value || "");
    document.querySelectorAll("details.ev").forEach(function (ev) {
      var visible = !q || norm(ev.dataset.noms || "").indexOf(q) !== -1;
      ev.style.display = visible ? "" : "none";
      if (q) ev.open = visible;
    });
    document.querySelectorAll("main section").forEach(function (sec) {
      var un = sec.querySelector("details.ev:not([style*='display: none'])");
      sec.style.display = un ? "" : "none";
    });
  });
})();
</script>"""


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
            blocs.append(bloc_evenement(ev, fiches, infos, False,
                                        prochaine_date))
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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prochains combats des francophones en MMA</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>{CSS}{css_fond}</style>
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

  <footer>
    Données issues de Sherdog. Les cartes évoluent, vérifie avant de bloquer ta soirée.
  </footer>

</div>
{JS}
</body>
</html>
"""


VERSION = 15


def main():
    print(f"generer_site v{VERSION}")
    combats = charger_json("combats.json")
    if combats is None:
        print("combats.json introuvable. Lance d'abord mma_tracker.py")
        return
    if combats == "ERREUR":
        print("combats.json illisible. Relance mma_tracker.py")
        return

    fiches = charger_json("fighters.json")
    fiches = {} if fiches in (None, "ERREUR") else fiches

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
    if not os.path.exists("fond.jpg"):
        print("fond.jpg absent : fond texture simple utilise.")


if __name__ == "__main__":
    main()
