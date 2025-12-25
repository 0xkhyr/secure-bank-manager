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

@dev_bp.route('/verify/preview/table')
def verify_preview_table():
    """Static preview: table style for verification UI"""
    return render_template('dev/verify_preview_table.html')

@dev_bp.route('/verify/preview/chain')
def verify_preview_chain():
    """Preview selector for chain visualization options"""
    return render_template('dev/verify_preview_chain.html')

@dev_bp.route('/verify/preview/chain/option1')
def verify_preview_chain_option1():
    """Static preview: chain visualization - Option 1 (Horizontal compact)"""
    return render_template('dev/verify_preview_chain_option1.html')

@dev_bp.route('/verify/preview/chain/option2')
def verify_preview_chain_option2():
    """Static preview: chain visualization - Option 2 (Vertical timeline)"""
    return render_template('dev/verify_preview_chain_option2.html')

@dev_bp.route('/verify/preview/chain/option3')
def verify_preview_chain_option3():
    """Static preview: chain visualization - Option 3 (Grouped cards)"""
    return render_template('dev/verify_preview_chain_option3.html')

@dev_bp.route('/verify/preview/chain/option4')
def verify_preview_chain_option4():
    """Static preview: chain visualization - Option 4 (Linked chain view)"""
    return render_template('dev/verify_preview_chain_option4.html')

@dev_bp.route('/verify/preview/chain/option5')
def verify_preview_chain_option5():
    """Static preview: chain visualization - Option 5 (Vertical chain with details)"""
    return render_template('dev/verify_preview_chain_option5.html')

# @dev_bp.route('/verify/preview/chain/option6')
# def verify_preview_chain_option6():
#     """Static preview: chain visualization - Option 6 (Block headers)"""
#     return render_template('dev/verify_preview_chain_option6.html')

@dev_bp.route('/verify/preview/chain/option7')
def verify_preview_chain_option7():
    """Static preview: chain visualization - Option 7 (Stacked blocks)"""
    return render_template('dev/verify_preview_chain_option7.html')
@dev_bp.route('/verify/preview/chain/option6')
def verify_preview_chain_option6():
    """Static preview: chain visualization - Option 6 (Minimal audit chain)"""
    return render_template('dev/verify_preview_chain_option6_minimal.html')
@dev_bp.route('/verify/preview/heatmap')
def verify_preview_heatmap():
    """Static preview: heatmap"""
    return render_template('dev/verify_preview_heatmap.html')

@dev_bp.route('/verify/preview/playbook')
def verify_preview_playbook():
    """Static preview: remediation playbook"""
    return render_template('dev/verify_preview_playbook.html')

@dev_bp.route('/verify/preview/diff')
def verify_preview_diff():
    """Static preview: diff viewer"""
    return render_template('dev/verify_preview_diff.html')

@dev_bp.route('/db/rebuild', methods=('POST',))
def rebuild_db():
    """Réinitialise complètement la base de données."""
    try:
        reinitialiser_base_donnees()
        flash('Base de données reconstruite avec succès (Admin par défaut : superadmin / admin / operateur).', 'success')
    except Exception as e:
        flash(f'Erreur lors de la reconstruction : {e}', 'danger')
    return redirect(url_for('dev.db_manager'))
