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
    demandes = session.query(OperationEnAttente).options(joinedload(OperationEnAttente.cree_par)).filter_by(statut=StatutAttente.PENDING).order_by(OperationEnAttente.cree_le.desc()).all()
    # Session remains valid until request teardown; eager load prevents DetachedInstanceError in templates
    result = render_template('admin/approbations.html', demandes=demandes)
    return result

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
