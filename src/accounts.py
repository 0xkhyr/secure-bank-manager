"""
# Gestion des Comptes Bancaires
# Règle métier : Ce module orchestre le cycle de vie des comptes (création, consultation, clôture).
# Sécurité : Chaque action modifiant l'état d'un compte est rigoureusement auditée et soumise à habilitation.
"""

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from src.auth import login_required, permission_required
from src.db import obtenir_session
from src.models import Client, Compte, Operation, TypeOperation, StatutCompte, gen_numero_compte
from src.config import Config
from src.audit_logger import log_action
from decimal import Decimal

accounts_bp = Blueprint('accounts', __name__, url_prefix='/accounts')

@accounts_bp.route('/nouveau/<int:client_id>', methods=('GET', 'POST'))
@permission_required('accounts.create')
def create(client_id):
    """
    # Règle métier : Ouverture de compte avec condition de dépôt initial minimum.
    # Sécurité : Vérifie l'éligibilité du client (statut actif requis) avant toute allocation de ressource.
    """
    session = obtenir_session()
    client = session.query(Client).filter_by(id=client_id).first()
    
    if client is None:
        flash('Client introuvable.', 'danger')
        return redirect(url_for('clients.index'))

    # Sécurité : Interdiction de créer des comptes pour des clients suspendus ou bloqués.
    client_statut = client.statut.value
    if client_statut != 'actif':
        flash(f'Action impossible : le client est {client_statut}.', 'danger')
        return redirect(url_for('clients.view', id=client_id))

    if request.method == 'POST':
        montant_initial = request.form['montant_initial']
        error = None

        try:
            montant = Decimal(montant_initial)
            # Règle métier : Le solde initial doit respecter le plancher configuré pour la banque.
            if montant < Config.SOLDE_MINIMUM_INITIAL:
                error = f'Le dépôt initial doit être d\'au moins {Config.SOLDE_MINIMUM_INITIAL} {Config.DEVISE}.'
        except:
            error = 'Montant invalide.'

        if error is None:
            try:
                # Audit : Attribution d'un numéro de compte unique généré selon les standards bancaires.
                nouveau_compte = Compte(
                    numero_compte=gen_numero_compte(),
                    client_id=client.id,
                    solde=montant, 
                    statut=StatutCompte.ACTIF
                )
                session.add(nouveau_compte)
                session.flush() 
                
                # Règle métier : Création automatique de la première opération pour la traçabilité du solde.
                operation = Operation(
                    compte_id=nouveau_compte.id,
                    utilisateur_id=g.user.id,
                    type_operation=TypeOperation.DEPOT,
                    montant=montant,
                    solde_avant=0,
                    solde_apres=montant,
                    description="Dépôt initial à l'ouverture"
                )
                session.add(operation)
                
                # Audit : Consignation de la création du compte avec l'identifiant du gestionnaire.
                log_action(g.user.id, "CREATION_COMPTE", f"Compte {nouveau_compte.numero_compte}", 
                           {"client_id": client.id, "depot_initial": str(montant)})
                
                session.commit()
                flash('Compte créé avec succès !', 'success')
                return redirect(url_for('clients.view', id=client.id))
                
            except Exception as e:
                session.rollback()
                error = f"Erreur lors de la création : {e}"

        if error is not None:
            flash(error, 'danger')
    
    result = render_template('accounts/create.html', client=client, config=Config)
    return result

@accounts_bp.route('/<numero_compte>')
@login_required
def view(numero_compte):
    """
    # Audit : Consultation détaillée d'un compte et de son historique transactionnel.
    # Traçabilité : L'accès aux données bancaires d'un client est un événement audité.
    """
    session = obtenir_session()
    compte = session.query(Compte).filter_by(numero_compte=numero_compte).first()
    
    if compte is None:
        flash('Compte introuvable.', 'danger')
        return redirect(url_for('clients.index'))
    
    client_id = compte.client_id
    operations = session.query(Operation).filter_by(compte_id=compte.id).order_by(Operation.date_operation.desc()).all()
    nb_operations = len(operations)

    # Audit : Enregistrement de la consultation de l'historique bancaire.
    log_action(g.user.id, "CONSULTATION_COMPTE", f"Compte {compte.numero_compte}",
               {"compte_id": compte.id, "numero_compte": compte.numero_compte, 
                "client_id": client_id, "nb_operations": nb_operations})
    
    response = render_template('accounts/view.html', compte=compte, client_id=client_id, operations=operations)
    return response

@accounts_bp.route('/<int:id>/cloturer', methods=('POST',))
@permission_required('accounts.close')
def close(id):
    """
    # Règle métier : Clôture administrative d'un compte.
    # Limitation : Un compte ne peut être clôturé tant que son solde n'est pas nul (obligation légale).
    """
    session = obtenir_session()
    compte = session.query(Compte).filter_by(id=id).first()
    
    if compte is None:
        flash('Compte introuvable.', 'danger')
        return redirect(url_for('clients.index'))
        
    if compte.solde != 0:
        flash('Impossible de clôturer un compte avec un solde positif. Veuillez tout retirer d\'abord.', 'danger')
        return redirect(url_for('accounts.view', numero_compte=compte.numero_compte))
    
    raison = request.form.get('raison', 'Demande client')
    client_id = compte.client_id
        
    try:
        compte.statut = StatutCompte.FERME
        # Audit : Traçabilité du motif de clôture et du responsable.
        log_action(g.user.id, "CLOTURE_COMPTE", f"Compte {compte.numero_compte}", 
                   {"raison": raison})
        session.commit()
        flash('Compte clôturé avec succès.', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Erreur : {e}', 'danger')
        
    return redirect(url_for('clients.view', id=client_id))


@accounts_bp.route('/<int:id>/reopen', methods=('POST',))
@permission_required('accounts.close')
def reopen(id):
    """
    # Règle métier : Réactivation d'un compte précédemment clôturé.
    # Sécurité : Vérifie que le titulaire est toujours autorisé (non figurant sur liste noire).
    """
    session = obtenir_session()
    compte = session.query(Compte).filter_by(id=id).first()
    
    if compte is None:
        flash('Compte introuvable.', 'danger')
        return redirect(url_for('clients.index'))
    
    if compte.statut.value != 'ferme':
        flash('Ce compte n\'est pas fermé.', 'danger')
        return redirect(url_for('accounts.view', numero_compte=compte.numero_compte))

    # Sécurité : Empêche la réouverture automatique si le client n'est plus en règle avec la banque.
    titulaire_statut = compte.client.statut.value
    if titulaire_statut != 'actif':
        flash(f'Action impossible : le titulaire du compte est {titulaire_statut}.', 'danger')
        return redirect(url_for('accounts.view', numero_compte=compte.numero_compte))
    
    raison = request.form.get('raison', 'Décision administrative')
    compte_id = compte.id
        
    try:
        compte.statut = StatutCompte.ACTIF
        # Audit : Toute réactivation doit être justifiée et imputable à un gestionnaire.
        log_action(g.user.id, "REOUVERTURE_COMPTE", f"Compte {compte.numero_compte}", 
                   {"raison": raison})
        session.commit()
        flash('Compte réouvert avec succès.', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Erreur : {e}', 'danger')
        
    return redirect(url_for('accounts.view', numero_compte=compte.numero_compte))
