"""
Recupere les combats a venir des combattants de la liste depuis Sherdog.

Premier lancement : le script cherche chaque combattant et memorise son
adresse dans fighters.json. Les fois suivantes il ira directement.

Resultat : affichage dans la console + fichier combats.json
"""

import json
import os
import re
import time
import unicodedata
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------
# La liste. Pour ajouter quelqu'un, ecris son nom dans cette liste.
# ---------------------------------------------------------------
COMBATTANTS = [
    "Ciryl Gane",
    "Nassourdine Imavov",
    "Benoit Saint Denis",
    "Manon Fiorot",
    "Salahdine Parnasse",
    "Morgan Charriere",
    "William Gomis",
    "Fares Ziam",
    "Oumar Sy",
    "Nora Cornolle",
    "Kevin Jousset",
    "Losene Keita",
    "Matthieu Letho Duclos",
    "Francis Ngannou",
    "Cedric Doumbe",
    "Taylor Lapilus",
    "Mansour Barnaoui",
    "Asael Adjoudj",
    "Baysangur Chamsoudinov",
    "Paul Denis Navero",
    "Abdoul Abdouraguimov",
    "Jordan Zebo",
    "Axel Sola",
    "Wilson Varela",
    "Ilian Bouafia",
    "Ramzan Jembiev",
    "Yanis Ghemmouri",
    "Alex Lohore",
    "Laid Zerhouni",
    "Mickael Groguhe",
    "Yazid Chouchane",
    "Ylies Djiroun",
    "Yves Landu",
    "Romain Debienne",
    "Anthony Salamone",
    "Nell Ariano",
    "Jorick Montagnac",
    "Damien Lapilus",
    "Moktar Benkaci",
    "Gregory Babene",
    "Nicolas Leblond",
    "Dimitry Solimeis",
    "Jason Ponet",
    "Amaury Wako-Zabo",
    "Alioune Nahaye",
    "Brice Picaud",
    "Thibault Gouti",
    "Davy Gallon",
    "Mathys Duragrin",
    "Mickael Lebout",
    "Hugo Deux",
    "Amin Ayoub",
    "Alexis Nicolas",
    "Adam Meskini",
    "Alfan Rocher Labes",
    "Mahio Campanella",
    "Eva Dourthe",
    "Aymard Guih",
    "Zakaria Hamou",
    "Youcef Ouabbas",
    "Souheil Kaouchen",
    "Noah Gugnon",
    "Anthony Morel",
    "Baris Adiguzel",
    "Bourama Camara",
    "Dylan Salvador",
    "Sofiane Bouafia",
    "Mehdi Saadi",
    "Anthony Dizy",
    "Atilla Kobas",
    "Elias Mahmoudi",
    "Sofiane Boukichou",
    "Fabacary Diatta",
    "Aboubakar Younousov",
    "Turpal Younousov",
    # Belgique
    "Bolaji Oki",
    "Patrick Habirora",
    "Khamzat Abaev",
    "Movsar Ibragimov",
    "Boris Atangana",
    "Donovan Desmae",
    "Youssef Boughanem",
    "Yassine Boughanem",
    "Jimmy Vienot",
    "Moustapha Aida",
    "Daguir Imavov",
    "Anzor Baybatyrov",
    "Souhil Arezki",
    "Alan Baudot",
    "Jade Jorand",
    "Oumar Kane",
    "Mathilde Aschenbrenner",
    "Marvin Caperan",
    "Nimo Djagbo",
    "Delphine Benouaich",
    "Anthony Nantois",
    "Theo Ulrich",
    "Modibo Diakite",
    "Vincent del Guerra",
    "Wissame Akhmouch",
    "Moustapha Diakhate",
    "Jacky Jeanne",
    "Benoit Prigent",
    "Alou Camara",
    "Alvi Dasuyev",
    "Walid Masmoudi",
    "Pierre Manzo",
    "Samba Sima",
    "Allan Landouzy",
    "Oualy Tandia",
    "Alexandra Tekenah",
    "Bafode Gassama",
    "Arnaud Prigent",
    "Arthur Demonceaux",
    "Mehdi Ben Lakhdhar",
    "Kevin Ruart",
    "Leopold Goi",
    "Michael Aljarouj",
    "Ghiles Oudelha",
    "Virgil Augen",
    "Xavier Lessou",
    "Oceane Samson",
]

