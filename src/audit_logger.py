"""
audit_logger.py - Système de journalisation d'audit sécurisé

Ce module gère l'enregistrement immuable des actions critiques.
Il utilise deux mécanismes de sécurité :
1. Chain Hash : Chaque entrée contient le hash de l'entrée précédente.
2. HMAC : Chaque entrée est signée cryptographiquement.

Cela garantit que :
- L'historique ne peut pas être modifié sans briser la chaîne de hash.
- On ne peut pas insérer de faux logs sans la clé secrète HMAC.
"""

import hashlib
import hmac
import json
from datetime import datetime
from sqlalchemy import desc, func, cast, Date as SQLDate
from src.db import obtenir_session
from src.models import Journal, ClotureJournal
from src.config import Config
from datetime import datetime, date as py_date

def calculer_hash(data):
    """
    Calcule le hash SHA-256 d'une chaîne de caractères.
    """
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def calculer_hmac(data):
    """
    Calcule la signature HMAC-SHA256 avec la clé secrète de l'application.
    """
    secret = Config.HMAC_SECRET_KEY.encode('utf-8')
    return hmac.new(secret, data.encode('utf-8'), hashlib.sha256).hexdigest()

def log_action(utilisateur_id, action, cible=None, details=None):
    """
    Enregistre une action dans le journal d'audit sécurisé.
    
    Args:
        utilisateur_id (int): ID de l'utilisateur effectuant l'action
        action (str): Type d'action (ex: 'CONNEXION', 'DEPOT')
        cible (str, optional): Cible de l'action (ex: 'Compte 123')
        details (dict, optional): Détails supplémentaires en JSON
    
    Returns:
        bool: True si l'enregistrement a réussi, False sinon
    """
    session = obtenir_session()
    try:
        # 1. Préparer les données
        details_json = json.dumps(details, ensure_ascii=False, sort_keys=True) if details else None
        horodatage = datetime.utcnow().replace(microsecond=0)
        
        # 2. Récupérer le hash du dernier log pour la chaîne (Verrouillage de ligne pour la concurrence)
        dernier_log = (
            session.query(Journal)
            .order_by(desc(Journal.id))
            .with_for_update()
            .first()
        )
        hash_precedent = dernier_log.hash_actuel if dernier_log else Config.GENESIS_HASH
        
        # 3. Construire la chaîne de données à hasher/signer
        # Format: json canonical        
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

        # 4. Calculer les sécurités
        hash_actuel = calculer_hash(canonical_json)
        signature = calculer_hmac(canonical_json)
        
        # 5. Créer l'entrée
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
        print(f"Audit: {action} enregistré avec succès.")
        return True
        
    except Exception as e:
        print(f"Erreur d'audit : {e}")
        session.rollback()
        return False

def verifier_integrite():
    """
    Vérifie l'intégrité complète de la chaîne de logs.
    
    Parcourt tous les logs et vérifie :
    1. Que le hash_precedent correspond bien au hash_actuel du log d'avant.
    2. Que le hash_actuel est valide par rapport aux données.
    3. Que la signature HMAC est valide.
    
    Returns:
        tuple: (bool, list) - (Valide?, Liste des erreurs trouvées)
    """
    session = obtenir_session()
    logs = session.query(Journal).order_by(Journal.id).all()
    session.close()
    
    erreurs = []
    hash_attendu_precedent = Config.GENESIS_HASH
    
    for log in logs:
        # Reconstruire les données au format JSON Canonique
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
        
        # Vérification 1 : Chaînage
        if log.hash_precedent != hash_attendu_precedent:
            erreurs.append(f"Log #{log.id} : Rupture de chaîne (Hash précédent invalide)")
            status = 'broken_precedent'
        else:
            status = 'ok'
        
        # Vérification 2 : Hash actuel
        hash_calcule = calculer_hash(canonical_json)
        if log.hash_actuel != hash_calcule:
            erreurs.append(f"Log #{log.id} : Données corrompues (Hash invalide)")
            status = 'bad_hash'
            
        # Vérification 3 : Signature HMAC
        hmac_calcule = calculer_hmac(canonical_json)
        if log.signature_hmac != hmac_calcule:
            erreurs.append(f"Log #{log.id} : Signature falsifiée (HMAC invalide)")
            status = 'bad_hmac'
            
        # Mise à jour pour le prochain tour
        hash_attendu_precedent = log.hash_actuel
        
    est_valide = len(erreurs) == 0
    return est_valide, erreurs


