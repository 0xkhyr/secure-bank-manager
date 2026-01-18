"""
# Journalisation d'Audit Sécurisée
# Audit : Ce module implémente un journal de transactions immuable et vérifiable.
# Sécurité : Utilise un chaînage de hash (Hash Chaining) et des signatures HMAC pour garantir
# l'intégrité, la non-répudiation et la détection de toute manipulation malveillante.
"""

import hashlib
import hmac
import json
from datetime import datetime, date as py_date
from sqlalchemy import desc, func, cast, Date as SQLDate
from sqlalchemy.orm import joinedload
from src.db import obtenir_session
from src.models import (
    Journal, ClotureJournal
)
from src.config import Config

def calculer_hash(data):
    """
    # Audit : Génère l'empreinte numérique (SHA-256) d'un jeu de données.
    # Cette empreinte est utilisée pour le chaînage avec l'entrée suivante.
    """
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def calculer_hmac(data):
    """
    # Sécurité : Signe cryptographiquement les données avec une clé secrète applicative.
    # Empêche la génération de logs valides par un attaquant n'ayant pas accès à la clé secrète.
    """
    secret = Config.HMAC_SECRET_KEY.encode('utf-8')
    return hmac.new(secret, data.encode('utf-8'), hashlib.sha256).hexdigest()

def log_action(utilisateur_id, action, cible=None, details=None):
    """
    # Audit : Enregistre de manière sécurisée une action utilisateur.
    # Politique : Toute action critique (flux financier, accès privilégié) doit être logguée.
    """
    session = obtenir_session()
    try:
        # Sécurité : Utilise un format JSON canonique (clés triées) pour garantir un hash reproductible.
        details_json = json.dumps(details, ensure_ascii=False, sort_keys=True) if details else None
        horodatage = datetime.utcnow().replace(microsecond=0)
        
        # Sécurité : Verrouillage sérialisé du dernier log pour éviter les collisions lors d'accès concurrents.
        dernier_log = (
            session.query(Journal)
            .order_by(desc(Journal.id))
            .with_for_update()
            .first()
        )
        hash_precedent = dernier_log.hash_actuel if dernier_log else Config.GENESIS_HASH
        
        # Audit : Construction du payload d'intégrité incluant le lien vers le passé (hash_precedent).
        audit_payload = {
            "timestamp": horodatage.isoformat() + "Z",
            "utilisateur_id": utilisateur_id,
            "action": action,
            "cible": cible,
            "details": json.loads(details_json) if details_json else None,
            "hash_precedent": hash_precedent
        }

        canonical_json = json.dumps(
            audit_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":")
        )

        # Sécurité : Double protection par empreinte (intégrité structurelle) et signature (authenticité).
        hash_actuel = calculer_hash(canonical_json)
        signature = calculer_hmac(canonical_json)
        
        nouveau_log = Journal(
            horodatage=horodatage,
            utilisateur_id=utilisateur_id,
            action=action,
            cible=cible,
            details=details_json,
            hash_precedent=hash_precedent,
            hash_actuel=hash_actuel,
            signature_hmac=signature
        )
        
        session.add(nouveau_log)
        session.commit()
        return True
        
    except Exception as e:
        # Limitation : En cas d'échec de l'audit, la transaction parente doit être annulée (Rollback).
        session.rollback()
        return False