# ---------------------------------------------------------------
# Exceptions : quand Sherdog ecrit le nom autrement, on donne
# directement l'adresse de la fiche. Format :
#     "Nom dans ma liste": "adresse de la fiche Sherdog",
# ---------------------------------------------------------------
FICHES_MANUELLES = {
    "Benoit Saint Denis": "https://www.sherdog.com/fighter/Benoit-St-Denis-317103",
    "Baysangur Chamsoudinov": "https://www.sherdog.com/fighter/Baissangour-Chamsoudinov-340851",
    "Damien Lapilus": "https://www.sherdog.com/fighter/Damien-Lapilus-87477",
    "Paul Denis Navero": "https://www.sherdog.com/fighter/Paul-Denis-Navero-408149",
    "Jimmy Vienot": "https://www.sherdog.com/fighter/Jimmy-Vienot-391216",
    "Moustapha Aida": "https://www.sherdog.com/fighter/Moustapha-Aida-250043",
    "Daguir Imavov": "https://www.sherdog.com/fighter/Daguir-Imavov-131617",
    "Souhil Arezki": "https://www.sherdog.com/fighter/Souhil-Arezki-395375",
    "Alan Baudot": "https://www.sherdog.com/fighter/Alan-Baudot-138183",
    "Jade Jorand": "https://www.sherdog.com/fighter/Jade-Jorand-375539",
    "Oumar Kane": "https://www.sherdog.com/fighter/Oumar-Kane-350661",
    "Mathilde Aschenbrenner": "https://www.sherdog.com/fighter/Mathilde-Aschenbrenner-403778",
    "Marvin Caperan": "https://www.sherdog.com/fighter/Marvin-Caperan-425239",
    "Nimo Djagbo": "https://www.sherdog.com/fighter/Nimo-Djagbo-425229",
    "Delphine Benouaich": "https://www.sherdog.com/fighter/Delphine-Benouaich-413666",
    "Anthony Nantois": "https://www.sherdog.com/fighter/Anthony-Nantois-399819",
    "Theo Ulrich": "https://www.sherdog.com/fighter/Theo-Ulrich-397608",
    "Modibo Diakite": "https://www.sherdog.com/fighter/Modibo-Diakite-440031",
    "Vincent del Guerra": "https://www.sherdog.com/fighter/Vincent-del-Guerra-57907",
    "Wissame Akhmouch": "https://www.sherdog.com/fighter/Wissame-Akhmouch-268781",
    "Moustapha Diakhate": "https://www.sherdog.com/fighter/Moustapha-Diakhate-413692",
    "Jacky Jeanne": "https://www.sherdog.com/fighter/Jacky-Jeanne-400010",
    "Benoit Prigent": "https://www.sherdog.com/fighter/Benoit-Prigent-289763",
    "Alou Camara": "https://www.sherdog.com/fighter/Alou-Camara-406862",
    "Alvi Dasuyev": "https://www.sherdog.com/fighter/Alvi-Dasuyev-390836",
    "Walid Masmoudi": "https://www.sherdog.com/fighter/Walid-Masmoudi-406848",
    "Pierre Manzo": "https://www.sherdog.com/fighter/Pierre-Manzo-485824",
    "Samba Sima": "https://www.sherdog.com/fighter/Samba-Sima-411650",
    "Allan Landouzy": "https://www.sherdog.com/fighter/Allan-Landouzy-408988",
    "Oualy Tandia": "https://www.sherdog.com/fighter/Oualy-Tandia-419548",
    "Alexandra Tekenah": "https://www.sherdog.com/fighter/Alexandra-Tekenah-398443",
    "Bafode Gassama": "https://www.sherdog.com/fighter/Bafode-Gassama-432759",
    "Arnaud Prigent": "https://www.sherdog.com/fighter/Arnaud-Prigent-399672",
    "Zakaria Hamou": "https://www.sherdog.com/fighter/Zakaria-Hamou-406859",
    "Mathys Duragrin": "https://www.sherdog.com/fighter/Mathys-Duragrin-406849",
    "Arthur Demonceaux": "https://www.sherdog.com/fighter/Arthur-Demonceaux-267287",
    "Mehdi Ben Lakhdhar": "https://www.sherdog.com/fighter/Mehdi-Ben-Lakhdhar-269793",
    "Kevin Ruart": "https://www.sherdog.com/fighter/Kevin-Ruart-170277",
    "Leopold Goi": "https://www.sherdog.com/fighter/Leopold-Goi-274915",
    "Michael Aljarouj": "https://www.sherdog.com/fighter/Michael-Aljarouj-250049",
    "Khamzat Abaev": "https://www.sherdog.com/fighter/Khamzat-Abaev-413927",
    "Ghiles Oudelha": "https://www.sherdog.com/fighter/Ghiles-Oudelha-191993",
    "Virgil Augen": "https://www.sherdog.com/fighter/Virgil-Augen-290441",
    "Xavier Lessou": "https://www.sherdog.com/fighter/Xavier-Lessou-402582",
    "Oceane Samson": "https://www.sherdog.com/fighter/Oceane-Samson-425132",
}

