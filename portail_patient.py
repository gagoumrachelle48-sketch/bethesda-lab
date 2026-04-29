"""
=============================================================
  LABORATOIRE BETHESDA — portail_patient.py
  Portail patient : accès aux résultats via code unique
  Conformité RGPD : droit d'accès, export, effacement
=============================================================
"""
import csv, json, hashlib
from datetime import datetime
from pathlib import Path
from config import DATA_DIR, DELIMITEUR, SECRET_KEY
from security import generer_code_acces_patient, chiffrer, dechiffrer
import database as db

CODES_CSV = DATA_DIR / "08_codes_acces.csv"
COLS_CODES = ["ID_Patient","Code_Acces","Date_Creation","Date_Expiration","Utilise"]

def _init():
    if not CODES_CSV.exists():
        with open(CODES_CSV, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=COLS_CODES, delimiter=DELIMITEUR).writeheader()

def generer_code_patient(id_patient: str) -> str:
    """Génère et stocke un code d'accès pour un patient."""
    _init()
    code = generer_code_acces_patient()
    # Hash du code stocké (pas le code en clair)
    code_hash = hashlib.sha256((code + SECRET_KEY).encode()).hexdigest()
    entree = {
        "ID_Patient":       id_patient,
        "Code_Acces":       code_hash,
        "Date_Creation":    datetime.now().strftime("%Y-%m-%d"),
        "Date_Expiration":  "",
        "Utilise":          "NON",
    }
    # Supprimer ancien code s'il existe
    with open(CODES_CSV, newline="", encoding="utf-8") as f:
        codes = [r for r in csv.DictReader(f, delimiter=DELIMITEUR)
                 if r.get("ID_Patient") != id_patient]
    codes.append(entree)
    with open(CODES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS_CODES, delimiter=DELIMITEUR)
        w.writeheader(); w.writerows(codes)
    return code  # Retourner le code en clair pour l'envoyer au patient

def verifier_code_patient(id_patient: str, code: str) -> bool:
    """Vérifie le code d'accès d'un patient."""
    _init()
    code_hash = hashlib.sha256((code.upper().strip() + SECRET_KEY).encode()).hexdigest()
    with open(CODES_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=DELIMITEUR):
            if r.get("ID_Patient") == id_patient and r.get("Code_Acces") == code_hash:
                return True
    return False

def get_donnees_patient_rgpd(id_patient: str) -> dict:
    """
    Retourne toutes les données d'un patient (droit d'accès RGPD).
    """
    patient     = db.trouver_par_id("patients", id_patient)
    examens     = db.filtrer("examens", ID_Patient=id_patient)
    diagnostics = db.filtrer("diagnostics", ID_Patient=id_patient)
    resultats   = []
    for ex in examens:
        res = db.filtrer("resultats", ID_Examen=ex["ID_Examen"])
        resultats.extend(res)
    return {
        "patient":     patient,
        "examens":     examens,
        "resultats":   resultats,
        "diagnostics": diagnostics,
        "export_date": datetime.now().isoformat(),
        "laboratoire": "Laboratoire Bethesda",
    }

def exporter_json_rgpd(id_patient: str) -> str:
    """Export JSON de toutes les données (droit à la portabilité RGPD)."""
    data = get_donnees_patient_rgpd(id_patient)
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)

def demander_effacement(id_patient: str, raison: str = "") -> dict:
    """
    Traite une demande d'effacement (droit à l'oubli RGPD).
    En production : déclencher workflow de validation médicale avant effacement.
    """
    # Log de la demande (on ne peut pas effacer immédiatement sans validation médicale)
    log_file = Path(DATA_DIR) / "demandes_effacement.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "id_patient": id_patient,
            "date":       datetime.now().isoformat(),
            "raison":     raison,
            "statut":     "EN_ATTENTE_VALIDATION",
        }, ensure_ascii=False) + "\n")
    return {
        "succes":  True,
        "message": "Demande d'effacement enregistrée. Traitement sous 30 jours (RGPD Art.17).",
        "delai":   "30 jours ouvrables",
    }

