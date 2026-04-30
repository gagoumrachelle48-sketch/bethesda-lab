"""
=============================================================
  LABORATOIRE BETHESDA — api_complete.py
  API REST Flask complète — Toutes les 17 fonctionnalités
  Usage : python api_complete.py
=============================================================
"""

import json, functools, os
from datetime import datetime
from flask import Flask, request, jsonify, Response, send_file
from config import API_HOST, API_PORT, API_PREFIX
import database as db
import auth as auth_mod
import security as sec
import notifications as notif
import facturation as fact
import rendez_vous as rdv_mod
import portail_patient as portail
import epidemiologie as epid
from pdf_rapport import generer_rapport_html

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

def get_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "—")

def token_requis(roles=None):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return err("Token manquant", 401)
            token   = header[7:]
            payload = auth_mod.verifier_token(token)
            if not payload:
                return err("Token invalide ou expiré", 401)
            if roles and payload.get("role") not in roles:
                return err("Accès refusé — rôle insuffisant", 403)
            request.utilisateur = payload
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@app.after_request
def after(resp):
    return cors(resp)

@app.route(f"{API_PREFIX}/<path:p>", methods=["OPTIONS"])
@app.route(f"{API_PREFIX}", methods=["OPTIONS"])
def preflight(p=""):
    return cors(Response(status=204))


# ═══════════════════════════════════════════
#  AUTH
# ═══════════════════════════════════════════

@app.route(f"{API_PREFIX}/auth/connexion", methods=["POST"])
def route_connexion():
    body  = request.get_json() or {}
    email = body.get("email","")
    mdp   = body.get("mot_de_passe","")
    code2fa = body.get("code_2fa","")
    if not email or not mdp:
        return err("Email et mot de passe requis")
    result = auth_mod.connexion(email, mdp)
    if not result:
        sec.audit_log("—", "CONNEXION_ECHEC", f"email={email}", get_ip(), "ECHEC")
        return err("Identifiants incorrects", 401)
    if "erreur" in result:
        return err("Compte bloqué après trop de tentatives", 403)
    # Vérifier 2FA si activé
    utilisateur = db.filtrer("utilisateurs", Email=email)
    if utilisateur and utilisateur[0].get("Secret_2FA"):
        if not code2fa:
            return ok({"need_2fa": True}, "Code 2FA requis", 202)
        if not sec.verifier_totp(utilisateur[0]["Secret_2FA"], code2fa):
            sec.audit_log(result["ID_Utilisateur"], "2FA_ECHEC", "", get_ip(), "ECHEC")
            return err("Code 2FA invalide", 401)
    sec.audit_log(result["ID_Utilisateur"], "CONNEXION", f"email={email}", get_ip(), "OK")
    return ok({
        "token":  result["token"],
        "id":     result["ID_Utilisateur"],
        "nom":    result["Nom"],
        "prenom": result["Prenom"],
        "role":   result["Role"],
        "email":  result["Email"],
    }, "Connexion réussie")

@app.route(f"{API_PREFIX}/auth/verifier", methods=["GET"])
@token_requis()
def route_verifier_token():
    return ok(request.utilisateur, "Token valide")

@app.route(f"{API_PREFIX}/auth/2fa/activer", methods=["POST"])
@token_requis()
def route_activer_2fa():
    uid   = request.utilisateur.get("sub","")
    user  = db.trouver_par_id("utilisateurs", uid)
    if not user:
        return err("Utilisateur introuvable", 404)
    secret = sec.generer_secret_totp()
    qr_url = sec.qr_totp_url(secret, user["Email"])
    qr_img = sec.generer_qr_svg(qr_url)
    # Stocker temporairement (à valider avant d'activer)
    db.mettre_a_jour("utilisateurs", "ID_Utilisateur", uid, {"Secret_2FA_Temp": secret})
    return ok({
        "secret":  secret,
        "qr_url":  qr_url,
        "qr_image": qr_img,
        "instructions": "Scannez ce QR code avec Google Authenticator, puis validez avec /auth/2fa/valider"
    })