BASE = "https://www.sherdog.com"
CACHE = "fighters.json"
PAUSE = 2  # secondes entre deux requetes, pour rester poli avec le site

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


# Attention a l'ordre : les libelles les plus longs d'abord, sinon
# "Welterweight" serait trouve a l'interieur de "Light Heavyweight".
CATEGORIES_POIDS = [
    "Light Heavyweight", "Super Heavyweight", "Heavyweight",
    "Middleweight", "Welterweight", "Featherweight", "Bantamweight",
    "Lightweight", "Flyweight", "Strawweight", "Atomweight", "Catchweight",
]

MOIS_SHERDOG = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


ESSAIS = 3
ATTENTES = [5, 15, 30]   # secondes avant chaque nouvelle tentative


def recuperer(url, params=None):
    """Va chercher une page, en reessayant si le reseau flanche.

    Renvoie la soupe HTML, ou None si la page reste inaccessible.
    """
    for tentative in range(ESSAIS):
        try:
            reponse = requests.get(url, params=params, headers=HEADERS,
                                   timeout=45)
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


def normaliser(texte):
    """Minuscules, sans accents ni tirets, espaces reduits. Sert a comparer les noms."""
    decompose = unicodedata.normalize("NFD", texte)
    sans_accent = "".join(c for c in decompose if unicodedata.category(c) != "Mn")
    for signe in "-'\u2019.":
        sans_accent = sans_accent.replace(signe, " ")
    return " ".join(sans_accent.lower().split())


def charger_cache():
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def sauver_cache(cache):
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def resultats_recherche(terme):
    """Renvoie la liste (nom, adresse) des fiches trouvees pour un terme."""
    soup = recuperer(BASE + "/stats/fightfinder", {"SearchTxt": terme})
    if soup is None:
        return []

    trouves = []
    for tableau in soup.select("table.fightfinder_result"):
        for lien in tableau.select('a[href^="/fighter/"]'):
            nom = lien.get_text(strip=True)
            if nom:
                trouves.append((nom, BASE + lien["href"]))
    return trouves


def chercher_combattant(nom):
    """Trouve la fiche correspondant exactement au nom demande."""
    cible = normaliser(nom)

    # On tente le nom complet, puis le nom de famille seul
    termes = [cible, cible.split()[-1]]

    candidats = []

    for terme in termes:
        trouves = resultats_recherche(terme)
        time.sleep(PAUSE)
        candidats.extend(trouves)

        for nom_trouve, url in trouves:
            if normaliser(nom_trouve) == cible:
                return url

        # Correspondance souple : tous les mots du nom sont presents
        mots = cible.split()
        for nom_trouve, url in trouves:
            if all(mot in normaliser(nom_trouve) for mot in mots):
                return url

    # Echec : on affiche les pistes pour que tu puisses choisir a la main
    if candidats:
        print("   candidats proposes par Sherdog :")
        deja_vus = set()
        for nom_trouve, url in candidats:
            if url not in deja_vus:
                deja_vus.add(url)
                print(f"      {nom_trouve}  ->  {url}")

    return None


def date_iso_sherdog(texte):
    """'Aug / 01 / 2026' -> '2026-08-01'"""
    m = re.search(r"([A-Za-z]{3})\s*/\s*(\d{1,2})\s*/\s*(\d{4})", texte)
    if not m:
        return ""
    mois = MOIS_SHERDOG.get(m.group(1).lower())
    if not mois:
        return ""
    return f"{m.group(3)}-{mois:02d}-{int(m.group(2)):02d}"


