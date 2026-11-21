"""
Releve sur Sherdog les infos des combattants qui ont une fiche.

Ne lit que les combattants presents dans bios.json (ceux pour qui tu as
ecrit une bio). Pour chacun : surnom, date de naissance, taille,
categorie, equipe, nationalite, palmares pro et dernier combat.

A lancer avant generer_site.py :
    python profils.py
    python generer_site.py

Produit profils.json, que generer_site.py utilise pour les fiches.
"""

import json
import re
import time
import unicodedata

import requests
from bs4 import BeautifulSoup

BASE = "https://www.sherdog.com"
PAUSE = 2  # secondes entre deux pages, pour rester poli avec le site

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

CATEGORIES_POIDS = [
    "Light Heavyweight", "Super Heavyweight", "Heavyweight",
    "Middleweight", "Welterweight", "Featherweight", "Bantamweight",
    "Lightweight", "Flyweight", "Strawweight", "Atomweight", "Catchweight",
]

MOIS_SHERDOG = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}

ESSAIS = 3
ATTENTES = [5, 15, 30]


def charger(nom, defaut):
    try:
        with open(nom, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return defaut
    except json.JSONDecodeError:
        print(f"{nom} est illisible (virgule ou guillemet en trop ?)")
        return None


def normaliser(texte):
    texte = unicodedata.normalize("NFKD", texte or "")
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texte).strip().lower()


def recuperer(url):
    for tentative in range(ESSAIS):
        try:
            reponse = requests.get(url, headers=HEADERS, timeout=45)
            reponse.raise_for_status()
            return BeautifulSoup(reponse.text, "html.parser")
        except requests.RequestException as erreur:
            if tentative < ESSAIS - 1:
                attente = ATTENTES[tentative]
                print(f"   reseau capricieux ({type(erreur).__name__}), "
                      f"nouvelle tentative dans {attente}s")
                time.sleep(attente)
            else:
                print(f"   echec apres {ESSAIS} tentatives : {url}")
    return None


def date_iso(texte):
    """'Aug 17, 1998', 'Aug / 17 / 1998' ou '1998-08-17' -> '1998-08-17'"""
    texte = texte or ""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", texte)
    if m:
        return m.group(0)
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s*/?\s*(\d{1,2}),?\s*/?\s*(\d{4})",
                  texte)
    if not m:
        return ""
    mois = MOIS_SHERDOG.get(m.group(1).lower())
    if not mois:
        return ""
    return f"{m.group(3)}-{mois:02d}-{int(m.group(2)):02d}"


def lire_taille(soup):
    """Taille en cm, ou "" si Sherdog ne la donne pas (il affiche 0'0")."""
    balise = soup.select_one('[itemprop="height"]')
    zone = balise.parent.get_text(" ", strip=True) if balise else ""
    m = re.search(r"(\d{3}(?:\.\d+)?)\s*cm", zone)
    if m:
        cm = round(float(m.group(1)))
        return str(cm) if cm > 100 else ""
    texte = balise.get_text(strip=True) if balise else ""
    m = re.search(r"(\d)\s*'\s*(\d{1,2})", texte)
    if m and (int(m.group(1)) or int(m.group(2))):
        return str(round((int(m.group(1)) * 12 + int(m.group(2))) * 2.54))
    return ""


def lire_categorie(soup):
    lien = soup.select_one('a[href*="weightclass"]')
    if lien:
        texte = lien.get_text(" ", strip=True)
        for cat in CATEGORIES_POIDS:
            if cat.lower() in texte.lower():
                return cat
    bloc = soup.select_one(".association-class")
    texte = bloc.get_text(" ", strip=True) if bloc else ""
    for cat in CATEGORIES_POIDS:
        if cat.lower() in texte.lower():
            return cat
    return ""


def lire_equipe(soup):
    balise = soup.select_one('[itemprop="memberOf"] [itemprop="name"]')
    if balise:
        return balise.get_text(" ", strip=True)
    balise = soup.select_one('[itemprop="memberOf"]')
    if balise:
        return balise.get_text(" ", strip=True)
    lien = soup.select_one(".association-class a[href*='/stats/']")
    if lien and "weightclass" not in lien.get("href", ""):
        return lien.get_text(" ", strip=True)
    return ""


