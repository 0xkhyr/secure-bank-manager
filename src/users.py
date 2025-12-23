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
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from src.auth import login_required, permission_required
from src.db import obtenir_session
from src.models import Utilisateur, RoleUtilisateur
from src.audit_logger import log_action
from passlib.hash import bcrypt

users_bp = Blueprint('users', __name__, url_prefix='/users')


def can_manage_user(current_user, target_user):
    """
    Vérifie si l'utilisateur actuel peut gérer l'utilisateur cible.
    
    Règles :
    - SUPERADMIN peut gérer tout le monde
    - ADMIN peut gérer uniquement OPERATEUR
    - OPERATEUR ne peut gérer personne
    - Personne ne peut se gérer soi-même pour certaines actions (changement de rôle, désactivation)
    
    Args:
        current_user: L'utilisateur actuellement connecté
        target_user: L'utilisateur à gérer
        
    Returns:
        bool: True si l'action est autorisée, False sinon
    """
    # SuperAdmin peut tout faire
    if current_user.role == RoleUtilisateur.SUPERADMIN:
        return True
    
    # Admin peut gérer uniquement les Opérateurs
    if current_user.role == RoleUtilisateur.ADMIN:
        return target_user.role == RoleUtilisateur.OPERATEUR
    
    # Opérateur ne peut rien gérer
    return False


def can_create_role(current_user, target_role):
    """
    Vérifie si l'utilisateur actuel peut créer un utilisateur avec le rôle cible.
    
    Règles :
    - SUPERADMIN peut créer n'importe quel rôle
    - ADMIN peut créer uniquement OPERATEUR
    - OPERATEUR ne peut rien créer
    
    Args:
        current_user: L'utilisateur actuellement connecté
        target_role: Le rôle à assigner au nouvel utilisateur
        
    Returns:
        bool: True si l'action est autorisée, False sinon
    """
    if current_user.role == RoleUtilisateur.SUPERADMIN:
        return True
    
    if current_user.role == RoleUtilisateur.ADMIN:
        return target_role == RoleUtilisateur.OPERATEUR
    
    return False


def get_manageable_roles(current_user):
    """
    Retourne la liste des rôles que l'utilisateur actuel peut créer/gérer.
    
    Args:
        current_user: L'utilisateur actuellement connecté
        
    Returns:
        list: Liste des rôles gérables
    """
    if current_user.role == RoleUtilisateur.SUPERADMIN:
        return [RoleUtilisateur.SUPERADMIN, RoleUtilisateur.ADMIN, RoleUtilisateur.OPERATEUR]
    
    if current_user.role == RoleUtilisateur.ADMIN:
        return [RoleUtilisateur.OPERATEUR]
    
    return []


@users_bp.route('/')
@login_required
def index():
    """
    Liste tous les utilisateurs selon les permissions.
    - SUPERADMIN voit tous les utilisateurs
    - ADMIN voit uniquement les OPERATEUR
    - OPERATEUR est redirigé (pas d'accès)
    """
    # Vérifier les permissions
    if g.user.role == RoleUtilisateur.OPERATEUR:
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard'))
    
    session = obtenir_session()
    
    # Filtrer selon le rôle
    if g.user.role == RoleUtilisateur.SUPERADMIN:
        # SuperAdmin voit tout
        users = session.query(Utilisateur).order_by(Utilisateur.id).all()
    else:
        # Admin voit uniquement les Opérateurs
        users = session.query(Utilisateur)\
            .filter_by(role=RoleUtilisateur.OPERATEUR)\
            .order_by(Utilisateur.id)\
            .all()
    
    nb_users = len(users)
    
    # Logger la consultation de la liste des utilisateurs
    log_action(g.user.id, "CONSULTATION_LISTE_UTILISATEURS", "Utilisateurs",
               {"nb_utilisateurs": nb_users, "role_viewer": g.user.role.value})
    
    # Convert UTC times to local for display
    from datetime import timedelta
    from src.config import Config
    users_local = []
    for user in users:
        locked_by_name = None
        if user.verrouille_par_id:
            lb = session.query(Utilisateur).filter_by(id=user.verrouille_par_id).first()
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
    
    result = render_template('users/list.html', users=users_local)
    session.close()
    return result