def generer_portail_html(id_patient: str) -> str:
    """Génère la page HTML du portail patient."""
    data    = get_donnees_patient_rgpd(id_patient)
    patient = data.get("patient") or {}
    examens = data.get("examens", [])
    diags   = data.get("diagnostics", [])
    porteurs = [d for d in diags if d.get("Est_Porteur") == "OUI"]

    rows = ""
    for ex in examens:
        res = db.filtrer("resultats", ID_Examen=ex["ID_Examen"])
        for r in res:
            st  = r.get("Statut_Valeur","—")
            col = {"NORMAL":"#16a34a","NEGATIF":"#16a34a","ELEVE":"#dc2626",
                   "TRES_ELEVE":"#7c3aed","BAS":"#2563eb","LIMITE":"#d97706"}.get(st,"#374151")
            rows += f"""<tr>
              <td>{ex.get('Date_Prelevement','—')}</td>
              <td>{ex.get('Categorie','—')}</td>
              <td>{r.get('Parametre','—')}</td>
              <td><b>{r.get('Valeur','—')} {r.get('Unite','')}</b></td>
              <td style="color:{col};font-weight:700">{st}</td>
            </tr>"""

    statut_bloc = ""
    if porteurs:
        statut_bloc = "<div style='background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;padding:12px;margin:12px 0;color:#dc2626;font-weight:600'>⚠ Des résultats nécessitent un suivi médical. Contactez votre médecin.</div>"
    else:
        statut_bloc = "<div style='background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:12px;margin:12px 0;color:#166534;font-weight:600'>✓ Vos résultats ne présentent pas d'anomalie majeure.</div>"

    return f"""<!DOCTYPE html><html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mes résultats — Bethesda</title>
<style>
body{{font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;font-size:13px;background:#f9fafb}}
.header{{background:#1e40af;color:white;padding:20px;border-radius:10px;margin-bottom:20px}}
.card{{background:white;border-radius:8px;padding:16px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
table{{width:100%;border-collapse:collapse}}
th{{background:#1e40af;color:white;padding:8px 12px;text-align:left;font-size:12px}}
td{{padding:7px 12px;border-bottom:1px solid #f3f4f6}}
tr:nth-child(even){{background:#f9fafb}}
h3{{color:#1e40af;margin:0 0 10px;font-size:14px}}
@media print{{body{{background:white}}.no-print{{display:none}}}}
</style></head><body>
<div class="header">
  <div style="font-size:18px;font-weight:700">Laboratoire Bethesda</div>
  <div style="opacity:.8;font-size:13px">Portail Résultats — Accès sécurisé</div>
</div>
<div class="card">
  <h3>Informations patient</h3>
  <p><b>{patient.get('Nom','')} {patient.get('Prenom','')}</b> &nbsp;|&nbsp;
     DDN : {patient.get('Date_Naissance','—')} &nbsp;|&nbsp;
     Groupe : {patient.get('Groupe_Sanguin','—')}</p>
  {statut_bloc}
</div>
<div class="card">
  <h3>Résultats d'analyses</h3>
  <table><thead><tr><th>Date</th><th>Examen</th><th>Paramètre</th><th>Valeur</th><th>Statut</th></tr></thead>
  <tbody>{rows if rows else '<tr><td colspan="5" style="text-align:center;color:#9ca3af">Aucun résultat disponible</td></tr>'}</tbody></table>
</div>
<div class="card no-print" style="background:#fef9c3;border:1px solid #fde047">
  <p style="color:#854d0e;font-size:12px">Ces résultats sont strictement confidentiels. Ne les partagez qu'avec votre médecin. Données protégées — Bethesda © {datetime.now().year}</p>
</div>
<div class="no-print" style="text-align:center;margin-top:12px">
  <button onclick="window.print()" style="background:#1e40af;color:white;padding:10px 24px;border:none;border-radius:6px;cursor:pointer;font-size:13px">Imprimer / Sauvegarder PDF</button>
</div>
</body></html>"""