@app.route(f"{API_PREFIX}/auth/2fa/valider", methods=["POST"])
@token_requis()
def route_valider_2fa():
    uid    = request.utilisateur.get("sub","")
    code   = (request.get_json() or {}).get("code","")
    user   = db.trouver_par_id("utilisateurs", uid)
    secret = user.get("Secret_2FA_Temp","") if user else ""
    if not secret or not sec.verifier_totp(secret, code):
        return err("Code invalide")
    db.mettre_a_jour("utilisateurs", "ID_Utilisateur", uid,
                     {"Secret_2FA": secret, "Secret_2FA_Temp": ""})
    sec.audit_log(uid, "2FA_ACTIVE", "", get_ip(), "OK")
    return ok(None, "2FA activé avec succès")


# ═══════════════════════════════════════════
#  UTILISATEURS
# ═══════════════════════════════════════════

@app.route(f"{API_PREFIX}/utilisateurs", methods=["GET"])
@token_requis(roles=["ADMIN"])
def route_lister_utilisateurs():
    users = db.get("utilisateurs")
    safe  = [{k: v for k, v in u.items() if k not in ("Mot_de_passe_hash","Secret_2FA","Secret_2FA_Temp")} for u in users]
    return ok(safe)

@app.route(f"{API_PREFIX}/utilisateurs", methods=["POST"])
@token_requis(roles=["ADMIN"])
def route_creer_utilisateur():
    body = request.get_json() or {}
    manquants = [c for c in ["Nom","Prenom","Role","Email","mot_de_passe"] if not body.get(c)]
    if manquants:
        return err(f"Champs requis : {', '.join(manquants)}")
    valide, msg = sec.valider_force_mdp(body["mot_de_passe"])
    if not valide:
        return err(f"Mot de passe insuffisant : {msg}")
    try:
        nouveau = auth_mod.creer_utilisateur(body)
        safe    = {k: v for k, v in nouveau.items() if k not in ("Mot_de_passe_hash","Secret_2FA")}
        sec.audit_log(request.utilisateur.get("sub",""), "CREATION_UTILISATEUR",
                      f"email={body['Email']}", get_ip(), "OK")
        return ok(safe, "Utilisateur créé", 201)
    except ValueError as e:
        return err(str(e))

@app.route(f"{API_PREFIX}/utilisateurs/<uid>", methods=["PUT"])
@token_requis(roles=["ADMIN"])
def route_modifier_utilisateur(uid):
    body = request.get_json() or {}
    for k in ("Mot_de_passe_hash","Secret_2FA","Secret_2FA_Temp"):
        body.pop(k, None)
    ok_ = db.mettre_a_jour("utilisateurs", "ID_Utilisateur", uid, body)
    return ok(None, "Modifié") if ok_ else err("Introuvable", 404)

@app.route(f"{API_PREFIX}/utilisateurs/<uid>/desactiver", methods=["PUT"])
@token_requis(roles=["ADMIN"])
def route_desactiver(uid):
    ok_ = db.mettre_a_jour("utilisateurs", "ID_Utilisateur", uid, {"Statut": "INACTIF"})
    sec.audit_log(request.utilisateur.get("sub",""), "DESACTIVATION_UTILISATEUR", f"uid={uid}", get_ip())
    return ok(None, "Désactivé") if ok_ else err("Introuvable", 404)


# ═══════════════════════════════════════════
#  PATIENTS
# ═══════════════════════════════════════════

@app.route(f"{API_PREFIX}/patients", methods=["GET"])
@token_requis()
def route_lister_patients():
    patients = db.get("patients")
    statut   = request.args.get("statut")
    terme    = request.args.get("q")
    if statut:
        patients = [p for p in patients if p.get("Statut_Global") == statut.upper()]
    if terme:
        patients = db.rechercher("patients", terme, ["Nom","Prenom","ID_Patient","Email"])
    return ok(patients)