@users_bp.route('/nouveau', methods=('GET', 'POST'))
@login_required
def create():
    """Crée un nouvel utilisateur."""
    # Vérifier les permissions
    if g.user.role == RoleUtilisateur.OPERATEUR:
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        nom_utilisateur = request.form['nom_utilisateur']
        mot_de_passe = request.form['mot_de_passe']
        role_str = request.form['role']
        error = None
        
        # Validation
        if not nom_utilisateur:
            error = 'Le nom d\'utilisateur est requis.'
            log_action(g.user.id, "ECHEC_CREATION_UTILISATEUR", "Utilisateur",
                       {"raison": "nom_utilisateur_vide"})
        elif not mot_de_passe:
            error = 'Le mot de passe est requis.'
            log_action(g.user.id, "ECHEC_CREATION_UTILISATEUR", "Utilisateur",
                       {"raison": "mot_de_passe_vide", "nom_utilisateur": nom_utilisateur, "user_id": None})
        elif len(mot_de_passe) < 6:
            error = 'Le mot de passe doit contenir au moins 6 caractères.'
            log_action(g.user.id, "ECHEC_CREATION_UTILISATEUR", "Utilisateur",
                       {"raison": "mot_de_passe_faible", "nom_utilisateur": nom_utilisateur, "longueur": len(mot_de_passe), "user_id": None})
        
        # Vérifier le rôle
        try:
            role = RoleUtilisateur(role_str)
            if not can_create_role(g.user, role):
                error = 'Vous n\'avez pas la permission de créer ce rôle.'
                log_action(g.user.id, "ECHEC_CREATION_UTILISATEUR", "Utilisateur",
                           {"raison": "role_non_autorise", "nom_utilisateur": nom_utilisateur, 
                            "role_demande": role_str, "role_actuel": g.user.role.value, "user_id": None})
        except ValueError:
            error = 'Rôle invalide.'
            log_action(g.user.id, "ECHEC_CREATION_UTILISATEUR", "Utilisateur",
                       {"raison": "role_invalide", "nom_utilisateur": nom_utilisateur, "role_demande": role_str, "user_id": None})
        
        if error is None:
            session = obtenir_session()
            
            # Vérifier si l'utilisateur existe déjà
            existing = session.query(Utilisateur).filter_by(nom_utilisateur=nom_utilisateur).first()
            if existing:
                error = f'L\'utilisateur {nom_utilisateur} existe déjà.'
                log_action(g.user.id, "ECHEC_CREATION_UTILISATEUR", "Utilisateur",
                           {"raison": "nom_utilisateur_deja_existant", "nom_utilisateur": nom_utilisateur, "user_id": existing.id})
            else:
                try:
                    # Créer l'utilisateur
                    new_user = Utilisateur(
                        nom_utilisateur=nom_utilisateur,
                        mot_de_passe_hash=bcrypt.hash(mot_de_passe),
                        role=role,
                        is_active=True
                    )
                    session.add(new_user)
                    session.commit()
                    
                    # Audit
                    log_action(g.user.id, "CREATION_UTILISATEUR", f"Utilisateur {nom_utilisateur}",
                               {"role": role.value, "user_id": new_user.id})
                    
                    flash(f'Utilisateur {nom_utilisateur} créé avec succès !', 'success')
                    session.close()
                    return redirect(url_for('users.index'))
                    
                except Exception as e:
                    session.rollback()
                    log_action(g.user.id, "ECHEC_CREATION_UTILISATEUR", "Utilisateur",
                               {"raison": "exception_systeme", "nom_utilisateur": nom_utilisateur, "erreur": str(e), "user_id": None})
                    error = f"Erreur lors de la création : {e}"
            
            session.close()
        
        if error:
            flash(error, 'danger')
    
    # Rendre le formulaire
    manageable_roles = get_manageable_roles(g.user)
    return render_template('users/create.html', manageable_roles=manageable_roles)


