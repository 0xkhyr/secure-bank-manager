"""
users.py - Gestion des utilisateurs

Ce module gère les routes pour :
- Lister les utilisateurs (selon les permissions)
- Créer un nouvel utilisateur
- Voir les détails d'un utilisateur
- Modifier un utilisateur
- Activer/Désactiver un utilisateur
- Réinitialiser le mot de passe

Hiérarchie des rôles :
- SUPERADMIN : Peut gérer tous les utilisateurs (Admin + Opérateur)
- ADMIN : Peut gérer uniquement les Opérateurs
- OPERATEUR : Aucun accès à la gestion des utilisateurs
"""

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, session as flask_session
)
from src.auth import login_required, permission_required
from src.db import obtenir_session
from src.models import Utilisateur, RoleUtilisateur, Journal
from src.audit_logger import log_action
from passlib.hash import bcrypt
from datetime import datetime, timedelta
from src.config import Config

users_bp = Blueprint('users', __name__, url_prefix='/users')


def can_manage_user(current_user, target_user):
    """
    Vérifie si l'utilisateur actuel peut gérer l'utilisateur cible.
    """
    if current_user.role == RoleUtilisateur.SUPERADMIN:
        return True
    
    if current_user.role == RoleUtilisateur.ADMIN:
        return target_user.role == RoleUtilisateur.OPERATEUR
    
    return False


def can_create_role(current_user, target_role):
    """
    Vérifie si l'utilisateur actuel peut créer un utilisateur avec le rôle cible.
    """
    if current_user.role == RoleUtilisateur.SUPERADMIN:
        return True
    
    if current_user.role == RoleUtilisateur.ADMIN:
        return target_role == RoleUtilisateur.OPERATEUR
    
    return False


def get_manageable_roles(current_user):
    """
    Retourne la liste des rôles que l'utilisateur actuel peut créer/gérer.
    """
    if current_user.role == RoleUtilisateur.SUPERADMIN:
        return [RoleUtilisateur.SUPERADMIN, RoleUtilisateur.ADMIN, RoleUtilisateur.OPERATEUR]
    
    if current_user.role == RoleUtilisateur.ADMIN:
        return [RoleUtilisateur.OPERATEUR]
    
    return []


@users_bp.route('/')
@login_required
def index():
    """Liste tous les utilisateurs selon les permissions."""
    if g.user.role == RoleUtilisateur.OPERATEUR:
        log_action(g.user.id, "ACCES_REFUSE", "Listing users", {"path": request.path})
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard'))
    
    session_db = obtenir_session()
    
    if g.user.role == RoleUtilisateur.SUPERADMIN:
        users = session_db.query(Utilisateur).order_by(Utilisateur.id).all()
    else:
        users = session_db.query(Utilisateur)\
            .filter_by(role=RoleUtilisateur.OPERATEUR)\
            .order_by(Utilisateur.id)\
            .all()
    
    nb_users = len(users)
    log_action(g.user.id, "CONSULTATION_LISTE_UTILISATEURS", "Utilisateurs",
               {"nb_utilisateurs": nb_users, "role_viewer": g.user.role.value})
    
    users_local = []
    for user in users:
        locked_by_name = None
        if user.verrouille_par_id:
            lb = session_db.query(Utilisateur).filter_by(id=user.verrouille_par_id).first()
            locked_by_name = lb.nom_utilisateur if lb else None

        user_dict = {
            'id': user.id,
            'nom_utilisateur': user.nom_utilisateur,
            'role': user.role,
            'is_active': user.is_active,
            'date_creation': user.date_creation + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS) if user.date_creation else None,
            'derniere_connexion': user.derniere_connexion + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS) if user.derniere_connexion else None,
            'verrouille_jusqu_a': user.verrouille_jusqu_a,
            'verrouille_raison': user.verrouille_raison,
            'verrouille_par_nom': locked_by_name
        }
        users_local.append(type('obj', (object,), user_dict)())
    
    return render_template('users/list.html', users=users_local)