@app.route(f"{API_PREFIX}/patients/<pid>", methods=["GET"])
@token_requis()
def route_get_patient(pid):
    patient = db.trouver_par_id("patients", pid)
    if not patient:
        return err("Patient introuvable", 404)
    examens     = db.filtrer("examens", ID_Patient=pid)
    diagnostics = db.filtrer("diagnostics", ID_Patient=pid)
    factures    = fact.get_factures_patient(pid)
    rdvs        = rdv_mod.get_rdv(id_patient=pid)
    for ex in examens:
        ex["resultats"] = db.filtrer("resultats", ID_Examen=ex["ID_Examen"])
    sec.audit_log(request.utilisateur.get("sub",""), "ACCES_DOSSIER", f"patient={pid}", get_ip())
    return ok({"patient": patient, "examens": examens, "diagnostics": diagnostics,
               "factures": factures, "rendez_vous": rdvs})

@app.route(f"{API_PREFIX}/patients", methods=["POST"])
@token_requis(roles=["ADMIN","SECRETAIRE","MEDECIN_PRESCRIPTEUR"])
def route_creer_patient():
    body = request.get_json() or {}
    manquants = [c for c in ["Nom","Prenom","Date_Naissance","Sexe"] if not body.get(c)]
    if manquants:
        return err(f"Champs requis : {', '.join(manquants)}")
    body["Nom"]    = body["Nom"].upper().strip()
    body["Prenom"] = body["Prenom"].strip().capitalize()
    body["Statut_Global"] = body.get("Statut_Global","NORMAL")
    body["ID_Utilisateur_Createur"] = request.utilisateur.get("sub","")
    # Générer code d'accès portail
    nouveau = db.inserer("patients", body)
    code    = portail.generer_code_patient(nouveau["ID_Patient"])
    nouveau["Code_Acces_Portail"] = code
    sec.audit_log(request.utilisateur.get("sub",""), "CREATION_PATIENT",
                  f"patient={nouveau['ID_Patient']}", get_ip(), "OK")
    return ok(nouveau, "Patient créé", 201)

@app.route(f"{API_PREFIX}/patients/<pid>", methods=["PUT"])
@token_requis(roles=["ADMIN","SECRETAIRE","MEDECIN_PRESCRIPTEUR","MEDECIN_VALIDEUR"])
def route_modifier_patient(pid):
    body = request.get_json() or {}
    ok_  = db.mettre_a_jour("patients", "ID_Patient", pid, body)
    sec.audit_log(request.utilisateur.get("sub",""), "MODIFICATION_PATIENT", f"patient={pid}", get_ip())
    return ok(None, "Patient mis à jour") if ok_ else err("Introuvable", 404)


# ═══════════════════════════════════════════
#  EXAMENS
# ═══════════════════════════════════════════

@app.route(f"{API_PREFIX}/examens", methods=["GET"])
@token_requis()
def route_lister_examens():
    examens  = db.get("examens")
    priorite = request.args.get("priorite")
    patient  = request.args.get("patient")
    if priorite:
        examens = [e for e in examens if e.get("Priorite") == priorite.upper()]
    if patient:
        examens = [e for e in examens if e.get("ID_Patient") == patient]
    return ok(examens)

@app.route(f"{API_PREFIX}/examens/<eid>", methods=["GET"])
@token_requis()
def route_get_examen(eid):
    ex = db.trouver_par_id("examens", eid)
    if not ex:
        return err("Examen introuvable", 404)
    ex["resultats"] = db.filtrer("resultats", ID_Examen=eid)
    return ok(ex)

@app.route(f"{API_PREFIX}/examens", methods=["POST"])
@token_requis(roles=["ADMIN","MEDECIN_PRESCRIPTEUR","MEDECIN_VALIDEUR"])
def route_creer_examen():
    body = request.get_json() or {}
    manquants = [c for c in ["ID_Patient","Categorie","Priorite"] if not body.get(c)]
    if manquants:
        return err(f"Champs requis : {', '.join(manquants)}")
    if not db.trouver_par_id("patients", body["ID_Patient"]):
        return err("Patient introuvable", 404)
    body["ID_Prescripteur"]   = body.get("ID_Prescripteur", request.utilisateur.get("sub",""))
    body["Date_Prescription"] = datetime.now().strftime("%Y-%m-%d")
    body["Statut_Examen"]     = "EN_ATTENTE"
    nouveau = db.inserer("examens", body)
    # Créer facture automatiquement
    facture = fact.creer_facture(body["ID_Patient"], nouveau["ID_Examen"],
                                  body["Categorie"], "EN_ATTENTE")
    nouveau["facture"] = facture
    sec.audit_log(request.utilisateur.get("sub",""), "CREATION_EXAMEN",
                  f"examen={nouveau['ID_Examen']} patient={body['ID_Patient']}", get_ip())
    return ok(nouveau, "Examen créé", 201)