def verifier_integrite():
    """
    # Audit : Parcourt et valide mathématiquement la totalité de la chaîne de logs.
    # Vérifie la continuité (hash_precedent), l'intégrité (hash_actuel) et l'authenticité (HMAC).
    """
    session = obtenir_session()
    logs = session.query(Journal).order_by(Journal.id).all()
    session.close()
    
    erreurs = []
    hash_attendu_precedent = Config.GENESIS_HASH
    
    for log in logs:
        # Audit : Recréation du payload canonique pour confrontation avec les valeurs stockées.
        audit_payload = {
            "timestamp": log.horodatage.isoformat() + "Z",
            "utilisateur_id": log.utilisateur_id,
            "action": log.action,
            "cible": log.cible,
            "details": json.loads(log.details) if log.details else None,
            "hash_precedent": log.hash_precedent
        }

        canonical_json = json.dumps(
            audit_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":")
        )
        
        # Sécurité : Détection de rupture de continuité dans la chaîne de preuve.
        if log.hash_precedent != hash_attendu_precedent:
            erreurs.append({"id": log.id, "message": f"Log #{log.id} : Rupture de chaîne (Hash précédent invalide)"})
        
        # Sécurité : Détection de modification directe de la ligne en base de données ou corruption.
        hash_calcule = calculer_hash(canonical_json)
        if log.hash_actuel != hash_calcule:
            erreurs.append({"id": log.id, "message": f"Log #{log.id} : Données corrompues (Hash invalide)"})
            
        # Sécurité : Détection d'injection malveillante sans possession de la clé secrète.
        hmac_calcule = calculer_hmac(canonical_json)
        if log.signature_hmac != hmac_calcule:
            erreurs.append({"id": log.id, "message": f"Log #{log.id} : Signature falsifiée (HMAC invalide)"})
            
        hash_attendu_precedent = log.hash_actuel
        
    est_valide = len(erreurs) == 0
    return est_valide, erreurs


