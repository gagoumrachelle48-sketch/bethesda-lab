"""
=============================================================
  LABORATOIRE BETHESDA — setup.py
  Initialisation du projet : crée les CSV vides
  et le premier compte ADMIN
  Usage : python setup.py
=============================================================
"""

import getpass
import sys
from pathlib import Path

# Ajouter le dossier parent au path
sys.path.insert(0, str(Path(__file__).parent))

import database as db
import auth as auth_mod
from config import C, DATA_DIR


def setup():
    print(f"\n  {'═'*55}")
    print(f"  {C.CYAN}{C.GRAS}  LABORATOIRE BETHESDA — Setup initial{C.RESET}")
    print(f"  {'═'*55}\n")

    # 1. Initialiser les CSV
    print(f"  {C.GRAS}1. Initialisation des fichiers CSV…{C.RESET}")
    db.initialiser_csv()
    print(f"  {C.VERT}✓ Fichiers CSV prêts dans : {DATA_DIR}{C.RESET}\n")

    # 2. Vérifier si des utilisateurs existent déjà
    utilisateurs = db.get("utilisateurs", forcer=True)
    if utilisateurs:
        print(f"  {C.JAUNE}Des utilisateurs existent déjà ({len(utilisateurs)}).{C.RESET}")
        rep = input("  Créer un nouvel utilisateur quand même ? (o/n) : ").strip().lower()
        if rep != "o":
            print(f"\n  {C.VERT}Setup terminé.{C.RESET}\n")
            return

    # 3. Créer le premier compte ADMIN
    print(f"  {C.GRAS}2. Création du compte administrateur{C.RESET}")
    print(f"  {C.JAUNE}(Ce compte aura accès à toutes les fonctionnalités){C.RESET}\n")

    nom    = input("  Nom           : ").strip().upper()
    prenom = input("  Prénom        : ").strip().capitalize()
    email  = input("  Email         : ").strip().lower()
    tel    = input("  Téléphone     : ").strip()

    print(f"\n  {C.JAUNE}Rôles disponibles :{C.RESET}")
    roles = ["ADMIN", "MEDECIN_VALIDEUR", "MEDECIN_PRESCRIPTEUR", "TECHNICIEN", "SECRETAIRE"]
    for i, r in enumerate(roles, 1):
        print(f"  [{i}] {r}")
    choix_role = input("  Choisir un rôle [1-5] (défaut=1 ADMIN) : ").strip()
    try:
        role = roles[int(choix_role) - 1]
    except (ValueError, IndexError):
        role = "ADMIN"

    mdp = getpass.getpass("  Mot de passe  : ")
    if not mdp:
        print(f"  {C.ROUGE}Mot de passe obligatoire.{C.RESET}")
        return

    mdp2 = getpass.getpass("  Confirmer     : ")
    if mdp != mdp2:
        print(f"  {C.ROUGE}Les mots de passe ne correspondent pas.{C.RESET}")
        return

    try:
        nouveau = auth_mod.creer_utilisateur({
            "Nom":           nom,
            "Prenom":        prenom,
            "Role":          role,
            "Email":         email,
            "Telephone":     tel,
            "mot_de_passe":  mdp,
        })
        print(f"\n  {C.VERT}{C.GRAS}✓ Utilisateur créé !{C.RESET}")
        print(f"  ID    : {nouveau['ID_Utilisateur']}")
        print(f"  Email : {nouveau['Email']}")
        print(f"  Rôle  : {nouveau['Role']}")
    except Exception as e:
        print(f"\n  {C.ROUGE}Erreur : {e}{C.RESET}")
        return

    print(f"\n  {'═'*55}")
    print(f"  {C.VERT}{C.GRAS}Setup terminé !{C.RESET}")
    print(f"\n  Prochaines étapes :")
    print(f"  {C.CYAN}1.{C.RESET} Démarrer l'API  : python api.py")
    print(f"  {C.CYAN}2.{C.RESET} Ouvrir le dashboard : bethesda_dashboard.html")
    print(f"  {'═'*55}\n")


if __name__ == "__main__":
    setup()
