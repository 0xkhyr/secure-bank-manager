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

# Generic message used to avoid username enumeration
GENERIC_LOGIN_ERROR = "Nom d'utilisateur ou mot de passe invalide."

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
    Décorateur pour restreindre l'accès aux administrateurs et superadmins uniquement.
    """
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        
        if g.user.role not in [RoleUtilisateur.ADMIN, RoleUtilisateur.SUPERADMIN]:
            from src.audit_logger import log_action
            log_action(g.user.id, "ACCES_REFUSE", "Admin required", {"path": request.path})
            flash("Accès refusé : Vous devez être administrateur.", "danger")
            return redirect(url_for('home'))
            
        return view(**kwargs)
    
    return wrapped_view

def operateur_required(view):
    """
    Décorateur pour restreindre l'accès aux opérateurs (ou admins/superadmins).
    """
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        
        # Les admins et superadmins ont aussi accès aux fonctions opérateurs
        if g.user.role not in [RoleUtilisateur.OPERATEUR, RoleUtilisateur.ADMIN, RoleUtilisateur.SUPERADMIN]:
            from src.audit_logger import log_action
            log_action(g.user.id, "ACCES_REFUSE", "Operateur required", {"path": request.path})
            flash("Accès refusé.", "danger")
            return redirect(url_for('home'))
            
        return view(**kwargs)
    
    return wrapped_view


# Mapping de permissions basique (role -> set de permissions)
# Use explicit permission strings so we can grant/revoke in the future. By default,
# only SUPERADMIN has full wildcard privileges. Admin keeps the typical operator
# permissions (can be extended later), while policy management is a separate
# fine-grained permission `policies.manage` which is only granted to SUPERADMIN
# by default.
PERMISSION_MAP = {
    RoleUtilisateur.SUPERADMIN.name: {'*'},  # SuperAdmin a toutes les permissions
    RoleUtilisateur.ADMIN.name: {
        'clients.view', 'clients.create', 'clients.update',
        'clients.deactivate','clients.reactivate','clients.archive',
        'accounts.view', 'accounts.create', 'accounts.close',
        'operations.create', 'operations.view',
        'audit.view', 'users.view', 'users.create', 'users.update', 'users.deactivate', 'users.reactivate',
        'policies.view', 'policies.edit', 'policies.toggle', 'policies.apply',
        'approbations.view', 'approbations.approve', 'approbations.reject'
    },
    RoleUtilisateur.OPERATEUR.name: {
        'clients.view', 'clients.create', 'clients.update',
        'clients.deactivate','clients.reactivate',
        'accounts.view', 'accounts.create', 'accounts.close',
        'operations.create', 'operations.view'
    },
    # Fine-grained client administrative permissions placeholders
    'clients.suspend': set(),
    'clients.deactivate': set(),
    'clients.archive': set(),
    'clients.reactivate': set(),
    # Policy management permission (superadmin-only by default)
    'policies.history': set(),
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
                # Logger l'expiration avant de clear
                try:
                    from src.audit_logger import log_action
                    duree = (datetime.utcnow() - datetime.fromisoformat(last_activity)).total_seconds()
                    log_action(user_id, "SESSION_EXPIREE", "Système",
                               {"duree_inactivite_secondes": int(duree), "timeout": Config.SESSION_TIMEOUT})
                except Exception:
                    pass
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
    # Si déjà connecté, redirection vers l'accueil
    if g.user:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db_session = obtenir_session()
        error = None
        
        # Recherche de l'utilisateur
        user = db_session.query(Utilisateur).filter_by(nom_utilisateur=username).first()
        
        if user is None:
            # Avoid revealing whether the username exists
            error = GENERIC_LOGIN_ERROR
            # Audit - tentative de connexion échouée (utilisateur inexistant)
            from src.audit_logger import log_action
            log_action(None, "ECHEC_CONNEXION", "Système", 
                      {"nom_utilisateur": username, "raison": "utilisateur_inexistant", "user_id": None})
        else:
            user_id_local = user.id
            # Vérifier si le compte est actif
            if not user.is_active:
                # Do not reveal account state to the client
                error = GENERIC_LOGIN_ERROR
                # Audit - tentative de connexion sur compte inactif
                from src.audit_logger import log_action
                log_action(user_id_local, "ECHEC_CONNEXION", "Système",
                          {"nom_utilisateur": username, "user_id": user_id_local, "raison": "compte_inactif"})
            # Vérifier si le compte est verrouillé
            elif user.est_verrouille():
                # Do not reveal that the account is locked to the client; use a generic message
                error = GENERIC_LOGIN_ERROR
                # Audit - tentative sur compte verrouillé
                from src.audit_logger import log_action
                log_action(user_id_local, "ECHEC_CONNEXION", "Système",
                          {"nom_utilisateur": username, "user_id": user_id_local, "raison": "compte_verrouille"})
            elif not bcrypt.verify(password, user.mot_de_passe_hash):
                # Use generic message so we don't reveal whether username or password was incorrect
                error = GENERIC_LOGIN_ERROR
                # Gestion des tentatives échouées et verrouillage
                user.tentatives_connexion = (user.tentatives_connexion or 0) + 1
                # Si on atteint le maximum, verrouiller le compte
                if user.tentatives_connexion >= Config.MAX_LOGIN_ATTEMPTS:
                    from src.audit_logger import log_action
                    now_utc = datetime.utcnow()
                    user.verrouille_jusqu_a = now_utc + timedelta(minutes=Config.LOCKOUT_MINUTES)
                    user.verrouille_raison = 'trop_de_tentatives'
                    user.verrouille_le = now_utc
                    user.verrouille_par_id = None
                    # Optionnel : reset counter after locking
                    user.tentatives_connexion = 0
                    db_session.commit()

                    # Audit - verrouillage automatique
                    try:
                        log_action(user_id_local, "VERROUILLAGE_AUTO_UTILISATEUR", "Système",
                                  {"nom_utilisateur": username, "user_id": user_id_local, "raison": "trop_de_tentatives", "duree_minutes": Config.LOCKOUT_MINUTES, "jusqu_a": user.verrouille_jusqu_a.isoformat()})
                    except Exception:
                        pass

                    # Keep a generic error message for the user (do not reveal lock details)
                    error = GENERIC_LOGIN_ERROR
                else:
                    db_session.commit()
                    # Audit - mauvais mot de passe
                    from src.audit_logger import log_action
                    log_action(user_id_local, "ECHEC_CONNEXION", "Système",
                              {"nom_utilisateur": username, "user_id": user_id_local, "raison": "mot_de_passe_incorrect"})
            
            # Vérifier si le compte était verrouillé et se déverrouille automatiquement
            was_locked = user.verrouille_jusqu_a is not None

            # Si une erreur a été détectée plus haut, ne pas procéder à la connexion
            if error:
                flash(error, 'danger')
            else:
                # Mise à jour des infos de connexion
                user.derniere_connexion = datetime.utcnow()
                user.tentatives_connexion = 0
                user.verrouille_jusqu_a = None
                db_session.commit()

                # Audit - déverrouillage automatique si applicable
                if was_locked:
                    from src.audit_logger import log_action
                    log_action(user_id_local, "DEVERROUILLAGE_AUTO", "Système",
                              {"nom_utilisateur": username, "user_id": user_id_local, "raison": "expiration_lockout"})

                # Audit - connexion réussie
                from src.audit_logger import log_action
                log_action(user_id_local, "CONNEXION", "Système", {"nom_utilisateur": username, "user_id": user_id_local})

                # Set session to mark user as logged in
                session['user_id'] = user_id_local
                session['last_activity'] = datetime.utcnow().isoformat()
                flash('Connexion réussie !', 'success')
                return redirect(url_for('home'))

        if error:
            # Avoid flashing the exact same message multiple times in the session
            existing = session.get('_flashes') or []
            if not any(c == 'danger' and m == error for c, m in existing):
                flash(error, 'danger')

    return render_template('auth/login.html')

# Apply rate limit to the login endpoint at import time to avoid decorator ordering/circular import issues
try:
    from src.app import limiter
    if limiter:
        # Wrap the login view with the configured login rate limit
        login = limiter.limit(getattr(Config, 'LOGIN_RATE_LIMIT', '10 per minute'))(login)
except Exception:
    # If Flask-Limiter is not available or import fails, keep behavior unchanged
    pass

@auth_bp.route('/logout')
def logout():
    """
    Route de déconnexion.
    Efface la session et redirige vers la connexion.
    """
    # Audit - déconnexion
    if g.user:
        from src.audit_logger import log_action
        log_action(g.user.id, "DECONNEXION", "Système", {"nom_utilisateur": g.user.nom_utilisateur, "user_id": g.user.id})
    
    session.clear()
    flash('Vous avez été déconnecté.', 'info')
    return redirect(url_for('auth.login'))
