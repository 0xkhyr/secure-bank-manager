"""
Module d'authentification et de contrôle d'accès.

Gère le cycle de vie des sessions, l'authentification multi-facteurs (MFA),
la protection contre les attaques par force brute et l'autorisation par rôles (RBAC).
"""

import functools
import pyotp
import io
import base64
import qrcode
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from passlib.hash import bcrypt
from src.db import obtenir_session
from src.models import Utilisateur, RoleUtilisateur
from src.config import Config
from datetime import datetime, timedelta

# Sécurité : Message générique pour prévenir l'énumération d'utilisateurs.
GENERIC_LOGIN_ERROR = "Nom d'utilisateur ou mot de passe invalide."

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def login_required(view):
    """Exige une session active pour accéder à la vue."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        
        return view(**kwargs)
    
    return wrapped_view

def admin_required(view):
    """Limite l'accès aux administrateurs (ADMIN/SUPERADMIN)."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        
        if g.user.role not in [RoleUtilisateur.ADMIN, RoleUtilisateur.SUPERADMIN]:
            # Audit : Trace des tentatives d'accès non autorisées aux fonctions administratives.
            from src.audit_logger import log_action
            log_action(g.user.id, "ACCES_REFUSE", "Admin required", {"path": request.path})
            flash("Accès refusé : Vous devez être administrateur.", "danger")
            return redirect(url_for('home'))
            
        return view(**kwargs)
    
    return wrapped_view

