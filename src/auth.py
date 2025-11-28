"""
auth.py - Gestion de l'authentification et des autorisations

Ce module gère :
- La connexion et la déconnexion des utilisateurs
- La gestion de la session utilisateur
- Les décorateurs pour protéger les routes (login_required, admin_required)
"""

import functools
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from passlib.hash import bcrypt
from src.db import obtenir_session
from src.models import Utilisateur, RoleUtilisateur
from src.config import Config
from datetime import datetime, timedelta

# Création du Blueprint pour l'authentification
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def login_required(view):
    """
    Décorateur pour restreindre l'accès aux utilisateurs connectés.
    Redirige vers la page de connexion si l'utilisateur n'est pas authentifié.
    """
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        
        return view(**kwargs)
    
    return wrapped_view

def admin_required(view):
    """
    Décorateur pour restreindre l'accès aux administrateurs uniquement.
    """
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        
        if g.user.role != RoleUtilisateur.ADMIN:
            flash("Accès refusé : Vous devez être administrateur.", "danger")
            return redirect(url_for('home'))
            
        return view(**kwargs)
    
    return wrapped_view

def operateur_required(view):
    """
    Décorateur pour restreindre l'accès aux opérateurs (ou admins).
    """
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        
        # Les admins ont aussi accès aux fonctions opérateurs
        if g.user.role not in [RoleUtilisateur.OPERATEUR, RoleUtilisateur.ADMIN]:
            flash("Accès refusé.", "danger")
            return redirect(url_for('home'))
            
        return view(**kwargs)
    
    return wrapped_view


# Mapping de permissions basique (role -> set de permissions)
PERMISSION_MAP = {
    RoleUtilisateur.ADMIN.name: {'*'},
    RoleUtilisateur.OPERATEUR.name: {
        'clients.view', 'clients.create', 'clients.update',
        'accounts.view', 'accounts.create', 'accounts.close',
        'operations.create', 'operations.view',
        'audit.view'
    }
}


def has_permission(user, perm: str) -> bool:
    """Vérifie si l'utilisateur a la permission demandée.

    Pour l'instant, utilise un mapping en mémoire. '*' signifie toutes les permissions.
    """
    if user is None:
        return False
    role_name = user.role.name if hasattr(user.role, 'name') else str(user.role)
    perms = PERMISSION_MAP.get(role_name, set())
    return '*' in perms or perm in perms


def permission_required(perm: str):
    """Décorateur qui vérifie la permission `perm` pour l'utilisateur courant.

    En cas d'accès refusé, enregistre un log d'audit `ACCES_REFUSE` et redirige.
    """
    def decorator(view):
        @functools.wraps(view)
        def wrapped_view(*args, **kwargs):
            from flask import g, request, url_for
            from src.audit_logger import log_action

            if g.user is None:
                return redirect(url_for('auth.login'))

            if not has_permission(g.user, perm):
                # Loguer l'accès refusé
                try:
                    log_action(g.user.id if g.user else None, 'ACCES_REFUSE', perm, {'path': request.path})
                except Exception:
                    pass
                flash("Accès refusé : privilèges insuffisants.", 'danger')
                return redirect(url_for('home'))

            return view(*args, **kwargs)

        return wrapped_view
    return decorator

@auth_bp.before_app_request
def load_logged_in_user():
    """
    Fonction exécutée avant chaque requête.
    Charge l'utilisateur depuis la base de données si son ID est dans la session.
    Vérifie également l'expiration de session.
    """
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        # Vérifier l'expiration de session
        last_activity = session.get('last_activity')
        if last_activity:
            if datetime.utcnow() - datetime.fromisoformat(last_activity) > timedelta(seconds=Config.SESSION_TIMEOUT):
                session.clear()
                g.user = None
                return
        
        # Mettre à jour l'activité
        session['last_activity'] = datetime.utcnow().isoformat()
        
        db_session = obtenir_session()
        g.user = db_session.query(Utilisateur).filter_by(id=user_id).first()
        # Note: Don't close the session here as it might interfere with view functions
        # The scoped session will be cleaned up automatically

@auth_bp.route('/login', methods=('GET', 'POST'))
def login():
    """
    Route de connexion.
    Gère l'affichage du formulaire et le traitement de la soumission.
    """
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db_session = obtenir_session()
        error = None
        
        # Recherche de l'utilisateur
        user = db_session.query(Utilisateur).filter_by(nom_utilisateur=username).first()
        
        if user is None:
            error = 'Nom d\'utilisateur incorrect.'
        else:
            # Vérifier si le compte est verrouillé
            if user.est_verrouille():
                remaining = user.verrouille_jusqu_a - datetime.utcnow()
                minutes = int(remaining.total_seconds() // 60) + 1
                error = f"Compte verrouillé. Réessayer dans {minutes} minute(s)."
            elif not bcrypt.verify(password, user.mot_de_passe_hash):
                error = 'Mot de passe incorrect.'
                # Gestion des tentatives échouées et verrouillage
                user.tentatives_connexion = (user.tentatives_connexion or 0) + 1
                # Si on atteint le maximum, verrouiller le compte
                if user.tentatives_connexion >= Config.MAX_LOGIN_ATTEMPTS:
                    user.verrouille_jusqu_a = datetime.utcnow() + timedelta(minutes=Config.LOCKOUT_MINUTES)
                    # Optionnel : reset counter after locking
                    user.tentatives_connexion = 0
                db_session.commit()
        
        if error is None:
            # Connexion réussie
            session.clear()
            session['user_id'] = user.id
            session['last_activity'] = datetime.utcnow().isoformat()
            
            # Mise à jour des infos de connexion
            user.derniere_connexion = datetime.utcnow()
            user.tentatives_connexion = 0
            user.verrouille_jusqu_a = None
            db_session.commit()
            db_session.close()
            
            flash('Connexion réussie !', 'success')
            return redirect(url_for('home'))
        
        db_session.close()
        flash(error, 'danger')

    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    """
    Route de déconnexion.
    Efface la session et redirige vers la connexion.
    """
    session.clear()
    flash('Vous avez été déconnecté.', 'info')
    return redirect(url_for('auth.login'))