def lire_historique(soup, nom_suivi, drapeau, limite=2):
    """Les derniers combats disputes, lus dans le tableau d'historique pro."""
    releves = []
    tableau = soup.select_one("div.fight_history table.new_table.fighter")
    if tableau is None:
        tableau = soup.select_one("table.new_table.fighter")
    if tableau is None:
        return releves

    for ligne in tableau.select("tr")[1:]:
        cellules = ligne.select("td")
        if len(cellules) < 4:
            continue
        badge = ligne.select_one("span.final_result")
        resultat = badge.get_text(strip=True).lower() if badge else ""
        if resultat not in ("win", "loss", "draw", "nc", "no contest"):
            continue

        lien_adv = cellules[1].select_one("a")
        adversaire = (lien_adv.get_text(strip=True) if lien_adv
                      else cellules[1].get_text(strip=True))

        texte_event = cellules[2].get_text(" ", strip=True)
        lien_ev = cellules[2].select_one("a")
        evenement = lien_ev.get_text(strip=True) if lien_ev else texte_event

        b = cellules[3].select_one("b")
        methode = (b.get_text(" ", strip=True) if b
                   else cellules[3].get_text(" ", strip=True)[:40])

        releves.append({
            "combattant": nom_suivi,
            "drapeau": drapeau,
            "resultat": resultat,
            "adversaire": adversaire,
            "evenement": evenement,
            "date": date_iso_sherdog(texte_event),
            "methode": methode,
        })
        if len(releves) >= limite:
            break
    return releves


def lire_combat_a_venir(url, nom_suivi):
    """Lit le bloc Upcoming Fights d'une fiche combattant."""
    chemin_suivi = url.replace(BASE, "")
    soup = recuperer(url)
    if soup is None:
        return "ERREUR", []

    # Nationalite : Sherdog affiche un drapeau en haut de la fiche,
    # dont le nom de fichier contient le code pays (ex: fr.png)
    drapeau = ""
    img_pays = soup.select_one('img[src*="img/flags/big/"]')
    if img_pays and img_pays.get("src"):
        nom_fichier = img_pays["src"].rsplit("/", 1)[-1]
        drapeau = nom_fichier.split(".")[0].lower()

    historique = lire_historique(soup, nom_suivi, drapeau)

    bloc = soup.select_one("div.fight_card_preview")
    if not bloc:
        return None, historique

    titre = bloc.select_one("h2")
    evenement = titre.get_text(strip=True) if titre else "Evenement inconnu"

    balise_date = bloc.select_one('meta[itemprop="startDate"]')
    date = balise_date["content"][:10] if balise_date else ""

    balise_lieu = bloc.select_one('span[itemprop="address"]')
    lieu = balise_lieu.get_text(strip=True) if balise_lieu else ""

    # On identifie l'adversaire par l'adresse de sa fiche, pas par son nom :
    # l'orthographe peut differer de celle de notre liste.
    adversaire = "?"
    url_adversaire = ""
    record_adversaire = ""
    record_suivi = ""
    for bloc_f in bloc.select("div.fighter"):
        balise_nom = bloc_f.select_one('span[itemprop="name"]')
        balise_record = bloc_f.select_one("span.record")
        lien = bloc_f.select_one('a[href^="/fighter/"]')
        chemin = lien["href"] if lien else ""

        if chemin and chemin != chemin_suivi:
            adversaire = balise_nom.get_text(strip=True) if balise_nom else "?"
            url_adversaire = BASE + chemin
            record_adversaire = balise_record.get_text(strip=True) if balise_record else ""
        elif chemin == chemin_suivi:
            record_suivi = balise_record.get_text(strip=True) if balise_record else ""

    lien_event = bloc.select_one("a.card_button")

    combat = {
        "combattant": nom_suivi,
        "url_suivi": url,
        "url_adversaire": url_adversaire,
        "drapeau": drapeau,
        "record_suivi": record_suivi,
        "titre": False,
        "categorie": "",
        "ordre": 500,
        "drapeau_adversaire": "",
        "adversaire": adversaire,
        "record_adversaire": record_adversaire,
        "evenement": evenement,
        "date": date,
        "lieu": lieu,
        "lien_evenement": BASE + lien_event["href"] if lien_event else "",
    }

    return combat, historique


_drapeaux = {}


