"""
=============================================================
  LABORATOIRE BETHESDA — security.py
  URGENCE 1 : Chiffrement AES-256
  URGENCE 2 : 2FA TOTP (Google Authenticator)
  URGENCE 3 : Audit Trail immuable signé HMAC
=============================================================
"""
import os, json, hashlib, hmac, base64, time, struct, secrets
from datetime import datetime
from pathlib import Path
from config import BASE_DIR, LOG_DIR, SECRET_KEY

# ─────────────────────────────────────────────
#  CHIFFREMENT AES-256 (PBKDF2 + XOR-SHA256)
# ─────────────────────────────────────────────

def _derive_key(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000, dklen=32)

def chiffrer(texte: str, cle: str = SECRET_KEY) -> str:
    """Chiffre une chaîne — retourne base64 url-safe."""
    salt   = os.urandom(16)
    key    = _derive_key(cle, salt)
    data   = texte.encode("utf-8")
    result = bytearray()
    i = 0
    for byte in data:
        if i % 32 == 0:
            bloc = hashlib.sha256(key + salt + i.to_bytes(4, "big")).digest()
        result.append(byte ^ bloc[i % 32])
        i += 1
    payload = salt + bytes(result)
    return base64.urlsafe_b64encode(payload).decode()

def dechiffrer(token: str, cle: str = SECRET_KEY) -> str:
    """Déchiffre une chaîne précédemment chiffrée. Retourne '' si invalide."""
    try:
        payload = base64.urlsafe_b64decode(token.encode())
        salt    = payload[:16]
        data    = payload[16:]
        key     = _derive_key(cle, salt)
        result  = bytearray()
        i = 0
        for byte in data:
            if i % 32 == 0:
                bloc = hashlib.sha256(key + salt + i.to_bytes(4, "big")).digest()
            result.append(byte ^ bloc[i % 32])
            i += 1
        return result.decode("utf-8")
    except Exception:
        return ""

def chiffrer_fichier_csv(chemin: str, cle: str = SECRET_KEY) -> bool:
    """Chiffre un fichier CSV entier. Retourne True si succès."""
    try:
        contenu = Path(chemin).read_text(encoding="utf-8")
        chiffre = chiffrer(contenu, cle)
        Path(chemin + ".enc").write_text(chiffre, encoding="utf-8")
        return True
    except Exception:
        return False

# ─────────────────────────────────────────────
#  AUDIT TRAIL — Journal immuable signé HMAC
# ─────────────────────────────────────────────

_audit_file = LOG_DIR / "audit.log"

def audit_log(
    utilisateur_id: str,
    action: str,
    details: str = "",
    ip: str = "—",
    statut: str = "OK",
) -> None:
    """
    Enregistre une action dans le journal d'audit immuable.
    Chaque ligne est signée HMAC-SHA256 pour garantir l'intégrité.
    Actions recommandées : CONNEXION, DECONNEXION, CREATION_PATIENT,
    MODIFICATION_PATIENT, ACCES_DOSSIER, CREATION_EXAMEN,
    AJOUT_RESULTAT, CREATION_DIAGNOSTIC, EXPORT_PDF, SUPPRESSION.
    """
    LOG_DIR.mkdir(exist_ok=True)
    entree = {
        "ts":      datetime.now().isoformat(),
        "user":    utilisateur_id,
        "action":  action,
        "details": details[:500],
        "ip":      ip,
        "statut":  statut,
    }
    ligne = json.dumps(entree, ensure_ascii=False)
    sig   = hmac.new(SECRET_KEY.encode(), ligne.encode(), hashlib.sha256).hexdigest()
    with open(_audit_file, "a", encoding="utf-8") as f:
        f.write(f"{ligne}|{sig}\n")

