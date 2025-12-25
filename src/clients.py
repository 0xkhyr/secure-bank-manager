"""
clients.py - Gestion des clients

Ce module gère les routes pour :
- Lister les clients
- Créer un nouveau client
- Voir les détails d'un client
"""

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from src.auth import login_required, permission_required
from src.db import obtenir_session
from src.models import Client, Compte, StatutClient, StatutCompte
from src.audit_logger import log_action

clients_bp = Blueprint('clients', __name__, url_prefix='/clients')

@clients_bp.route('/')
@login_required
def index():
    """Affiche la liste des clients."""
    session = obtenir_session()
    clients = session.query(Client).all()
    nb_clients = len(clients)
    
    # Logger la consultation de la liste
    log_action(g.user.id, "CONSULTATION_LISTE_CLIENTS", "Clients",
               {"nb_clients": nb_clients})
    
    return render_template('clients/list.html', clients=clients)

@clients_bp.route('/nouveau', methods=('GET', 'POST'))
@permission_required('clients.create')
def create():
    """Crée un nouveau client."""
    if request.method == 'POST':
        nom = request.form['nom']
        prenom = request.form['prenom']
        cin = request.form['cin']
        telephone = request.form['telephone']
        email = request.form.get('email')
        adresse = request.form['adresse']
        
        session = obtenir_session()
        error = None

        if not nom or not prenom or not cin or not telephone:
            error = 'Les champs Nom, Prénom, CIN et Téléphone sont obligatoires.'
        elif session.query(Client).filter_by(cin=cin).first() is not None:
            error = f'Un client avec le CIN {cin} existe déjà.'

        if error is None:
            nouveau_client = Client(
                nom=nom,
                prenom=prenom,
                cin=cin,
                telephone=telephone,
                email=email,
                adresse=adresse
            )
            session.add(nouveau_client)
            session.commit()
            
            # Récupérer l'ID
            client_id = nouveau_client.id
            
            # Audit
            log_action(g.user.id, "CREATION_CLIENT", f"Client {client_id}", 
                       {"nom": nom, "prenom": prenom, "cin": cin})
            
            flash('Client créé avec succès !', 'success')
            return redirect(url_for('clients.view', id=client_id))

        flash(error, 'danger')

    return render_template('clients/create.html')

@clients_bp.route('/<int:id>')
@login_required
def view(id):
    """Affiche les détails d'un client et ses comptes."""
    session = obtenir_session()
    client = session.query(Client).filter_by(id=id).first()
    
    if client is None:
        flash('Client introuvable.', 'danger')
        return redirect(url_for('clients.index'))
        
    # Charger les comptes du client
    comptes = session.query(Compte).filter_by(client_id=id).all()
    nb_comptes = len(comptes)
    
    # Logger la consultation du client
    log_action(g.user.id, "CONSULTATION_CLIENT", f"Client {id}",
               {"client_id": id, "cin": client.cin, "nb_comptes": nb_comptes})
    
    return render_template('clients/view.html', client=client, comptes=comptes)

@clients_bp.route('/<int:id>/desactiver', methods=('POST',))
@permission_required('clients.delete') # Using delete permission for deactivation
def deactivate(id):
    """
    Désactive un client (Soft Delete / Archive).
    Vérifie que les comptes sont fermés.
    """
    session = obtenir_session()
    client = session.query(Client).filter_by(id=id).first()
    
    if client is None:
        flash('Client introuvable.', 'danger')
        return redirect(url_for('clients.index'))

    # Vérifier si tous les comptes sont fermés
    comptes_ouverts = [c for c in client.comptes if c.statut != StatutCompte.FERME]
    
    if comptes_ouverts:
        flash(f'Impossible de désactiver le client : il possède encore {len(comptes_ouverts)} comptes actifs.', 'danger')
        return redirect(url_for('clients.view', id=id))

    try:
        raison = request.form.get('raison', 'Désactivation demandée')
        nouveau_statut_str = request.form.get('statut', 'inactif').upper()
        
        try:
            nouveau_statut = StatutClient[nouveau_statut_str]
        except KeyError:
            nouveau_statut = StatutClient.INACTIF

        client.statut = nouveau_statut
        
        log_action(g.user.id, "DESACTIVATION_CLIENT", f"Client {id}", 
                   {"nouveau_statut": nouveau_statut.value, "raison": raison})
        
        session.commit()
        flash(f'Client passé au statut {nouveau_statut.value} avec succès.', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Erreur : {e}', 'danger')
        
    return redirect(url_for('clients.view', id=id))


@clients_bp.route('/<int:id>/reactiver', methods=('POST',))
@permission_required('clients.delete')
def reactivate(id):
    """Réactive un client désactivé."""
    session = obtenir_session()
    client = session.query(Client).filter_by(id=id).first()
    
    if client is None:
        flash('Client introuvable.', 'danger')
        return redirect(url_for('clients.index'))

    try:
        raison = request.form.get('raison', 'Réactivation administrative')
        client.statut = StatutClient.ACTIF
        log_action(g.user.id, "REACTIVATION_CLIENT", f"Client {id}", {"raison": raison})
        session.commit()
        flash('Client réactivé avec succès.', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Erreur : {e}', 'danger')
        
    return redirect(url_for('clients.view', id=id))