def lire_historique_pro(soup):
    """Palmares pro (calcule ligne par ligne) et dernier combat."""
    tableau = soup.select_one("div.fight_history table.new_table.fighter")
    if tableau is None:
        tableau = soup.select_one("table.new_table.fighter")
    if tableau is None:
        return "", {}

    v = d = n = 0
    dernier = {}
    for ligne in tableau.select("tr")[1:]:
        cellules = ligne.select("td")
        if len(cellules) < 4:
            continue
        badge = ligne.select_one("span.final_result")
        resultat = badge.get_text(strip=True).lower() if badge else ""
        if resultat == "win":
            v += 1
        elif resultat == "loss":
            d += 1
        elif resultat == "draw":
            n += 1
        elif resultat not in ("nc", "no contest"):
            continue

        if not dernier:
            lien_adv = cellules[1].select_one("a")
            texte_event = cellules[2].get_text(" ", strip=True)
            lien_ev = cellules[2].select_one("a")
            b = cellules[3].select_one("b")
            methode = (b.get_text(" ", strip=True) if b
                       else cellules[3].get_text(" ", strip=True)[:40])
            dernier = {
                "resultat": resultat,
                "adversaire": (lien_adv.get_text(strip=True) if lien_adv
                               else cellules[1].get_text(strip=True)),
                "evenement": (lien_ev.get_text(strip=True) if lien_ev
                              else texte_event),
                "lien_evenement": (BASE + lien_ev["href"]
                                   if lien_ev and lien_ev.get("href", "").startswith("/")
                                   else ""),
                "date": date_iso(texte_event),
                "methode": methode,
                "round": (cellules[4].get_text(strip=True)
                          if len(cellules) > 4 else ""),
                "temps": (cellules[5].get_text(strip=True)
                          if len(cellules) > 5 else ""),
            }

    return f"{v}-{d}-{n}", dernier


def lire_profil(url):
    soup = recuperer(url)
    if soup is None:
        return None

    surnom = ""
    balise = soup.select_one(".nickname em") or soup.select_one(".nickname")
    if balise:
        surnom = balise.get_text(strip=True).strip('"“” ')

    naissance = ""
    balise = soup.select_one('[itemprop="birthDate"]')
    if balise:
        naissance = date_iso(balise.get("content", "")
                             or balise.get_text(" ", strip=True))

    drapeau = ""
    img = soup.select_one('img[src*="img/flags/big/"]')
    if img and img.get("src"):
        drapeau = img["src"].rsplit("/", 1)[-1].split(".")[0].lower()

    record, dernier = lire_historique_pro(soup)

    return {
        "url": url,
        "surnom": surnom,
        "naissance": naissance,
        "taille_cm": lire_taille(soup),
        "categorie": lire_categorie(soup),
        "equipe": lire_equipe(soup),
        "drapeau": drapeau,
        "record": record,
        "dernier_combat": dernier,
    }


def main():
    bios = charger("bios.json", {})
    if bios is None:
        return
    adresses = charger("fighters.json", {}) or {}
    anciens = charger("profils.json", {}) or {}

    noms = [n for n in bios if not n.startswith("_")]
    if not noms:
        print("bios.json est vide : aucune fiche a preparer.")
        return

    sortie = {}
    for nom in noms:
        url = adresses.get(nom, "")
        if not url:
            # on tolere une difference d'accent ou de majuscule
            for k, v in adresses.items():
                if normaliser(k) == normaliser(nom):
                    url = v
                    break
        if not url:
            print(f"- {nom} : adresse Sherdog inconnue (absent de fighters.json)")
            if nom in anciens:
                sortie[nom] = anciens[nom]
            continue

        print(f"- {nom}")
        profil = lire_profil(url)
        if profil is None:
            print("   page inaccessible, on garde le releve precedent")
            if nom in anciens:
                sortie[nom] = anciens[nom]
            continue

        manquants = [k for k in ("surnom", "naissance", "taille_cm",
                                 "categorie", "equipe", "record")
                     if not profil.get(k)]
        dc = profil["dernier_combat"]
        print(f"   palmares {profil['record'] or '?'}, "
              f"dernier combat : {dc.get('date', '?') if dc else 'aucun'}")
        if manquants:
            print(f"   non trouve sur Sherdog : {', '.join(manquants)}")
        sortie[nom] = profil
        time.sleep(PAUSE)

    with open("profils.json", "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=2)
    print(f"profils.json ecrit : {len(sortie)} combattant(s)")


if __name__ == "__main__":
    main()
