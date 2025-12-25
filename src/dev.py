from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from src.db import obtenir_session, reinitialiser_base_donnees
from src.models import Client, Compte, Operation, Journal, ClotureJournal, Utilisateur
from sqlalchemy import func

dev_bp = Blueprint('dev', __name__, url_prefix='/dev')

@dev_bp.before_request
def check_dev_mode():
    if not current_app.debug and current_app.config.get('ENV') != 'development':
        return "Access Forbidden: Dev tools only available in debug/dev mode", 403

@dev_bp.route('/db')
def db_manager():
    """Affiche les statistiques et outils de la base de données."""
    session = obtenir_session()
    stats = {
        'clients': session.query(Client).count(),
        'comptes': session.query(Compte).count(),
        'operations': session.query(Operation).count(),
        'journaux': session.query(Journal).count(),
        'clotures': session.query(ClotureJournal).count(),
        'utilisateurs': session.query(Utilisateur).count()
    }
    session.close()
    return render_template('dev/db.html', stats=stats)

