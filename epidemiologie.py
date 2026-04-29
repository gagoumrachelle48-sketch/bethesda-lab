"""
=============================================================
  LABORATOIRE BETHESDA — epidemiologie.py
  Statistiques épidémiologiques — Santé publique
=============================================================
"""
from collections import Counter
from datetime import datetime
import database as db

def stats_porteurs_par_region() -> dict:
    """Analyse la distribution géographique des porteurs."""
    diagnostics = db.get("diagnostics")
    patients    = {p["ID_Patient"]: p for p in db.get("patients")}
    porteurs    = [d for d in diagnostics if d.get("Est_Porteur") == "OUI"]
    regions = Counter()
    for d in porteurs:
        p      = patients.get(d["ID_Patient"], {})
        adresse = p.get("Adresse", "Inconnu")
        ville   = adresse.split(",")[-1].strip() if "," in adresse else adresse[:30]
        regions[ville] += 1
    return dict(regions.most_common(20))

def stats_pathologies() -> dict:
    """Distribution des pathologies détectées."""
    diagnostics = db.get("diagnostics")
    porteurs    = [d for d in diagnostics if d.get("Est_Porteur") == "OUI"]
    return dict(Counter(d.get("Pathologie_Detectee","—") for d in porteurs).most_common(15))

def stats_age_genre() -> dict:
    """Analyse par tranche d'âge et genre."""
    patients = db.get("patients")
    today    = datetime.now()
    tranches = {"0-17":0,"18-35":0,"36-50":0,"51-65":0,"65+":0,"Inconnu":0}
    genres   = Counter(p.get("Sexe","?") for p in patients)
    for p in patients:
        try:
            nais = datetime.strptime(p.get("Date_Naissance",""), "%Y-%m-%d")
            age  = (today - nais).days // 365
            if age < 18:     tranches["0-17"] += 1
            elif age < 36:   tranches["18-35"] += 1
            elif age < 51:   tranches["36-50"] += 1
            elif age < 66:   tranches["51-65"] += 1
            else:            tranches["65+"] += 1
        except Exception:
            tranches["Inconnu"] += 1
    return {"tranches_age": tranches, "genres": dict(genres)}

def stats_examens_par_periode() -> dict:
    """Nombre d'examens par mois."""
    examens = db.get("examens")
    mois    = Counter()
    for e in examens:
        date = e.get("Date_Prelevement","")
        if date and len(date) >= 7:
            mois[date[:7]] += 1
    return dict(sorted(mois.items()))

def rapport_epidemiologique() -> dict:
    """Rapport épidémiologique complet."""
    patients    = db.get("patients")
    diagnostics = db.get("diagnostics")
    porteurs    = [d for d in diagnostics if d.get("Est_Porteur") == "OUI"]
    nb_pat      = len(patients)
    nb_port     = len({d["ID_Patient"] for d in porteurs})
    risques     = Counter(d.get("Niveau_Risque","?") for d in porteurs)
    return {
        "date_rapport":         datetime.now().isoformat(),
        "nb_patients":          nb_pat,
        "nb_porteurs":          nb_port,
        "taux_porteurs_pct":    round(nb_port / nb_pat * 100, 1) if nb_pat else 0,
        "distribution_risque":  dict(risques),
        "pathologies_top":      stats_pathologies(),
        "repartition_age_genre":stats_age_genre(),
        "examens_par_mois":     stats_examens_par_periode(),
        "regions_affectees":    stats_porteurs_par_region(),
    }