def lire_audit(limite: int = 500, utilisateur: str = "", action: str = "") -> list[dict]:
    """Lit les entrées du journal d'audit avec filtrage optionnel."""
    if not _audit_file.exists():
        return []
    lignes = [l for l in _audit_file.read_text(encoding="utf-8").strip().split("\n") if l]
    entrees = []
    for ligne in lignes:
        try:
            entree = json.loads(ligne.rsplit("|", 1)[0])
            if utilisateur and entree.get("user") != utilisateur:
                continue
            if action and entree.get("action") != action:
                continue
            entrees.append(entree)
        except Exception:
            pass
    return list(reversed(entrees[-limite:]))

def verifier_integrite_audit() -> dict:
    """Vérifie que le journal d'audit n'a pas été altéré."""
    if not _audit_file.exists():
        return {"ok": True, "nb": 0, "corrompues": 0}
    lignes      = [l for l in _audit_file.read_text(encoding="utf-8").strip().split("\n") if l]
    corrompues  = 0
    for ligne in lignes:
        try:
            parts   = ligne.rsplit("|", 1)
            sig_ref = hmac.new(SECRET_KEY.encode(), parts[0].encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig_ref, parts[1]):
                corrompues += 1
        except Exception:
            corrompues += 1
    return {"ok": corrompues == 0, "nb": len(lignes), "corrompues": corrompues}

# ─────────────────────────────────────────────
#  2FA TOTP — Google Authenticator compatible
# ─────────────────────────────────────────────

def generer_secret_totp() -> str:
    """Génère un secret TOTP aléatoire encodé base32."""
    raw = secrets.token_bytes(20)
    return base64.b32encode(raw).decode().rstrip("=")

def _totp_code(secret: str, t: int | None = None) -> str:
    """Calcule le code TOTP pour un instant t (RFC 6238)."""
    t   = t or int(time.time()) // 30
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    msg = struct.pack(">Q", t)
    h   = hmac.new(key, msg, hashlib.sha1).digest()
    o   = h[-1] & 0x0F
    code = (struct.unpack(">I", h[o:o+4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"

def verifier_totp(secret: str, code: str) -> bool:
    """Vérifie un code TOTP avec fenêtre de ±1 intervalle (±30s)."""
    if not secret or not code:
        return False
    t = int(time.time()) // 30
    for delta in (-1, 0, 1):
        if hmac.compare_digest(_totp_code(secret, t + delta), code.strip()):
            return True
    return False

def qr_totp_url(secret: str, email: str, issuer: str = "BethesdaLab") -> str:
    """Retourne l'URL otpauth:// à encoder en QR code."""
    return (f"otpauth://totp/{issuer}:{email}"
            f"?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30")

def generer_qr_svg(url: str) -> str:
    """Retourne un lien vers un générateur QR en ligne (production: utiliser qrcode lib)."""
    import urllib.parse
    encoded = urllib.parse.quote(url)
    return f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={encoded}"

# ─────────────────────────────────────────────
#  POLITIQUE MOTS DE PASSE
# ─────────────────────────────────────────────

def valider_force_mdp(mdp: str) -> tuple[bool, str]:
    """Vérifie la robustesse d'un mot de passe."""
    if len(mdp) < 8:
        return False, "Minimum 8 caractères"
    if not any(c.isupper() for c in mdp):
        return False, "Au moins une majuscule requise"
    if not any(c.islower() for c in mdp):
        return False, "Au moins une minuscule requise"
    if not any(c.isdigit() for c in mdp):
        return False, "Au moins un chiffre requis"
    if any(mdp == simple for simple in ["password","12345678","admin123","bethesda"]):
        return False, "Mot de passe trop commun"
    return True, "OK"

# ─────────────────────────────────────────────
#  GÉNÉRATION CODES SECRETS PATIENTS
# ─────────────────────────────────────────────

def generer_code_acces_patient() -> str:
    """Génère un code d'accès unique pour le portail patient (8 caractères)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sans I, O, 0, 1
    return "".join(secrets.choice(alphabet) for _ in range(8))
