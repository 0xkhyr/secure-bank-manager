"""
accounts.py - Gestion des comptes bancaires

Ce module gère les routes pour :
- Créer un nouveau compte (avec dépôt initial)
- Voir les détails et l'historique d'un compte
- Clôturer un compte
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
    Crée un nouveau compte pour un client spécifique.
    Nécessite un dépôt initial minimum.
    """
    session = obtenir_session()
    client = session.query(Client).filter_by(id=client_id).first()
    
    if client is None:
        flash('Client introuvable.', 'danger')
        return redirect(url_for('clients.index'))

    # VERIFICATION: Le client doit être actif pour créer un compte
    client_statut = client.statut.value
    if client_statut != 'actif':
        flash(f'Action impossible : le client est {client_statut}.', 'danger')
        return redirect(url_for('clients.view', id=client_id))

    if request.method == 'POST':
        montant_initial = request.form['montant_initial']
        error = None

        try:
            montant = Decimal(montant_initial)
            if montant < Config.SOLDE_MINIMUM_INITIAL:
                error = f'Le dépôt initial doit être d\'au moins {Config.SOLDE_MINIMUM_INITIAL} {Config.DEVISE}.'
        except:
            error = 'Montant invalide.'

        if error is None:
            try:
                # 1. Créer le compte
                nouveau_compte = Compte(
                    numero_compte=gen_numero_compte(),
                    client_id=client.id,
                    solde=montant, # Le solde initial est le dépôt
                    statut=StatutCompte.ACTIF
                )
                session.add(nouveau_compte)
                session.flush() # Pour avoir l'ID du compte
                
                # 2. Créer l'opération de dépôt initial
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
                
                # 3. Audit
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
    
    # Ne pas fermer la session avant de rendre le template car le template accède aux propriétés du client
    result = render_template('accounts/create.html', client=client, config=Config)
    return result

@accounts_bp.route('/<int:id>')
@login_required
def view(id):
    """Affiche les détails d'un compte et son historique."""
    session = obtenir_session()
    compte = session.query(Compte).filter_by(id=id).first()
    
    if compte is None:
        flash('Compte introuvable.', 'danger')
        return redirect(url_for('clients.index'))
    
    # Accéder au client_id avant de fermer la session
    client_id = compte.client_id
        
    # Charger l'historique des opérations (plus récent en premier)
    operations = session.query(Operation).filter_by(compte_id=id).order_by(Operation.date_operation.desc()).all()
    nb_operations = len(operations)
    # Logger la consultation du compte et de l'historique
    log_action(g.user.id, "CONSULTATION_COMPTE", f"Compte {compte.numero_compte}",
               {"compte_id": id, "numero_compte": compte.numero_compte, 
                "client_id": client_id, "nb_operations": nb_operations})
    
    response = render_template('accounts/view.html', compte=compte, client_id=client_id, operations=operations)
    return response


@accounts_bp.route('/<numero_compte>')
@login_required
def view_by_num(numero_compte):
    """Redirige vers la vue canonique du compte en utilisant l'identifiant numérique.

    Autorise des URL lisibles telles que /accounts/CPT251227212555 et redirige vers /accounts/<id>.
    """
    session = obtenir_session()
    compte = session.query(Compte).filter_by(numero_compte=numero_compte).first()
    if compte is None:
        from flask import abort
        session.close()
        abort(404)
    # Render the canonical view directly so /accounts/<numero> is a friendly, canonical URL
    target_id = compte.id
    session.close()
    return view(target_id)

@accounts_bp.route('/<int:id>/cloturer', methods=('POST',))
@permission_required('accounts.close')
def close(id):
    """
    Clôture un compte bancaire.
    Le solde doit être à 0.
    """
    session = obtenir_session()
    compte = session.query(Compte).filter_by(id=id).first()
    
    if compte is None:
        flash('Compte introuvable.', 'danger')
        return redirect(url_for('clients.index'))
        
    if compte.solde != 0:
        flash('Impossible de clôturer un compte avec un solde positif. Veuillez tout retirer d\'abord.', 'danger')
        return redirect(url_for('accounts.view', id=id))
    
    # Récupérer la raison de clôture
    raison = request.form.get('raison', 'Demande client')
    
    # Extraire client_id avant de fermer la session
    client_id = compte.client_id
        
    try:
        compte.statut = StatutCompte.FERME
        log_action(g.user.id, "CLOTURE_COMPTE", f"Compte {compte.numero_compte}", 
                   {"raison": raison})
        session.commit()
        flash('Compte clôturé avec succès.', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Erreur : {e}', 'danger')
        
    return redirect(url_for('clients.view', id=client_id))


@accounts_bp.route('/<int:id>/reopen', methods=('POST',))
@permission_required('accounts.close')  # Same permission as closing
def reopen(id):
    """
    Réouvre un compte bancaire fermé.
    Permet à un administrateur de réactiver un compte clôturé.
    """
    session = obtenir_session()
    compte = session.query(Compte).filter_by(id=id).first()
    
    if compte is None:
        flash('Compte introuvable.', 'danger')
        return redirect(url_for('clients.index'))
    
    if compte.statut.value != 'ferme':
        flash('Ce compte n\'est pas fermé.', 'danger')
        return redirect(url_for('accounts.view', id=id))

    # VERIFICATION: Le client doit être actif pour réouvrir un compte
    titulaire_statut = compte.client.statut.value
    if titulaire_statut != 'actif':
        flash(f'Action impossible : le titulaire du compte est {titulaire_statut}.', 'danger')
        return redirect(url_for('accounts.view', id=id))
    
    # Récupérer la raison de réouverture
    raison = request.form.get('raison', 'Décision administrative')
    
    # Extraire compte_id avant de fermer la session
    compte_id = compte.id
        
    try:
        compte.statut = StatutCompte.ACTIF
        log_action(g.user.id, "REOUVERTURE_COMPTE", f"Compte {compte.numero_compte}", 
                   {"raison": raison})
        session.commit()
        flash('Compte réouvert avec succès.', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Erreur : {e}', 'danger')
        
    return redirect(url_for('accounts.view', id=compte_id))
