"""
=============================================================
  LABORATOIRE BETHESDA — pdf_rapport.py
  FONCTIONNALITÉ 4 : Génération de rapports PDF
  (sans dépendance externe — HTML → impression navigateur)
=============================================================
"""
from datetime import datetime
import database as db

LAB_NOM     = "Laboratoire Bethesda"
LAB_ADRESSE = "À configurer dans config.py"
LAB_TEL     = ""
LAB_EMAIL   = ""

COULEURS = {
    "NORMAL":     "#16a34a", "NEGATIF": "#16a34a", "SENSIBLE": "#16a34a",
    "LIMITE":     "#d97706", "RESISTANTE": "#d97706",
    "BAS":        "#2563eb",
    "ELEVE":      "#dc2626", "TRES_ELEVE": "#7c3aed", "POSITIF": "#dc2626",
    "INCONNU":    "#6b7280",
}

def _statut(r: dict) -> str:
    st = r.get("Statut_Valeur","").strip()
    if st: return st
    v = r.get("Valeur","").lower()
    if "négatif" in v or "negatif" in v: return "NEGATIF"
    if "positif" in v or "positive" in v: return "POSITIF"
    return "INCONNU"

def generer_rapport_html(id_patient: str, id_examen: str | None = None) -> str:
    """
    Génère un rapport HTML complet prêt à imprimer/sauvegarder en PDF.
    Retourne le contenu HTML complet.
    """
    patient = db.trouver_par_id("patients", id_patient)
    if not patient:
        return "<html><body><h1>Patient introuvable</h1></body></html>"

    examens     = db.filtrer("examens", ID_Patient=id_patient)
    if id_examen:
        examens = [e for e in examens if e["ID_Examen"] == id_examen]
    diagnostics = db.filtrer("diagnostics", ID_Patient=id_patient)
    porteurs    = [d for d in diagnostics if d.get("Est_Porteur") == "OUI"]

    date_rapport = datetime.now().strftime("%d/%m/%Y à %H:%M")
    ddn          = patient.get("Date_Naissance","—")
    age          = ""
    try:
        nais = datetime.strptime(ddn, "%Y-%m-%d")
        age  = f"{(datetime.now() - nais).days // 365} ans"
    except Exception:
        pass

    # ── Tableau résultats ──────────────────────────────────
    rows_exam = ""
    for ex in examens:
        resultats = db.filtrer("resultats", ID_Examen=ex["ID_Examen"])
        if not resultats:
            continue
        rows_exam += f"""
        <tr style="background:#f0f9ff">
          <td colspan="5" style="padding:10px 14px;font-weight:700;color:#1e40af;font-size:13px;border-top:2px solid #bfdbfe">
            {ex.get('Categorie','—')} — {ex.get('ID_Examen','—')} — {ex.get('Date_Prelevement','—')}
          </td>
        </tr>"""
        for r in resultats:
            st   = _statut(r)
            col  = COULEURS.get(st, "#374151")
            crit = " ⚠" if r.get("Est_Critique") == "OUI" else ""
            ref  = f"{r.get('Ref_Min','?')} – {r.get('Ref_Max','?')}" if r.get("Ref_Min") else "—"
            rows_exam += f"""
        <tr>
          <td style="padding:7px 14px">{r.get('Parametre','—')}</td>
          <td style="padding:7px 14px;font-weight:600">{r.get('Valeur','—')} {r.get('Unite','')}</td>
          <td style="padding:7px 14px;color:#6b7280">{ref}</td>
          <td style="padding:7px 14px;color:{col};font-weight:700">{st}{crit}</td>
          <td style="padding:7px 14px;color:#6b7280;font-size:12px">{r.get('Interpretation','')}</td>
        </tr>"""

    # ── Diagnostics / Porteur ──────────────────────────────
    statut_porteur = ""
    if porteurs:
        statut_porteur = f"""
        <div style="background:#fef2f2;border:2px solid #fca5a5;border-radius:8px;padding:14px 18px;margin:16px 0">
          <div style="color:#dc2626;font-weight:700;font-size:14px;margin-bottom:8px">
            ⚠ PATIENT PORTEUR — {len(porteurs)} pathologie(s) détectée(s)
          </div>
          {''.join(f'<div style="margin:6px 0;color:#374151"><strong>{d["Pathologie_Detectee"]}</strong> — Risque : <span style="color:#dc2626">{d["Niveau_Risque"]}</span><br><small style="color:#6b7280">{d.get("Recommandation","")}</small></div>' for d in porteurs)}
        </div>"""
    else:
        statut_porteur = """
        <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:12px 18px;margin:16px 0;color:#166534;font-weight:600">
          ✓ NON PORTEUR — Aucune pathologie confirmée
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Rapport — {patient.get('Nom','')} {patient.get('Prenom','')} — {date_rapport}</title>
<style>
  @media print {{
    body {{ margin: 0; }}
    .no-print {{ display: none; }}
    .page-break {{ page-break-before: always; }}
  }}
  body {{ font-family: Arial, sans-serif; font-size: 13px; color: #111827; margin: 0; padding: 24px; background:#fff }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 16px }}
  tr:nth-child(even) {{ background: #f9fafb }}
  th {{ background: #1e40af; color: white; padding: 9px 14px; text-align: left; font-size: 12px }}
  td {{ border-bottom: 0.5px solid #e5e7eb }}
  .header {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #1e40af; padding-bottom: 16px; margin-bottom: 20px }}
  .lab {{ font-size: 20px; font-weight: 700; color: #1e40af }}
  .section {{ font-size: 13px; font-weight: 700; color: #1e40af; border-bottom: 1px solid #bfdbfe; padding-bottom: 4px; margin: 20px 0 10px; text-transform: uppercase; letter-spacing: .5px }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px }}
  .info-row {{ display: flex; gap: 8px; margin-bottom: 5px; font-size: 13px }}
  .info-lbl {{ color: #6b7280; width: 130px; flex-shrink: 0 }}
  .info-val {{ font-weight: 600 }}
  .footer {{ margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 12px; font-size: 11px; color: #9ca3af; display: flex; justify-content: space-between }}
  .print-btn {{ position: fixed; bottom: 24px; right: 24px; background: #1e40af; color: white; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 700; border: none; z-index: 999 }}
  .print-btn:hover {{ background: #1d4ed8 }}
</style>
</head>
<body>

<button class="print-btn no-print" onclick="window.print()">Imprimer / Sauvegarder PDF</button>

<div class="header">
  <div>
    <div class="lab">{LAB_NOM}</div>
    <div style="color:#6b7280;font-size:12px;margin-top:4px">{LAB_ADRESSE}</div>
    <div style="color:#6b7280;font-size:12px">{LAB_TEL} {LAB_EMAIL}</div>
  </div>
  <div style="text-align:right">
    <div style="font-weight:700;font-size:15px">RAPPORT D'ANALYSES MÉDICALES</div>
    <div style="color:#6b7280;font-size:12px">Édité le {date_rapport}</div>
    <div style="font-size:12px;margin-top:4px;color:#1e40af;font-weight:600">ID : {patient.get('ID_Patient','—')}</div>
  </div>
</div>

<div class="section">Informations patient</div>
<div class="grid2">
  <div>
    <div class="info-row"><span class="info-lbl">Nom & Prénom</span><span class="info-val">{patient.get('Nom','')} {patient.get('Prenom','')}</span></div>
    <div class="info-row"><span class="info-lbl">Date de naissance</span><span class="info-val">{ddn} ({age})</span></div>
    <div class="info-row"><span class="info-lbl">Sexe</span><span class="info-val">{'Féminin' if patient.get('Sexe')=='F' else 'Masculin'}</span></div>
    <div class="info-row"><span class="info-lbl">Groupe sanguin</span><span class="info-val">{patient.get('Groupe_Sanguin','—')}</span></div>
  </div>
  <div>
    <div class="info-row"><span class="info-lbl">Médecin traitant</span><span class="info-val">{patient.get('Medecin_Traitant','—')}</span></div>
    <div class="info-row"><span class="info-lbl">Téléphone</span><span class="info-val">{patient.get('Telephone','—')}</span></div>
    <div class="info-row"><span class="info-lbl">Email</span><span class="info-val">{patient.get('Email','—')}</span></div>
    <div class="info-row"><span class="info-lbl">Adresse</span><span class="info-val">{patient.get('Adresse','—')}</span></div>
  </div>
</div>

<div class="section">Statut porteur</div>
{statut_porteur}

<div class="section">Résultats d'analyses</div>
<table>
  <thead><tr><th>Paramètre</th><th>Valeur</th><th>Références</th><th>Statut</th><th>Interprétation</th></tr></thead>
  <tbody>{rows_exam}</tbody>
</table>

<div class="footer">
  <span>Document généré par {LAB_NOM} — Confidentiel</span>
  <span>Page 1/1 — {date_rapport}</span>
</div>

</body>
</html>"""
    return html