@users_bp.route('/<int:id>')
@login_required
def view(id):
    """Affiche les détails d'un utilisateur."""
    session = obtenir_session()
    user = session.query(Utilisateur).filter_by(id=id).first()
    
    if user is None:
        session.close()
        flash('Utilisateur introuvable.', 'danger')
        return redirect(url_for('users.index'))
    
    # Vérifier les permissions
    if not can_manage_user(g.user, user) and g.user.id != user.id:
        session.close()
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Compter les actions de l'utilisateur
    from src.models import Journal
    from datetime import datetime, timedelta
    from src.config import Config
    nb_actions = session.query(Journal).filter_by(utilisateur_id=user.id).count()
    
    # Logger la consultation de l'utilisateur
    log_action(g.user.id, "CONSULTATION_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
               {"user_id": id, "username": user.nom_utilisateur, "role": user.role.value})
    
    # Get lock metadata
    locked_by_user = None
    if user.verrouille_par_id:
        locked_by_user = session.query(Utilisateur).filter_by(id=user.verrouille_par_id).first()
    
    # Convert UTC times to local for display
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
        'tentatives_echouees': user.tentatives_echouees
    })()
    
    # Convert lock time to local timezone for display
    lock_time_local = None
    locked_by_name = None
    if user.verrouille_jusqu_a:
        lock_time_local = user.verrouille_jusqu_a + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS)
    if locked_by_user:
        locked_by_name = locked_by_user.nom_utilisateur
    
    result = render_template('users/view.html', user=user_local, nb_actions=nb_actions, 
                            now=datetime.utcnow(), lock_time_local=lock_time_local,
                            locked_by_name=locked_by_name)
    session.close()
    return result