# ═══════════════════════════════════════════
#  RÉSULTATS
# ═══════════════════════════════════════════

@app.route(f"{API_PREFIX}/resultats", methods=["POST"])
@token_requis(roles=["ADMIN","TECHNICIEN","MEDECIN_VALIDEUR"])
def route_creer_resultat():
    body = request.get_json() or {}
    manquants = [c for c in ["ID_Examen","Parametre","Valeur"] if not body.get(c)]
    if manquants:
        return err(f"Champs requis : {', '.join(manquants)}")
    ex = db.trouver_par_id("examens", body["ID_Examen"])
    if not ex:
        return err("Examen introuvable", 404)
    # Calcul automatique statut + critique
    try:
        val  = float(str(body.get("Valeur","")).replace(",","."))
        rmin = float(str(body.get("Ref_Min","")).replace(",",".")) if body.get("Ref_Min") else None
        rmax = float(str(body.get("Ref_Max","")).replace(",",".")) if body.get("Ref_Max") else None
        if rmin is not None and rmax is not None:
            if val < rmin * 0.5:
                body.setdefault("Statut_Valeur","BAS"); body["Est_Critique"] = "OUI"
            elif val < rmin:
                body.setdefault("Statut_Valeur","BAS")
            elif val > rmax * 1.5:
                body.setdefault("Statut_Valeur","TRES_ELEVE"); body["Est_Critique"] = "OUI"
            elif val > rmax:
                body.setdefault("Statut_Valeur","ELEVE")
            else:
                body.setdefault("Statut_Valeur","NORMAL")
    except (ValueError, TypeError):
        pass
    body.setdefault("Est_Critique","NON")
    nouveau = db.inserer("resultats", body)
    # Notifier si critique
    if nouveau.get("Est_Critique") == "OUI":
        patient = db.trouver_par_id("patients", ex.get("ID_Patient",""))
        if patient:
            notif.notifier_alerte_critique(patient, body.get("Parametre",""), body.get("Valeur",""))
    sec.audit_log(request.utilisateur.get("sub",""), "AJOUT_RESULTAT",
                  f"examen={body['ID_Examen']} critique={nouveau.get('Est_Critique')}", get_ip())
    return ok(nouveau, "Résultat enregistré", 201)

@app.route(f"{API_PREFIX}/resultats/critiques", methods=["GET"])
@token_requis()
def route_critiques():
    resultats = db.filtrer("resultats", Est_Critique="OUI")
    enrichis  = []
    exam_idx  = {e["ID_Examen"]: e for e in db.get("examens")}
    pat_idx   = {p["ID_Patient"]: p for p in db.get("patients")}
    for r in resultats:
        ex  = exam_idx.get(r.get("ID_Examen",""), {})
        p   = pat_idx.get(ex.get("ID_Patient",""), {})
        enrichis.append({**r,
            "patient_nom":    p.get("Nom","?"),
            "patient_prenom": p.get("Prenom","?"),
            "patient_id":     ex.get("ID_Patient","?"),
        })
    return ok(enrichis)


# ═══════════════════════════════════════════
#  DIAGNOSTICS
# ═══════════════════════════════════════════

