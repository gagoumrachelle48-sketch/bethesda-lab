"""
=============================================================
  LABORATOIRE BETHESDA — config.py
  Configuration centrale — Projet professionnel v2.0
=============================================================
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
LOG_DIR  = BASE_DIR / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

FICHIERS = {
    "utilisateurs": str(DATA_DIR / "01_utilisateurs.csv"),
    "patients":     str(DATA_DIR / "02_patients.csv"),
    "examens":      str(DATA_DIR / "03_examens.csv"),
    "resultats":    str(DATA_DIR / "04_resultats.csv"),
    "diagnostics":  str(DATA_DIR / "05_diagnostics.csv"),
}

COLONNES = {
    "utilisateurs": ["ID_Utilisateur","Nom","Prenom","Role","Email","Mot_de_passe_hash","Telephone","Date_Creation","Statut"],
    "patients":     ["ID_Patient","Nom","Prenom","Date_Naissance","Sexe","Groupe_Sanguin","Adresse","Telephone","Email","Medecin_Traitant","ID_Utilisateur_Createur","Date_Inscription","Statut_Global"],
    "examens":      ["ID_Examen","ID_Patient","ID_Prescripteur","ID_Technicien","ID_Valideur","Date_Prescription","Date_Prelevement","Date_Resultat","Type_Examen","Categorie","Sous_Categorie","Priorite","Statut_Examen","Mode_Prelevement"],
    "resultats":    ["ID_Resultat","ID_Examen","Parametre","Valeur","Unite","Ref_Min","Ref_Max","Statut_Valeur","Interpretation","Est_Critique"],
    "diagnostics":  ["ID_Diagnostic","ID_Patient","ID_Examen","ID_Valideur","Date_Diagnostic","Conclusion","Est_Porteur","Pathologie_Detectee","Niveau_Risque","Recommandation","Prochain_Controle","Commentaire_Medical"],
}

PREFIXES_ID = {"utilisateurs":"USR","patients":"PAT","examens":"EXA","resultats":"RES","diagnostics":"DGN"}
DELIMITEUR  = ";"

STATUTS_ANORMAUX  = {"ELEVE","TRES_ELEVE","BAS","LIMITE","POSITIF","RESISTANTE"}
STATUTS_CRITIQUES = {"TRES_ELEVE","POSITIF"}
NIVEAUX_RISQUE    = ["FAIBLE","MODERE","ELEVE","TRES_ELEVE"]
STATUTS_PATIENTS  = ["NORMAL","SUIVI","PORTEUR","CRITIQUE"]
PRIORITES_EXAMEN  = ["NORMAL","URGENT","TRES_URGENT"]
GROUPES_SANGUINS  = ["A+","A-","B+","B-","AB+","AB-","O+","O-"]

ROLES_VALIDES = {"MEDECIN_VALIDEUR","MEDECIN_PRESCRIPTEUR","TECHNICIEN","SECRETAIRE","ADMIN"}

SECRET_KEY     = os.environ.get("BETHESDA_SECRET","bethesda-dev-2026-change-in-prod")
TOKEN_EXPIRE_H = 8
BCRYPT_ROUNDS  = 12
MAX_TENTATIVES = 3

API_HOST    = "0.0.0.0"
API_PORT    = 5000
API_DEBUG   = os.environ.get("BETHESDA_DEBUG","true").lower() == "true"
API_VERSION = "v1"
API_PREFIX  = f"/api/{API_VERSION}"

class C:
    RESET="\033[0m"; GRAS="\033[1m"; ROUGE="\033[91m"; VERT="\033[92m"
    JAUNE="\033[93m"; BLEU="\033[94m"; MAGENTA="\033[95m"; CYAN="\033[96m"

COULEUR_STATUT  = {"NORMAL":C.VERT,"NEGATIF":C.VERT,"SENSIBLE":C.VERT,"LIMITE":C.JAUNE,"RESISTANTE":C.JAUNE,"BAS":C.BLEU,"ELEVE":C.ROUGE,"TRES_ELEVE":C.MAGENTA,"POSITIF":C.ROUGE,"INCONNU":C.CYAN}
COULEUR_RISQUE  = {"FAIBLE":C.VERT,"MODERE":C.JAUNE,"ELEVE":C.ROUGE,"TRES_ELEVE":C.MAGENTA}