def verifier_integrite_detailed(limit=None):
    """
    # Audit : Génère un rapport détaillé de l'état de la chaîne pour l'interface d'administration.
    """
    session = obtenir_session()
    query = session.query(Journal).order_by(Journal.id)
    logs = query.all() if limit is None else query.limit(limit).all()

    entries = []
    errors = []
    hash_attendu_precedent = Config.GENESIS_HASH

    for log in logs:
        raw_details = json.loads(log.details) if log.details else None
        audit_payload = {
            "timestamp": log.horodatage.isoformat() + "Z",
            "utilisateur_id": log.utilisateur_id,
            "action": log.action,
            "cible": log.cible,
            "details": json.loads(log.details) if log.details else None,
            "hash_precedent": log.hash_precedent
        }
        canonical_json = json.dumps(audit_payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

        entry_errors = []
        status = 'ok'

        # Sécurité : Vérification séquentielle de l'intégrité de chaque maillon.
        if log.hash_precedent != hash_attendu_precedent:
            entry_errors.append('rupture_precedent')
            status = 'broken_precedent'
            errors.append((log.id, 'rupture_precedent'))

        hash_calcule = calculer_hash(canonical_json)
        if log.hash_actuel != hash_calcule:
            entry_errors.append('hash_invalide')
            status = 'bad_hash'
            errors.append((log.id, 'hash_invalide'))

        hmac_calcule = calculer_hmac(canonical_json)
        if log.signature_hmac != hmac_calcule:
            entry_errors.append('hmac_invalide')
            status = 'bad_hmac'
            errors.append((log.id, 'hmac_invalide'))

        entries.append({
            'id': log.id,
            'horodatage': log.horodatage.isoformat(),
            'utilisateur_id': log.utilisateur_id,
            'action': log.action,
            'cible': log.cible,
            'details': raw_details,
            'hash_precedent': log.hash_precedent,
            'hash_actuel': log.hash_actuel,
            'signature_hmac': log.signature_hmac,
            'status': status,
            'errors': entry_errors
        })

        hash_attendu_precedent = log.hash_actuel

    est_valide = len(errors) == 0
    session.close()
    return {'valid': est_valide, 'entries': entries, 'errors': errors}

def cloturer_journee(date_cloture=None):
    """
    # Audit : Fige l'état du journal pour une journée donnée via une clôture cryptographique.
    # Cette étape crée un point d'ancrage immuable référençant le dernier log valide.
    """
    if date_cloture is None:
        from datetime import timedelta
        date_cloture = py_date.today() - timedelta(days=1)
        
    session = obtenir_session()
    try:
        # Sécurité : Une journée déjà clôturée ne peut pas être recalculée pour masquer des altérations.
        cloture_existante = session.query(ClotureJournal).filter_by(date=date_cloture).first()
        if cloture_existante:
            return False, f"La journée du {date_cloture} est déjà clôturée."

        debut_jour = datetime.combine(date_cloture, datetime.min.time())
        fin_jour = datetime.combine(date_cloture, datetime.max.time())
        
        dernier_log = session.query(Journal)\
            .filter(Journal.horodatage >= debut_jour)\
            .filter(Journal.horodatage <= fin_jour)\
            .order_by(desc(Journal.id))\
            .first()
            
        if not dernier_log:
            return False, f"Aucun log trouvé pour la journée du {date_cloture}."

        # Audit : Le "Hash Racine" devient l'identifiant cryptographique unique de la journée.
        hash_racine = dernier_log.hash_actuel
        
        # Sécurité : Signature du point d'ancrage pour garantir son authenticité temporelle.
        payload_cloture = f"CLOTURE|{date_cloture.isoformat()}|{dernier_log.id}|{hash_racine}"
        signature = calculer_hmac(payload_cloture)
        
        nouvelle_cloture = ClotureJournal(
            date=date_cloture,
            dernier_log_id=dernier_log.id,
            hash_racine=hash_racine,
            signature_hmac=signature
        )
        
        session.add(nouvelle_cloture)
        session.commit()
        return True, f"Clôture du {date_cloture} réussie."
        
    except Exception as e:
        session.rollback()
        return False, f"Erreur de clôture : {e}"


# --- Routes dynamiques pour visualisation de la chaîne ---
from flask import Blueprint, render_template, jsonify, abort, request, flash, redirect, url_for, g
from src.auth import permission_required

audit_bp = Blueprint('audit', __name__, url_prefix='/audit')

# French-only chain verification routes (keep only /verifier/*)
@audit_bp.route('/verifier/chain')
@permission_required('audit.view')
def verifier_chain():
    # pass limit of recent logs; None returns all — for performance we limit to 500
    data = verifier_integrite_detailed(limit=500)

    # Build a concise summary for the minimal chain view server-side to avoid complex template logic
    entries = data.get('entries', [])
    n = len(entries)
    summary = {}
    if n == 0:
        summary = {'n': 0}
    else:
        summary['n'] = n
        # Genesis is a virtual node taken from config (not the first log entry)
        from src.config import Config
        summary['genesis'] = {'id': None, 'hash_actuel': Config.GENESIS_HASH, 'is_virtual': True}
        summary['daily'] = entries[-1]
        # compute broken indices
        broken_idxs = [i for i, e in enumerate(entries) if e['status'] != 'ok']
        summary['broken_first'] = broken_idxs[0] if broken_idxs else None
        summary['broken_count'] = len(broken_idxs)
        summary['broken_ids'] = [entries[i]['id'] for i in broken_idxs]

        # Build ordered segments per your approach
        segments = []
        segments.append({'type': 'genesis', 'entry': summary['genesis'], 'idx': None})

        if len(broken_idxs) == 0:
            # no broken nodes: show first node if exists, gap, then daily
            if n > 0:
                segments.append({'type': 'first', 'entry': entries[0], 'idx': 0})
                gap = (n - 1) - 0 - 1
                if gap > 0:
                    segments.append({'type': 'gap', 'count': gap})
                # if the first is also the last, skip duplicate daily
                if n > 1:
                    segments.append({'type': 'daily', 'entry': entries[-1], 'idx': n - 1})
        else:
            # handle the case where first log is good -> show it
            if entries[0]['status'] == 'ok':
                segments.append({'type': 'first', 'entry': entries[0], 'idx': 0})
                # gap between first node and first broken
                first_b = broken_idxs[0]
                gap = first_b - 0 - 1
                if gap > 0:
                    segments.append({'type': 'gap', 'count': gap})
            # add broken nodes and intermediate gaps
            for i, b_idx in enumerate(broken_idxs):
                segments.append({'type': 'broken', 'entry': entries[b_idx], 'idx': b_idx})
                next_b = broken_idxs[i + 1] if i + 1 < len(broken_idxs) else None
                if next_b is not None:
                    between = next_b - b_idx - 1
                    if between > 0:
                        segments.append({'type': 'gap', 'count': between})
                else:
                    # gap between last broken and daily
                    tail = (n - 1) - b_idx - 1
                    if tail > 0:
                        segments.append({'type': 'gap', 'count': tail})
                    segments.append({'type': 'daily', 'entry': entries[-1], 'idx': n - 1})
        summary['segments'] = segments
        # provide a small preview of broken entries (up to 5) to render individually
        preview_limit = 5
        summary['broken_preview'] = [entries[i] for i in broken_idxs[:preview_limit]]
        summary['broken_remaining'] = max(0, len(broken_idxs) - preview_limit)
        summary['entries'] = entries

    return render_template('audit/verify_chain_minimal.html', data=data, summary=summary)

@audit_bp.route('/verifier/chain/<int:id>')
@permission_required('audit.view')
def verifier_chain_detail(id):
    data = verifier_integrite_detailed()
    # find entry
    entry = next((e for e in data['entries'] if e['id'] == id), None)
    if not entry:
        abort(404)
    return jsonify(entry)

def verifier_clotures():
    """
    # Audit : Vérifie la validité des signatures de toutes les clôtures journalières.
    # Garantit que les points d'ancrage temporels n'ont pas été altérés.
    """
    session = obtenir_session()
    clotures = session.query(ClotureJournal).order_by(ClotureJournal.date).all()
    session.close()
    
    erreurs = []
    ids_invalides = set()
    for c in clotures:
        # Sécurité : Recalcul de la signature HMAC pour confrontation.
        payload = f"CLOTURE|{c.date.isoformat()}|{c.dernier_log_id}|{c.hash_racine}"
        signature_calculee = calculer_hmac(payload)
        
        if c.signature_hmac != signature_calculee:
            erreurs.append(f"Clôture du {c.date} : Signature HMAC invalide (Falsification détectée)")
            ids_invalides.add(c.id)
            
    return len(erreurs) == 0, erreurs

@audit_bp.route('/')
@permission_required('audit.view')
def index():
    """
    # Audit : Interface de consultation du journal.
    # Traçabilité : Chaque accès au journal est lui-même consigné dans l'audit.
    """
    from src.models import Utilisateur
    
    page = int(request.args.get('page', 1))
    per_page = 50
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    user_id = request.args.get('user_id')
    action_filter = request.args.get('action')
    
    session = obtenir_session()
    
    # Audit : Construction dynamique des filtres pour l'analyse forensique.
    query = session.query(Journal).options(joinedload(Journal.utilisateur))
    
    if start_date:
        query = query.filter(Journal.horodatage >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(Journal.horodatage <= datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59))
    if user_id and user_id != 'all':
        query = query.filter(Journal.utilisateur_id == int(user_id))
    if action_filter and action_filter != 'all':
        query = query.filter(Journal.action == action_filter)
    
    total_entries = query.count()
    utilisateurs = session.query(Utilisateur).filter_by(is_active=True).order_by(Utilisateur.nom_utilisateur).all()
    actions_distinctes = [r[0] for r in session.query(Journal.action).distinct().order_by(Journal.action).all()]
    
    entries = query.order_by(desc(Journal.id))\
        .offset((page - 1) * per_page)\
        .limit(per_page)\
        .all()
    
    # Audit : Consignation de l'accès au journal avec les filtres appliqués.
    log_action(g.user.id, "CONSULTATION_AUDIT", "Journal",
               {"page": page, "total_entrees_filtrees": total_entries, 
                "filtres": {"start": start_date, "end": end_date, "user": user_id, "action": action_filter}})
    
    total_pages = (total_entries + per_page - 1) // per_page
    
    from datetime import timedelta
    from src.config import Config
    entries_local = []
    for entry in entries:
        user_obj = None
        if entry.utilisateur:
            user_obj = type('obj', (object,), {
                'nom_utilisateur': entry.utilisateur.nom_utilisateur
            })()
        
        entry_dict = {
            'id': entry.id,
            'horodatage': entry.horodatage + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS),
            'utilisateur_id': entry.utilisateur_id,
            'utilisateur': user_obj,
            'action': entry.action,
            'cible': entry.cible
        }
        entries_local.append(type('obj', (object,), entry_dict)())

    filters = {
        'start_date': start_date,
        'end_date': end_date,
        'user_id': user_id,
        'action': action_filter
    }
    
    return render_template('audit/index.html', 
                         entries=entries_local, 
                         page=page, 
                         total_pages=total_pages,
                         total_entries=total_entries,
                         utilisateurs=utilisateurs,
                         actions=actions_distinctes,
                         filters=filters)

