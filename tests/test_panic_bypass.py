from src.app import app
from src.policy import set_policy, invalidate_cache
from src.db import obtenir_session
from src.models import Utilisateur


def test_admin_sets_panic_bypass_and_modal_no_longer_shown():
    app.config['WTF_CSRF_ENABLED'] = False
    set_policy('maintenance.panic_mode', 'true', type_='bool', comment='test')
    invalidate_cache()

    client = app.test_client()
    session = obtenir_session()
    try:
        admin = session.query(Utilisateur).filter_by(nom_utilisateur='admin').first()
        admin_id = admin.id
    finally:
        session.close()

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id

    # Initially modal shown on dashboard
    resp = client.get('/dashboard')
    assert b'id="panicModal"' in resp.data

    # Post bypass
    resp2 = client.post('/panic/bypass')
    assert resp2.status_code == 200

    # Subsequent page should not show modal
    resp3 = client.get('/dashboard')
    assert b'id="panicModal"' not in resp3.data

    # cleanup
    set_policy('maintenance.panic_mode', 'false', type_='bool', comment='test')
    invalidate_cache()


def test_non_admin_cannot_set_bypass():
    app.config['WTF_CSRF_ENABLED'] = False
    set_policy('maintenance.panic_mode', 'true', type_='bool', comment='test')
    invalidate_cache()

    client = app.test_client()
    session = obtenir_session()
    try:
        op = session.query(Utilisateur).filter_by(role='operateur').first()
    except Exception:
        # Fallback: pick any non-admin; create if necessary
        op = session.query(Utilisateur).filter_by(nom_utilisateur='op_test').first()
    finally:
        session.close()

    with client.session_transaction() as sess:
        sess['user_id'] = op.id if op else None

    resp = client.post('/panic/bypass')
    assert resp.status_code in (401,403)

    # cleanup
    set_policy('maintenance.panic_mode', 'false', type_='bool', comment='test')
    invalidate_cache()