def lire_drapeau(url):
    """Nationalite d'un combattant, lue une seule fois par adresse."""
    if not url:
        return ""
    if url in _drapeaux:
        return _drapeaux[url]
    soup = recuperer(url)
    if soup is None:
        _drapeaux[url] = ""
        return ""
    img = soup.select_one('img[src*="img/flags/big/"]')
    code = ""
    if img and img.get("src"):
        code = img["src"].rsplit("/", 1)[-1].split(".")[0].lower()
    _drapeaux[url] = code
    time.sleep(PAUSE)
    return code


def detecter_titres(resultats, cache):
    """Visite chaque page evenement une fois et marque les combats de titre.

    Sherdog ecrit "TITLE FIGHT" sur la ligne du combat concerne.
    """
    liens = []
    for c in resultats:
        lien = c.get("lien_evenement", "")
        if lien and lien not in liens:
            liens.append(lien)

    if not liens:
        return

    print("\nVerification des combats de titre...")
    for lien in liens:
        soup = recuperer(lien)
        if soup is None:
            continue
        time.sleep(PAUSE)

        for c in resultats:
            if c.get("lien_evenement") != lien:
                continue

            url_fiche = cache.get(c["combattant"], "")
            chemin = url_fiche.replace(BASE, "") if url_fiche else ""
            if not chemin:
                continue

            el = soup.select_one(f'a[href="{chemin}"]')
            if el is None:
                continue

            # Il faut regarder UNIQUEMENT le combat concerne, sinon la
            # mention TITLE FIGHT de la tete d'affiche deteint sur toute
            # la carte.
            ligne = el.find_parent("tr")
            if ligne is not None:
                # combattant de sous-carte : sa ligne du tableau suffit
                texte = ligne.get_text(" ", strip=True)
                # Sherdog numerote les combats, le plus grand numero etant
                # le plus haut de la carte, juste sous la tete d'affiche
                cellules = ligne.select("td")
                if cellules and cellules[0].get_text(strip=True).isdigit():
                    c["ordre"] = 1000 - int(cellules[0].get_text(strip=True))
                # sinon on garde la valeur neutre : ni en haut ni en bas
            else:
                # tete d'affiche : on remonte juste assez pour attraper
                # son encadre, sans deborder sur le reste de la page
                # tete d'affiche : elle passe en premier
                c["ordre"] = 0
                texte = ""
                for parent in el.parents:
                    candidat = parent.get_text(" ", strip=True) if parent else ""
                    if len(candidat) > 500:
                        break
                    texte = candidat

            for poids in CATEGORIES_POIDS:
                if poids in texte:
                    c["categorie"] = poids
                    break

            if "TITLE FIGHT" in texte:
                c["titre"] = True
                print(f"   ceinture en jeu : {c['combattant']}")

    # drapeaux des adversaires : une requete par adversaire concerne
    print("\nNationalite des adversaires...")
    for c in resultats:
        if c.get("url_adversaire") and not c.get("drapeau_adversaire"):
            c["drapeau_adversaire"] = lire_drapeau(c["url_adversaire"])