@audit_bp.route('/verifier', methods=('GET', 'POST'))
@permission_required('audit.verify')
def verify():
    """
    # Audit : Interface de déclenchement manuel de la vérification d'intégrité.
    """
    if request.method == 'GET':
        return render_template('audit/verify.html', result=None)

    valide, erreurs = verifier_integrite()
    session = obtenir_session()
    total = session.query(Journal).count()
    session.close()

    result = {
        'valid': valide,
        'total': total,
        'invalid': len(erreurs),
        'invalid_entries': [e['id'] for e in erreurs if 'id' in e] if not valide else []
    }
    
    # Audit : Enregistrement du résultat de la vérification (Succès/Échec).
    if valide:
        log_action(g.user.id, "VERIFICATION_INTEGRITE_AUDIT", "Journal",
                   {"resultat": "valide", "nb_entrees_verifiees": total})
        flash('L\'intégrité du journal d\'audit est validée.', 'success')
    else:
        log_action(g.user.id, "VERIFICATION_INTEGRITE_AUDIT", "Journal",
                   {"resultat": "compromis", "nb_erreurs": len(erreurs)})
        flash(f'L\'intégrité du journal est compromise ! {len(erreurs)} erreur(s) détectée(s).', 'danger')
    
    return render_template('audit/verify.html', result=result)

