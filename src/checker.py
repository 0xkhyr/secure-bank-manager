"""
# Workflow de Double Validation (Maker-Checker)
# Règle métier : Implémente le principe des "quatre yeux" pour les actions sensibles.
# Sécurité : Garantit qu'aucune transaction critique ne peut être réalisée par un seul individu.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from src.db import obtenir_session
from src.models import OperationEnAttente, StatutAttente, Journal, RoleUtilisateur
from src.audit_logger import log_action
from src.auth import admin_required, login_required, permission_required, has_permission
from datetime import datetime

checker_bp = Blueprint('checker', __name__, url_prefix='/approbations')

@checker_bp.route('/')
@checker_bp.route('')
@permission_required('approbations.view')
def index():
    """
    # Audit : Liste les demandes en attente pour les administrateurs (Checkers).
    """
    session = obtenir_session()
    # Sécurité : Utilise joinedload pour éviter les problèmes d'objets détachés lors du rendu.
    from sqlalchemy.orm import joinedload
    q = session.query(OperationEnAttente).options(joinedload(OperationEnAttente.cree_par)).filter(OperationEnAttente.statut == StatutAttente.PENDING)

    filter_param = request.args.get('filter')
    show_mine = (filter_param == 'mine')
    if show_mine:
        q = q.filter(OperationEnAttente.cree_par_id == g.user.id)

    demandes = q.order_by(OperationEnAttente.cree_le.desc()).all()
    result = render_template('admin/approbations.html', demandes=demandes, filter=filter_param)
    return result


@checker_bp.route('/mes')
@login_required
def mes():
    """
    # Règle métier : Historique personnel des demandes soumises par l'utilisateur (Maker).
    """
    session = obtenir_session()
    demandes = session.query(OperationEnAttente).filter_by(cree_par_id=g.user.id).order_by(OperationEnAttente.cree_le.desc()).all()
    return render_template('checker/mes.html', demandes=demandes)

@checker_bp.route('/decider/<int:id>', methods=('POST',))
@permission_required('approbations.view')
def decider(id):
    """
    # Règle métier : Point de décision pour l'approbation ou le rejet d'une demande.
    """
    action = request.form.get('action')
    raison = request.form.get('raison')
    commentaire = request.form.get('commentaire')
    admin_id = g.user.id

    # Sécurité : Vérification granulaire des permissions d'approbation/rejet.
    if action == 'approve':
        if not has_permission(g.user, 'approbations.approve'):
            log_action(admin_id, 'ACCES_REFUSE', 'approbations.approve', {'path': request.path})
            flash("Accès refusé : privilèges insuffisants pour approuver.", 'danger')
            return redirect(url_for('checker.index'))
        success, message = executer_approbation(id, admin_id, raison, commentaire)
        category = 'success' if success else 'danger'
        flash(message, category)
    elif action == 'reject':
        if not has_permission(g.user, 'approbations.reject'):
            log_action(admin_id, 'ACCES_REFUSE', 'approbations.reject', {'path': request.path})
            flash("Accès refusé : privilèges insuffisants pour rejeter.", 'danger')
            return redirect(url_for('checker.index'))
        success, message = rejeter_approbation(id, admin_id, raison, commentaire)
        flash(message, 'info' if success else 'danger')
        
    return redirect(url_for('checker.index'))

def soumettre_approbation(session, type_operation, payload, user_id):
    """
    # Règle métier : Place une opération jugée sensible en quarantaine pour validation.
    """
    nouvelle_demande = OperationEnAttente(
        type_operation=type_operation,
        payload=payload,
        cree_par_id=user_id,
        statut=StatutAttente.PENDING
    )
    session.add(nouvelle_demande)
    session.flush() 
    
    # Audit : Trace la soumission initiale avec masquage des données sensibles.
    details = {"demande_id": nouvelle_demande.id, "payload": _sanitize_payload(payload)}
    log_action(user_id, "SOUMISSION_APPROBATION", type_operation, details)
               
    return nouvelle_demande

def executer_approbation(approbation_id, admin_id, raison=None, commentaire=None):
    """
    # Sécurité : Valide et exécute l'opération finale après contrôle par un tiers.
    """
    session = obtenir_session()
    try:
        demande = session.query(OperationEnAttente).get(approbation_id)
        if not demande or demande.statut != StatutAttente.PENDING:
            return False, "Demande introuvable ou déjà traitée."
            
        # Sécurité : Application stricte du principe des 4 yeux (Auto-approbation interdite).
        if demande.cree_par_id == admin_id:
            details = { "demande_id": demande.id, "maker_id": demande.cree_par_id, "attempt": "self_approval" }
            log_action(admin_id, 'ACCES_REFUSE', 'Tentative_auto-approbation', details)
            return False, "Le 'Checker' doit être différent du 'Maker' (Principe des 4 yeux)."
        
        demande.statut = StatutAttente.APPROVED
        demande.valide_par_id = admin_id
        demande.valide_le = datetime.utcnow()
        demande.decision_reason = raison
        demande.decision_comment = commentaire
        
        # Règle métier : Dispatch l'exécution vers le module métier concerné.
        success, message = _dispatcher_execution(session, demande, admin_id)
        
        if success:
            session.commit()
            log_action(admin_id, "APPROBATION_VALIDEE", demande.type_operation, 
                       {"demande_id": demande.id, "raison": raison, "commentaire": commentaire})
            return True, "Opération validée et exécutée avec succès."
        else:
            session.rollback()
            return False, f"Erreur lors de l'exécution : {message}"
            
    except Exception as e:
        session.rollback()
        return False, f"Erreur technique : {str(e)}"

def rejeter_approbation(approbation_id, admin_id, raison=None, commentaire=None):
    """
    # Sécurité : Refus officiel d'une demande avec motif obligatoire pour l'audit.
    """
    session = obtenir_session()
    try:
        demande = session.query(OperationEnAttente).get(approbation_id)
        if not demande or demande.statut != StatutAttente.PENDING:
            return False, "Demande introuvable ou déjà traitée."

        # Sécurité : Un utilisateur ne peut pas rejeter sa propre demande pour contourner les logs.
        if demande.cree_par_id == admin_id:
            details = {"demande_id": demande.id, "maker_id": demande.cree_par_id, "attempt": "self_reject"}
            log_action(admin_id, 'ACCES_REFUSE', 'Tentative_auto-rejet', details)
            return False, "Le 'Checker' doit être différent du 'Maker' (Principe des 4 yeux)."
            
        demande.statut = StatutAttente.REJECTED
        demande.valide_par_id = admin_id
        demande.valide_le = datetime.utcnow()
        demande.decision_reason = raison
        demande.decision_comment = commentaire
        
        session.commit()
        log_action(admin_id, "APPROBATION_REJETEE", demande.type_operation, 
                   {"demande_id": demande.id, "raison": raison, "commentaire": commentaire})
        return True, "Opération rejetée."
    except Exception as e:
        session.rollback()
        return False, str(e)

def _dispatcher_execution(session, demande, admin_id):
    """
    # Règle métier : Pivot central d'exécution des transactions approuvées.
    """
    payload = demande.payload
    
    if demande.type_operation == 'RETRAIT_EXCEPTIONNEL':
        from src.operations import effectuer_operation
        from src.models import TypeOperation
        # Audit : L'acteur original (Maker) est consigné comme initiateur, l'admin comme validateur.
        maker_id = demande.cree_par_id or admin_id
        success, msg_or_op = effectuer_operation(
            payload['compte_id'],
            payload['montant'],
            TypeOperation.RETRAIT,
            maker_id, 
            payload.get('description', 'Approuvé par Maker-Checker'),
            valide_par=admin_id 
        )
        return success, msg_or_op if not success else "OK"
    
    return False, "Type d'opération inconnu"

def _mask_partial(value, keep=4, placeholder='*'):
    """# Audit : Masquage partiel des données sensibles pour le journal."""
    s = str(value)
    if len(s) <= keep:
        return placeholder * len(s)
    return placeholder * (len(s) - keep) + s[-keep:]

