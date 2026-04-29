"""
=============================================================
  LABORATOIRE BETHESDA — database.py
  Couche d'accès aux données CSV — Thread-safe
  Lecture, écriture, cache, génération d'IDs
=============================================================
"""

import csv
import os
import threading
from datetime import datetime
from pathlib import Path
from config import FICHIERS, COLONNES, PREFIXES_ID, DELIMITEUR

# ── Verrou pour écriture thread-safe ─────────────────────
_verrou = threading.Lock()
_cache: dict[str, list[dict]] = {}


# ─────────────────────────────────────────────
#  INITIALISATION — créer CSV si absent
# ─────────────────────────────────────────────

def initialiser_csv() -> None:
    """Crée les fichiers CSV avec headers si inexistants."""
    for cle, chemin in FICHIERS.items():
        if not Path(chemin).exists():
            with open(chemin, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=COLONNES[cle], delimiter=DELIMITEUR)
                writer.writeheader()
            print(f"  [DB] Créé : {chemin}")


# ─────────────────────────────────────────────
#  LECTURE
# ─────────────────────────────────────────────

def _charger(cle: str) -> list[dict]:
    chemin = FICHIERS[cle]
    if not Path(chemin).exists():
        return []
    rows = []
    with open(chemin, newline="", encoding="utf-8") as f:
        premiere = f.readline()
    delim = ";" if premiere.count(";") >= premiere.count(",") else ","
    with open(chemin, newline="", encoding="utf-8") as f:
        for ligne in csv.DictReader(f, delimiter=delim):
            propre = {k.strip(): (v.strip() if v else "") for k, v in ligne.items() if k and k.strip()}
            rows.append(propre)
    return rows


def get(cle: str, forcer: bool = False) -> list[dict]:
    """Retourne les données depuis le cache ou le CSV."""
    if cle not in _cache or forcer:
        _cache[cle] = _charger(cle)
    return _cache[cle]


def invalider(cle: str) -> None:
    _cache.pop(cle, None)


def charger_tout() -> None:
    for cle in FICHIERS:
        get(cle, forcer=True)


# ─────────────────────────────────────────────
#  GÉNÉRATION D'ID
# ─────────────────────────────────────────────

def generer_id(cle: str) -> str:
    """Génère un ID unique séquentiel : PAT-001, EXA-042, etc."""
    prefix  = PREFIXES_ID[cle]
    records = get(cle)
    champ   = COLONNES[cle][0]  # premier champ = clé primaire
    nums = []
    for r in records:
        val = r.get(champ, "")
        if val.startswith(prefix + "-"):
            try:
                nums.append(int(val.split("-")[-1]))
            except ValueError:
                pass
    suivant = (max(nums) + 1) if nums else 1
    return f"{prefix}-{suivant:03d}"


# ─────────────────────────────────────────────
#  ÉCRITURE — thread-safe
# ─────────────────────────────────────────────

def inserer(cle: str, donnees: dict) -> dict:
    """
    Insère un nouvel enregistrement dans le CSV.
    Retourne l'enregistrement avec l'ID généré.
    """
    with _verrou:
        chemin  = FICHIERS[cle]
        colonnes = COLONNES[cle]

        # Générer ID si absent
        champ_id = colonnes[0]
        if not donnees.get(champ_id):
            donnees[champ_id] = generer_id(cle)

        # Horodatage automatique
        if "Date_Creation" in colonnes and not donnees.get("Date_Creation"):
            donnees["Date_Creation"] = datetime.now().strftime("%Y-%m-%d")
        if "Date_Inscription" in colonnes and not donnees.get("Date_Inscription"):
            donnees["Date_Inscription"] = datetime.now().strftime("%Y-%m-%d")
        if "Date_Diagnostic" in colonnes and not donnees.get("Date_Diagnostic"):
            donnees["Date_Diagnostic"] = datetime.now().strftime("%Y-%m-%d")

        # Compléter les champs manquants
        ligne = {col: donnees.get(col, "") for col in colonnes}

        # Écrire dans le fichier
        fichier_existe = Path(chemin).exists()
        with open(chemin, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=colonnes, delimiter=DELIMITEUR)
            if not fichier_existe or Path(chemin).stat().st_size == 0:
                writer.writeheader()
            writer.writerow(ligne)

        # Invalider le cache pour cette table
        invalider(cle)
        return ligne


def mettre_a_jour(cle: str, champ_id: str, id_val: str, mises_a_jour: dict) -> bool:
    """Met à jour un enregistrement existant. Retourne True si trouvé."""
    with _verrou:
        records = get(cle, forcer=True)
        trouve = False
        for r in records:
            if r.get(champ_id) == id_val:
                r.update(mises_a_jour)
                trouve = True
                break
        if not trouve:
            return False
        # Réécrire tout le fichier
        chemin   = FICHIERS[cle]
        colonnes = COLONNES[cle]
        with open(chemin, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=colonnes, delimiter=DELIMITEUR)
            writer.writeheader()
            for r in records:
                writer.writerow({col: r.get(col, "") for col in colonnes})
        invalider(cle)
        return True


def supprimer(cle: str, champ_id: str, id_val: str) -> bool:
    """Supprime un enregistrement. Retourne True si trouvé."""
    with _verrou:
        records = get(cle, forcer=True)
        nouveaux = [r for r in records if r.get(champ_id) != id_val]
        if len(nouveaux) == len(records):
            return False
        chemin   = FICHIERS[cle]
        colonnes = COLONNES[cle]
        with open(chemin, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=colonnes, delimiter=DELIMITEUR)
            writer.writeheader()
            for r in nouveaux:
                writer.writerow({col: r.get(col, "") for col in colonnes})
        invalider(cle)
        return True


# ─────────────────────────────────────────────
#  REQUÊTES
# ─────────────────────────────────────────────

def trouver_par_id(cle: str, id_val: str) -> dict | None:
    champ = COLONNES[cle][0]
    return next((r for r in get(cle) if r.get(champ) == id_val), None)


def filtrer(cle: str, **criteres) -> list[dict]:
    table = get(cle)
    for champ, valeur in criteres.items():
        table = [r for r in table if r.get(champ) == valeur]
    return table


def rechercher(cle: str, terme: str, champs: list[str]) -> list[dict]:
    terme = terme.lower().strip()
    return [r for r in get(cle) if any(terme in r.get(c, "").lower() for c in champs)]


def stats_globales() -> dict:
    patients    = get("patients")
    examens     = get("examens")
    resultats   = get("resultats")
    diagnostics = get("diagnostics")
    porteurs    = [d for d in diagnostics if d.get("Est_Porteur") == "OUI"]
    critiques   = [r for r in resultats   if r.get("Est_Critique") == "OUI"]
    risques     = {"FAIBLE":0,"MODERE":0,"ELEVE":0,"TRES_ELEVE":0}
    for d in diagnostics:
        niv = d.get("Niveau_Risque","")
        if niv in risques:
            risques[niv] += 1
    statuts = {}
    for p in patients:
        s = p.get("Statut_Global","INCONNU")
        statuts[s] = statuts.get(s, 0) + 1
    return {
        "nb_patients":         len(patients),
        "nb_examens":          len(examens),
        "nb_resultats":        len(resultats),
        "nb_diagnostics":      len(diagnostics),
        "nb_utilisateurs":     len(get("utilisateurs")),
        "nb_porteurs_uniques": len({d["ID_Patient"] for d in porteurs}),
        "nb_critiques":        len(critiques),
        "distribution_risque": risques,
        "statuts_patients":    statuts,
    }