def detecter_changements(anciens, nouveaux):
    """Compare avec la passe precedente : combats annules ou reportes.

    Le resultat est memorise dans annulations.json et affiche sur le site
    jusqu'a ce que la date passe (annulation) ou 15 jours (report).
    """
    aujourd_hui = date.today().isoformat()

    def cle_duel(c):
        return (normaliser(c.get("combattant", "")) + " vs "
                + normaliser(c.get("adversaire", "")))

    dates_par_duel = {}
    for c in nouveaux:
        dates_par_duel.setdefault(cle_duel(c), set()).add(c.get("date", ""))

    changements = []
    if os.path.exists("annulations.json"):
        try:
            with open("annulations.json", encoding="utf-8") as f:
                changements = json.load(f)
        except ValueError:
            changements = []

    # menage dans la memoire existante
    limite_report = (date.today() - timedelta(days=15)).isoformat()
    conserves = []
    for m in changements:
        duel = cle_duel(m)
        if m.get("type") == "annule":
            # on garde tant que la date n'est pas passee et que le duel
            # n'est pas revenu au programme
            if m.get("date", "") >= aujourd_hui and duel not in dates_par_duel:
                conserves.append(m)
        else:
            if (m.get("detecte_le", "") >= limite_report
                    and m.get("nouvelle_date", "")
                    in dates_par_duel.get(duel, set())):
                conserves.append(m)
    changements = conserves
    deja = {(m.get("type"), cle_duel(m)) for m in changements}

    for ancien in anciens:
        if ancien.get("date", "") < aujourd_hui:
            continue
        duel = cle_duel(ancien)
        if duel in dates_par_duel:
            if ancien.get("date") not in dates_par_duel[duel] \
                    and ("reporte", duel) not in deja:
                changements.append({
                    "type": "reporte",
                    "combattant": ancien.get("combattant", ""),
                    "adversaire": ancien.get("adversaire", ""),
                    "ancienne_date": ancien.get("date", ""),
                    "nouvelle_date": sorted(dates_par_duel[duel])[0],
                    "detecte_le": aujourd_hui,
                })
                print(f"   REPORTE : {ancien.get('combattant')} "
                      f"vs {ancien.get('adversaire')}")
        elif ("annule", duel) not in deja:
            copie = dict(ancien)
            copie["type"] = "annule"
            copie["detecte_le"] = aujourd_hui
            changements.append(copie)
            print(f"   ANNULE : {ancien.get('combattant')} "
                  f"vs {ancien.get('adversaire')}")

    with open("annulations.json", "w", encoding="utf-8") as f:
        json.dump(changements, f, ensure_ascii=False, indent=2)

    return changements


def main():
    cache = charger_cache()
    resultats = []
    recents = []
    introuvables = []
    inaccessibles = []

    # passe precedente : sert de filet si un combattant devient injoignable
    anciens = []
    if os.path.exists("combats.json"):
        try:
            with open("combats.json", encoding="utf-8") as f:
                anciens = json.load(f)
        except ValueError:
            anciens = []
    par_nom = {c.get("combattant"): c for c in anciens}

    total = len(COMBATTANTS)
    for numero, nom in enumerate(COMBATTANTS, start=1):
        print(f"[{numero}/{total}] {nom}")

        if nom in FICHES_MANUELLES and cache.get(nom) != FICHES_MANUELLES[nom]:
            cache[nom] = FICHES_MANUELLES[nom]
            sauver_cache(cache)

        if nom not in cache:
            url = chercher_combattant(nom)
            if not url:
                print("   fiche introuvable")
                introuvables.append(nom)
                continue
            cache[nom] = url
            sauver_cache(cache)

        combat, historique = lire_combat_a_venir(cache[nom], nom)
        time.sleep(PAUSE)
        recents.extend(historique)

        if combat == "ERREUR":
            # fiche injoignable : on garde ce qu'on savait la fois d'avant
            inaccessibles.append(nom)
            ancien = par_nom.get(nom)
            if ancien:
                print("   injoignable, on garde la donnee precedente")
                resultats.append(ancien)
            else:
                print("   injoignable")
        elif combat:
            print(f"   {combat['date']} vs {combat['adversaire']}")
            resultats.append(combat)
        else:
            print("   pas de combat annonce")

    detecter_titres(resultats, cache)

    print("\nComparaison avec la passe precedente...")
    if inaccessibles:
        # une panne reseau ne doit pas etre prise pour une annulation
        print("   comparaison prudente : des fiches etaient injoignables")
    detecter_changements(anciens, resultats)

    recents.sort(key=lambda c: c.get("date", ""), reverse=True)
    with open("resultats.json", "w", encoding="utf-8") as f:
        json.dump(recents, f, ensure_ascii=False, indent=2)

    resultats.sort(key=lambda c: c["date"])

    with open("combats.json", "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 55)
    print("COMBATS A VENIR")
    print("=" * 55)
    for c in resultats:
        print(f"\n{c['date']}  |  {c['evenement']}")
        print(f"{c['combattant']} vs {c['adversaire']}")
        print(f"{c['lieu']}")

    print("\n" + "=" * 55)
    print(f"{len(resultats)} combat(s) trouve(s) sur {len(COMBATTANTS)} combattants")
    if introuvables:
        print("Fiches non trouvees :", ", ".join(introuvables))
    if inaccessibles:
        print("Fiches injoignables cette fois :", ", ".join(inaccessibles))
    print("Details enregistres dans combats.json")
    print("Derniers resultats dans resultats.json, "
          "changements dans annulations.json")


if __name__ == "__main__":
    main()
