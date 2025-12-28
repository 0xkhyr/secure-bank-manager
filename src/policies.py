from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash
from flask import g
from src.auth import admin_required
from src.db import obtenir_session
from src.models import Politique, HistoriquePolitique
from src.policy import get_policy, set_policy, invalidate_cache
from src.audit_logger import log_action
from src.auth import permission_required

policies_bp = Blueprint('policies', __name__, url_prefix='/admin/policies')


@policies_bp.route('/')
@permission_required('policies.view')
def index():
    session = obtenir_session()
    try:
        policies = session.query(Politique).order_by(Politique.cle).all()
        return render_template('admin/policies.html', policies=policies)
    finally:
        session.close()


@policies_bp.route('/<key>', methods=['GET', 'POST'])
@permission_required('policies.view')
def edit(key):
    session = obtenir_session()
    try:
        policy = session.query(Politique).filter_by(cle=key).first()
        if request.method == 'POST':
            # Require explicit edit permission for POST
            from src.auth import has_permission
            from src.policy import invalidate_cache as invalidate_policy_cache
            if not has_permission(g.user, 'policies.edit'):
                flash('Accès refusé : privilèges insuffisants pour modifier.', 'danger')
                return redirect(url_for('policies.index'))

            value = request.form.get('value')
            type_ = request.form.get('type') or 'string'
            desc = request.form.get('description')
            comment = request.form.get('comment')
            # The 'active' switch: unchecked checkboxes are not sent in the form
            active_present = 'active' in request.form
            desired_active = bool(active_present)

            try:
                # Update value/type/description via set_policy (handles validation + history)
                set_policy(key, value, type_=type_, description=desc, changed_by= g.user.id, comment=comment)
            except ValueError as e:
                flash(f"Erreur de validation : {e}", 'danger')
                return redirect(url_for('policies.edit', key=key))
            except Exception as e:
                flash('Erreur lors de la mise à jour.', 'danger')
                return redirect(url_for('policies.edit', key=key))

            # Refresh the policy from DB in our session to adjust 'active' if needed
            session.refresh(session.query(Politique).filter_by(cle=key).first())
            politique = session.query(Politique).filter_by(cle=key).first()
            if politique and politique.active != desired_active:
                politique.active = desired_active
                session.commit()
                # Audit the toggle so we have a record
                log_action(g.user.id, 'TOGGLE_POLITIQUE', politique.cle, {'active': politique.active})
                invalidate_policy_cache()

            flash('Politique mise à jour.', 'success')
            return redirect(url_for('policies.index'))
        history = session.query(HistoriquePolitique).filter_by(cle=key).order_by(HistoriquePolitique.modifie_le.desc()).limit(20).all()
        # Enrich history with usernames for display
        user_ids = [h.modifie_par for h in history if h.modifie_par]
        users_map = {}
        if user_ids:
            from src.models import Utilisateur
            users = session.query(Utilisateur).filter(Utilisateur.id.in_(user_ids)).all()
            users_map = {u.id: u.nom_utilisateur for u in users}
        return render_template('admin/policies_edit.html', policy=policy, history=history, users_map=users_map)
    finally:
        session.close()


@policies_bp.route('/create', methods=['GET','POST'])
@permission_required('policies.create')
def create():
    # GET -> render create form
    if request.method == 'GET':
        return render_template('admin/policies_create.html')

    # POST -> process creation
    key = request.form.get('key')
    value = request.form.get('value')
    type_ = request.form.get('type') or 'string'
    desc = request.form.get('description')
    comment = request.form.get('comment')
    try:
        set_policy(key, value, type_=type_, description=desc, changed_by=g.user.id, comment=comment)
    except ValueError as e:
        flash(f"Erreur de validation : {e}", 'danger')
        # re-render form with user input preserved
        return render_template('admin/policies_create.html')
    except Exception:
        flash('Erreur lors de la création de la politique.', 'danger')
        return render_template('admin/policies_create.html')

    # Audit explicite
    log_action(g.user.id, 'CHANGEMENT_POLITIQUE', key, {"nouveau": value, "type": type_, "commentaire": comment})
    flash('Politique créée.', 'success')
    return redirect(url_for('policies.index'))


@policies_bp.route('/toggle/<int:id>', methods=['POST'])
@permission_required('policies.toggle')
def toggle(id):
    session = obtenir_session()
    try:
        policy = session.query(Politique).get(id)
        if not policy:
            flash('Politique introuvable', 'danger')
            return redirect(url_for('policies.index'))
        policy.active = not policy.active
        session.commit()
        log_action(g.user.id, 'TOGGLE_POLITIQUE', policy.cle, {'active': policy.active})
        invalidate_cache()
        flash('État mis à jour.', 'success')
        return redirect(url_for('policies.index'))
    finally:
        session.close()


@policies_bp.route('/apply', methods=['POST'])
@permission_required('policies.apply')
def apply_now():
    invalidate_cache()
    flash('Cache invalidé et politiques rechargées.', 'success')
    return redirect(url_for('policies.index'))