def verifier_integrite_detailed(limit=None):
    """
    Fournit un rapport détaillé par log pour la visualisation en chaîne.
    - limit (int) : si fourni, limite le nombre de logs retournés (les plus récents si négatif)

    Retourne un dict: { 'valid': bool, 'entries': [ {id, horodatage, utilisateur_id, action, hash_precedent, hash_actuel, signature_hmac, status, errors: [] } ], 'errors': [] }
    """
    session = obtenir_session()
    query = session.query(Journal).order_by(Journal.id)
    logs = query.all() if limit is None else query.limit(limit).all()

    entries = []
    errors = []
    hash_attendu_precedent = Config.GENESIS_HASH

    for log in logs:
        # keep raw details for detail view
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
    Crée une clôture cryptographique pour une journée spécifique.
    
    Args:
        date_cloture (date, optional): La date à clôturer. Par défaut, hier.
    Returns:
        tuple: (bool, str) - (Succès?, Message)
    """
    if date_cloture is None:
        from datetime import timedelta
        date_cloture = py_date.today() - timedelta(days=1)
        
    session = obtenir_session()
    try:
        # 1. Vérifier si une clôture existe déjà pour cette date
        cloture_existante = session.query(ClotureJournal).filter_by(date=date_cloture).first()
        if cloture_existante:
            return False, f"La journée du {date_cloture} est déjà clôturée."

        # 2. Trouver le dernier log de cette journée (filtrage par plage de temps)
        debut_jour = datetime.combine(date_cloture, datetime.min.time())
        fin_jour = datetime.combine(date_cloture, datetime.max.time())
        
        dernier_log = session.query(Journal)\
            .filter(Journal.horodatage >= debut_jour)\
            .filter(Journal.horodatage <= fin_jour)\
            .order_by(desc(Journal.id))\
            .first()
            
        if not dernier_log:
            return False, f"Aucun log trouvé pour la journée du {date_cloture}."

        # 3. Le "Hash Racine" est le hash_actuel du dernier log de la journée
        hash_racine = dernier_log.hash_actuel
        
        # 4. Signer cryptographiquement ce hash racine
        payload_cloture = f"CLOTURE|{date_cloture.isoformat()}|{dernier_log.id}|{hash_racine}"
        signature = calculer_hmac(payload_cloture)
        
        # 5. Créer l'entrée de clôture
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
from flask import Blueprint, render_template, jsonify, abort
from src.auth import permission_required

# Reuse the existing blueprint if defined in this module
try:
    audit_bp
except NameError:
    from flask import Blueprint
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
    Vérifie l'intégrité de toutes les clôtures journalières.
    Returns:
        tuple: (bool, list, set) - (Tout valide?, Liste erreurs, Set des IDs invalides)
    """
    session = obtenir_session()
    clotures = session.query(ClotureJournal).order_by(ClotureJournal.date).all()
    session.close()
    
    erreurs = []
    ids_invalides = set()
    for c in clotures:
        # Re-calculer la signature
        payload = f"CLOTURE|{c.date.isoformat()}|{c.dernier_log_id}|{c.hash_racine}"
        signature_calculee = calculer_hmac(payload)
        
        if c.signature_hmac != signature_calculee:
            erreurs.append(f"Clôture du {c.date} : Signature HMAC invalide (Falsification détectée)")
            ids_invalides.add(c.id)
            
    return len(erreurs) == 0, erreurs, ids_invalides

"""
Interface web pour le système d'audit sécurisé
"""

from flask import (
    Blueprint, flash, g, render_template, request, url_for, redirect
)
from src.auth import permission_required
from src.db import obtenir_session
from src.models import Journal
from sqlalchemy import desc
from sqlalchemy.orm import joinedload
import json

# Reuse the audit_bp created above (avoid redefining and losing previously-decorated routes)

