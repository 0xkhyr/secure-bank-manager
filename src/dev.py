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

    # Assemble dev user credentials for display (development-only helpers)
    import os
    dev_users = [
        {
            'username': 'superadmin',
            'password': os.getenv('DEV_SUPERADMIN_PW') or 'superadmin123 (default if using scripts/seed_dev_users.py)'
        },
        {
            'username': 'admin',
            'password': os.getenv('DEV_ADMIN_PW') or 'admin123 (default if using scripts/seed_dev_users.py)'
        },
        {
            'username': 'operateur',
            'password': os.getenv('DEV_OPER_PW') or 'operateur123 (default if using scripts/seed_dev_users.py)'
        }
    ]

    return render_template('dev/db.html', stats=stats, dev_users=dev_users)


@dev_bp.route('/db/rebuild', methods=('POST',))
def rebuild_db():
    """Rebuild the development database (DESCTRUCTIVE)."""
    # Only available in debug/dev mode due to check in before_request
    try:
        # Reinitialize the DB schema and seed default users
        reinitialiser_base_donnees()
        try:
            from src.audit_logger import log_action
            # log who triggered it if available; silent if not
            from flask import g
            log_action(getattr(g, 'user', None) and g.user.id or None, 'REBUILD_DB', 'Système', {'info': 'dev rebuild invoked'})
        except Exception:
            pass
        flash('La base de données a été reconstruite avec succès.', 'success')
    except Exception as e:
        flash(f'Erreur durant la reconstruction: {e}', 'danger')
    return redirect(url_for('dev.db_manager'))

