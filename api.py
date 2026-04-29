"""
=============================================================
  LABORATOIRE BETHESDA — api.py
  API REST Flask — Toutes les routes CRUD
  Usage : python api.py
=============================================================
"""

import json
import functools
from datetime import datetime
from flask import Flask, request, jsonify, Response
from config import API_HOST, API_PORT, API_DEBUG, API_PREFIX
import database as db
import auth as auth_mod

app = Flask(__name__)
app.config["JSON_ENSURE_ASCII"] = False


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def cors(resp: Response) -> Response:
    resp.headers["Access-Control-Allow-Origin"]  = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    return resp


def ok(data=None, msg="", code=200):
    return cors(jsonify({"succes": True, "message": msg, "data": data})), code


def err(msg="Erreur", code=400):
    return cors(jsonify({"succes": False, "erreur": msg})), code


def token_requis(roles=None):
    """Décorateur : vérifie le token JWT et optionnellement le rôle."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return err("Token manquant", 401)
            token = header[7:]
            payload = auth_mod.verifier_token(token)
            if not payload:
                return err("Token invalide ou expiré", 401)
            if roles and payload.get("role") not in roles:
                return err("Accès refusé", 403)
            request.utilisateur = payload
            return fn(*args, **kwargs)
        return wrapper
    return decorator


@app.after_request
def after(resp):
    return cors(resp)


@app.route(f"{API_PREFIX}/options", methods=["OPTIONS"])
@app.route(f"{API_PREFIX}/<path:p>", methods=["OPTIONS"])
def preflight(p=""):
    return cors(Response(status=204))


# ─────────────────────────────────────────────
#  AUTH
# ─────────────────────────────────────────────

@app.route(f"{API_PREFIX}/auth/connexion", methods=["POST"])
def route_connexion():
    body = request.get_json() or {}
    email = body.get("email", "")
    mdp   = body.get("mot_de_passe", "")
    if not email or not mdp:
        return err("Email et mot de passe requis")
    result = auth_mod.connexion(email, mdp)
    if not result:
        return err("Identifiants incorrects", 401)
    if "erreur" in result:
        return err("Compte bloqué", 403)
    return ok({
        "token":   result["token"],
        "id":      result["ID_Utilisateur"],
        "nom":     result["Nom"],
        "prenom":  result["Prenom"],
        "role":    result["Role"],
        "email":   result["Email"],
    }, "Connexion réussie")


@app.route(f"{API_PREFIX}/auth/verifier", methods=["GET"])
@token_requis()
def route_verifier_token():
    return ok(request.utilisateur, "Token valide")


# ─────────────────────────────────────────────
#  UTILISATEURS
# ─────────────────────────────────────────────

@app.route(f"{API_PREFIX}/utilisateurs", methods=["GET"])
@token_requis(roles=["ADMIN"])
def route_lister_utilisateurs():
    users = db.get("utilisateurs")
    # Ne jamais exposer le hash
    safe = [{k: v for k, v in u.items() if k != "Mot_de_passe_hash"} for u in users]
    return ok(safe)


@app.route(f"{API_PREFIX}/utilisateurs", methods=["POST"])
@token_requis(roles=["ADMIN"])
def route_creer_utilisateur():
    body = request.get_json() or {}
    champs_requis = ["Nom", "Prenom", "Role", "Email", "mot_de_passe"]
    manquants = [c for c in champs_requis if not body.get(c)]
    if manquants:
        return err(f"Champs requis : {', '.join(manquants)}")
    try:
        nouveau = auth_mod.creer_utilisateur(body)
        safe = {k: v for k, v in nouveau.items() if k != "Mot_de_passe_hash"}
        return ok(safe, "Utilisateur créé", 201)
    except ValueError as e:
        return err(str(e))


@app.route(f"{API_PREFIX}/utilisateurs/<uid>", methods=["PUT"])
@token_requis(roles=["ADMIN"])
def route_modifier_utilisateur(uid):
    body = request.get_json() or {}
    body.pop("Mot_de_passe_hash", None)
    ok_ = db.mettre_a_jour("utilisateurs", "ID_Utilisateur", uid, body)
    return ok(None, "Mis à jour") if ok_ else err("Utilisateur introuvable", 404)


@app.route(f"{API_PREFIX}/utilisateurs/<uid>/desactiver", methods=["PUT"])
@token_requis(roles=["ADMIN"])
def route_desactiver_utilisateur(uid):
    ok_ = db.mettre_a_jour("utilisateurs", "ID_Utilisateur", uid, {"Statut": "INACTIF"})
    return ok(None, "Désactivé") if ok_ else err("Utilisateur introuvable", 404)


# ─────────────────────────────────────────────
#  PATIENTS
# ─────────────────────────────────────────────

@app.route(f"{API_PREFIX}/patients", methods=["GET"])
@token_requis()
def route_lister_patients():
    patients = db.get("patients")
    statut   = request.args.get("statut")
    terme    = request.args.get("q")
    if statut:
        patients = [p for p in patients if p.get("Statut_Global") == statut.upper()]
    if terme:
        patients = db.rechercher("patients", terme, ["Nom", "Prenom", "ID_Patient", "Email"])
    return ok(patients)


@app.route(f"{API_PREFIX}/patients/<pid>", methods=["GET"])
@token_requis()
def route_get_patient(pid):
    patient = db.trouver_par_id("patients", pid)
    if not patient:
        return err("Patient introuvable", 404)
    examens     = db.filtrer("examens", ID_Patient=pid)
    diagnostics = db.filtrer("diagnostics", ID_Patient=pid)
    for ex in examens:
        ex["resultats"] = db.filtrer("resultats", ID_Examen=ex["ID_Examen"])
    return ok({"patient": patient, "examens": examens, "diagnostics": diagnostics})


@app.route(f"{API_PREFIX}/patients", methods=["POST"])
@token_requis(roles=["ADMIN", "SECRETAIRE", "MEDECIN_PRESCRIPTEUR"])
def route_creer_patient():
    body = request.get_json() or {}
    champs_requis = ["Nom", "Prenom", "Date_Naissance", "Sexe"]
    manquants = [c for c in champs_requis if not body.get(c)]
    if manquants:
        return err(f"Champs requis : {', '.join(manquants)}")
    body["Nom"]          = body["Nom"].upper().strip()
    body["Prenom"]       = body["Prenom"].strip().capitalize()
    body["Statut_Global"] = body.get("Statut_Global", "NORMAL")
    body["ID_Utilisateur_Createur"] = request.utilisateur.get("sub", "")
    nouveau = db.inserer("patients", body)
    return ok(nouveau, "Patient créé", 201)


@app.route(f"{API_PREFIX}/patients/<pid>", methods=["PUT"])
@token_requis(roles=["ADMIN", "SECRETAIRE", "MEDECIN_PRESCRIPTEUR", "MEDECIN_VALIDEUR"])
def route_modifier_patient(pid):
    body = request.get_json() or {}
    ok_ = db.mettre_a_jour("patients", "ID_Patient", pid, body)
    return ok(None, "Patient mis à jour") if ok_ else err("Patient introuvable", 404)


# ─────────────────────────────────────────────
#  EXAMENS
# ─────────────────────────────────────────────

@app.route(f"{API_PREFIX}/examens", methods=["GET"])
@token_requis()
def route_lister_examens():
    examens   = db.get("examens")
    priorite  = request.args.get("priorite")
    patient   = request.args.get("patient")
    if priorite:
        examens = [e for e in examens if e.get("Priorite") == priorite.upper()]
    if patient:
        examens = [e for e in examens if e.get("ID_Patient") == patient]
    return ok(examens)


@app.route(f"{API_PREFIX}/examens/<eid>", methods=["GET"])
@token_requis()
def route_get_examen(eid):
    examen = db.trouver_par_id("examens", eid)
    if not examen:
        return err("Examen introuvable", 404)
    examen["resultats"] = db.filtrer("resultats", ID_Examen=eid)
    return ok(examen)


@app.route(f"{API_PREFIX}/examens", methods=["POST"])
@token_requis(roles=["ADMIN", "MEDECIN_PRESCRIPTEUR", "MEDECIN_VALIDEUR"])
def route_creer_examen():
    body = request.get_json() or {}
    champs_requis = ["ID_Patient", "Categorie", "Priorite"]
    manquants = [c for c in champs_requis if not body.get(c)]
    if manquants:
        return err(f"Champs requis : {', '.join(manquants)}")
    if not db.trouver_par_id("patients", body["ID_Patient"]):
        return err("Patient introuvable", 404)
    body["ID_Prescripteur"]   = body.get("ID_Prescripteur", request.utilisateur.get("sub", ""))
    body["Date_Prescription"] = body.get("Date_Prescription", datetime.now().strftime("%Y-%m-%d"))
    body["Statut_Examen"]     = "EN_ATTENTE"
    nouveau = db.inserer("examens", body)
    return ok(nouveau, "Examen créé", 201)


# ─────────────────────────────────────────────
#  RÉSULTATS
# ─────────────────────────────────────────────

@app.route(f"{API_PREFIX}/resultats", methods=["POST"])
@token_requis(roles=["ADMIN", "TECHNICIEN", "MEDECIN_VALIDEUR"])
def route_creer_resultat():
    body = request.get_json() or {}
    champs_requis = ["ID_Examen", "Parametre", "Valeur"]
    manquants = [c for c in champs_requis if not body.get(c)]
    if manquants:
        return err(f"Champs requis : {', '.join(manquants)}")
    if not db.trouver_par_id("examens", body["ID_Examen"]):
        return err("Examen introuvable", 404)
    # Calcul automatique du statut critique
    try:
        val  = float(str(body.get("Valeur", "")).replace(",", "."))
        rmin = float(str(body.get("Ref_Min", "")).replace(",", ".")) if body.get("Ref_Min") else None
        rmax = float(str(body.get("Ref_Max", "")).replace(",", ".")) if body.get("Ref_Max") else None
        if rmin is not None and rmax is not None:
            if val < rmin:
                body.setdefault("Statut_Valeur", "BAS")
            elif val > rmax * 1.5:
                body.setdefault("Statut_Valeur", "TRES_ELEVE")
                body["Est_Critique"] = "OUI"
            elif val > rmax:
                body.setdefault("Statut_Valeur", "ELEVE")
            else:
                body.setdefault("Statut_Valeur", "NORMAL")
    except (ValueError, TypeError):
        pass
    body.setdefault("Est_Critique", "NON")
    nouveau = db.inserer("resultats", body)
    return ok(nouveau, "Résultat enregistré", 201)


@app.route(f"{API_PREFIX}/resultats/critiques", methods=["GET"])
@token_requis()
def route_resultats_critiques():
    resultats = db.filtrer("resultats", Est_Critique="OUI")
    enrichis  = []
    for r in resultats:
        examen  = db.trouver_par_id("examens", r.get("ID_Examen", "")) or {}
        patient = db.trouver_par_id("patients", examen.get("ID_Patient", "")) or {}
        enrichis.append({**r, "patient_nom": patient.get("Nom",""), "patient_prenom": patient.get("Prenom",""), "patient_id": examen.get("ID_Patient","")})
    return ok(enrichis)


# ─────────────────────────────────────────────
#  DIAGNOSTICS
# ─────────────────────────────────────────────

@app.route(f"{API_PREFIX}/diagnostics", methods=["POST"])
@token_requis(roles=["ADMIN", "MEDECIN_VALIDEUR"])
def route_creer_diagnostic():
    body = request.get_json() or {}
    champs_requis = ["ID_Patient", "Conclusion", "Est_Porteur"]
    manquants = [c for c in champs_requis if not body.get(c) and body.get(c) != "NON"]
    if manquants:
        return err(f"Champs requis : {', '.join(manquants)}")
    if body.get("Est_Porteur") not in ("OUI", "NON"):
        return err("Est_Porteur doit être OUI ou NON")
    body["ID_Valideur"]     = request.utilisateur.get("sub", "")
    body["Date_Diagnostic"] = datetime.now().strftime("%Y-%m-%d")
    # Mettre à jour statut patient si porteur
    if body.get("Est_Porteur") == "OUI":
        risque = body.get("Niveau_Risque", "MODERE")
        statut = "CRITIQUE" if risque == "TRES_ELEVE" else "PORTEUR"
        db.mettre_a_jour("patients", "ID_Patient", body["ID_Patient"], {"Statut_Global": statut})
    nouveau = db.inserer("diagnostics", body)
    return ok(nouveau, "Diagnostic enregistré", 201)


@app.route(f"{API_PREFIX}/diagnostics/porteurs", methods=["GET"])
@token_requis()
def route_porteurs():
    diagnostics = db.filtrer("diagnostics", Est_Porteur="OUI")
    patients    = {p["ID_Patient"]: p for p in db.get("patients")}
    par_patient = {}
    for d in diagnostics:
        pid = d["ID_Patient"]
        par_patient.setdefault(pid, {"patient": patients.get(pid, {}), "diagnostics": []})
        par_patient[pid]["diagnostics"].append(d)
    return ok(list(par_patient.values()))


# ─────────────────────────────────────────────
#  STATISTIQUES
# ─────────────────────────────────────────────

@app.route(f"{API_PREFIX}/stats", methods=["GET"])
@token_requis()
def route_stats():
    return ok(db.stats_globales())


# ─────────────────────────────────────────────
#  SANTÉ DE L'API
# ─────────────────────────────────────────────

@app.route(f"{API_PREFIX}/sante", methods=["GET"])
def route_sante():
    return ok({"version": "2.0", "heure": datetime.now().isoformat(), "statut": "OK"})


@app.route("/", methods=["GET"])
def racine():
    return ok({"message": "API Bethesda v2.0", "docs": f"{API_PREFIX}/sante"})


# ─────────────────────────────────────────────
#  DÉMARRAGE
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("\n  ╔═══════════════════════════════════════╗")
    print("  ║   LABORATOIRE BETHESDA — API v2.0    ║")
    print("  ╚═══════════════════════════════════════╝\n")
    db.initialiser_csv()
    db.charger_tout()
    stats = db.stats_globales()
    print(f"  Base chargée : {stats['nb_patients']} patients | {stats['nb_examens']} examens | {stats['nb_utilisateurs']} utilisateurs")
    print(f"  API démarrée sur http://localhost:{API_PORT}{API_PREFIX}\n")
    app.run(host=API_HOST, port=API_PORT, debug=API_DEBUG)
