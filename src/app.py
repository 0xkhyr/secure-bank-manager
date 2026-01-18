"""
# Point d'Entrée Principal (Boilerplate Flask)
# Configuration : Initialise le moteur Flask, les extensions de sécurité et les variables d'environnement.
# Sécurité : Centralise le durcissement (Hardening) des cookies et des en-têtes HTTP.
"""

import json
from flask import Flask, redirect, url_for, render_template, g
from src.db import initialiser_base_donnees, verifier_connexion, obtenir_session
from src.config import Config
from src.auth import auth_bp, login_required
from src.clients import clients_bp
from src.accounts import accounts_bp
from src.operations import operations_bp
from src.audit_logger import audit_bp
from src.users import users_bp
from src.policies import policies_bp
from src.dev import dev_bp
from src.checker import checker_bp

# Initialisation de l'instance Flask avec redirection vers les dossiers sources.
app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Sécurité : Chargement de la configuration centralisée pour garantir l'immutabilité des paramètres.
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['DATABASE_PATH'] = Config.DATABASE_PATH
app.config['DEVISE'] = Config.DEVISE

# Sécurité : Application des directives OWASP sur le durcissement des cookies de session.
app.config['SESSION_COOKIE_SECURE'] = Config.SESSION_COOKIE_SECURE         # HTTPS Only
app.config['SESSION_COOKIE_HTTPONLY'] = Config.SESSION_COOKIE_HTTPONLY     # No JS access
app.config['SESSION_COOKIE_SAMESITE'] = Config.SESSION_COOKIE_SAMESITE     # CSRF mitigation

@app.template_filter('decode_json')
def decode_json_filter(json_string):
    """
    # Audit : Formate les logs JSON pour une lecture humaine sans altérer l'encodage d'origine.
    """
    if not json_string:
        return '-'
    try:
        data = json.loads(json_string)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except:
        return json_string

@app.template_filter('to_local_time')
def to_local_time_filter(utc_datetime):
    """
    # Audit : Normalisation de l'affichage temporel (UTC vers fuseau configuré).
    """
    if utc_datetime:
        from datetime import timedelta
        return utc_datetime + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS)
    return None

import secrets

@app.context_processor
def inject_now():
    """
    # Sécurité : Injection globale de l'utilitaire de protection CSRF.
    # Fournit également les outils de gestion du temps aux templates Jinja2.
    """
    from datetime import datetime, timedelta

    def generate_csrf_token():
        # Sécurité : Persiste un jeton unique par session pour contrer les attaques CSRF.
        from flask import session
        token = session.get('csrf_token')
        if not token:
            token = secrets.token_urlsafe(24)
            session['csrf_token'] = token
        return token

    from src.auth import has_permission

    return {
        'now': datetime.utcnow, 
        'timedelta': timedelta,
        'max': max,
        'min': min,
        'csrf_token': generate_csrf_token,
        'has_permission': has_permission,
    }

@app.context_processor
def inject_pending_approbations():
    """
    # Règle métier : Affiche en temps réel le nombre de validations en attente (Maker-Checker).
    """
    from flask import g
    try:
        if not getattr(g, 'user', None):
            return {}
        if g.user.role.value not in ['admin', 'superadmin']:
            return {}
        
        from src.db import session_factory
        session = session_factory()
        try:
            from src.models import OperationEnAttente, StatutAttente
            count = session.query(OperationEnAttente).filter_by(statut=StatutAttente.PENDING).count()
        finally:
            session.close()
        return {'pending_approbations_count': count}
    except Exception:
        return {}

@app.context_processor
def inject_policies():
    """
    # Politique : Injection des règles métier dynamiques accessibles globalement.
    # Permet au front-end d'ajuster l'affichage selon les limites configurées.
    """
    try:
        from src.policy_helpers import get_policy_int, get_policy_bool
        from src.policy import get_policy
        return {
            'RETRAIT_LIMIT': get_policy_int('retrait.limite_journaliere', default=1000),
            'MAKER_CHECKER_THRESHOLD': get_policy_int('maker_checker.seuil_montant', default=5000),
            'VELOCITY_ACTIVE': get_policy_bool('velocity.actif', default=False),
            'VELOCITY_RETRAIT_MAX_PER_MIN': get_policy_int('velocity.retrait.max_par_minute', default=3),
            'SESSION_TIMEOUT': get_policy_int('session.delai_expiration_secondes', default=1800),
            'AUDIT_RETENTION_DAYS': get_policy_int('audit.retention_jours', default=365),
            'POLICY_CACHE_TTL': get_policy_int('politiques.cache_ttl_secondes', default=30),
            'MFA_ROLES': get_policy('mfa.roles_obligatoires', default=[]),
            'MAINTENANCE_MODE': get_policy_bool('maintenance.enabled', default=False),
            'MAINTENANCE_MESSAGE': get_policy('maintenance.message', default="Site en maintenance — certaines fonctions sont indisponibles."),
            'PANIC_MODE': get_policy_bool('maintenance.panic_mode', default=False),
            'PANIC_MESSAGE': get_policy('maintenance.panic_message', default="Le site est en mode panique. Toutes les opérations sont suspendues."),
        }
    except Exception:
        return {}


