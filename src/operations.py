"""
operations.py - Gestion des opérations bancaires

Ce module gère les routes pour :
- Effectuer un dépôt sur un compte
- Effectuer un retrait sur un compte (avec vérification des limites)
"""

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from src.auth import login_required, permission_required
from src.db import obtenir_session
from src.models import Compte, Operation, TypeOperation, StatutCompte
from src.config import Config
from src.audit_logger import log_action
from decimal import Decimal
from datetime import datetime

operations_bp = Blueprint('operations', __name__, url_prefix='/operations')

@operations_bp.route('/depot/<int:compte_id>', methods=('GET', 'POST'))
@permission_required('operations.create')
def depot(compte_id):
    """
    Effectue un dépôt sur un compte.
    Aucune limite de montant pour les dépôts.
    """
    session = obtenir_session()
    compte = session.query(Compte).filter_by(id=compte_id).first()
    
    if compte is None:
        flash('Compte introuvable.', 'danger')
        return redirect(url_for('clients.index'))
    
    # Vérifier que le compte est actif
    if compte.statut.value != 'actif':
        log_action(g.user.id, "ECHEC_DEPOT", f"Compte {compte.numero_compte}",
                   {"raison": "compte_inactif", "statut": compte.statut.value})
        flash('Opération impossible : le compte n\'est pas actif.', 'danger')
        return redirect(url_for('accounts.view', id=compte_id))

    # VERIFICATION: Le client doit être actif pour effectuer un dépôt
    titulaire_statut = compte.client.statut.value
    if titulaire_statut != 'actif':
        log_action(g.user.id, "ECHEC_DEPOT", f"Compte {compte.numero_compte}",
                   {"raison": "client_non_actif", "client_statut": titulaire_statut})
        flash(f'Opération impossible : le titulaire est {titulaire_statut}.', 'danger')
        return redirect(url_for('accounts.view', id=compte_id))

    if request.method == 'POST':
        montant_str = request.form['montant']
        description = request.form.get('description', '')
        error = None

        try:
            montant = Decimal(montant_str)
            if montant <= 0:
                error = 'Le montant doit être supérieur à 0.'
                log_action(g.user.id, "ECHEC_DEPOT", f"Compte {compte.numero_compte}",
                           {"raison": "montant_invalide", "montant": montant_str})
        except:
            error = 'Montant invalide.'
            log_action(g.user.id, "ECHEC_DEPOT", f"Compte {compte.numero_compte}",
                       {"raison": "montant_invalide", "montant": montant_str})

        if error is None:
            try:
                success, msg_or_op = effectuer_operation(compte.id, montant, TypeOperation.DEPOT, g.user.id, description)
                
                if success:
                    flash(f'Dépôt de {montant} {Config.DEVISE} effectué avec succès !', 'success')
                    return redirect(url_for('accounts.view', id=compte.id))
                else:
                    error = f"Erreur lors du dépôt : {msg_or_op}"
                
            except Exception as e:
                session.rollback()
                log_action(g.user.id, "ECHEC_DEPOT", f"Compte {compte.numero_compte}",
                           {"raison": "exception_systeme", "erreur": str(e), "montant": str(montant)})
                error = f"Erreur lors du dépôt : {e}"

        if error is not None:
            flash(error, 'danger')
    else:
        # GET request - Logger l'accès au formulaire
        log_action(g.user.id, "ACCES_FORMULAIRE_DEPOT", f"Compte {compte.numero_compte}",
                   {"compte_id": compte_id, "numero_compte": compte.numero_compte})
    
    # Rendre le template
    result = render_template('operations/depot.html', compte=compte, config=Config)
    return result

