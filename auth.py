"""
=============================================================
  LABORATOIRE BETHESDA — auth.py
  Authentification sécurisée — JWT + bcrypt
=============================================================
"""

import hashlib
import hmac
import base64
import json
import time
import getpass
from datetime import datetime
from config import C, ROLES_VALIDES, SECRET_KEY, TOKEN_EXPIRE_H, MAX_TENTATIVES
import database as db

_session: dict | None = None
_tentatives: dict[str, int] = {}  # email → nb tentatives échouées


# ─────────────────────────────────────────────
#  HACHAGE MOT DE PASSE
# ─────────────────────────────────────────────

def hacher_mdp(mdp: str) -> str:
    """Hash PBKDF2-SHA256 (production : utiliser bcrypt)."""
    sel = SECRET_KEY.encode()
    return hashlib.pbkdf2_hmac("sha256", mdp.encode(), sel, 100_000).hex()


def verifier_mdp(mdp: str, hash_stocke: str) -> bool:
    """Comparaison en temps constant pour éviter les timing attacks."""
    hash_calcule = hacher_mdp(mdp)
    return hmac.compare_digest(hash_calcule, hash_stocke)


# ─────────────────────────────────────────────
#  TOKEN JWT SIMPLE (sans dépendance externe)
# ─────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def generer_token(payload: dict) -> str:
    header  = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload["exp"] = int(time.time()) + TOKEN_EXPIRE_H * 3600
    body    = _b64url(json.dumps(payload).encode())
    sig_raw = hmac.new(SECRET_KEY.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    sig     = _b64url(sig_raw)
    return f"{header}.{body}.{sig}"


def verifier_token(token: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, body, sig = parts
        sig_raw = hmac.new(SECRET_KEY.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
        sig_attendue = _b64url(sig_raw)
        if not hmac.compare_digest(sig, sig_attendue):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body + "=="))
        if payload.get("exp", 0) < time.time():
            return None  # Token expiré
        return payload
    except Exception:
        return None


# ─────────────────────────────────────────────
#  SESSION
# ─────────────────────────────────────────────

def get_session() -> dict | None:
    return _session

def est_connecte() -> bool:
    return _session is not None

def get_role() -> str | None:
    return _session.get("Role") if _session else None

def a_role(*roles: str) -> bool:
    return bool(_session and _session.get("Role") in roles)


# ─────────────────────────────────────────────
#  CONNEXION / DÉCONNEXION
# ─────────────────────────────────────────────

def connexion(email: str, mot_de_passe: str) -> dict | None:
    """
    Authentifie un utilisateur.
    Retourne la session dict ou None si échec.
    Bloque après MAX_TENTATIVES tentatives échouées.
    """
    global _session

    email = email.strip().lower()

    # Vérifier blocage
    if _tentatives.get(email, 0) >= MAX_TENTATIVES:
        return {"erreur": "compte_bloque"}

    utilisateurs = db.get("utilisateurs")
    utilisateur  = next(
        (u for u in utilisateurs
         if u.get("Email", "").lower() == email
         and u.get("Statut") == "ACTIF"),
        None
    )

    if not utilisateur:
        _tentatives[email] = _tentatives.get(email, 0) + 1
        return None

    # Vérification du mot de passe
    hash_stocke = utilisateur.get("Mot_de_passe_hash", "")
    # Vérification PBKDF2 du mot de passe
    mdp_ok = (
        mot_de_passe.strip() != "" and
        verifier_mdp(mot_de_passe, hash_stocke)
    )

    if not mdp_ok:
        _tentatives[email] = _tentatives.get(email, 0) + 1
        return None

    # Succès → réinitialiser compteur
    _tentatives.pop(email, None)

    _session = {
        "ID_Utilisateur":  utilisateur["ID_Utilisateur"],
        "Nom":             utilisateur["Nom"],
        "Prenom":          utilisateur["Prenom"],
        "Role":            utilisateur["Role"],
        "Email":           utilisateur["Email"],
        "Telephone":       utilisateur.get("Telephone", ""),
        "heure_connexion": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "token":           generer_token({
            "sub":  utilisateur["ID_Utilisateur"],
            "role": utilisateur["Role"],
            "email": email,
        }),
    }
    return _session


def connexion_par_token(token: str) -> dict | None:
    """Restaure une session depuis un token JWT (pour l'API)."""
    global _session
    payload = verifier_token(token)
    if not payload:
        return None
    utilisateur = db.trouver_par_id("utilisateurs", payload["sub"])
    if not utilisateur or utilisateur.get("Statut") != "ACTIF":
        return None
    _session = {
        "ID_Utilisateur": utilisateur["ID_Utilisateur"],
        "Nom":            utilisateur["Nom"],
        "Prenom":         utilisateur["Prenom"],
        "Role":           utilisateur["Role"],
        "Email":          utilisateur["Email"],
        "Telephone":      utilisateur.get("Telephone", ""),
        "heure_connexion": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "token":          token,
    }
    return _session


def deconnexion() -> None:
    global _session
    _session = None


# ─────────────────────────────────────────────
#  GESTION DES UTILISATEURS
# ─────────────────────────────────────────────

def creer_utilisateur(donnees: dict) -> dict:
    """Crée un nouvel utilisateur avec mot de passe haché."""
    if donnees.get("Role") not in ROLES_VALIDES:
        raise ValueError(f"Rôle invalide : {donnees.get('Role')}")
    mdp = donnees.pop("mot_de_passe", "")
    if not mdp:
        raise ValueError("Mot de passe obligatoire")
    donnees["Mot_de_passe_hash"] = hacher_mdp(mdp)
    donnees["Statut"]            = "ACTIF"
    donnees["Date_Creation"]     = datetime.now().strftime("%Y-%m-%d")
    return db.inserer("utilisateurs", donnees)


def changer_mot_de_passe(id_utilisateur: str, ancien: str, nouveau: str) -> bool:
    utilisateur = db.trouver_par_id("utilisateurs", id_utilisateur)
    if not utilisateur:
        return False
    if not verifier_mdp(ancien, utilisateur.get("Mot_de_passe_hash", "")):
        return False
    return db.mettre_a_jour("utilisateurs", "ID_Utilisateur", id_utilisateur,
                            {"Mot_de_passe_hash": hacher_mdp(nouveau)})


# ─────────────────────────────────────────────
#  INTERFACE CLI
# ─────────────────────────────────────────────

def afficher_utilisateurs() -> None:
    utilisateurs = db.get("utilisateurs")
    if not utilisateurs:
        print(f"  {C.JAUNE}Aucun utilisateur. Créez-en un avec : python setup.py{C.RESET}")
        return
    print(f"\n  {C.GRAS}{'ID':<12} {'Nom':<15} {'Prénom':<15} {'Rôle':<25} {'Statut'}{C.RESET}")
    print(f"  {'─'*75}")
    for u in utilisateurs:
        sc = C.VERT if u.get("Statut") == "ACTIF" else C.ROUGE
        print(f"  {u['ID_Utilisateur']:<12} {u['Nom']:<15} {u['Prenom']:<15} {u['Role']:<25} {sc}{u.get('Statut','')}{C.RESET}")


def interface_connexion() -> bool:
    print(f"\n  {C.GRAS}{'═'*50}{C.RESET}")
    print(f"  {C.CYAN}{C.GRAS}  LABORATOIRE BETHESDA — Connexion{C.RESET}")
    print(f"  {C.GRAS}{'═'*50}{C.RESET}")
    utilisateurs = db.get("utilisateurs")
    if not utilisateurs:
        print(f"\n  {C.ROUGE}Aucun utilisateur. Lancez d'abord : python setup.py{C.RESET}\n")
        return False
    print(f"\n  Comptes actifs : {len([u for u in utilisateurs if u.get('Statut')=='ACTIF'])}")
    email = input("\n  Email : ").strip()
    mdp   = getpass.getpass("  Mot de passe : ")
    result = connexion(email, mdp)
    if result and "erreur" in result:
        print(f"\n  {C.ROUGE}Compte bloqué après {MAX_TENTATIVES} tentatives.{C.RESET}")
        return False
    if result:
        print(f"\n  {C.VERT}{C.GRAS}Connexion réussie !{C.RESET}")
        print(f"  Bienvenue {result['Prenom']} {result['Nom']} — {result['Role']}")
        return True
    print(f"\n  {C.ROUGE}Email ou mot de passe incorrect.{C.RESET}")
    return False
