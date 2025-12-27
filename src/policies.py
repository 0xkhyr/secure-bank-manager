from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash
from flask import g
from src.auth import admin_required
from src.db import obtenir_session
from src.models import Policy, PolicyHistory
from src.policy import get_policy, set_policy, invalidate_cache
from src.audit_logger import log_action

policies_bp = Blueprint('policies', __name__, url_prefix='/admin/policies')


@policies_bp.route('/')
@admin_required
def index():
    session = obtenir_session()
    try:
        policies = session.query(Policy).order_by(Policy.key).all()
        return render_template('admin/policies.html', policies=policies)
    finally:
        session.close()


@policies_bp.route('/<key>', methods=['GET', 'POST'])
@admin_required
def edit(key):
    session = obtenir_session()
    try:
        policy = session.query(Policy).filter_by(key=key).first()
        if request.method == 'POST':
            value = request.form.get('value')
            type_ = request.form.get('type') or 'string'
            desc = request.form.get('description')
            comment = request.form.get('comment')
            set_policy(key, value, type_=type_, description=desc, changed_by= g.user.id, comment=comment)
            flash('Politique mise à jour.', 'success')
            return redirect(url_for('policies.index'))
        history = session.query(PolicyHistory).filter_by(key=key).order_by(PolicyHistory.changed_at.desc()).limit(20).all()
        return render_template('admin/policies_edit.html', policy=policy, history=history)
    finally:
        session.close()


@policies_bp.route('/create', methods=['POST'])
@admin_required
def create():
    key = request.form.get('key')
    value = request.form.get('value')
    type_ = request.form.get('type') or 'string'
    desc = request.form.get('description')
    comment = request.form.get('comment')
    set_policy(key, value, type_=type_, description=desc, changed_by=g.user.id, comment=comment)
    flash('Politique créée.', 'success')
    return redirect(url_for('policies.index'))


@policies_bp.route('/toggle/<int:id>', methods=['POST'])
@admin_required
def toggle(id):
    session = obtenir_session()
    try:
        policy = session.query(Policy).get(id)
        if not policy:
            flash('Policy introuvable', 'danger')
            return redirect(url_for('policies.index'))
        policy.active = not policy.active
        session.commit()
        log_action(g.user.id, 'POLICY_TOGGLE', policy.key, {'active': policy.active})
        invalidate_cache()
        flash('État mis à jour.', 'success')
        return redirect(url_for('policies.index'))
    finally:
        session.close()


@policies_bp.route('/apply', methods=['POST'])
@admin_required
def apply_now():
    invalidate_cache()
    flash('Cache invalidé et politiques rechargées.', 'success')
    return redirect(url_for('policies.index'))