@audit_bp.route('/')
@permission_required('audit.view')
def index():
    """Affiche la liste des entrées du journal d'audit avec filtrage."""
    from flask import g
    from src.models import Utilisateur
    
    # 1. Capture des paramètres de filtrage et pagination
    page = int(request.args.get('page', 1))
    per_page = 50
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    user_id = request.args.get('user_id')
    action_filter = request.args.get('action')
    
    session = obtenir_session()
    
    # 2. Construction de la requête de base
    query = session.query(Journal).options(joinedload(Journal.utilisateur))
    
    # 3. Application des filtres dynamiques
    if start_date:
        query = query.filter(Journal.horodatage >= datetime.fromisoformat(start_date))
    if end_date:
        # Fin de journée pour end_date (23:59:59)
        query = query.filter(Journal.horodatage <= datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59))
    if user_id and user_id != 'all':
        query = query.filter(Journal.utilisateur_id == int(user_id))
    if action_filter and action_filter != 'all':
        query = query.filter(Journal.action == action_filter)
    
    # 4. Statistiques et données pour les dropdowns
    total_entries = query.count()
    
    # Liste des utilisateurs pour le filtre
    utilisateurs = session.query(Utilisateur).filter_by(is_active=True).order_by(Utilisateur.nom_utilisateur).all()
    
    # Liste des actions distinctes présentes dans le journal
    actions_distinctes = [r[0] for r in session.query(Journal.action).distinct().order_by(Journal.action).all()]
    
    # 5. Exécution de la requête avec pagination (plus récentes en premier)
    entries = query.order_by(desc(Journal.id))\
        .offset((page - 1) * per_page)\
        .limit(per_page)\
        .all()
    
    # 6. Logger l'accès filtré
    log_action(g.user.id, "CONSULTATION_AUDIT", "Journal",
               {"page": page, "total_entrees_filtrees": total_entries, 
                "filtres": {"start": start_date, "end": end_date, "user": user_id, "action": action_filter}})
    
    total_pages = (total_entries + per_page - 1) // per_page
    
    # Convert UTC times to local for display
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

    # Préparation des paramètres de filtrage pour le template
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
    """Vérifie l'intégrité du journal d'audit."""
    from flask import g
    valide, erreurs = verifier_integrite()
    
    # Logger la vérification d'intégrité
    if valide:
        log_action(g.user.id, "VERIFICATION_INTEGRITE_AUDIT", "Journal",
                   {"resultat": "valide", "nb_entrees_verifiees": "toutes"})
        flash('L\'intégrité du journal d\'audit est validée.', 'success')
    else:
        log_action(g.user.id, "VERIFICATION_INTEGRITE_AUDIT", "Journal",
                   {"resultat": "compromis", "nb_erreurs": len(erreurs), "erreurs": erreurs[:5]})
        flash(f'L\'intégrité du journal est compromise ! {len(erreurs)} erreur(s) détectée(s).', 'danger')
    
    return render_template('audit/verify.html', valide=valide, erreurs=erreurs)

@audit_bp.route('/<int:id>')
@permission_required('audit.view')
def view(id):
    """Affiche les détails d'une entrée d'audit."""
    from flask import g
    session = obtenir_session()
    entry = session.query(Journal)\
        .options(joinedload(Journal.utilisateur))\
        .filter_by(id=id)\
        .first()
    session.close()
    
    if entry is None:
        flash('Entrée d\'audit introuvable.', 'danger')
        return redirect(url_for('audit.index'))
    
    # Logger la consultation de cette entrée
    log_action(g.user.id, "CONSULTATION_AUDIT", f"Entrée {id}",
               {"entry_id": id, "action_consultee": entry.action})
    
    # Parser les détails JSON si présents
    details = None
    if entry.details:
        try:
            details = json.loads(entry.details)
        except:
            details = entry.details
    
    # Convert to local time for display
    from datetime import timedelta
    from src.config import Config
    
    # Create user object if available
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
    """Affiche la liste des clôtures journalières."""
    session = obtenir_session()
    clotures = session.query(ClotureJournal).order_by(desc(ClotureJournal.date)).all()
    session.close()
    
    # Vérifier l'intégrité globale des clôtures
    tout_valide, erreurs, ids_invalides = verifier_clotures()
    
    return render_template('audit/clotures.html', 
                         clotures=clotures, 
                         tout_valide=tout_valide, 
                         erreurs_cloture=erreurs,
                         ids_invalides=ids_invalides)

@audit_bp.route('/cloturer-hier', methods=('POST',))
@permission_required('audit.verify')
def cloturer_hier():
    """Déclenche la clôture de la journée d'hier."""
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
            print(f"  - {err}")