@app.context_processor
def inject_panic_bypass():
    """Expose whether the current session has requested an admin panic bypass (used to suppress the modal)."""
    from flask import session
    return {'PANIC_BYPASS': session.get('panic_bypass', False)}


# Rate limiting (Flask-Limiter)
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    # Use configured storage or in-memory as default
    limiter = Limiter(key_func=get_remote_address, storage_uri=Config.RATE_LIMIT_STORAGE_URI)
    # Defer actual app binding until after app exists
    limiter.init_app(app)
    # If running under test runner, disable by default to avoid global test interference.
    import sys
    if 'pytest' in sys.modules:
        try:
            limiter.enabled = False
        except Exception:
            pass
except Exception:
    limiter = None

# Enregistrement des Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(clients_bp)
app.register_blueprint(accounts_bp)
app.register_blueprint(operations_bp)
app.register_blueprint(audit_bp)
app.register_blueprint(users_bp)
app.register_blueprint(policies_bp)
app.register_blueprint(checker_bp)

# Outils de dev (uniquement en debug/dev)
if app.debug:
    app.register_blueprint(dev_bp)

# Apply login rate limit at app level to avoid circular import / decorator ordering issues
if limiter:
    try:
        login_view = app.view_functions.get('auth.login')
        if login_view:
            app.view_functions['auth.login'] = limiter.limit(getattr(Config, 'LOGIN_RATE_LIMIT', '10 per minute'))(login_view)
    except Exception:
        # Fallback: do nothing if limiter interaction fails
        pass

# Sécurité : Initialisation de la protection CSRF (Flask-WTF).
try:
    from flask_wtf import CSRFProtect
    csrf = CSRFProtect(app)
except Exception:
    # Limitation : Mécanisme de repli si l'extension Flask-WTF est absente.
    csrf = None

if csrf is None:
    @app.before_request
    def simple_csrf_protect():
        """
        # Sécurité : Implémentation manuelle de la protection CSRF.
        # Vérifie la présence d'un jeton valide pour toute méthode modifiant l'état (POST, PUT, DELETE).
        """
        from flask import request, abort, g
        if app.config.get('WTF_CSRF_ENABLED') is False:
            return

        # Sécurité : Le mode "Panic" est prioritaire sur les autres vérifications.
        from src.policy_helpers import get_policy_bool
        from src.policy import get_policy
        if get_policy_bool('maintenance.panic_mode', default=False):
            if request.path.startswith(app.static_url_path):
                return
            if request.endpoint == 'health':
                return
            if request.endpoint == 'auth.login':
                return
            if request.endpoint == 'panic':
                return
            if getattr(g, 'user', None) and getattr(g.user, 'role', None) and g.user.role.value in ['admin', 'superadmin']:
                return
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                message = get_policy('maintenance.panic_message', default='Service indisponible pour maintenance')
                abort(503, description=str(message))

        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return
        if request.path.startswith(app.static_url_path):
            return
        from flask import session
        token = session.get('csrf_token')
        if not token:
            abort(400)
        
        # Sécurité : Validation croisée entre la session et le corps de la requête ou les en-têtes HTTP.
        form_token = request.form.get('csrf_token')
        header_token = request.headers.get('X-CSRF-Token')
        if form_token == token or header_token == token:
            return
        abort(400)


    @app.before_request
    def maintenance_panic_guard():
        """
        # Sécurité : Mode "Panic" (Arrêt d'Urgence).
        # En cas de compromission suspectée, toutes les opérations sont suspendues pour les non-admins.
        """
        from flask import request, abort, g, redirect, url_for
        from src.policy_helpers import get_policy_bool
        from src.policy import get_policy

        if not get_policy_bool('maintenance.panic_mode', default=False):
            return

        if request.path.startswith(app.static_url_path):
            return
        if request.endpoint == 'health':
            return

        if request.endpoint == 'auth.login' or request.path.startswith(url_for('auth.login')):
            return

        if request.endpoint == 'panic' or request.path.startswith(url_for('panic')):
            return

        # Sécurité : Seuls les administrateurs conservent l'accès pour corriger la situation.
        if getattr(g, 'user', None) and getattr(g.user, 'role', None) and g.user.role.value in ['admin', 'superadmin']:
            return

        message = get_policy('maintenance.panic_message', default='Service indisponible pour maintenance')

        if request.method == 'GET':
            return redirect(url_for('panic'))

        abort(503, description=str(message))


# Alias route: top-level /profile forwards to the users.profile view (keeps existing implementation)
from src.users import profile as _users_profile_view

@app.route('/profile', methods=('GET','POST'))
def profile():
    """Top-level profile URL that delegates to users.profile"""
    return _users_profile_view()

