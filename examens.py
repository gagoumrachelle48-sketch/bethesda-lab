"""
=============================================================
  LABORATOIRE BETHESDA — examens.py
=============================================================
"""
from config import C, COULEUR_STATUT, STATUTS_ANORMAUX
import database as db

def normaliser_statut(res):
    st = res.get("Statut_Valeur","").strip()
    if st: return st
    val = res.get("Valeur","").lower()
    if any(m in val for m in ["négatif","negatif"]): return "NEGATIF"
    if any(m in val for m in ["positif","positive"]): return "POSITIF"
    if "résistant" in val or "resistant" in val: return "RESISTANTE"
    if "sensible" in val: return "SENSIBLE"
    return "INCONNU"

def afficher_examen(id_examen):
    examens = db.filtrer("examens", ID_Examen=id_examen)
    if not examens:
        print(f"  {C.ROUGE}Examen introuvable.{C.RESET}"); return
    ex  = examens[0]
    res = db.filtrer("resultats", ID_Examen=id_examen)
    print(f"\n{'═'*65}\n  {C.GRAS}EXAMEN {ex['ID_Examen']}{C.RESET}\n{'═'*65}")
    print(f"  Patient    : {ex['ID_Patient']}")
    print(f"  Catégorie  : {C.GRAS}{ex.get('Categorie','')}{C.RESET}")
    print(f"  Priorité   : {ex.get('Priorite','—')}  |  Mode : {ex.get('Mode_Prelevement','—')}")
    print(f"  Prélèvement: {ex.get('Date_Prelevement','—')}  |  Résultat : {ex.get('Date_Resultat','—')}")
    print(f"\n  {C.GRAS}{'Paramètre':<35} {'Valeur':<18} {'Unité':<16} Statut{C.RESET}")
    print(f"  {'─'*63}")
    for r in res:
        st   = normaliser_statut(r)
        coul = COULEUR_STATUT.get(st,"")
        crit = f" {C.ROUGE}[!]{C.RESET}" if r.get("Est_Critique")=="OUI" else ""
        print(f"  {r.get('Parametre',''):<35} {r.get('Valeur','—'):<18} {r.get('Unite','—'):<16} {coul}{st}{C.RESET}{crit}")
        if r.get("Interpretation"):
            print(f"  {'':35} → {r['Interpretation']}")

def alertes_critiques():
    resultats = db.filtrer("resultats", Est_Critique="OUI")
    patients  = {p["ID_Patient"]: p for p in db.get("patients")}
    examens   = {e["ID_Examen"]: e for e in db.get("examens")}
    print(f"\n{'═'*65}\n  {C.ROUGE}{C.GRAS}ALERTES CRITIQUES — {len(resultats)} résultat(s){C.RESET}\n{'═'*65}")
    for r in resultats:
        ex  = examens.get(r.get("ID_Examen",""),{})
        pid = ex.get("ID_Patient","?")
        p   = patients.get(pid,{})
        st  = normaliser_statut(r)
        coul= COULEUR_STATUT.get(st,"")
        print(f"\n  {C.ROUGE}▶{C.RESET} {C.GRAS}{p.get('Nom','?')} {p.get('Prenom','?')}{C.RESET} ({pid})")
        print(f"    {r.get('Parametre','?')} : {coul}{r.get('Valeur','?')} {r.get('Unite','')}{C.RESET}")
        print(f"    → {r.get('Interpretation','')}")

def stats_examens():
    examens   = db.get("examens")
    resultats = db.get("resultats")
    par_cat   = {}
    par_prio  = {}
    par_st    = {}
    for e in examens:
        cat = e.get("Categorie","Inconnu"); par_cat[cat] = par_cat.get(cat,0)+1
        p   = e.get("Priorite","Inconnu");  par_prio[p]  = par_prio.get(p,0)+1
    for r in resultats:
        st = normaliser_statut(r); par_st[st] = par_st.get(st,0)+1
    return {"par_categorie":par_cat,"par_priorite":par_prio,"par_statut":par_st}

def afficher_stats_examens():
    stats = stats_examens()
    print(f"\n  {C.GRAS}Examens par catégorie :{C.RESET}")
    for cat,nb in sorted(stats["par_categorie"].items(),key=lambda x:-x[1]):
        print(f"  {cat:<40} {'█'*nb} {nb}")