@operations_bp.route('/retrait/<int:compte_id>', methods=('GET', 'POST'))
@permission_required('operations.create')
def retrait(compte_id):
    """
    Effectue un retrait sur un compte.
    Vérifie les limites de retrait et le solde minimum.
    """
    session = obtenir_session()
    compte = session.query(Compte).filter_by(id=compte_id).first()
    
    if compte is None:
        flash('Compte introuvable.', 'danger')
        return redirect(url_for('clients.index'))
    
    # Vérifier que le compte est actif
    if compte.statut.value != 'actif':
        log_action(g.user.id, "ECHEC_RETRAIT", f"Compte {compte.numero_compte}",
                   {"raison": "compte_inactif", "statut": compte.statut.value})
        flash('Opération impossible : le compte n\'est pas actif.', 'danger')
        return redirect(url_for('accounts.view', id=compte_id))

    # VERIFICATION: Le client doit être actif pour effectuer un retrait
    titulaire_statut = compte.client.statut.value
    if titulaire_statut != 'actif':
        log_action(g.user.id, "ECHEC_RETRAIT", f"Compte {compte.numero_compte}",
                   {"raison": "client_non_actif", "client_statut": titulaire_statut})
        flash(f'Opération impossible : le titulaire est {titulaire_statut}.', 'danger')
        return redirect(url_for('accounts.view', id=compte_id))

    if request.method == 'POST':
        montant_str = request.form['montant']
        description = request.form.get('description', '')
        error = None

        try:
            montant = Decimal(montant_str)
            
            # Vérifications des règles métier
            if montant <= 0:
                error = 'Le montant doit être supérieur à 0.'
                log_action(g.user.id, "ECHEC_RETRAIT", f"Compte {compte.numero_compte}",
                           {"raison": "montant_invalide", "montant": montant_str})
            elif montant > Config.RETRAIT_MAXIMUM:
                error = f'Le retrait maximum autorisé est de {Config.RETRAIT_MAXIMUM} {Config.DEVISE}.'
                log_action(g.user.id, "ECHEC_RETRAIT", f"Compte {compte.numero_compte}",
                           {"raison": "limite_depassee", "montant": str(montant), "limite": str(Config.RETRAIT_MAXIMUM)})
            elif not compte.peut_retirer(montant):
                error = f'Solde insuffisant. Le solde minimum autorisé est de {Config.SOLDE_MINIMUM_COMPTE} {Config.DEVISE}.'
                log_action(g.user.id, "ECHEC_RETRAIT", f"Compte {compte.numero_compte}",
                           {"raison": "solde_insuffisant", "montant": str(montant), "solde": str(compte.solde)})
        except:
            error = 'Montant invalide.'
            log_action(g.user.id, "ECHEC_RETRAIT", f"Compte {compte.numero_compte}",
                       {"raison": "montant_invalide", "montant": montant_str})

        if error is None:
            # INTERCEPTION MAKER-CHECKER : Si le montant dépasse le seuil, on met en attente
            if montant > Config.MAKER_CHECKER_THRESHOLD:
                from src.checker import soumettre_approbation
                try:
                    payload = {
                        'compte_id': compte.id,
                        'numero_compte': compte.numero_compte,
                        'montant': str(montant),
                        'description': description,
                        'date_demande': datetime.utcnow().isoformat()
                    }
                    demande = soumettre_approbation(session, 'RETRAIT_EXCEPTIONNEL', payload, g.user.id)
                    session.commit()
                    flash(f'Le retrait de {montant} {Config.DEVISE} dépasse le seuil de sécurité. La demande # {demande.id} a été mise en attente de validation par un administrateur.', 'warning')
                    return redirect(url_for('accounts.view', id=compte.id))
                except Exception as e:
                    session.rollback()
                    flash(f"Erreur lors de la mise en attente : {e}", 'danger')
                    return redirect(url_for('accounts.view', id=compte.id))

            try:
                # Exécution normale (si sous le seuil)
                success, msg_or_op = effectuer_operation(compte.id, montant, TypeOperation.RETRAIT, g.user.id, description)
                if success:
                    flash(f'Retrait de {montant} {Config.DEVISE} effectué avec succès !', 'success')
                    return redirect(url_for('accounts.view', id=compte.id))
                else:
                    error = f"Erreur lors du retrait : {msg_or_op}"
            except Exception as e:
                session.rollback()
                log_action(g.user.id, "ECHEC_RETRAIT", f"Compte {compte.numero_compte}",
                           {"raison": "exception_systeme", "erreur": str(e), "montant": str(montant)})
                error = f"Erreur lors du retrait : {e}"

        if error is not None:
            flash(error, 'danger')
    else:
        # GET request - Logger l'accès au formulaire
        log_action(g.user.id, "ACCES_FORMULAIRE_RETRAIT", f"Compte {compte.numero_compte}",
                   {"compte_id": compte_id, "numero_compte": compte.numero_compte, "solde_actuel": str(compte.solde)})
    
    # Rendre le template
    result = render_template('operations/retrait.html', compte=compte, config=Config)
    return result

def effectuer_operation(compte_id, montant, type_op, user_id, description="", valide_par=None):
    """
    Fonction cœur pour exécuter une opération bancaire.
    Peut être appelée par une route ou par le dispatcher Maker-Checker.

    Args:
        valide_par (int|None): ID de l'admin/checker ayant validé l'opération (optionnel).
    """
    session = obtenir_session()
    try:
        compte = session.query(Compte).filter_by(id=compte_id).with_for_update().first()
        if not compte:
            return False, "Compte introuvable."
            
        if compte.statut != StatutCompte.ACTIF:
            return False, "Compte inactif."

        montant = Decimal(str(montant))
        solde_avant = compte.solde
        
        if type_op == TypeOperation.DEPOT:
            compte.solde += montant
        elif type_op == TypeOperation.RETRAIT:
            if not compte.peut_retirer(montant):
                return False, "Solde insuffisant ou limite dépassée."
            compte.solde -= montant
        
        operation = Operation(
            compte_id=compte.id,
            utilisateur_id=user_id,
            type_operation=type_op,
            montant=montant,
            solde_avant=solde_avant,
            solde_apres=compte.solde,
            description=description
        )

        # Enregistrer qui a validé (si fourni)
        if valide_par is not None:
            operation.valide_par_id = int(valide_par)

        session.add(operation)
        
        # Audit
        extra = {"montant": str(montant), "nouveau_solde": str(compte.solde)}
        if valide_par is not None:
            extra['valide_par'] = int(valide_par)
        log_action(user_id, type_op.value.upper(), f"Compte {compte.numero_compte}", extra)
        
        session.commit()
        return True, operation
    except Exception as e:
        session.rollback()
        return False, str(e)
