"""
app.py - Application Flask principale

Point d'entrée de l'application bancaire.
Configure Flask, initialise la base de données et définit toutes les routes.
"""

from flask import Flask, redirect, url_for, render_template
from src.db import initialiser_base_donnees, verifier_connexion, obtenir_session
from src.config import Config
from src.auth import auth_bp, login_required
from src.clients import clients_bp
from src.accounts import accounts_bp
from src.operations import operations_bp
from src.audit_logger import audit_bp

# Créer l'application Flask
# On spécifie les dossiers templates et static car app.py est dans src/
app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Configuration (utilise la classe Config centralisée)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['DATABASE_PATH'] = Config.DATABASE_PATH
app.config['DEVISE'] = Config.DEVISE

# Enregistrement des Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(clients_bp)
app.register_blueprint(accounts_bp)
app.register_blueprint(operations_bp)
app.register_blueprint(audit_bp)

# Initialiser la base de données au démarrage
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
    from src.models import Client, Compte, Operation
    from sqlalchemy import func
    from sqlalchemy.orm import joinedload
    
    session = obtenir_session()
    
    # Statistiques générales
    stats = {
        'total_clients': session.query(Client).count(),
        'total_comptes': session.query(Compte).count(),
        'total_operations': session.query(Operation).count(),
        'solde_total': session.query(func.sum(Compte.solde)).scalar() or 0
    }
    
    # Dernières opérations (5 plus récentes) avec eager loading du compte
    dernieres_operations = session.query(Operation)\
        .options(joinedload(Operation.compte))\
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