@audit_bp.route('/<int:id>')
@permission_required('audit.view')
def view(id):
    """
    # Audit : Consultation détaillée d'un enregistrement spécifique.
    """
    session = obtenir_session()
    entry = session.query(Journal)\
        .options(joinedload(Journal.utilisateur))\
        .filter_by(id=id)\
        .first()
    session.close()
    
    if entry is None:
        flash('Entrée d\'audit introuvable.', 'danger')
        return redirect(url_for('audit.index'))
    
    # Audit : Traçabilité de la consultation d'un log spécifique.
    log_action(g.user.id, "CONSULTATION_AUDIT", f"Entrée {id}",
               {"entry_id": id, "action_consultee": entry.action})
    
    details = None
    if entry.details:
        try:
            details = json.loads(entry.details)
        except:
            details = entry.details
    
    from datetime import timedelta
    from src.config import Config
    
    user_obj = None
    if entry.utilisateur:
        user_obj = type('obj', (object,), {
            'nom_utilisateur': entry.utilisateur.nom_utilisateur
        })()
    
    entry_local = type('obj', (object,), {
        'id': entry.id,
        'horodatage': entry.horodatage + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS),
        'utilisateur_id': entry.utilisateur_id,
        'utilisateur': user_obj,
        'action': entry.action,
        'cible': entry.cible,
        'details': entry.details,
        'hash_precedent': entry.hash_precedent,
        'hash_actuel': entry.hash_actuel,
        'signature_hmac': entry.signature_hmac
    })()
    
    return render_template('audit/view.html', entry=entry_local, details=details)

@audit_bp.route('/clotures')
@permission_required('audit.view')
def clotures():
    """
    # Audit : Visualisation des points de clôture cryptographiques journaliers.
    """
    session = obtenir_session()
    clotures = session.query(ClotureJournal).order_by(desc(ClotureJournal.date)).all()
    session.close()
    
    res = verifier_clotures()
    if isinstance(res, tuple) and len(res) == 3:
        tout_valide, erreurs, ids_invalides = res
    else:
        tout_valide, erreurs = res
        ids_invalides = set()
    
    return render_template('audit/clotures.html', 
                         clotures=clotures, 
                         tout_valide=tout_valide, 
                         erreurs_cloture=erreurs,
                         ids_invalides=ids_invalides)

@audit_bp.route('/cloturer-hier', methods=('POST',))
@permission_required('audit.verify')
def cloturer_hier():
    """
    # Audit : Déclenchement manuel de la clôture pour la veille.
    """
    succes, message = cloturer_journee()
    if succes:
        flash(message, 'success')
    else:
        flash(message, 'warning')
    return redirect(url_for('audit.clotures'))

if __name__ == '__main__':
    # Test rapide si exécuté directement
    print("=== Test du système d'audit ===")
    
    # 1. Créer un log
    print("\n1. Création d'un log de test...")
    log_action(1, "TEST_ACTION", "Système", {"test": "ok"})
    
    # 2. Vérifier l'intégrité
    print("\n2. Vérification de l'intégrité...")
    valide, erreurs = verifier_integrite()
    
    if valide:
        print("Intégrité du journal : VALIDE")
    else:
        print("Intégrité du journal : INVALIDE")
        for err in erreurs:
            message = err.get('message', str(err))
            print(f"  - {message}")
