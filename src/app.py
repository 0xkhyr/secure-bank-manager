"""
app.py - Application Flask principale

Point d'entrée de l'application bancaire.
Configure Flask, initialise la base de données et définit toutes les routes.
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

# Créer l'application Flask
# On spécifie les dossiers templates et static car app.py est dans src/
app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Configuration (utilise la classe Config centralisée)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['DATABASE_PATH'] = Config.DATABASE_PATH
app.config['DEVISE'] = Config.DEVISE

# Session cookie hardening
# These values can be controlled via environment variables documented in README
app.config['SESSION_COOKIE_SECURE'] = Config.SESSION_COOKIE_SECURE
app.config['SESSION_COOKIE_HTTPONLY'] = Config.SESSION_COOKIE_HTTPONLY
app.config['SESSION_COOKIE_SAMESITE'] = Config.SESSION_COOKIE_SAMESITE

# Custom Jinja filter to decode JSON properly
@app.template_filter('decode_json')
def decode_json_filter(json_string):
    """Decode JSON string and return it properly formatted with UTF-8"""
    if not json_string:
        return '-'
    try:
        # Parse JSON and dump it again with ensure_ascii=False to show UTF-8
        data = json.loads(json_string)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except:
        return json_string

# Custom Jinja filter to convert UTC to local time (Tunisia UTC+1)
@app.template_filter('to_local_time')
def to_local_time_filter(utc_datetime):
    """Convert UTC datetime to Tunisia local time (UTC+1)."""
    if utc_datetime:
        from datetime import timedelta
        return utc_datetime + timedelta(hours=Config.TIMEZONE_OFFSET_HOURS)
    return None

import secrets

# Add datetime.now as a global function in Jinja2 and expose CSRF token helper
@app.context_processor
def inject_now():
    """Make datetime.now(), timedelta and csrf_token available in all templates."""
    from datetime import datetime, timedelta

    def generate_csrf_token():
        # Persist a csrf token per session
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


# Inject pending approbations count for admins (used to display nav badge)
@app.context_processor
def inject_pending_approbations():
    from flask import g
    try:
        if not getattr(g, 'user', None):
            return {}
        if g.user.role.value not in ['admin', 'superadmin']:
            return {}
        # Use a temporary non-scoped session to avoid interfering with request-scoped sessions
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

# Initialize CSRF protection (Flask-WTF) if available
try:
    from flask_wtf import CSRFProtect
    csrf = CSRFProtect(app)
except Exception:
    # Fallback to a simple in-app CSRF implementation if Flask-WTF is not installed
    csrf = None

# If Flask-WTF isn't available, enforce CSRF checks manually for unsafe methods
if csrf is None:
    @app.before_request
    def simple_csrf_protect():
        # Local imports to avoid NameErrors
        from flask import request, abort
        # Only check for unsafe methods
        # Allow tests to disable CSRF fallback via app config
        if app.config.get('WTF_CSRF_ENABLED') is False:
            return

        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return
        # Skip static assets
        if request.path.startswith(app.static_url_path):
            return
        from flask import session
        token = session.get('csrf_token')
        if not token:
            # No token in session -> reject
            abort(400)
        # Check form token or header
        form_token = request.form.get('csrf_token')
        header_token = request.headers.get('X-CSRF-Token')
        if form_token == token or header_token == token:
            return
        abort(400)


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