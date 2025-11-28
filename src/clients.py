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
from src.models import Client, Compte
from src.audit_logger import log_action

clients_bp = Blueprint('clients', __name__, url_prefix='/clients')

@clients_bp.route('/')
@login_required
def index():
    """Affiche la liste des clients."""
    session = obtenir_session()
    clients = session.query(Client).all()
    session.close()
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
            
            # Récupérer l'ID avant de fermer la session
            client_id = nouveau_client.id
            
            # Audit
            log_action(g.user.id, "CREATION_CLIENT", f"Client {client_id}", 
                       {"nom": nom, "prenom": prenom, "cin": cin})
            
            session.close()
            flash('Client créé avec succès !', 'success')
            return redirect(url_for('clients.view', id=client_id))

        session.close()
        flash(error, 'danger')

    return render_template('clients/create.html')

@clients_bp.route('/<int:id>')
@login_required
def view(id):
    """Affiche les détails d'un client et ses comptes."""
    session = obtenir_session()
    client = session.query(Client).filter_by(id=id).first()
    
    if client is None:
        session.close()
        flash('Client introuvable.', 'danger')
        return redirect(url_for('clients.index'))
        
    # Charger les comptes du client
    comptes = session.query(Compte).filter_by(client_id=id).all()
    session.close()
    
    return render_template('clients/view.html', client=client, comptes=comptes)
