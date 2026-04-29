"""
=============================================================
  LABORATOIRE BETHESDA — patients.py
  Gestion CLI des patients
=============================================================
"""
import csv
from datetime import datetime
from config import C, COULEUR_RISQUE, FICHIERS, DELIMITEUR
import database as db
import auth

def _couleur_statut(statut):
    return {"NORMAL":C.VERT,"SUIVI":C.JAUNE,"PORTEUR":C.ROUGE,"CRITIQUE":C.MAGENTA}.get(statut, C.CYAN)

def lister_patients(filtre_statut=""):
    patients = db.get("patients")
    if filtre_statut:
        patients = [p for p in patients if p.get("Statut_Global")==filtre_statut.upper()]
    if not patients:
        print(f"  {C.JAUNE}Aucun patient.{C.RESET}")
        return
    print(f"\n  {C.GRAS}{'ID':<10} {'Nom':<15} {'Prénom':<15} {'DDN':<12} {'S':<2} {'Médecin':<25} {'Statut'}{C.RESET}")
    print(f"  {'─'*90}")
    for p in patients:
        sc = _couleur_statut(p.get("Statut_Global",""))
        print(f"  {p['ID_Patient']:<10} {p['Nom']:<15} {p['Prenom']:<15} {p['Date_Naissance']:<12} {p['Sexe']:<2} {p['Medecin_Traitant']:<25} {sc}{p.get('Statut_Global','')}{C.RESET}")
    print(f"\n  Total : {len(patients)} patient(s)")

def fiche_patient(id_patient):
    patient = db.trouver_par_id("patients", id_patient)
    if not patient:
        print(f"  {C.ROUGE}Patient introuvable.{C.RESET}"); return
    examens     = db.filtrer("examens", ID_Patient=id_patient)
    diagnostics = db.filtrer("diagnostics", ID_Patient=id_patient)
    porteurs    = [d for d in diagnostics if d.get("Est_Porteur")=="OUI"]
    sc = _couleur_statut(patient.get("Statut_Global",""))
    print(f"\n{'═'*65}")
    print(f"  {C.GRAS}FICHE PATIENT — {patient['Nom']} {patient['Prenom']}{C.RESET}")
    print(f"{'═'*65}")
    for k,v in [("ID",patient['ID_Patient']),("DDN",patient['Date_Naissance']),("Sexe",patient['Sexe']),("Groupe sg.",patient.get('Groupe_Sanguin','—')),("Téléphone",patient.get('Telephone','—')),("Email",patient.get('Email','—')),("Médecin",patient.get('Medecin_Traitant','—')),("Inscription",patient.get('Date_Inscription','—'))]:
        print(f"  {k:<15} : {v}")
    print(f"  {'Statut':<15} : {sc}{C.GRAS}{patient.get('Statut_Global','—')}{C.RESET}")
    print(f"\n  {'─'*63}")
    if porteurs:
        print(f"  {C.ROUGE}{C.GRAS}PORTEUR — {len(porteurs)} pathologie(s){C.RESET}")
        for d in porteurs:
            cr = COULEUR_RISQUE.get(d.get("Niveau_Risque",""),"")
            print(f"\n  ▶ {C.GRAS}{d['Pathologie_Detectee']}{C.RESET}  Risque: {cr}{d['Niveau_Risque']}{C.RESET}")
            print(f"    → {d['Recommandation']}")
    else:
        print(f"  {C.VERT}{C.GRAS}NON PORTEUR{C.RESET}")
    print(f"\n  Examens : {len(examens)}")

def rechercher_patient(terme):
    return db.rechercher("patients", terme, ["Nom","Prenom","ID_Patient","Email"])

def enregistrer_patient(data):
    if not auth.a_role("SECRETAIRE","ADMIN","MEDECIN_PRESCRIPTEUR"):
        print(f"  {C.ROUGE}Accès refusé.{C.RESET}"); return ""
    data["Nom"]    = data.get("Nom","").upper()
    data["Prenom"] = data.get("Prenom","").capitalize()
    data["Statut_Global"] = "NORMAL"
    data["ID_Utilisateur_Createur"] = (auth.get_session() or {}).get("ID_Utilisateur","INCONNU")
    nouveau = db.inserer("patients", data)
    print(f"  {C.VERT}Patient créé : {nouveau['ID_Patient']}{C.RESET}")
    return nouveau["ID_Patient"]

def interface_enregistrer_patient():
    print(f"\n  {C.GRAS}─── Nouveau patient ───{C.RESET}")
    data = {
        "Nom":              input("  Nom           : ").strip(),
        "Prenom":           input("  Prénom        : ").strip(),
        "Date_Naissance":   input("  DDN (AAAA-MM-JJ) : ").strip(),
        "Sexe":             input("  Sexe (M/F)    : ").strip().upper(),
        "Groupe_Sanguin":   input("  Groupe sg.    : ").strip(),
        "Adresse":          input("  Adresse       : ").strip(),
        "Telephone":        input("  Téléphone     : ").strip(),
        "Email":            input("  Email         : ").strip(),
        "Medecin_Traitant": input("  Médecin       : ").strip(),
    }
    enregistrer_patient(data)