def _sanitize_payload(payload, redact_keys=None, max_len=1000):
    """# Audit : Nettoyage préventif des données avant écriture dans le journal d'audit."""
    import json
    redact_keys = set(redact_keys or ('numero_compte','cin','card_number','ssn','token'))
    try:
        p = dict(payload) if isinstance(payload, dict) else {'value': payload}
        for k in list(p.keys()):
            try:
                if k in redact_keys:
                    p[k] = _mask_partial(p[k], keep=4)
                else:
                    v = p[k]
                    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, (str,int,float,bool)) else str(v)
                    p[k] = (s[:max_len] + '...') if len(s) > max_len else s
            except Exception:
                p[k] = '[REDACTED]'
        return p
    except Exception:
        return {'summary': str(payload)[:max_len]}

def retirer_approbation(approbation_id, user_id, raison=None, commentaire=None):
    """# Règle métier : Permet au Maker d'annuler sa demande avant traitement par un Checker."""
    session = obtenir_session()
    try:
        demande = session.query(OperationEnAttente).get(approbation_id)
        if not demande or demande.statut != StatutAttente.PENDING:
            return False, "Demande introuvable ou déjà traitée."

        # Sécurité : Seul l'auteur original peut rétracter sa demande.
        if demande.cree_par_id != user_id:
            details = {"demande_id": demande.id, "actor_id": user_id, "attempt": "unauthorized_withdraw"}
            log_action(user_id, 'ACCES_REFUSE', 'Tentative_retrait_non_autorisee', details)
            return False, "Vous n'êtes pas autorisé à retirer cette demande."

        demande.statut = StatutAttente.CANCELLED
        demande.valide_le = datetime.utcnow()
        demande.decision_reason = raison or 'withdraw'
        demande.decision_comment = commentaire
        session.commit()
        
        details = {"demande_id": demande.id, "raison": demande.decision_reason}
        if commentaire:
            details["commentaire"] = commentaire
        
        # Audit : Extraction des métadonnées de l'opération pour la traçabilité.
        try:
            p = demande.payload
            if isinstance(p, dict) and 'montant' in p:
                details['montant'] = str(p['montant'])
        except Exception:
            pass
        
        log_action(user_id, 'SOUMISSION_RETRACTION', demande.type_operation, details)
        return True, "Demande retirée avec succès."
    except Exception as e:
        session.rollback()
        return False, str(e)

@checker_bp.route('/retirer/<int:id>', methods=('POST',))
@login_required
def retirer(id):
    """
    # Règle métier : Route d'annulation pour le Maker.
    """
    raison = request.form.get('raison')
    commentaire = request.form.get('commentaire')
    success, msg = retirer_approbation(id, g.user.id, raison, commentaire)
    flash(msg, 'success' if success else 'danger')
    return redirect(url_for('checker.index'))