def operateur_required(view):
    """Limite l'accès aux fonctions métier (OPERATEUR et plus)."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        
        if g.user.role not in [RoleUtilisateur.OPERATEUR, RoleUtilisateur.ADMIN, RoleUtilisateur.SUPERADMIN]:
            # Audit : Trace des accès refusés aux opérations métier.
            from src.audit_logger import log_action
            log_action(g.user.id, "ACCES_REFUSE", "Operateur required", {"path": request.path})
            flash("Accès refusé.", "danger")
            return redirect(url_for('home'))
            
        return view(**kwargs)
    
    return wrapped_view


# Sécurité : Mapping granulaire des permissions par rôle pour respecter le principe du moindre privilège.
PERMISSION_MAP = {
    RoleUtilisateur.SUPERADMIN.name: {'*'},
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
    'clients.suspend': set(),
    'clients.deactivate': set(),
    'clients.archive': set(),
    'clients.reactivate': set(),
    'policies.history': set(),
}


def has_permission(user, perm: str) -> bool:
    """Vérifie l'attribution d'une permission spécifique selon le rôle."""
    if user is None:
        return False
    role_name = user.role.name if hasattr(user.role, 'name') else str(user.role)
    perms = PERMISSION_MAP.get(role_name, set())
    return '*' in perms or perm in perms


def permission_required(perm: str):
    """Décorateur de contrôle d'accès basé sur les permissions.

    Audit : Enregistre une trace ACCES_REFUSE en cas d'autorisation insuffisante.
    """
    def decorator(view):
        @functools.wraps(view)
        def wrapped_view(*args, **kwargs):
            from flask import g, request, url_for
            from src.audit_logger import log_action

            if g.user is None:
                return redirect(url_for('auth.login'))

            if not has_permission(g.user, perm):
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
    """Charge l'utilisateur en session et gère l'expiration d'inactivité.

    Limitation : Force la déconnexion automatique si SESSION_TIMEOUT est atteint.
    """
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        last_activity = session.get('last_activity')
        if last_activity:
            if datetime.utcnow() - datetime.fromisoformat(last_activity) > timedelta(seconds=Config.SESSION_TIMEOUT):
                # Audit : Trace de la fin de session pour inactivité.
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
        
        session['last_activity'] = datetime.utcnow().isoformat()
        
        db_session = obtenir_session()
        g.user = db_session.query(Utilisateur).filter_by(id=user_id).first()

@auth_bp.route('/login', methods=('GET', 'POST'))
def login():
    """Gère l'authentification initiale et les protections contre les attaques par force brute."""
    if g.user:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db_session = obtenir_session()
        error = None
        
        user = db_session.query(Utilisateur).filter_by(nom_utilisateur=username).first()
        
        if user is None:
            # Sécurité : Utilise un message générique pour éviter l'énumération des noms d'utilisateurs.
            error = GENERIC_LOGIN_ERROR
            # Audit : Trace de l'échec de connexion (utilisateur non trouvé).
            from src.audit_logger import log_action
            log_action(None, "ECHEC_CONNEXION", "Système", 
                      {"nom_utilisateur": username, "raison": "utilisateur_inexistant", "user_id": None})
        else:
            user_id_local = user.id
            if not user.is_active:
                error = GENERIC_LOGIN_ERROR
                # Audit : Tentative sur un compte désactivé.
                from src.audit_logger import log_action
                log_action(user_id_local, "ECHEC_CONNEXION", "Système",
                          {"nom_utilisateur": username, "user_id": user_id_local, "raison": "compte_inactif"})

            elif user.est_verrouille():
                error = GENERIC_LOGIN_ERROR
                # Audit : Tentative sur un compte déjà sous verrouillage temporaire.
                from src.audit_logger import log_action
                log_action(user_id_local, "ECHEC_CONNEXION", "Système",
                          {"nom_utilisateur": username, "user_id": user_id_local, "raison": "compte_verrouille"})

            elif not bcrypt.verify(password, user.mot_de_passe_hash):
                error = GENERIC_LOGIN_ERROR
                # Sécurité : Incrémentation du compteur de tentatives pour le ralentissement ou verrouillage.
                user.tentatives_connexion = (user.tentatives_connexion or 0) + 1
                
                if user.tentatives_connexion >= Config.MAX_LOGIN_ATTEMPTS:
                    # Sécurité : Verrouillage automatique après dépassement du seuil MAX_LOGIN_ATTEMPTS.
                    from src.audit_logger import log_action
                    now_utc = datetime.utcnow()
                    user.verrouille_jusqu_a = now_utc + timedelta(minutes=Config.LOCKOUT_MINUTES)
                    user.verrouille_raison = 'trop_de_tentatives'
                    user.verrouille_le = now_utc
                    user.verrouille_par_id = None
                    user.tentatives_connexion = 0
                    db_session.commit()

                    # Audit : Trace du verrouillage automatique du compte.
                    try:
                        log_action(user_id_local, "VERROUILLAGE_AUTO_UTILISATEUR", "Système",
                                  {"nom_utilisateur": username, "user_id": user_id_local, "raison": "trop_de_tentatives", "duree_minutes": Config.LOCKOUT_MINUTES, "jusqu_a": user.verrouille_jusqu_a.isoformat()})
                    except Exception:
                        pass
                else:
                    db_session.commit()
                    # Audit : Mot de passe incorrect.
                    from src.audit_logger import log_action
                    log_action(user_id_local, "ECHEC_CONNEXION", "Système",
                              {"nom_utilisateur": username, "user_id": user_id_local, "raison": "mot_de_passe_incorrect"})
            
            was_locked = user.verrouille_jusqu_a is not None

            if error:
                flash(error, 'danger')
            else:
                user.derniere_connexion = datetime.utcnow()
                user.tentatives_connexion = 0
                user.verrouille_jusqu_a = None
                db_session.commit()

                # Audit : Déverrouillage automatique après expiration du délai de bannissement.
                if was_locked:
                    from src.audit_logger import log_action
                    log_action(user_id_local, "DEVERROUILLAGE_AUTO", "Système",
                              {"nom_utilisateur": username, "user_id": user_id_local, "raison": "expiration_lockout"})

                # Audit : Authentification par mot de passe réussie (Étape 1).
                from src.audit_logger import log_action
                log_action(user_id_local, "CONNEXION_STEP1", "Système", {"nom_utilisateur": username, "user_id": user_id_local})

                # Sécurité : Vérification de l'obligation du second facteur selon la politique ou le choix utilisateur.
                from src.policy_helpers import get_policy
                mfa_roles = get_policy('mfa.roles_obligatoires', default=[])
                role_name = user.role.value if hasattr(user.role, 'value') else str(user.role)
                
                mfa_required = user.mfa_enabled or (role_name in mfa_roles)

                if mfa_required:
                    if not user.mfa_enabled:
                        # Règle métier : Forcer la configuration MFA si elle est exigée par le rôle.
                        session['mfa_setup_user_id'] = user_id_local
                        flash("La double authentification est obligatoire pour votre rôle. Veuillez la configurer.", "warning")
                        return redirect(url_for('auth.mfa_setup'))
                    
                    # Sécurité : Redirection vers le challenge MFA.
                    session['mfa_user_id'] = user_id_local
                    return redirect(url_for('auth.mfa_verify'))

                session['user_id'] = user_id_local
                session['last_activity'] = datetime.utcnow().isoformat()
                flash('Connexion réussie !', 'success')
                return redirect(url_for('home'))

        if error:
            existing = session.get('_flashes') or []
            if not any(c == 'danger' and m == error for c, m in existing):
                flash(error, 'danger')

    return render_template('auth/login.html')