@app.route(f"{API_PREFIX}/diagnostics", methods=["POST"])
@token_requis(roles=["ADMIN","MEDECIN_VALIDEUR"])
def route_creer_diagnostic():
    body = request.get_json() or {}
    if not body.get("ID_Patient") or not body.get("Conclusion"):
        return err("ID_Patient et Conclusion requis")
    if body.get("Est_Porteur") not in ("OUI","NON"):
        return err("Est_Porteur doit être OUI ou NON")
    body["ID_Valideur"]     = request.utilisateur.get("sub","")
    body["Date_Diagnostic"] = datetime.now().strftime("%Y-%m-%d")
    # Mettre à jour statut patient
    if body.get("Est_Porteur") == "OUI":
        niv    = body.get("Niveau_Risque","MODERE")
        statut = "CRITIQUE" if niv == "TRES_ELEVE" else "PORTEUR"
        db.mettre_a_jour("patients","ID_Patient",body["ID_Patient"],{"Statut_Global":statut})
    nouveau = db.inserer("diagnostics", body)
    sec.audit_log(request.utilisateur.get("sub",""), "CREATION_DIAGNOSTIC",
                  f"patient={body['ID_Patient']} porteur={body.get('Est_Porteur')}", get_ip())
    return ok(nouveau, "Diagnostic enregistré", 201)

@app.route(f"{API_PREFIX}/diagnostics/porteurs", methods=["GET"])
@token_requis()
def route_porteurs():
    diags   = db.filtrer("diagnostics", Est_Porteur="OUI")
    patients = {p["ID_Patient"]: p for p in db.get("patients")}
    par_pat  = {}
    for d in diags:
        pid = d["ID_Patient"]
        par_pat.setdefault(pid, {"patient": patients.get(pid,{}), "diagnostics": []})
        par_pat[pid]["diagnostics"].append(d)
    return ok(list(par_pat.values()))


# ═══════════════════════════════════════════
#  PDF RAPPORTS
# ═══════════════════════════════════════════

@app.route(f"{API_PREFIX}/pdf/<pid>", methods=["GET"])
@token_requis()
def route_pdf_patient(pid):
    eid  = request.args.get("examen")
    html = generer_rapport_html(pid, eid)
    sec.audit_log(request.utilisateur.get("sub",""), "EXPORT_PDF", f"patient={pid}", get_ip())
    return Response(html, mimetype="text/html", headers={
        "Content-Disposition": f"inline; filename=rapport_{pid}.html"
    })


# ═══════════════════════════════════════════
#  FACTURATION
# ═══════════════════════════════════════════

@app.route(f"{API_PREFIX}/factures", methods=["GET"])
@token_requis()
def route_factures():
    pid = request.args.get("patient")
    if pid:
        return ok(fact.get_factures_patient(pid))
    return ok(fact.stats_facturation())

@app.route(f"{API_PREFIX}/factures/<fid>/payer", methods=["POST"])
@token_requis(roles=["ADMIN","SECRETAIRE"])
def route_payer(fid):
    body = request.get_json() or {}
    ok_  = fact.payer_facture(fid, body.get("reference",""), body.get("mode","ESPECES"))
    sec.audit_log(request.utilisateur.get("sub",""), "PAIEMENT", f"facture={fid}", get_ip())
    return ok(None,"Payé") if ok_ else err("Facture introuvable",404)

@app.route(f"{API_PREFIX}/factures/<fid>/recu", methods=["GET"])
@token_requis()
def route_recu(fid):
    html = fact.generer_recu_html(fid)
    return Response(html, mimetype="text/html")


# ═══════════════════════════════════════════
#  RENDEZ-VOUS
# ═══════════════════════════════════════════

@app.route(f"{API_PREFIX}/rdv", methods=["GET"])
@token_requis()
def route_rdv():
    date    = request.args.get("date","")
    patient = request.args.get("patient","")
    return ok(rdv_mod.get_rdv(date=date, id_patient=patient))

@app.route(f"{API_PREFIX}/rdv/creneaux", methods=["GET"])
@token_requis()
def route_creneaux():
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    return ok({"date": date, "creneaux_libres": rdv_mod.creneaux_libres(date)})