@users_bp.route('/<int:id>/modifier', methods=('GET', 'POST'))
@login_required
def edit(id):
    # existing edit route continues (no change)
    
    """Modifie un utilisateur."""
    session = obtenir_session()
    user = session.query(Utilisateur).filter_by(id=id).first()
    
    if user is None:
        session.close()
        flash('Utilisateur introuvable.', 'danger')
        return redirect(url_for('users.index'))
    
    # Vérifier les permissions
    if not can_manage_user(g.user, user):
        session.close()
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        nom_utilisateur = request.form['nom_utilisateur']
        role_str = request.form.get('role')
        error = None
        
        if not nom_utilisateur:
            error = 'Le nom d\'utilisateur est requis.'
            log_action(g.user.id, "ECHEC_MODIFICATION_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                       {"raison": "nom_utilisateur_vide", "user_id": id})
        
        # Vérifier le changement de rôle
        if role_str:
            try:
                new_role = RoleUtilisateur(role_str)
                if new_role != user.role:
                    # Empêcher l'auto-changement de rôle
                    if user.id == g.user.id:
                        error = 'Vous ne pouvez pas changer votre propre rôle.'
                        log_action(g.user.id, "ECHEC_MODIFICATION_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                                   {"raison": "auto_modification_role", "role_actuel": user.role.value, "role_demande": role_str})
                    elif not can_create_role(g.user, new_role):
                        error = 'Vous n\'avez pas la permission d\'assigner ce rôle.'
                        log_action(g.user.id, "ECHEC_MODIFICATION_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                                   {"raison": "role_non_autorise", "user_id": id, "role_demande": role_str, "role_actuel_operateur": g.user.role.value})
            except ValueError:
                error = 'Rôle invalide.'
                log_action(g.user.id, "ECHEC_MODIFICATION_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                           {"raison": "role_invalide", "user_id": id, "role_demande": role_str})
        
        if error is None:
            try:
                # Mettre à jour
                user.nom_utilisateur = nom_utilisateur
                if role_str:
                    new_role = RoleUtilisateur(role_str)
                    if new_role != user.role:
                        old_role = user.role.value
                        user.role = new_role
                        log_action(g.user.id, "MODIFICATION_ROLE_UTILISATEUR",
                                   f"Utilisateur {user.nom_utilisateur}",
                                   {"ancien_role": old_role, "nouveau_role": new_role.value})
                
                session.commit()
                log_action(g.user.id, "MODIFICATION_UTILISATEUR",
                           f"Utilisateur {user.nom_utilisateur}", {})
                
                flash(f'Utilisateur {nom_utilisateur} modifié avec succès !', 'success')
                session.close()
                return redirect(url_for('users.view', id=id))
                
            except Exception as e:
                session.rollback()
                log_action(g.user.id, "ECHEC_MODIFICATION_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                           {"raison": "exception_systeme", "user_id": id, "erreur": str(e)})
                error = f"Erreur lors de la modification : {e}"
        
        if error:
            flash(error, 'danger')
    
    manageable_roles = get_manageable_roles(g.user)
    result = render_template('users/edit.html', user=user, manageable_roles=manageable_roles)
    session.close()
    return result


@users_bp.route('/<int:id>/toggle-active', methods=('POST',))
@login_required
def toggle_active(id):
    """Active ou désactive un utilisateur."""
    session = obtenir_session()
    user = session.query(Utilisateur).filter_by(id=id).first()
    
    if user is None:
        session.close()
        flash('Utilisateur introuvable.', 'danger')
        return redirect(url_for('users.index'))
    
    # Vérifier les permissions
    if not can_manage_user(g.user, user):
        log_action(g.user.id, "ECHEC_ACTIVATION_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                   {"raison": "permission_refusee", "user_id": id, "role_cible": user.role.value})
        session.close()
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Empêcher l'auto-désactivation
    if user.id == g.user.id:
        log_action(g.user.id, "ECHEC_ACTIVATION_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                   {"raison": "auto_desactivation", "user_id": id})
        session.close()
        flash('Vous ne pouvez pas vous désactiver vous-même.', 'danger')
        return redirect(url_for('users.view', id=id))
    
    try:
        user.is_active = not user.is_active
        session.commit()
        
        action = "ACTIVATION_UTILISATEUR" if user.is_active else "DESACTIVATION_UTILISATEUR"
        log_action(g.user.id, action, f"Utilisateur {user.nom_utilisateur}", {})
        
        status = "activé" if user.is_active else "désactivé"
        flash(f'Utilisateur {user.nom_utilisateur} {status} avec succès !', 'success')
        
    except Exception as e:
        session.rollback()
        log_action(g.user.id, "ECHEC_ACTIVATION_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                   {"raison": "exception_systeme", "user_id": id, "erreur": str(e)})
        flash(f"Erreur : {e}", 'danger')
    
    session.close()
    return redirect(url_for('users.view', id=id))


@users_bp.route('/<int:id>/reset-password', methods=('POST',))
@login_required
def reset_password(id):
    """Réinitialise le mot de passe d'un utilisateur."""
    session = obtenir_session()
    user = session.query(Utilisateur).filter_by(id=id).first()
    
    if user is None:
        session.close()
        flash('Utilisateur introuvable.', 'danger')
        return redirect(url_for('users.index'))
    
    # Vérifier les permissions
    if not can_manage_user(g.user, user):
        log_action(g.user.id, "ECHEC_RESET_PASSWORD_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                   {"raison": "permission_refusee", "user_id": id, "role_cible": user.role.value})
        session.close()
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard'))
    
    new_password = request.form.get('new_password')
    
    if not new_password or len(new_password) < 6:
        log_action(g.user.id, "ECHEC_RESET_PASSWORD_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                   {"raison": "mot_de_passe_faible", "user_id": id, "longueur": len(new_password) if new_password else 0})
        flash('Le mot de passe doit contenir au moins 6 caractères.', 'danger')
    else:
        try:
            user.mot_de_passe_hash = bcrypt.hash(new_password)
            session.commit()
            
            log_action(g.user.id, "RESET_PASSWORD_UTILISATEUR",
                       f"Utilisateur {user.nom_utilisateur}", {})
            
            flash(f'Mot de passe de {user.nom_utilisateur} réinitialisé avec succès !', 'success')
            
        except Exception as e:
            session.rollback()
            log_action(g.user.id, "ECHEC_RESET_PASSWORD_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                       {"raison": "exception_systeme", "user_id": id, "erreur": str(e)})
            flash(f"Erreur : {e}", 'danger')
    
    session.close()
    return redirect(url_for('users.view', id=id))


@users_bp.route('/<int:id>/lock', methods=('POST',))
@login_required
def lock_account(id):
    """Verrouille manuellement un compte utilisateur pour une durée spécifique."""
    session = obtenir_session()
    user = session.query(Utilisateur).filter_by(id=id).first()
    
    if user is None:
        session.close()
        flash('Utilisateur introuvable.', 'danger')
        return redirect(url_for('users.index'))
    
    # Vérifier les permissions
    if not can_manage_user(g.user, user):
        log_action(g.user.id, "ECHEC_VERROUILLAGE_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                   {"raison": "permission_refusee", "user_id": id, "role_cible": user.role.value})
        session.close()
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Empêcher l'auto-verrouillage
    if user.id == g.user.id:
        log_action(g.user.id, "ECHEC_VERROUILLAGE_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                   {"raison": "auto_verrouillage", "user_id": id})
        session.close()
        flash('Vous ne pouvez pas vous verrouiller vous-même.', 'danger')
        return redirect(url_for('users.view', id=id))
    
    # Récupérer la durée de verrouillage
    duration_minutes = request.form.get('duration_minutes', type=int)
    raison = request.form.get('raison', 'Verrouillage manuel')
    
    if not duration_minutes or duration_minutes <= 0:
        log_action(g.user.id, "ECHEC_VERROUILLAGE_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                   {"raison": "duree_invalide", "user_id": id, "duree": duration_minutes})
        flash('Durée de verrouillage invalide.', 'danger')
    else:
        try:
            from datetime import datetime, timedelta
            now_utc = datetime.utcnow()
            user.verrouille_jusqu_a = now_utc + timedelta(minutes=duration_minutes)
            user.verrouille_raison = raison
            user.verrouille_par_id = g.user.id
            user.verrouille_le = now_utc
            session.commit()
            
            log_action(g.user.id, "VERROUILLAGE_MANUEL_UTILISATEUR",
                       f"Utilisateur {user.nom_utilisateur}",
                       {"duree_minutes": duration_minutes, "jusqu_a": user.verrouille_jusqu_a.isoformat(), "raison": raison})
            
            # Friendly flash message: human-readable duration + local unlock time
            from src.config import Config
            unlock_local = user.verrouille_jusqu_a + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS)

            def _format_duration(mins: int) -> str:
                if mins < 60:
                    return f"{mins} minute(s)"
                hours = mins // 60
                if hours < 24:
                    return f"{hours} heure(s)"
                days = hours // 24
                if days < 7:
                    return f"{days} jour(s)"
                weeks = days // 7
                return f"{weeks} semaine(s)"

            readable = _format_duration(duration_minutes)
            flash(f"Utilisateur {user.nom_utilisateur} verrouillé jusqu'au {unlock_local.strftime('%d/%m/%Y %H:%M')} ({readable}).", 'success')
            
        except Exception as e:
            session.rollback()
            log_action(g.user.id, "ECHEC_VERROUILLAGE_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                       {"raison": "exception_systeme", "user_id": id, "erreur": str(e)})
            flash(f"Erreur : {e}", 'danger')
    
    session.close()
    return redirect(url_for('users.view', id=id))


@users_bp.route('/<int:id>/unlock', methods=('POST',))
@login_required
def unlock_account(id):
    """Déverrouille manuellement un compte utilisateur."""
    session = obtenir_session()
    user = session.query(Utilisateur).filter_by(id=id).first()


@users_bp.route('/profile', methods=('GET','POST'))
@login_required
def profile():
    """Affiche et modifie le profil de l'utilisateur connecté (display name + change password)."""
    session = obtenir_session()
    user = session.query(Utilisateur).filter_by(id=g.user.id).first()
    if user is None:
        session.close()
        flash('Utilisateur introuvable.', 'danger')
        return redirect(url_for('dashboard'))

    # POST handling
    if request.method == 'POST':
        # Update display name
        if request.form.get('action') == 'update_profile':
            new_display = request.form.get('display_name', '').strip()
            if len(new_display) > 100:
                log_action(g.user.id, 'ECHEC_MODIFICATION_PROFIL_UTILISATEUR', f'Utilisateur {user.nom_utilisateur}', {'raison': 'display_too_long'})
                flash('Le nom affiché est trop long (<= 100 caractères).', 'danger')
            else:
                old = user.display_name
                user.display_name = new_display or None
                session.commit()
                log_action(g.user.id, 'MODIFICATION_PROFIL_UTILISATEUR', f'Utilisateur {user.nom_utilisateur}', {'field': 'display_name', 'old': old, 'new': new_display})
                flash('Profil mis à jour.', 'success')
        # Change password
        elif request.form.get('action') == 'change_password':
            current = request.form.get('current_password', '')
            new = request.form.get('new_password', '')
            confirm = request.form.get('confirm_password', '')
            if not bcrypt.verify(current, user.mot_de_passe_hash):
                log_action(g.user.id, 'ECHEC_MODIFICATION_MOT_DE_PASSE_UTILISATEUR', f'Utilisateur {user.nom_utilisateur}', {'raison': 'wrong_current'})
                flash('Mot de passe actuel incorrect.', 'danger')
            elif len(new) < 6:
                log_action(g.user.id, 'ECHEC_MODIFICATION_MOT_DE_PASSE_UTILISATEUR', f'Utilisateur {user.nom_utilisateur}', {'raison': 'weak_password'})
                flash('Le nouveau mot de passe doit contenir au moins 6 caractères.', 'danger')
            elif new != confirm:
                log_action(g.user.id, 'ECHEC_MODIFICATION_MOT_DE_PASSE_UTILISATEUR', f'Utilisateur {user.nom_utilisateur}', {'raison': 'mismatch'})
                flash('Les nouveaux mots de passe ne correspondent pas.', 'danger')
            else:
                user.mot_de_passe_hash = bcrypt.hash(new)
                session.commit()
                log_action(g.user.id, 'MODIFICATION_MOT_DE_PASSE_UTILISATEUR', f'Utilisateur {user.nom_utilisateur}', {'raison': 'changed'})
                flash('Mot de passe modifié avec succès.', 'success')

    # Prepare data for rendering
    from datetime import timedelta
    from src.config import Config
    user_local = type('obj',(object,),{
        'id': user.id,
        'nom_utilisateur': user.nom_utilisateur,
        'display_name': user.display_name,
        'date_creation': user.date_creation + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS) if user.date_creation else None,
        'derniere_connexion': user.derniere_connexion + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS) if user.derniere_connexion else None
    })()
    session.close()
    return render_template('users/profile.html', user=user_local)
    
    if user is None:
        session.close()
        flash('Utilisateur introuvable.', 'danger')
        return redirect(url_for('users.index'))
    
    # Vérifier les permissions
    if not can_manage_user(g.user, user):
        log_action(g.user.id, "ECHEC_DEVERROUILLAGE_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                   {"raison": "permission_refusee", "user_id": id, "role_cible": user.role.value})
        session.close()
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Vérifier si le compte est verrouillé
    if user.verrouille_jusqu_a is None:
        log_action(g.user.id, "ECHEC_DEVERROUILLAGE_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                   {"raison": "compte_non_verrouille", "user_id": id})
        session.close()
        flash('Le compte n\'est pas verrouillé.', 'danger')
        return redirect(url_for('users.view', id=id))
    
    try:
        from datetime import datetime
        was_locked_until = user.verrouille_jusqu_a.isoformat()
        user.verrouille_jusqu_a = None
        user.verrouille_raison = None
        user.verrouille_par_id = None
        user.verrouille_le = None
        user.tentatives_connexion = 0
        session.commit()
        
        log_action(g.user.id, "DEVERROUILLAGE_MANUEL_UTILISATEUR",
                   f"Utilisateur {user.nom_utilisateur}",
                   {"etait_verrouille_jusqu_a": was_locked_until})
        
        flash(f'Utilisateur {user.nom_utilisateur} déverrouillé avec succès !', 'success')
        
    except Exception as e:
        session.rollback()
        log_action(g.user.id, "ECHEC_DEVERROUILLAGE_UTILISATEUR", f"Utilisateur {user.nom_utilisateur}",
                   {"raison": "exception_systeme", "user_id": id, "erreur": str(e)})
        flash(f"Erreur : {e}", 'danger')
    
    session.close()
    return redirect(url_for('users.view', id=id))