try:
    from src.app import limiter
    if limiter:
        # Limitation : Protection anti-abus par limitation du débit de requêtes sur le login.
        login = limiter.limit(getattr(Config, 'LOGIN_RATE_LIMIT', '10 per minute'))(login)
except Exception:
    pass

@auth_bp.route('/logout')
def logout():
    """Réinitialise la session et enregistre la déconnexion."""
    if g.user:
        # Audit : Trace de déconnexion volontaire.
        from src.audit_logger import log_action
        log_action(g.user.id, "DECONNEXION", "Système", {"nom_utilisateur": g.user.nom_utilisateur, "user_id": g.user.id})
    
    session.clear()
    flash('Vous avez été déconnecté.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/mfa/verify', methods=('GET', 'POST'))
def mfa_verify():
    """Valide le second facteur (TOTP) ou un code de secours."""
    user_id = session.get('mfa_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code = request.form.get('code')
        db_session = obtenir_session()
        user = db_session.query(Utilisateur).get(user_id)

        # Sécurité : Vérification du code TOTP dynamique (RFC 6238).
        is_totp_valid = user and pyotp.TOTP(user.mfa_secret).verify(code)
        
        is_backup_valid = False
        if user and not is_totp_valid and user.mfa_backup_codes:
            # Sécurité : Les codes de secours sont hachés avec bcrypt pour protéger l'accès physique à la base.
            clean_code = code.strip().upper()
            hashed_list = user.mfa_backup_codes.split(',')
            new_hashed_list = []
            
            for h in hashed_list:
                if not is_backup_valid and bcrypt.verify(clean_code, h):
                    is_backup_valid = True
                else:
                    new_hashed_list.append(h)
            
            if is_backup_valid:
                # Sécurité : Un code de secours est à usage unique et supprimé immédiatement après validation.
                user.mfa_backup_codes = ",".join(new_hashed_list)
                db_session.commit()

        if is_totp_valid or is_backup_valid:
            session.pop('mfa_user_id', None)
            session['user_id'] = user.id
            session['last_activity'] = datetime.utcnow().isoformat()
            
            # Audit : Trace discriminée selon le mode de validation (TOTP vs Backup).
            from src.audit_logger import log_action
            log_type = "CONNEXION_MFA_SUCCESS" if is_totp_valid else "CONNEXION_BACKUP_CODE"
            log_action(user.id, log_type, "Système", {"user_id": user.id})
            
            flash('Connexion réussie !', 'success')
            return redirect(url_for('home'))
        else:
            flash('Code invalide. Veuillez réessayer.', 'danger')
            # Audit : Tentative MFA échouée.
            from src.audit_logger import log_action
            log_action(user_id, "ECHEC_MFA", "Système", {"user_id": user_id, "raison": "code_invalide"})

    return render_template('auth/mfa_verify.html')


@auth_bp.route('/mfa/recovery', methods=('GET', 'POST'))
def mfa_recovery():
    """Gère la récupération d'accès via les codes de secours à usage unique."""
    user_id = session.get('mfa_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code = request.form.get('code')
        db_session = obtenir_session()
        user = db_session.query(Utilisateur).get(user_id)

        is_backup_valid = False
        if user and user.mfa_backup_codes:
            clean_code = code.strip().upper()
            hashed_list = user.mfa_backup_codes.split(',')
            new_hashed_list = []
            
            for h in hashed_list:
                if not is_backup_valid and bcrypt.verify(clean_code, h):
                    is_backup_valid = True
                else:
                    new_hashed_list.append(h)
            
            if is_backup_valid:
                # Sécurité : Règle du code à usage unique appliquée ici aussi.
                user.mfa_backup_codes = ",".join(new_hashed_list)
                db_session.commit()

                session.pop('mfa_user_id', None)
                session['user_id'] = user.id
                session['last_activity'] = datetime.utcnow().isoformat()
                
                # Audit : Utilisation d'un code de secours enregistrée pour surveillance.
                from src.audit_logger import log_action
                log_action(user.id, "CONNEXION_BACKUP_CODE", "Système", {"user_id": user.id})
                
                flash('Connexion réussie via code de secours !', 'success')
                return redirect(url_for('home'))

        flash('Code de secours invalide ou déjà utilisé.', 'danger')
        # Audit : Tentative de récupération infructueuse.
        from src.audit_logger import log_action
        log_action(user_id, "ECHEC_MFA_RECOVERY", "Système", {"user_id": user_id, "raison": "code_invalide"})

    return render_template('auth/mfa_recovery.html')


@auth_bp.route('/mfa/setup', methods=('GET', 'POST'))
def mfa_setup():
    """Initialise le secret TOTP et génère les codes de secours initiaux."""
    user_id = session.get('mfa_setup_user_id') or (g.user.id if g.user else None)
    
    if not user_id:
        return redirect(url_for('auth.login'))

    db_session = obtenir_session()
    user = db_session.query(Utilisateur).get(user_id)

    if request.method == 'POST':
        code = request.form.get('code')
        secret = session.get('temp_mfa_secret')
        
        if secret and pyotp.TOTP(secret).verify(code):
            # Sécurité : Génération de 8 codes de secours aléatoires et hachage immédiat.
            import secrets
            recovery_codes = [secrets.token_hex(4).upper() for _ in range(8)]
            hashed_codes = ",".join([bcrypt.hash(c) for c in recovery_codes])
            
            user.mfa_secret = secret
            user.mfa_enabled = True
            user.mfa_backup_codes = hashed_codes
            db_session.commit()
            
            session.pop('temp_mfa_secret', None)
            session.pop('mfa_setup_user_id', None)
            
            if not g.user:
                session['user_id'] = user.id
                session['last_activity'] = datetime.utcnow().isoformat()
            
            # Audit : Trace d'activation de la MFA pour cet utilisateur.
            from src.audit_logger import log_action
            log_action(user.id, "MFA_ACTIVE", "Utilisateur", {"user_id": user.id})
            
            return render_template('auth/mfa_setup.html', success=True, recovery_codes=recovery_codes)
        else:
            flash('Code de confirmation invalide. Veuillez scanner à nouveau.', 'danger')

    if 'temp_mfa_secret' not in session:
        session['temp_mfa_secret'] = pyotp.random_base32()
    
    secret = session['temp_mfa_secret']
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=user.nom_utilisateur, issuer_name="SecureBank")
    
    # Génération du QR Code en base64
    img = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    return render_template('auth/mfa_setup.html', qr_code=qr_base64, secret=secret)


@auth_bp.route('/mfa/disable', methods=('POST',))
@login_required
def mfa_disable():
    """Désactivation du MFA depuis le profil."""
    # Note: On devrait normalement demander confirmation du mot de passe ici
    db_session = obtenir_session()
    user = db_session.query(Utilisateur).get(g.user.id)
    user.mfa_enabled = False
    user.mfa_secret = None
    db_session.commit()
    
    from src.audit_logger import log_action
    log_action(user.id, "MFA_DESACTIVE", "Utilisateur", {"user_id": user.id})
    
    flash('Double authentification désactivée.', 'warning')
    return redirect(url_for('home'))
