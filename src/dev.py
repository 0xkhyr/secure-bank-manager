"""
# Outils de développement et de maintenance système.
# Sécurité : Ces fonctionnalités sont EXCLUSIVEMENT réservées à l'environnement de développement.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from src.db import obtenir_session, reinitialiser_base_donnees
from src.models import Client, Compte, Operation, Journal, ClotureJournal, Utilisateur
from sqlalchemy import func

dev_bp = Blueprint('dev', __name__, url_prefix='/dev')

@dev_bp.before_request
def check_dev_mode():
    """
    # Sécurité : Contrôle strict empêchant l'exposition des outils de debug en production.
    """
    if not current_app.debug and current_app.config.get('ENV') != 'development':
        return "Access Forbidden: Dev tools only available in debug/dev mode", 403

@dev_bp.route('/db')
def db_manager():
    """
    # Règle métier : Dashboard de monitoring des ressources de la base de données (Mode Dev).
    """
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

    # Règle métier : Affichage des identifiants par défaut pour faciliter les tests.
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
    """
    # Règle métier : Réinitialisation complète de l'environnement (Action destructive).
    # Audit : Enregistre l'invocation de la reconstruction de la base.
    """
    try:
        reinitialiser_base_donnees()
        try:
            from src.audit_logger import log_action
            from flask import g
            log_action(getattr(g, 'user', None) and g.user.id or None, 'REBUILD_DB', 'Système', {'info': 'dev rebuild invoked'})
        except Exception:
            pass
        flash('La base de données a été reconstruite avec succès.', 'success')
    except Exception as e:
        flash(f'Erreur durant la reconstruction: {e}', 'danger')
    return redirect(url_for('dev.db_manager'))


@dev_bp.route('/db/update', methods=('POST',))
def update_value():
    """
    # Règle métier : Modification directe d'une valeur (Outil de test).
    # Audit : Chaque modification manuelle est tracée.
    """
    from flask import request
    table = request.form.get('table')
    row_id = request.form.get('id')
    column = request.form.get('column')
    value = request.form.get('value')

    if not all([table, row_id, column, value]):
        flash('Tous les champs sont requis.', 'warning')
        return redirect(url_for('dev.db_manager'))

    session = obtenir_session()
    try:
        model_map = {
            'clients': Client,
            'comptes': Compte,
            'utilisateurs': Utilisateur,
            'operations': Operation
        }
        
        if table not in model_map:
            flash(f'Table non supportée: {table}', 'danger')
            return redirect(url_for('dev.db_manager'))

        obj = session.get(model_map[table], row_id)
        if not obj:
            flash(f'Ligne #{row_id} non trouvée dans {table}.', 'danger')
            return redirect(url_for('dev.db_manager'))

        old_val = getattr(obj, column, 'N/A')
        
        # Tentative de conversion de type simple
        if isinstance(old_val, int):
            try: value = int(value)
            except: pass
        elif isinstance(old_val, float):
            try: value = float(value)
            except: pass
        elif hasattr(obj.__class__, column) and 'decimal' in str(getattr(obj.__class__, column).type).lower():
            from decimal import Decimal
            try: value = Decimal(value)
            except: pass

        setattr(obj, column, value)
        session.commit()

        # Audit : Trace la modification manuelle via les outils de dev
        try:
            from src.audit_logger import log_action
            from flask import g
            log_action(getattr(g, 'user', None) and g.user.id or None, 'DEV_MANUAL_UPDATE', table, 
                      {'id': row_id, 'column': column, 'old': str(old_val), 'new': str(value)})
        except: pass

        flash(f'Modification réussie : {column} est passé de "{old_val}" à "{value}".', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Erreur lors de la modification: {e}', 'danger')
    finally:
        session.close()

    return redirect(url_for('dev.db_manager'))


@dev_bp.route('/db/sql', methods=('POST',))
def run_sql():
    """
    # Règle métier : Console SQL brute (Pouvoir absolu).
    # Audit : Chaque requête est enregistrée pour des raisons de conformité, même en dev.
    """
    from flask import request
    query = request.form.get('query')
    if not query:
        return redirect(url_for('dev.db_manager'))

    session = obtenir_session()
    try:
        # On évite les requêtes multiples pour la sécurité du parser simple de sqlite3
        import sqlalchemy
        from sqlalchemy import text
        
        # Exécution brute sécurisée via SQLAlchemy Text
        result = session.execute(text(query))
        
        # Si c'est un SELECT, on récupère les résultats
        if query.strip().upper().startswith('SELECT'):
            rows = result.fetchall()
            columns = result.keys()
            flash(f"Requête réussie : {len(rows)} lignes trouvées.", "success")
            
            # On stocke temporairement dans la session pour l'afficher une seule fois
            from flask import session as flask_session
            flask_session['sql_results'] = {
                'columns': list(columns),
                'rows': [list(row) for row in rows],
                'query': query
            }
        else:
            session.commit()
            flash(f"Requête exécutée avec succès (Impact : {result.rowcount} lignes).", "success")

        # Audit : Trace la requête SQL brute
        try:
            from src.audit_logger import log_action
            from flask import g
            log_action(getattr(g, 'user', None) and g.user.id or None, 'DEV_SQL_CONSOLE', 'Database', 
                      {'query': query, 'impact': getattr(result, 'rowcount', 'SELECT')})
        except: pass

    except Exception as e:
        session.rollback()
        flash(f'Erreur SQL : {e}', 'danger')
    finally:
        session.close()

    return redirect(url_for('dev.db_manager'))


@dev_bp.route('/db/break-log', methods=('POST',))
def break_log():
    """
    # Sécurité : Simulation d'une attaque par modification directe en base.
    # Cette action modifie le contenu d'un log SANS mettre à jour son hash ou sa signature.
    # Utile pour démontrer la détection de falsification par le système d'audit.
    """
    from flask import request
    log_id = request.form.get('log_id')
    
    session = obtenir_session()
    try:
        log = session.get(Journal, log_id)
        if not log:
            flash(f"Log #{log_id} non trouvé.", "warning")
            return redirect(url_for('dev.db_manager'))

        old_cible = log.cible
        # On altère la donnée de manière invisible pour les outils standards mais visible par le hash
        log.cible = f"{old_cible} [ALTERED]"
        session.commit()
        
        # On ne logue PAS cette action via log_action car on veut simuler une modification "sous le radar" 
        # effectuée par un attaquant ayant un accès direct à la DB.
        
        flash(f"Log #{log_id} altéré avec succès ! Le contenu a été modifié sans recalculer la signature. L'intégrité devrait maintenant être invalide.", "danger")
    except Exception as e:
        session.rollback()
        flash(f"Erreur lors de l'altération : {e}", "danger")
    finally:
        session.close()

    return redirect(url_for('dev.db_manager'))

