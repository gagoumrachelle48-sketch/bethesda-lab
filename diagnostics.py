"""
=============================================================
  LABORATOIRE BETHESDA — diagnostics.py
=============================================================
"""
from config import C, COULEUR_RISQUE
import database as db

def diagnostic_patient(id_patient):
    patient     = db.trouver_par_id("patients", id_patient)
    diagnostics = db.filtrer("diagnostics", ID_Patient=id_patient)
    if not patient:
        print(f"  {C.ROUGE}Patient introuvable.{C.RESET}"); return
    porteurs = [d for d in diagnostics if d.get("Est_Porteur")=="OUI"]
    print(f"\n{'═'*65}\n  {C.GRAS}DIAGNOSTIC — {patient['Nom']} {patient['Prenom']}{C.RESET}\n{'═'*65}")
    if porteurs:
        ordre = ["FAIBLE","MODERE","ELEVE","TRES_ELEVE"]
        rmax  = max(porteurs, key=lambda d: ordre.index(d.get("Niveau_Risque","FAIBLE")) if d.get("Niveau_Risque","FAIBLE") in ordre else 0)
        cr    = COULEUR_RISQUE.get(rmax.get("Niveau_Risque",""),"")
        print(f"\n  {C.ROUGE}{C.GRAS}PORTEUR CONFIRMÉ{C.RESET}  Risque max : {cr}{C.GRAS}{rmax.get('Niveau_Risque','')}{C.RESET}")
        for d in porteurs:
            cr2 = COULEUR_RISQUE.get(d.get("Niveau_Risque",""),"")
            print(f"\n  {C.ROUGE}[PORTEUR]{C.RESET} {C.GRAS}{d['Pathologie_Detectee']}{C.RESET}")
            print(f"  Risque : {cr2}{d['Niveau_Risque']}{C.RESET} | {d.get('Date_Diagnostic','—')}")
            print(f"  → {d['Recommandation']}")
    else:
        print(f"\n  {C.VERT}{C.GRAS}NON PORTEUR{C.RESET}")

def rapport_porteurs_global():
    diagnostics = db.filtrer("diagnostics", Est_Porteur="OUI")
    patients    = {p["ID_Patient"]:p for p in db.get("patients")}
    par_patient = {}
    for d in diagnostics:
        pid = d["ID_Patient"]
        par_patient.setdefault(pid,[]).append(d)
    print(f"\n{'═'*65}\n  {C.ROUGE}{C.GRAS}RAPPORT PORTEURS — {len(par_patient)} patient(s){C.RESET}\n{'═'*65}")
    ordre = ["FAIBLE","MODERE","ELEVE","TRES_ELEVE"]
    for niv in reversed(ordre):
        groupe = [(pid,diags) for pid,diags in par_patient.items() if max(diags,key=lambda d:ordre.index(d.get("Niveau_Risque","FAIBLE")) if d.get("Niveau_Risque","FAIBLE") in ordre else 0).get("Niveau_Risque")==niv]
        if not groupe: continue
        cr = COULEUR_RISQUE.get(niv,"")
        print(f"\n  {cr}{C.GRAS}── RISQUE {niv} ({len(groupe)}) ──{C.RESET}")
        for pid,diags in groupe:
            p = patients.get(pid,{})
            print(f"  {C.GRAS}{p.get('Nom','?')} {p.get('Prenom','?')}{C.RESET} ({pid})")
            for d in diags:
                print(f"    • {d['Pathologie_Detectee']}")

def stats_diagnostics():
    diagnostics = db.get("diagnostics")
    nb_total    = len(diagnostics)
    nb_porteurs = sum(1 for d in diagnostics if d.get("Est_Porteur")=="OUI")
    print(f"\n  Diagnostics totaux   : {nb_total}")
    print(f"  {C.ROUGE}Porteurs             : {nb_porteurs}{C.RESET}")
    print(f"  {C.VERT}Non porteurs         : {nb_total-nb_porteurs}{C.RESET}")