@app.route(f"{API_PREFIX}/rdv", methods=["POST"])
@token_requis(roles=["ADMIN","SECRETAIRE","MEDECIN_PRESCRIPTEUR"])
def route_creer_rdv():
    body = request.get_json() or {}
    manquants = [c for c in ["ID_Patient","Date","Heure"] if not body.get(c)]
    if manquants:
        return err(f"Champs requis : {', '.join(manquants)}")
    result = rdv_mod.creer_rdv(
        body["ID_Patient"], body["Date"], body["Heure"],
        body.get("Type_Examen",""), body.get("Prescripteur",""),
        body.get("Notes",""), int(body.get("Duree",30))
    )
    if "erreur" in result:
        return err(result["erreur"])
    # Notif SMS
    patient = db.trouver_par_id("patients", body["ID_Patient"])
    if patient:
        notif.notifier_rappel_rdv(patient, body["Date"], body["Heure"])
    sec.audit_log(request.utilisateur.get("sub",""), "CREATION_RDV",
                  f"patient={body['ID_Patient']} date={body['Date']}", get_ip())
    return ok(result, "Rendez-vous créé", 201)

@app.route(f"{API_PREFIX}/rdv/<rid>/annuler", methods=["PUT"])
@token_requis(roles=["ADMIN","SECRETAIRE"])
def route_annuler_rdv(rid):
    ok_ = rdv_mod.annuler_rdv(rid)
    return ok(None,"Annulé") if ok_ else err("RDV introuvable",404)


# ═══════════════════════════════════════════
#  PORTAIL PATIENT (accès sans token)
# ═══════════════════════════════════════════

@app.route(f"{API_PREFIX}/portail/<pid>", methods=["GET"])
def route_portail(pid):
    code = request.args.get("code","")
    if not code:
        return err("Code d'accès requis", 401)
    if not portail.verifier_code_patient(pid, code):
        return err("Code invalide ou expiré", 401)
    html = portail.generer_portail_html(pid)
    return Response(html, mimetype="text/html")

@app.route(f"{API_PREFIX}/portail/<pid>/export", methods=["GET"])
def route_export_rgpd(pid):
    code = request.args.get("code","")
    if not portail.verifier_code_patient(pid, code):
        return err("Code invalide", 401)
    data = portail.exporter_json_rgpd(pid)
    return Response(data, mimetype="application/json",
                    headers={"Content-Disposition": f"attachment; filename=mes_donnees_{pid}.json"})

@app.route(f"{API_PREFIX}/portail/<pid>/effacement", methods=["POST"])
def route_effacement_rgpd(pid):
    code   = request.args.get("code","")
    raison = (request.get_json() or {}).get("raison","")
    if not portail.verifier_code_patient(pid, code):
        return err("Code invalide", 401)
    result = portail.demander_effacement(pid, raison)
    return ok(result, "Demande enregistrée")


# ═══════════════════════════════════════════
#  NOTIFICATIONS
# ═══════════════════════════════════════════

@app.route(f"{API_PREFIX}/notif/resultats/<pid>", methods=["POST"])
@token_requis(roles=["ADMIN","TECHNICIEN","MEDECIN_VALIDEUR"])
def route_notif_resultats(pid):
    patient = db.trouver_par_id("patients", pid)
    if not patient:
        return err("Patient introuvable", 404)
    result = notif.notifier_resultats_prets(patient)
    return ok(result, "Notification envoyée")

@app.route(f"{API_PREFIX}/notif/logs", methods=["GET"])
@token_requis(roles=["ADMIN"])
def route_notif_logs():
    return ok(notif.lire_log_notifications())


# ═══════════════════════════════════════════
#  AUDIT & SÉCURITÉ
# ═══════════════════════════════════════════

@app.route(f"{API_PREFIX}/audit", methods=["GET"])
@token_requis(roles=["ADMIN"])
def route_audit():
    limite      = int(request.args.get("limite", 200))
    utilisateur = request.args.get("user","")
    action      = request.args.get("action","")
    return ok(sec.lire_audit(limite, utilisateur, action))

@app.route(f"{API_PREFIX}/audit/integrite", methods=["GET"])
@token_requis(roles=["ADMIN"])
def route_audit_integrite():
    return ok(sec.verifier_integrite_audit())


