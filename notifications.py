"""
=============================================================
  LABORATOIRE BETHESDA — notifications.py
  SMS patients (Twilio / Orange Cameroun / MTN)
  Email notifications
=============================================================
"""
import json, urllib.request, urllib.parse, base64
from datetime import datetime
from pathlib import Path
from config import LOG_DIR

# ── Config SMS (à remplir dans .env) ─────────────────────
TWILIO_SID   = ""
TWILIO_TOKEN = ""
TWILIO_FROM  = ""
_notif_log   = LOG_DIR / "notifications.log"

def _log(type_: str, dest: str, message: str, statut: str) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    entree = {"ts": datetime.now().isoformat(), "type": type_,
               "dest": dest, "msg": message[:120], "statut": statut}
    with open(_notif_log, "a", encoding="utf-8") as f:
        f.write(json.dumps(entree, ensure_ascii=False) + "\n")

def envoyer_sms_twilio(telephone: str, message: str) -> dict:
    """Envoie un SMS via Twilio (international + Cameroun)."""
    if not TWILIO_SID or not TWILIO_TOKEN:
        _log("SMS_DEMO", telephone, message, "DEMO")
        return {"succes": True, "mode": "demo",
                "message": f"[DEMO] SMS à {telephone}: {message[:80]}"}
    try:
        url  = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
        data = urllib.parse.urlencode({
            "From": TWILIO_FROM, "To": telephone, "Body": message
        }).encode()
        auth = base64.b64encode(f"{TWILIO_SID}:{TWILIO_TOKEN}".encode()).decode()
        req  = urllib.request.Request(url, data=data,
               headers={"Authorization": f"Basic {auth}"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read())
        _log("SMS", telephone, message, "OK")
        return {"succes": True, "sid": resp.get("sid", "")}
    except Exception as e:
        _log("SMS", telephone, message, f"ERREUR: {e}")
        return {"succes": False, "erreur": str(e)}

def notifier_resultats_prets(patient: dict) -> dict:
    """Notifie le patient que ses résultats sont disponibles."""
    tel = patient.get("Telephone", "")
    nom = f"{patient.get('Prenom','')} {patient.get('Nom','')}".strip()
    msg = (f"Bonjour {nom}, vos résultats d'analyses sont disponibles "
           f"au Laboratoire Bethesda. Code d'accès: {patient.get('Code_Acces', 'N/A')}. "
           f"Tél: {patient.get('Tel_Labo', '—')}")
    if tel:
        return envoyer_sms_twilio(tel, msg)
    return {"succes": False, "erreur": "Pas de téléphone"}

def notifier_alerte_critique(patient: dict, parametre: str, valeur: str) -> dict:
    """Notifie le médecin d'un résultat critique."""
    medecin_tel = patient.get("Tel_Medecin", "")
    msg = (f"ALERTE BETHESDA — Patient {patient.get('Nom','')} {patient.get('Prenom','')}: "
           f"{parametre} = {valeur} [CRITIQUE]. Action requise immédiatement.")
    if medecin_tel:
        return envoyer_sms_twilio(medecin_tel, msg)
    return {"succes": False, "erreur": "Pas de téléphone médecin"}

def notifier_rappel_rdv(patient: dict, date_rdv: str, heure: str) -> dict:
    """Rappel rendez-vous par SMS 24h avant."""
    tel = patient.get("Telephone", "")
    nom = f"{patient.get('Prenom','')} {patient.get('Nom','')}".strip()
    msg = (f"Rappel Bethesda: Bonjour {nom}, votre rendez-vous est prévu "
           f"le {date_rdv} à {heure}. Pour annuler, appelez le laboratoire.")
    if tel:
        return envoyer_sms_twilio(tel, msg)
    return {"succes": False, "erreur": "Pas de téléphone"}

def lire_log_notifications(limite: int = 100) -> list[dict]:
    """Retourne les dernières notifications envoyées."""
    if not _notif_log.exists():
        return []
    lignes = [l for l in _notif_log.read_text(encoding="utf-8").strip().split("\n") if l]
    result = []
    for l in lignes[-limite:]:
        try:
            result.append(json.loads(l))
        except Exception:
            pass
    return list(reversed(result))