@users_bp.route('/nouveau', methods=('GET', 'POST'))
@login_required
def create():
    """Crée un nouvel utilisateur."""
    if g.user.role == RoleUtilisateur.OPERATEUR:
        log_action(g.user.id, "ACCES_REFUSE", "Creating user", {"path": request.path})
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        nom_utilisateur = request.form['nom_utilisateur']
        mot_de_passe = request.form['mot_de_passe']
        role_str = request.form['role']
        error = None
        
        if not nom_utilisateur:
            error = 'Le nom d\'utilisateur est requis.'
        elif not mot_de_passe:
            error = 'Le mot de passe est requis.'
        elif len(mot_de_passe) < 6:
            error = 'Le mot de passe doit contenir au moins 6 caractères.'
        
        try:
            role = RoleUtilisateur(role_str)
            if not can_create_role(g.user, role):
                error = 'Vous n\'avez pas la permission de créer ce rôle.'
        except ValueError:
            error = 'Rôle invalide.'
        
        if error is None:
            session_db = obtenir_session()
            existing = session_db.query(Utilisateur).filter_by(nom_utilisateur=nom_utilisateur).first()
            if existing:
                error = f'L\'utilisateur {nom_utilisateur} existe déjà.'
            else:
                try:
                    new_user = Utilisateur(
                        nom_utilisateur=nom_utilisateur,
                        mot_de_passe_hash=bcrypt.hash(mot_de_passe),
                        role=role,
                        is_active=True
                    )
                    session_db.add(new_user)
                    session_db.commit()
                    log_action(g.user.id, "CREATION_UTILISATEUR", f"Utilisateur {nom_utilisateur}",
                               {"role": role.value, "user_id": new_user.id})
                    flash(f'Utilisateur {nom_utilisateur} créé avec succès !', 'success')
                    return redirect(url_for('users.index'))
                except Exception as e:
                    session_db.rollback()
                    error = f"Erreur lors de la création : {e}"
        
        if error:
            flash(error, 'danger')
    
    manageable_roles = get_manageable_roles(g.user)
    return render_template('users/create.html', manageable_roles=manageable_roles)


@users_bp.route('/<int:id>')
@login_required
def view(id):
    """Affiche les détails d'un utilisateur."""
    session_db = obtenir_session()
    user = session_db.query(Utilisateur).filter_by(id=id).first()
    
    if user is None:
        flash('Utilisateur introuvable.', 'danger')
        return redirect(url_for('users.index'))
    
    if not can_manage_user(g.user, user) and g.user.id != user.id:
        log_action(g.user.id, "ACCES_REFUSE", f"Viewing user {user.nom_utilisateur}", {"target_user_id": id})
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard'))
    
    nb_actions = session_db.query(Journal).filter_by(utilisateur_id=user.id).count()
    log_action(g.user.id, "CONSULTATION_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
               {"user_id": id, "username": user.nom_utilisateur, "role": user.role.value})
    
    locked_by_user = None
    if user.verrouille_par_id:
        locked_by_user = session_db.query(Utilisateur).filter_by(id=user.verrouille_par_id).first()
    
    user_local = type('obj', (object,), {
        'id': user.id,
        'nom_utilisateur': user.nom_utilisateur,
        'role': user.role,
        'is_active': user.is_active,
        'date_creation': user.date_creation + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS) if user.date_creation else None,
        'derniere_connexion': user.derniere_connexion + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS) if user.derniere_connexion else None,
        'verrouille_jusqu_a': user.verrouille_jusqu_a,
        'verrouille_raison': user.verrouille_raison,
        'verrouille_le': user.verrouille_le + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS) if user.verrouille_le else None,
        'tentatives_connexion': user.tentatives_connexion
    })()
    
    lock_time_local = None
    locked_by_name = None
    if user.verrouille_jusqu_a:
        lock_time_local = user.verrouille_jusqu_a + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS)
    if locked_by_user:
        locked_by_name = locked_by_user.nom_utilisateur
    
    return render_template('users/view.html', user=user_local, nb_actions=nb_actions, 
                            now=datetime.utcnow(), lock_time_local=lock_time_local,
                            locked_by_name=locked_by_name)


