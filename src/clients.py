"""
# Gestion du Référentiel Clients (KYC)
# Règle métier : Ce module gère l'enrôlement et la consultation des données clients.
# Sécurité : Chaque action est tracée en audit pour garantir la conformité aux exigences bancaires.
"""

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from src.auth import login_required, permission_required, has_permission
from src.db import obtenir_session
from src.models import Client, Compte, StatutClient, StatutCompte
from src.audit_logger import log_action

clients_bp = Blueprint('clients', __name__, url_prefix='/clients')

@clients_bp.route('/')
@login_required
def index():
    """
    # Règle métier : Indexation et recherche des clients du portefeuille.
    # Audit : Trace la consultation de la liste des clients pour surveillance des accès.
    """
    session = obtenir_session()
    clients = session.query(Client).all()
    nb_clients = len(clients)
    
    log_action(g.user.id, "CONSULTATION_LISTE_CLIENTS", "Clients",
               {"nb_clients": nb_clients})
    
    return render_template('clients/list.html', clients=clients)

@clients_bp.route('/nouveau', methods=('GET', 'POST'))
@permission_required('clients.create')
def create():
    """
    # Règle métier : Procédure d'entrée en relation (KYC).
    # Sécurité : Vérifie l'unicité du CIN pour prévenir la fraude d'identité.
    """
    if request.method == 'POST':
        nom = request.form['nom']
        prenom = request.form['prenom']
        cin = request.form['cin']
        telephone = request.form['telephone']
        email = request.form.get('email')
        adresse = request.form['adresse']
        
        session = obtenir_session()
        error = None

        # Règle métier : validation des champs obligatoires pour la conformité.
        if not nom or not prenom or not cin or not telephone:
            error = 'Les champs Nom, Prénom, CIN et Téléphone sont obligatoires.'
        elif session.query(Client).filter_by(cin=cin).first() is not None:
            # Sécurité : Détection de tentative de doublon d'identité.
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
            
            client_id = nouveau_client.id
            
            # Audit : Enregistrement de la création avec les attributs d'identité.
            log_action(g.user.id, "CREATION_CLIENT", f"Client {client_id}", 
                       {"nom": nom, "prenom": prenom, "cin": cin})
            
            flash('Client créé avec succès !', 'success')
            return redirect(url_for('clients.view', id=client_id))

        flash(error, 'danger')

    return render_template('clients/create.html')

@clients_bp.route('/<int:id>')
@login_required
def view(id):
    """
    # Règle métier : Consultation de la fiche 360° du client et son état de conformité.
    # Audit : Enregistre l'identité du client consulté à des fins de reporting.
    """
    session = obtenir_session()
    client = session.query(Client).filter_by(id=id).first()
    
    if client is None:
        flash('Client introuvable.', 'danger')
        return redirect(url_for('clients.index'))
        
    comptes = session.query(Compte).filter_by(client_id=id).all()
    nb_comptes = len(comptes)
    
    log_action(g.user.id, "CONSULTATION_CLIENT", f"Client {id}",
               {"client_id": id, "cin": client.cin, "nb_comptes": nb_comptes})
    
    return render_template('clients/view.html', client=client, comptes=comptes)

@clients_bp.route('/<int:id>/desactiver', methods=('POST',))
@permission_required('clients.deactivate')
def deactivate(id):
    """
    Change le statut d'un client (suspendre / désactiver / archiver).
    Vérifie que les comptes sont fermés pour les statuts qui l'exigent.
    """
    session = obtenir_session()
    client = session.query(Client).filter_by(id=id).first()

    if client is None:
        flash('Client introuvable.', 'danger')
        return redirect(url_for('clients.index'))

    # Vérifier si tous les comptes sont fermés (pour désactivation / archivage)
    comptes_ouverts = [c for c in client.comptes if c.statut != StatutCompte.FERME]
    if comptes_ouverts:
        flash(f'Impossible de changer le statut : le client possède encore {len(comptes_ouverts)} comptes actifs.', 'danger')
        return redirect(url_for('clients.view', id=id))

    try:
        raison = request.form.get('raison', 'Désactivation demandée')
        nouveau_statut_str = request.form.get('statut', 'inactif').upper()

        try:
            nouveau_statut = StatutClient[nouveau_statut_str]
        except KeyError:
            nouveau_statut = StatutClient.INACTIF

        # Fine-grained permission checks depending on requested status
        if nouveau_statut == StatutClient.SUSPENDU and not has_permission(g.user, 'clients.suspend'):
            try:
                log_action(g.user.id if g.user else None, 'ACCES_REFUSE', f"Action on client {client.cin}", {"target_client_id": id, "attempted": "suspend", "path": request.path})
            except Exception:
                pass
            flash('Accès refusé : permission insuffisante pour suspendre un client.', 'danger')
            return redirect(url_for('clients.view', id=id))

        if nouveau_statut == StatutClient.ARCHIVE and not has_permission(g.user, 'clients.archive'):
            try:
                log_action(g.user.id if g.user else None, 'ACCES_REFUSE', f"Action on client {client.cin}", {"target_client_id": id, "attempted": "archive", "path": request.path})
            except Exception:
                pass
            flash('Accès refusé : permission insuffisante pour archiver un client.', 'danger')
            return redirect(url_for('clients.view', id=id))

        # 'inactif' or other deactivations require deactivation permission
        if nouveau_statut == StatutClient.INACTIF and not has_permission(g.user, 'clients.deactivate'):
            try:
                log_action(g.user.id if g.user else None, 'ACCES_REFUSE', f"Action on client {client.cin}", {"target_client_id": id, "attempted": "deactivate", "path": request.path})
            except Exception:
                pass
            flash('Accès refusé : permission insuffisante pour désactiver un client.', 'danger')
            return redirect(url_for('clients.view', id=id))

        client.statut = nouveau_statut
        log_action(g.user.id, "DESACTIVATION_CLIENT", f"Client {id}", {"nouveau_statut": nouveau_statut.value, "raison": raison})
        session.commit()
        flash(f'Client passé au statut {nouveau_statut.value} avec succès.', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Erreur : {e}', 'danger')

    return redirect(url_for('clients.view', id=id))


@clients_bp.route('/<int:id>/reactiver', methods=('POST',))
@permission_required('clients.reactivate')
def reactivate(id):
    """Réactive un client désactivé."""
    session = obtenir_session()
    client = session.query(Client).filter_by(id=id).first()

    if client is None:
        flash('Client introuvable.', 'danger')
        return redirect(url_for('clients.index'))

    # Permission check (redundant with decorator but explicit for clarity)
    if not has_permission(g.user, 'clients.reactivate'):
        try:
            log_action(g.user.id if g.user else None, 'ACCES_REFUSE', f"Action on client {client.cin}", {"target_client_id": id, "attempted": "reactivate", "path": request.path})
        except Exception:
            pass
        flash('Accès refusé : permission insuffisante pour réactiver un client.', 'danger')
        return redirect(url_for('clients.view', id=id))

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
