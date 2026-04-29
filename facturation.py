"""
=============================================================
  LABORATOIRE BETHESDA — facturation.py
  Facturation patients + Mobile Money (Cameroun) + CB (Europe)
=============================================================
"""
import csv, json
from datetime import datetime
from pathlib import Path
from config import BASE_DIR, DATA_DIR, DELIMITEUR

TARIFS = {
    "NFS":                       5000,
    "Bilan Lipidique":           8000,
    "Bilan Rénal":               7500,
    "Bilan Hépatique":           7500,
    "Bilan Thyroïdien":         10000,
    "Glycémie et Diabète":       4500,
    "Bilan Martial":             6000,
    "Marqueurs Inflammatoires":  9000,
    "Ionogramme Sanguin":        6500,
    "Bilan Vitamines":           8500,
    "ECBU":                      4000,
    "Enzymes Cardiaques":       12000,
    "Bilan Coagulation":         7000,
    "Sérologie Infectieuse":    15000,
    "Marqueurs Tumoraux":       18000,
    "Sérologie Virale VIH":     12000,
    "Hémoculture":              10000,
    "Auto-Immunité":            14000,
    "Antibiogramme":             6000,
    "Bilan Hormonal":           11000,
    "DEFAULT":                   5000,
}
DEVISE = "FCFA"
FACTURES_DIR = DATA_DIR / "factures"
FACTURES_DIR.mkdir(exist_ok=True)
FACTURES_CSV = DATA_DIR / "06_factures.csv"
COLS_FACTURE  = ["ID_Facture","ID_Patient","ID_Examen","Date","Montant","Devise",
                 "Mode_Paiement","Statut","Reference_Paiement","Notes"]

def _init_factures():
    if not FACTURES_CSV.exists():
        with open(FACTURES_CSV, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=COLS_FACTURE, delimiter=DELIMITEUR).writeheader()

def get_tarif(categorie: str) -> int:
    return TARIFS.get(categorie, TARIFS["DEFAULT"])

def creer_facture(id_patient: str, id_examen: str, categorie: str,
                  mode_paiement: str = "ESPECES") -> dict:
    """Crée une facture pour un examen."""
    _init_factures()
    factures = []
    if FACTURES_CSV.exists():
        with open(FACTURES_CSV, newline="", encoding="utf-8") as f:
            factures = list(csv.DictReader(f, delimiter=DELIMITEUR))
    nums  = [int(r["ID_Facture"].split("-")[-1]) for r in factures
             if r.get("ID_Facture","").startswith("FAC-") and r["ID_Facture"].split("-")[-1].isdigit()]
    new_id = f"FAC-{(max(nums, default=0)+1):04d}"
    facture = {
        "ID_Facture":        new_id,
        "ID_Patient":        id_patient,
        "ID_Examen":         id_examen,
        "Date":              datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Montant":           str(get_tarif(categorie)),
        "Devise":            DEVISE,
        "Mode_Paiement":     mode_paiement,
        "Statut":            "EN_ATTENTE",
        "Reference_Paiement": "",
        "Notes":             categorie,
    }
    with open(FACTURES_CSV, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=COLS_FACTURE, delimiter=DELIMITEUR).writerow(facture)
    return facture

def payer_facture(id_facture: str, reference: str = "",
                  mode: str = "ESPECES") -> bool:
    """Marque une facture comme payée."""
    if not FACTURES_CSV.exists():
        return False
    with open(FACTURES_CSV, newline="", encoding="utf-8") as f:
        factures = list(csv.DictReader(f, delimiter=DELIMITEUR))
    for fac in factures:
        if fac.get("ID_Facture") == id_facture:
            fac["Statut"]            = "PAYE"
            fac["Reference_Paiement"] = reference
            fac["Mode_Paiement"]     = mode
            break
    else:
        return False
    with open(FACTURES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS_FACTURE, delimiter=DELIMITEUR)
        w.writeheader(); w.writerows(factures)
    return True

def get_factures_patient(id_patient: str) -> list[dict]:
    """Retourne toutes les factures d'un patient."""
    if not FACTURES_CSV.exists():
        return []
    with open(FACTURES_CSV, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f, delimiter=DELIMITEUR)
                if r.get("ID_Patient") == id_patient]

def stats_facturation() -> dict:
    """Statistiques financières globales."""
    if not FACTURES_CSV.exists():
        return {"total": 0, "paye": 0, "en_attente": 0, "ca_total": 0, "ca_encaisse": 0}
    with open(FACTURES_CSV, newline="", encoding="utf-8") as f:
        factures = list(csv.DictReader(f, delimiter=DELIMITEUR))
    paye      = [r for r in factures if r.get("Statut") == "PAYE"]
    en_attente = [r for r in factures if r.get("Statut") == "EN_ATTENTE"]
    ca_total   = sum(int(r.get("Montant","0") or 0) for r in factures)
    ca_encaisse= sum(int(r.get("Montant","0") or 0) for r in paye)
    modes = {}
    for r in paye:
        m = r.get("Mode_Paiement","INCONNU")
        modes[m] = modes.get(m, 0) + int(r.get("Montant","0") or 0)
    return {
        "total": len(factures), "paye": len(paye),
        "en_attente": len(en_attente),
        "ca_total": ca_total, "ca_encaisse": ca_encaisse,
        "modes_paiement": modes,
    }

def generer_recu_html(id_facture: str) -> str:
    """Génère un reçu HTML imprimable."""
    if not FACTURES_CSV.exists():
        return "<p>Facture introuvable</p>"
    with open(FACTURES_CSV, newline="", encoding="utf-8") as f:
        fac = next((r for r in csv.DictReader(f, delimiter=DELIMITEUR)
                    if r.get("ID_Facture") == id_facture), None)
    if not fac:
        return "<p>Facture introuvable</p>"
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<title>Reçu {id_facture}</title>
<style>body{{font-family:Arial;max-width:400px;margin:30px auto;font-size:13px}}
.center{{text-align:center}}.big{{font-size:18px;font-weight:700}}.sep{{border-top:1px dashed #999;margin:10px 0}}
.ok{{color:#16a34a;font-weight:700}}.warn{{color:#d97706;font-weight:700}}
@media print{{.no-print{{display:none}}}}</style></head><body>
<div class="center">
  <div class="big">LABORATOIRE BETHESDA</div>
  <div style="font-size:12px;color:#6b7280">Reçu de paiement</div>
</div>
<div class="sep"></div>
<p><b>Reçu N°</b> : {id_facture}</p>
<p><b>Patient</b> : {fac.get('ID_Patient','—')}</p>
<p><b>Examen</b>  : {fac.get('Notes','—')}</p>
<p><b>Date</b>    : {fac.get('Date','—')}</p>
<div class="sep"></div>
<p><b>Montant</b> : <span class="big">{fac.get('Montant','0')} {fac.get('Devise','FCFA')}</span></p>
<p><b>Paiement</b>: {fac.get('Mode_Paiement','—')}</p>
<p><b>Statut</b>  : <span class="{'ok' if fac.get('Statut')=='PAYE' else 'warn'}">{fac.get('Statut','—')}</span></p>
{f"<p><b>Référence</b>: {fac.get('Reference_Paiement','')}</p>" if fac.get('Reference_Paiement') else ""}
<div class="sep"></div>
<p class="center" style="font-size:11px;color:#6b7280">Merci pour votre confiance — Laboratoire Bethesda</p>
<button class="no-print" onclick="window.print()" style="display:block;margin:20px auto;padding:8px 20px;background:#1e40af;color:white;border:none;border-radius:6px;cursor:pointer">Imprimer</button>
</body></html>"""
