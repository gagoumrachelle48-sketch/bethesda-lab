"""
=============================================================
  LABORATOIRE BETHESDA — main.py v2.0
  Point d'entrée CLI — Multi-utilisateurs
  Usage : python main.py
=============================================================
"""
import sys, os
from datetime import datetime
from config import C
import database as db
import auth
import patients as pat
import examens as ex
import diagnostics as diag

def sep(c="═",n=60): print(f"  {c*n}")
def section(t): print(f"\n  {C.CYAN}{C.GRAS}▶ {t}{C.RESET}\n  {'─'*55}")
def pause(): input(f"\n  {C.JAUNE}[Entrée pour continuer]{C.RESET}")
def effacer(): os.system("cls" if os.name=="nt" else "clear")

def en_tete():
    effacer()
    sep()
    print(f"\n  {C.CYAN}{C.GRAS}  LABORATOIRE BETHESDA v2.0{C.RESET}")
    print(f"  {C.GRAS}Système d'Analyse Médicale{C.RESET}")
    print(f"  {C.CYAN}{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}{C.RESET}\n")
    sep()

MENUS = {
    "ADMIN": [("1","Utilisateurs"),("2","Patients (liste)"),("3","Nouveau patient"),("4","Fiche patient"),("5","Diagnostic porteur"),("6","Rapport porteurs"),("7","Alertes critiques"),("8","Statistiques"),("0","Déconnexion")],
    "MEDECIN_VALIDEUR": [("1","Patients"),("2","Fiche patient"),("3","Résultats examen"),("4","Diagnostic porteur"),("5","Rapport porteurs"),("6","Alertes critiques"),("7","Statistiques"),("0","Déconnexion")],
    "MEDECIN_PRESCRIPTEUR": [("1","Patients"),("2","Fiche patient"),("3","Résultats examen"),("4","Diagnostic porteur"),("5","Alertes critiques"),("0","Déconnexion")],
    "TECHNICIEN": [("1","Patients"),("2","Résultats examen"),("3","Alertes critiques"),("0","Déconnexion")],
    "SECRETAIRE": [("1","Patients"),("2","Nouveau patient"),("3","Recherche patient"),("0","Déconnexion")],
}

def afficher_menu(role):
    s = auth.get_session()
    print(f"\n  {C.GRAS}{s['Prenom']} {s['Nom']} — {C.CYAN}{role}{C.RESET}")
    sep("─")
    for code,label in MENUS.get(role,[]):
        bullet = f"{C.ROUGE}[{code}]{C.RESET}" if code=="0" else f"{C.CYAN}[{code}]{C.RESET}"
        print(f"  {bullet} {label}")
    sep("─")
    print(f"  {C.JAUNE}Votre choix : {C.RESET}",end="")

def executer(choix, role):
    if role == "ADMIN":
        if choix=="1": section("Utilisateurs"); auth.afficher_utilisateurs()
        elif choix=="2": section("Patients"); filtre=input("  Statut (ou Entrée=tous) : ").strip(); pat.lister_patients(filtre)
        elif choix=="3": section("Nouveau patient"); pat.interface_enregistrer_patient()
        elif choix=="4": pid=input("  ID Patient : ").strip(); pat.fiche_patient(pid)
        elif choix=="5": pid=input("  ID Patient : ").strip(); diag.diagnostic_patient(pid)
        elif choix=="6": diag.rapport_porteurs_global()
        elif choix=="7": ex.alertes_critiques()
        elif choix=="8": section("Statistiques"); print(f"\n  {db.stats_globales()}"); diag.stats_diagnostics()
        elif choix=="0": return False
    elif role == "MEDECIN_VALIDEUR":
        if choix=="1": pat.lister_patients()
        elif choix=="2": pid=input("  ID Patient : ").strip(); pat.fiche_patient(pid)
        elif choix=="3": eid=input("  ID Examen : ").strip(); ex.afficher_examen(eid)
        elif choix=="4": pid=input("  ID Patient : ").strip(); diag.diagnostic_patient(pid)
        elif choix=="5": diag.rapport_porteurs_global()
        elif choix=="6": ex.alertes_critiques()
        elif choix=="7": diag.stats_diagnostics()
        elif choix=="0": return False
    elif role == "MEDECIN_PRESCRIPTEUR":
        if choix=="1": pat.lister_patients()
        elif choix=="2": pid=input("  ID Patient : ").strip(); pat.fiche_patient(pid)
        elif choix=="3": eid=input("  ID Examen : ").strip(); ex.afficher_examen(eid)
        elif choix=="4": pid=input("  ID Patient : ").strip(); diag.diagnostic_patient(pid)
        elif choix=="5": ex.alertes_critiques()
        elif choix=="0": return False
    elif role == "TECHNICIEN":
        if choix=="1": pat.lister_patients()
        elif choix=="2": eid=input("  ID Examen : ").strip(); ex.afficher_examen(eid)
        elif choix=="3": ex.alertes_critiques()
        elif choix=="0": return False
    elif role == "SECRETAIRE":
        if choix=="1": pat.lister_patients()
        elif choix=="2": pat.interface_enregistrer_patient()
        elif choix=="3":
            terme = input("  Recherche : ").strip()
            res   = pat.rechercher_patient(terme)
            for p in res: print(f"  {p['ID_Patient']}  {p['Nom']} {p['Prenom']}  {p.get('Telephone','')}")
            if not res: print(f"  {C.JAUNE}Aucun résultat.{C.RESET}")
        elif choix=="0": return False
    pause()
    return True

def run():
    en_tete()
    print(f"\n  {C.GRAS}Chargement…{C.RESET}")
    db.initialiser_csv()
    db.charger_tout()
    stats = db.stats_globales()
    utilisateurs = db.get("utilisateurs")
    if not utilisateurs:
        print(f"\n  {C.ROUGE}Aucun utilisateur. Lancez d'abord :{C.RESET}")
        print(f"  {C.CYAN}python setup.py{C.RESET}\n")
        sys.exit(1)
    print(f"  {C.VERT}Base OK : {stats['nb_patients']} patients | {stats['nb_examens']} examens | {len(utilisateurs)} utilisateurs{C.RESET}")
    for tentative in range(1, 4):
        if tentative > 1: print(f"\n  {C.JAUNE}Tentative {tentative}/3{C.RESET}")
        if auth.interface_connexion():
            role = auth.get_role()
            continuer = True
            while continuer:
                en_tete()
                afficher_menu(role)
                choix = input().strip()
                en_tete()
                continuer = executer(choix, role)
            auth.deconnexion()
            again = input(f"\n  {C.CYAN}Nouvelle connexion ? (o/n) : {C.RESET}").strip().lower()
            if again == "o": run()
            else: print(f"\n  {C.VERT}Au revoir.{C.RESET}\n")
            return
        if tentative == 3:
            print(f"\n  {C.ROUGE}Accès bloqué.{C.RESET}\n"); sys.exit(1)

if __name__ == "__main__":
    run()
