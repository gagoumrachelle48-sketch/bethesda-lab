"""
=============================================================
  LABORATOIRE BETHESDA — rendez_vous.py
  Gestion des rendez-vous et planning du laboratoire
=============================================================
"""
import csv
from datetime import datetime, timedelta
from pathlib import Path
from config import DATA_DIR, DELIMITEUR

RDV_CSV  = DATA_DIR / "07_rendez_vous.csv"
COLS_RDV = ["ID_RDV","ID_Patient","Date","Heure","Duree_Min",
            "Type_Examen","Prescripteur","Statut","Notes","Cree_Le"]

CRENEAUX_DISPO = ["07:30","08:00","08:30","09:00","09:30","10:00",
                  "10:30","11:00","11:30","14:00","14:30","15:00",
                  "15:30","16:00","16:30","17:00"]

def _init():
    if not RDV_CSV.exists():
        with open(RDV_CSV, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=COLS_RDV, delimiter=DELIMITEUR).writeheader()

def get_rdv(date: str = "", id_patient: str = "") -> list[dict]:
    """Retourne les rendez-vous filtrés."""
    _init()
    with open(RDV_CSV, newline="", encoding="utf-8") as f:
        rdvs = list(csv.DictReader(f, delimiter=DELIMITEUR))
    if date:
        rdvs = [r for r in rdvs if r.get("Date") == date]
    if id_patient:
        rdvs = [r for r in rdvs if r.get("ID_Patient") == id_patient]
    return rdvs

def creer_rdv(id_patient: str, date: str, heure: str,
              type_examen: str = "", prescripteur: str = "",
              notes: str = "", duree: int = 30) -> dict:
    """Crée un rendez-vous. Retourne le RDV créé ou une erreur."""
    _init()
    # Vérifier disponibilité
    rdvs_jour = get_rdv(date=date)
    if any(r.get("Heure") == heure and r.get("Statut") != "ANNULE"
           for r in rdvs_jour):
        return {"erreur": f"Créneau {heure} déjà pris le {date}"}
    rdvs = get_rdv()
    nums = [int(r["ID_RDV"].split("-")[-1]) for r in rdvs
            if r.get("ID_RDV","").startswith("RDV-") and r["ID_RDV"].split("-")[-1].isdigit()]
    new_id = f"RDV-{(max(nums, default=0)+1):04d}"
    rdv = {
        "ID_RDV":       new_id,
        "ID_Patient":   id_patient,
        "Date":         date,
        "Heure":        heure,
        "Duree_Min":    str(duree),
        "Type_Examen":  type_examen,
        "Prescripteur": prescripteur,
        "Statut":       "CONFIRME",
        "Notes":        notes,
        "Cree_Le":      datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    with open(RDV_CSV, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=COLS_RDV, delimiter=DELIMITEUR).writerow(rdv)
    return rdv

def annuler_rdv(id_rdv: str) -> bool:
    """Annule un rendez-vous."""
    if not RDV_CSV.exists():
        return False
    with open(RDV_CSV, newline="", encoding="utf-8") as f:
        rdvs = list(csv.DictReader(f, delimiter=DELIMITEUR))
    for r in rdvs:
        if r.get("ID_RDV") == id_rdv:
            r["Statut"] = "ANNULE"; break
    else:
        return False
    with open(RDV_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS_RDV, delimiter=DELIMITEUR)
        w.writeheader(); w.writerows(rdvs)
    return True

def creneaux_libres(date: str) -> list[str]:
    """Retourne les créneaux disponibles pour une date donnée."""
    rdvs_pris = {r.get("Heure") for r in get_rdv(date=date)
                 if r.get("Statut") != "ANNULE"}
    return [c for c in CRENEAUX_DISPO if c not in rdvs_pris]

def planning_semaine(date_debut: str) -> dict:
    """Retourne le planning de la semaine à partir d'une date."""
    try:
        debut = datetime.strptime(date_debut, "%Y-%m-%d")
    except ValueError:
        debut = datetime.now()
    planning = {}
    for i in range(7):
        jour = (debut + timedelta(days=i)).strftime("%Y-%m-%d")
        planning[jour] = {
            "rdvs":   get_rdv(date=jour),
            "libres": creneaux_libres(jour),
        }
    return planning
