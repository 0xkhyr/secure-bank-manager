from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from src.db import obtenir_session
from src.models import OperationEnAttente, StatutAttente, Journal, RoleUtilisateur
from src.audit_logger import log_action
from src.auth import admin_required, login_required
from datetime import datetime

checker_bp = Blueprint('checker', __name__, url_prefix='/approbations')

@checker_bp.route('/')
@admin_required
def index():
    """Liste les opérations en attente pour les admins."""
    session = obtenir_session()
    # Eager-load the requester to avoid lazy-loading while rendering after session lifecycle changes
    from sqlalchemy.orm import joinedload
    q = session.query(OperationEnAttente).options(joinedload(OperationEnAttente.cree_par)).filter(OperationEnAttente.statut == StatutAttente.PENDING)

    # Optional filter: show only current user's demandes
    filter_param = request.args.get('filter')
    show_mine = (filter_param == 'mine')
    if show_mine:
        q = q.filter(OperationEnAttente.cree_par_id == g.user.id)

    demandes = q.order_by(OperationEnAttente.cree_le.desc()).all()
    # Session remains valid until request teardown; eager load prevents DetachedInstanceError in templates
    result = render_template('admin/approbations.html', demandes=demandes, filter=filter_param)
    return result


@checker_bp.route('/mes')
@login_required
def mes():
    """Liste les demandes soumises par l'utilisateur courant (Maker)."""
    session = obtenir_session()
    demandes = session.query(OperationEnAttente).filter_by(cree_par_id=g.user.id).order_by(OperationEnAttente.cree_le.desc()).all()
    return render_template('checker/mes.html', demandes=demandes)

@checker_bp.route('/decider/<int:id>', methods=('POST',))
@admin_required
def decider(id):
    """Approuve ou rejette une demande."""
    action = request.form.get('action')
    raison = request.form.get('raison')
    commentaire = request.form.get('commentaire')
    admin_id = g.user.id
    
    if action == 'approve':
        success, message = executer_approbation(id, admin_id, raison, commentaire)
        category = 'success' if success else 'danger'
        flash(message, category)
    elif action == 'reject':
        success, message = rejeter_approbation(id, admin_id, raison, commentaire)
        flash(message, 'info' if success else 'danger')
        
    return redirect(url_for('checker.index'))

def soumettre_approbation(session, type_operation, payload, user_id):
    """
    Met une opération en attente de validation.
    
    Args:
        session : Session SQLAlchemy active
        type_operation (str) : Identifiant du type d'action (ex: 'RETRAIT_IMPORTANT')
        payload (dict) : Données nécessaires à l'exécution finale
        user_id (int) : ID de l'utilisateur (Maker) qui soumet la requête
        
    Returns:
        OperationEnAttente : L'objet créé
    """
    nouvelle_demande = OperationEnAttente(
        type_operation=type_operation,
        payload=payload,
        cree_par_id=user_id,
        statut=StatutAttente.PENDING
    )
    session.add(nouvelle_demande)
    session.flush() # Pour avoir l'ID avant le commit final si besoin
    
    # Log d'audit de la soumission
    log_action(user_id, f"SOUMISSION_APPROBATION", type_operation, 
               {"demande_id": nouvelle_demande.id})
               
    return nouvelle_demande

def executer_approbation(approbation_id, admin_id, raison=None, commentaire=None):
    """
    Valide et exécute une opération en attente.
    Cette fonction doit être appelée par un administrateur.
    """
    session = obtenir_session()
    try:
        demande = session.query(OperationEnAttente).get(approbation_id)
        if not demande or demande.statut != StatutAttente.PENDING:
            return False, "Demande introuvable ou déjà traitée."
            
        if demande.cree_par_id == admin_id:
            # Audit attempt: user tried to approve their own request (4-eyes principle violation)
            details = {
                "demande_id": demande.id,
                "maker_id": demande.cree_par_id,
                "attempt": "self_approval"
            }
            try:
                # include request path if available (guard against missing request context)
                details["path"] = request.path
            except Exception:
                pass
            log_action(admin_id, 'ACCES_REFUSE', 'Tentative_auto-approbation', details)
            return False, "Le 'Checker' doit être différent du 'Maker' (Principe des 4 yeux)."
        

        # 1. Marquer comme approuvé
        demande.statut = StatutAttente.APPROVED
        demande.valide_par_id = admin_id
        demande.valide_le = datetime.utcnow()
        demande.decision_reason = raison
        demande.decision_comment = commentaire
        
        # 2. Exécution Logique (Dispatcher)
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
    """Refuse une opération en attente."""
    session = obtenir_session()
    try:
        demande = session.query(OperationEnAttente).get(approbation_id)
        if not demande or demande.statut != StatutAttente.PENDING:
            return False, "Demande introuvable ou déjà traitée."

        # Disallow self-reject (maker cannot reject their own request)
        if demande.cree_par_id == admin_id:
            details = {"demande_id": demande.id, "maker_id": demande.cree_par_id, "attempt": "self_reject"}
            try:
                details["path"] = request.path
            except Exception:
                pass
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
    Exécute la logique réelle selon le type d'opération.
    """
    payload = demande.payload
    
    if demande.type_operation == 'RETRAIT_EXCEPTIONNEL':
        from src.operations import effectuer_operation
        from src.models import TypeOperation
        # Important: when approving a Maker-Checker request, the *original maker* should be
        # recorded as the operation initiator to avoid confusion (the admin only validates).
        # Pass the creator's user id as the operation user; the approval is separately logged.
        maker_id = demande.cree_par_id or admin_id
        success, msg_or_op = effectuer_operation(
            payload['compte_id'],
            payload['montant'],
            TypeOperation.RETRAIT,
            maker_id, # Record the maker as the operation actor
            payload.get('description', 'Approuvé par Maker-Checker'),
            valide_par=admin_id # Record who validated the request
        )
        return success, msg_or_op if not success else "OK"
    
    elif demande.type_operation == 'OUVERTURE_COMPTE':
        from src.accounts import create
        # Exemple simulation
        # success, account = create(payload['client_id'], payload['solde_initial'])
        # return success, "OK"
        return False, "Action non implémentée"
        
    return False, "Type d'opération inconnu"


def retirer_approbation(approbation_id, user_id):
    """Permet au maker de retirer (annuler) sa propre demande en attente."""
    session = obtenir_session()
    try:
        demande = session.query(OperationEnAttente).get(approbation_id)
        if not demande or demande.statut != StatutAttente.PENDING:
            return False, "Demande introuvable ou déjà traitée."

        # Only the original maker can withdraw
        if demande.cree_par_id != user_id:
            details = {"demande_id": demande.id, "actor_id": user_id, "attempt": "unauthorized_withdraw"}
            try:
                details["path"] = request.path
            except Exception:
                pass
            log_action(user_id, 'ACCES_REFUSE', 'Tentative_retrait_non_autorisee', details)
            return False, "Vous n'êtes pas autorisé à retirer cette demande."

        demande.statut = StatutAttente.CANCELLED
        demande.valide_le = datetime.utcnow()
        demande.decision_reason = 'withdraw'
        session.commit()
        log_action(user_id, 'SOUMISSION_RETRACTION', demande.type_operation, {"demande_id": demande.id})
        return True, "Demande retirée avec succès."
    except Exception as e:
        session.rollback()
        return False, str(e)


@checker_bp.route('/retirer/<int:id>', methods=('POST',))
@login_required
def retirer(id):
    """Route pour que le maker retire sa propre demande."""
    success, msg = retirer_approbation(id, g.user.id)
    flash(msg, 'success' if success else 'danger')
    return redirect(url_for('checker.index'))