@users_bp.route('/<int:id>/modifier', methods=('GET', 'POST'))
@login_required
def edit(id):
    """Modifie un utilisateur."""
    session_db = obtenir_session()
    user = session_db.query(Utilisateur).filter_by(id=id).first()
    
    if user is None:
        flash('Utilisateur introuvable.', 'danger')
        return redirect(url_for('users.index'))
    
    if not can_manage_user(g.user, user):
        log_action(g.user.id, "ACCES_REFUSE", f"Action on user {user.nom_utilisateur}", {"target_user_id": id, "path": request.path})
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        nom_utilisateur = request.form['nom_utilisateur']
        role_str = request.form.get('role')
        error = None
        
        if not nom_utilisateur:
            error = 'Le nom d\'utilisateur est requis.'
        
        if role_str:
            try:
                new_role = RoleUtilisateur(role_str)
                if new_role != user.role:
                    if user.id == g.user.id:
                        error = 'Vous ne pouvez pas changer votre propre rôle.'
                    elif not can_create_role(g.user, new_role):
                        error = 'Vous n\'avez pas la permission d\'assigner ce rôle.'
            except ValueError:
                error = 'Rôle invalide.'
        
        if error is None:
            try:
                user.nom_utilisateur = nom_utilisateur
                if role_str:
                    new_role = RoleUtilisateur(role_str)
                    if new_role != user.role:
                        old_role = user.role.value
                        user.role = new_role
                        log_action(g.user.id, "MODIFICATION_ROLE_UTILISATEUR",
                                   f"Utilisateur {user.nom_utilisateur}",
                                   {"ancien_role": old_role, "nouveau_role": new_role.value})
                
                session_db.commit()
                log_action(g.user.id, "MODIFICATION_UTILISATEUR",
                           f"Utilisateur {user.nom_utilisateur}", {})
                flash(f'Utilisateur {nom_utilisateur} modifié avec succès !', 'success')
                return redirect(url_for('users.view', id=id))
            except Exception as e:
                session_db.rollback()
                error = f"Erreur lors de la modification : {e}"
        
        if error:
            flash(error, 'danger')
    
    manageable_roles = get_manageable_roles(g.user)
    return render_template('users/edit.html', user=user, manageable_roles=manageable_roles)


@users_bp.route('/<int:id>/toggle-active', methods=('POST',))
@login_required
def toggle_active(id):
    """Active ou désactive un utilisateur."""
    session_db = obtenir_session()
    user = session_db.query(Utilisateur).filter_by(id=id).first()
    
    if user is None:
        flash('Utilisateur introuvable.', 'danger')
        return redirect(url_for('users.index'))
    
    if not can_manage_user(g.user, user):
        log_action(g.user.id, "ACCES_REFUSE", f"Action on user {user.nom_utilisateur}", {"target_user_id": id, "path": request.path})
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard'))
    
    if user.id == g.user.id:
        flash('Vous ne pouvez pas vous désactiver vous-même.', 'danger')
        return redirect(url_for('users.view', id=id))
    
    try:
        user.is_active = not user.is_active
        session_db.commit()
        action = "ACTIVATION_UTILISATEUR" if user.is_active else "DESACTIVATION_UTILISATEUR"
        log_action(g.user.id, action, f"Utilisateur {user.nom_utilisateur}", {})
        status = "activé" if user.is_active else "désactivé"
        flash(f'Utilisateur {user.nom_utilisateur} {status} avec succès !', 'success')
    except Exception as e:
        session_db.rollback()
        flash(f"Erreur : {e}", 'danger')
    
    return redirect(url_for('users.view', id=id))


@users_bp.route('/<int:id>/reset-password', methods=('POST',))
@login_required
def reset_password(id):
    """Réinitialise le mot de passe d'un utilisateur."""
    session_db = obtenir_session()
    user = session_db.query(Utilisateur).filter_by(id=id).first()
    
    if user is None:
        flash('Utilisateur introuvable.', 'danger')
        return redirect(url_for('users.index'))
    
    if not can_manage_user(g.user, user):
        log_action(g.user.id, "ACCES_REFUSE", f"Action on user {user.nom_utilisateur}", {"target_user_id": id, "path": request.path})
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard'))
    
    new_password = request.form.get('new_password')
    if not new_password or len(new_password) < 6:
        flash('Le mot de passe doit contenir au moins 6 caractères.', 'danger')
    else:
        try:
            user.mot_de_passe_hash = bcrypt.hash(new_password)
            session_db.commit()
            log_action(g.user.id, "RESET_PASSWORD_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}", {})
            flash(f'Mot de passe de {user.nom_utilisateur} réinitialisé avec succès !', 'success')
        except Exception as e:
            session_db.rollback()
            flash(f"Erreur : {e}", 'danger')
    
    return redirect(url_for('users.view', id=id))