# Initialiser la base de données au démarrage
@app.teardown_appcontext
def shutdown_session(exception=None):
    """
    Nettoye la session SQLAlchemy à la fin de chaque requête.
    Indispensable pour scoped_session.
    """
    from src.db import Session
    Session.remove()

with app.app_context():
    if verifier_connexion():
        print("✓ Base de données connectée")
        initialiser_base_donnees()
    else:
        print("✗ Erreur de connexion à la base de données")

# Route d'accueil - Redirige vers le tableau de bord
@app.route('/')
def home():
    """Redirige vers le tableau de bord approprié selon le rôle."""
    from flask import g
    if g.user:
        return redirect(url_for('dashboard'))
    return redirect(url_for('auth.login'))

# Tableau de bord
@app.route('/dashboard')
@login_required
def dashboard():
    """Affiche le tableau de bord selon le rôle de l'utilisateur."""
    from src.models import Client, Compte, Operation, StatutCompte
    from sqlalchemy import func
    from sqlalchemy.orm import joinedload
    from datetime import datetime
    
    session = obtenir_session()
    
    # Statistiques générales
    # Admin voit toutes les statistiques, Opérateur voit uniquement ses opérations
    total_operations_query = session.query(Operation)
    if g.user.role.value == 'operateur':
        total_operations_query = total_operations_query.filter(Operation.utilisateur_id == g.user.id)
    
    stats = {
        'total_clients': session.query(Client).count(),
        'total_comptes': session.query(Compte).count(),
        'comptes_actifs': session.query(Compte).filter_by(statut=StatutCompte.ACTIF).count(),
        'total_operations': total_operations_query.count(),
        'solde_total': session.query(func.sum(Compte.solde)).scalar() or 0
    }
    
    # Dernières opérations (5 plus récentes) avec eager loading du compte et utilisateur
    # Admin voit toutes les opérations, Opérateur voit uniquement les siennes
    query = session.query(Operation)\
        .options(joinedload(Operation.compte), joinedload(Operation.utilisateur))
    
    if g.user.role.value == 'operateur':
        # Filtrer uniquement les opérations de cet utilisateur
        query = query.filter(Operation.utilisateur_id == g.user.id)
    
    dernieres_operations = query\
        .order_by(Operation.date_operation.desc())\
        .limit(5)\
        .all()
    
    # Rendre le template avant de fermer la session
    result = render_template('dashboard.html', stats=stats, operations=dernieres_operations)
    session.close()
    
    return result
# Endpoint de santé
@app.route('/health')
def health():
    """Endpoint de santé de l'application"""
    return "OK", 200


# Panic page shown to blocked users (returns 503)
@app.route('/panic')
def panic():
    """Human-friendly panic/status page.

    - Accessible at all times.
    - When `maintenance.panic_mode` is enabled, returns HTTP 503 and shows the panic message.
    - When disabled, returns HTTP 200 and shows a neutral status message (can be configured via policy `maintenance.panic_public_message`).
    """
    from src.policy_helpers import get_policy_bool
    from src.policy import get_policy

    active = get_policy_bool('maintenance.panic_mode', default=False)
    if active:
        message = get_policy('maintenance.panic_message', default="Le site est en mode panique. Toutes les opérations sont suspendues.")
        status = 503
    else:
        message = get_policy('maintenance.panic_public_message', default="Aucune alerte active — cette page affiche l'état du service.")
        status = 200
    return render_template('panic.html', message=message, active=active), status


@app.route('/panic/bypass', methods=['POST'])
def panic_bypass():
    """Set a per-session bypass for admins so they are not shown the panic modal on every page.

    Only an authenticated admin or superadmin may set this.
    """
    from flask import session, abort, jsonify
    from src.auth import login_required

    # Require login and role check
    # We apply authorization inline so we can return 403 for non-admins
    if not getattr(g, 'user', None):
        abort(401)
    if not getattr(g.user, 'role', None) or g.user.role.value not in ['admin', 'superadmin']:
        abort(403)

    session['panic_bypass'] = True
    return jsonify({'ok': True})

# Remove revealing server headers (e.g., Server, X-Powered-By) from responses
@app.after_request
def strip_server_headers(response):
    """Strip or obfuscate server and framework headers to reduce fingerprinting."""
    # Common headers that may reveal implementation/version details
    for header in ('Server', 'X-Powered-By', 'X-Generator', 'Server-Timing'):
        if header in response.headers:
            response.headers.pop(header, None)
    return response


# verifier la connexion a la base de données
## if FLASK_ENV == 'development': afficher le message de connexion a la base de données
# if app.config['FLASK_ENV'] == 'development':
#     @app.route('/verifier-connexion')
#     def verifier_connexion_endpoint():
#         """Endpoint pour vérifier la connexion à la base de données"""
#         if verifier_connexion():
#             return {"message": "Connexion à la base de données réussie"}, 200
#         else:
#             return {"message": "Échec de la connexion à la base de données"}, 500









# Démarrer l'application Flask
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)