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
from src.models import Compte, Operation, TypeOperation
from src.config import Config
from src.audit_logger import log_action
from decimal import Decimal

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
        session.close()
        flash('Compte introuvable.', 'danger')
        return redirect(url_for('clients.index'))
    
    # Vérifier que le compte est actif
    if compte.statut.value != 'actif':
        log_action(g.user.id, "ECHEC_DEPOT", f"Compte {compte.numero_compte}",
                   {"raison": "compte_inactif", "statut": compte.statut.value})
        session.close()
        flash('Opération impossible : le compte n\'est pas actif.', 'danger')
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
                # 1. Sauvegarder l'ancien solde
                solde_avant = compte.solde
                
                # 2. Mettre à jour le solde
                compte.solde += montant
                
                # 3. Créer l'opération
                operation = Operation(
                    compte_id=compte.id,
                    utilisateur_id=g.user.id,
                    type_operation=TypeOperation.DEPOT,
                    montant=montant,
                    solde_avant=solde_avant,
                    solde_apres=compte.solde,
                    description=description
                )
                session.add(operation)
                
                # 4. Audit
                log_action(g.user.id, "DEPOT", f"Compte {compte.numero_compte}", 
                           {"montant": str(montant), "nouveau_solde": str(compte.solde)})
                
                session.commit()
                compte_id = compte.id
                flash(f'Dépôt de {montant} {Config.DEVISE} effectué avec succès !', 'success')
                session.close()  # Fermer après le flash mais avant le redirect
                return redirect(url_for('accounts.view', id=compte_id))
                
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
    session.close()
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
        session.close()
        flash('Compte introuvable.', 'danger')
        return redirect(url_for('clients.index'))
    
    # Vérifier que le compte est actif
    if compte.statut.value != 'actif':
        log_action(g.user.id, "ECHEC_RETRAIT", f"Compte {compte.numero_compte}",
                   {"raison": "compte_inactif", "statut": compte.statut.value})
        session.close()
        flash('Opération impossible : le compte n\'est pas actif.', 'danger')
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
            try:
                # 1. Sauvegarder l'ancien solde
                solde_avant = compte.solde
                
                # 2. Mettre à jour le solde
                compte.solde -= montant
                
                # 3. Créer l'opération
                operation = Operation(
                    compte_id=compte.id,
                    utilisateur_id=g.user.id,
                    type_operation=TypeOperation.RETRAIT,
                    montant=montant,
                    solde_avant=solde_avant,
                    solde_apres=compte.solde,
                    description=description
                )
                session.add(operation)
                
                # 4. Audit
                log_action(g.user.id, "RETRAIT", f"Compte {compte.numero_compte}", 
                           {"montant": str(montant), "nouveau_solde": str(compte.solde)})
                
                session.commit()
                compte_id = compte.id
                flash(f'Retrait de {montant} {Config.DEVISE} effectué avec succès !', 'success')
                session.close()  # Fermer après le flash mais avant le redirect
                return redirect(url_for('accounts.view', id=compte_id))
                
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
    session.close()
    return result