@users_bp.route('/<int:id>/lock', methods=('POST',))
@login_required
def lock_account(id):
    """Verrouille manuellement un compte utilisateur."""
    session_db = obtenir_session()
    user = session_db.query(Utilisateur).filter_by(id=id).first()
    
    if user is None:
        flash('Utilisateur introuvable.', 'danger')
        return redirect(url_for('users.index'))
    
    if not can_manage_user(g.user, user):
        log_action(g.user.id, "ACCES_REFUSE", f"Action on user {user.nom_utilisateur}", {"target_user_id": id, "path": request.path})
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard'))
    
    if user.id == g.user.id:
        flash('Vous ne pouvez pas vous verrouiller vous-même.', 'danger')
        return redirect(url_for('users.view', id=id))
    
    duration_minutes = request.form.get('duration_minutes', type=int)
    raison = request.form.get('raison', 'Verrouillage manuel')
    
    if not duration_minutes or duration_minutes <= 0:
        flash('Durée de verrouillage invalide.', 'danger')
    else:
        try:
            now_utc = datetime.utcnow()
            user.verrouille_jusqu_a = now_utc + timedelta(minutes=duration_minutes)
            user.verrouille_raison = raison
            user.verrouille_par_id = g.user.id
            user.verrouille_le = now_utc
            session_db.commit()
            log_action(g.user.id, "VERROUILLAGE_MANUEL_UTILISATEUR",
                       f"Utilisateur {user.nom_utilisateur}",
                       {"duree_minutes": duration_minutes, "jusqu_a": user.verrouille_jusqu_a.isoformat(), "raison": raison})
            
            unlock_local = user.verrouille_jusqu_a + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS)
            flash(f"Utilisateur {user.nom_utilisateur} verrouillé jusqu'au {unlock_local.strftime('%d/%m/%Y %H:%M')}.", 'success')
        except Exception as e:
            session_db.rollback()
            flash(f"Erreur : {e}", 'danger')
    
    return redirect(url_for('users.view', id=id))


@users_bp.route('/<int:id>/unlock', methods=('POST',))
@login_required
def unlock_account(id):
    """Déverrouille manuellement un compte utilisateur."""
    session_db = obtenir_session()
    user = session_db.query(Utilisateur).filter_by(id=id).first()
    
    if user is None:
        flash('Utilisateur introuvable.', 'danger')
        return redirect(url_for('users.index'))
    
    if not can_manage_user(g.user, user):
        log_action(g.user.id, "ACCES_REFUSE", f"Action on user {user.nom_utilisateur}", {"target_user_id": id, "path": request.path})
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard'))
    
    if user.verrouille_jusqu_a is None:
        flash('Le compte n\'est pas verrouillé.', 'danger')
        return redirect(url_for('users.view', id=id))
    
    try:
        was_locked_until = user.verrouille_jusqu_a.isoformat()
        user.verrouille_jusqu_a = None
        user.verrouille_raison = None
        user.verrouille_par_id = None
        user.verrouille_le = None
        user.tentatives_connexion = 0
        session_db.commit()
        log_action(g.user.id, "DEVERROUILLAGE_MANUEL_UTILISATEUR",
                   f"Utilisateur {user.nom_utilisateur}",
                   {"etait_verrouille_jusqu_a": was_locked_until})
        flash(f'Utilisateur {user.nom_utilisateur} déverrouillé avec succès !', 'success')
    except Exception as e:
        session_db.rollback()
        flash(f"Erreur : {e}", 'danger')
    
    return redirect(url_for('users.view', id=id))


@users_bp.route('/profile', methods=('GET','POST'))
@login_required
def profile():
    """Profil de l'utilisateur connecté."""
    session_db = obtenir_session()
    user = session_db.query(Utilisateur).filter_by(id=g.user.id).first()
    
    if user is None:
        flash('Utilisateur introuvable.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_profile':
            new_display = request.form.get('display_name', '').strip()
            if len(new_display) > 100:
                flash('Le nom affiché est trop long.', 'danger')
            else:
                user.display_name = new_display or None
                session_db.commit()
                flash('Profil mis à jour.', 'success')
        elif action == 'change_password':
            current = request.form.get('current_password', '')
            new = request.form.get('new_password', '')
            confirm = request.form.get('confirm_password', '')
            if not bcrypt.verify(current, user.mot_de_passe_hash):
                flash('Mot de passe actuel incorrect.', 'danger')
            elif len(new) < 6:
                flash('Le nouveau mot de passe doit contenir au moins 6 caractères.', 'danger')
            elif new != confirm:
                flash('Les nouveaux mots de passe ne correspondent pas.', 'danger')
            else:
                user.mot_de_passe_hash = bcrypt.hash(new)
                session_db.commit()
                flash('Mot de passe modifié avec succès.', 'success')

    user_local = type('obj',(object,),{
        'id': user.id,
        'nom_utilisateur': user.nom_utilisateur,
        'display_name': user.display_name,
        'date_creation': user.date_creation + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS) if user.date_creation else None,
        'derniere_connexion': user.derniere_connexion + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS) if user.derniere_connexion else None
    })()
    
    return render_template('users/profile.html', user=user_local)