# ═══════════════════════════════════════════
#  ÉPIDÉMIOLOGIE
# ═══════════════════════════════════════════

@app.route(f"{API_PREFIX}/epidemio/rapport", methods=["GET"])
@token_requis(roles=["ADMIN","MEDECIN_VALIDEUR"])
def route_epidemio():
    return ok(epid.rapport_epidemiologique())

@app.route(f"{API_PREFIX}/epidemio/pathologies", methods=["GET"])
@token_requis()
def route_pathologies():
    return ok(epid.stats_pathologies())


# ═══════════════════════════════════════════
#  STATISTIQUES GLOBALES
# ═══════════════════════════════════════════

@app.route(f"{API_PREFIX}/stats", methods=["GET"])
@token_requis()
def route_stats():
    stats = db.stats_globales()
    stats["facturation"] = fact.stats_facturation()
    return ok(stats)


# ═══════════════════════════════════════════
#  SANTÉ API
# ═══════════════════════════════════════════


# ═══════════════════════════════════════════
#  SETUP INITIAL — Créer premier admin
# ═══════════════════════════════════════════

@app.route(f"{API_PREFIX}/setup", methods=["GET"])
def route_setup_status():
    utilisateurs = db.get("utilisateurs")
    return ok({
        "nb_utilisateurs": len(utilisateurs),
        "setup_requis": len(utilisateurs) == 0
    })

@app.route(f"{API_PREFIX}/setup/admin", methods=["POST"])
def route_setup_admin():
    """Crée le premier admin — seulement si aucun utilisateur nexiste."""
    utilisateurs = db.get("utilisateurs")
    if utilisateurs:
        return err("Setup déjà effectué — des utilisateurs existent", 403)
    body = request.get_json() or {}
    if not body.get("mot_de_passe"):
        return err("mot_de_passe requis")
    body.setdefault("Nom", "ADMIN")
    body.setdefault("Prenom", "Admin")
    body.setdefault("Role", "ADMIN")
    body.setdefault("Email", "admin@bethesda-lab.fr")
    try:
        nouveau = auth_mod.creer_utilisateur(body)
        safe = {k: v for k, v in nouveau.items() if k != "Mot_de_passe_hash"}
        return ok(safe, "Premier admin créé avec succès", 201)
    except Exception as e:
        return err(str(e))

@app.route(f"{API_PREFIX}/sante", methods=["GET"])
def route_sante():
    return ok({
        "version":    "2.0",
        "heure":      datetime.now().isoformat(),
        "statut":     "OK",
        "modules":    ["auth","patients","examens","resultats","diagnostics",
                       "pdf","facturation","rdv","portail","notif","audit","epidemio"],
    })

@app.route("/api", methods=["GET"])
def racine():
    return ok({"message": "API Bethesda v2.0 — Complète", "docs": f"{API_PREFIX}/sante"})

@app.route("/", methods=["GET"])
@app.route("/dashboard", methods=["GET"])
def route_dashboard():
    import os
    if os.path.exists("bethesda_dashboard.html"):
        html = open("bethesda_dashboard.html", encoding="utf-8").read()
    else:
        html = "<h1>Dashboard introuvable</h1>"
    return Response(html, mimetype="text/html")


# ─────────────────────────────────────────────
#  DÉMARRAGE
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("\n  ╔══════════════════════════════════════════════╗")
    print("  ║   LABORATOIRE BETHESDA — API v2.0 Complète  ║")
    print("  ║   17 fonctionnalités — Cameroun & Europe     ║")
    print("  ╚══════════════════════════════════════════════╝\n")
    db.initialiser_csv()
    db.charger_tout()
    stats = db.stats_globales()
    print(f"  Base : {stats['nb_patients']} patients | {stats['nb_examens']} examens | {stats['nb_utilisateurs']} utilisateurs")
    print(f"  API  : http://localhost:{API_PORT}{API_PREFIX}\n")
    app.run(host=API_HOST, port=API_PORT, debug=True)
