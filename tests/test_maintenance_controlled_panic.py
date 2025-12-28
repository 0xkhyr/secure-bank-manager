from src.app import app
from src.policy import set_policy, invalidate_cache
from src.db import obtenir_session
from src.models import Utilisateur


def test_gets_redirected_to_panic_for_anonymous():
    set_policy('maintenance.panic_mode', 'true', type_='bool', comment='test')
    set_policy('maintenance.panic_message', 'Controlled panic message', type_='string', comment='test')
    invalidate_cache()

    client = app.test_client()

    resp = client.get('/', follow_redirects=False)
    # should redirect to /panic (guard intercepts before view redirect)
    assert resp.status_code in (302, 303)
    assert '/panic' in resp.headers.get('Location', '')

    # cleanup
    set_policy('maintenance.panic_mode', 'false', type_='bool', comment='test')
    invalidate_cache()


def test_panic_page_returns_503_and_shows_message():
    set_policy('maintenance.panic_mode', 'true', type_='bool', comment='test')
    set_policy('maintenance.panic_message', 'Controlled panic message', type_='string', comment='test')
    invalidate_cache()

    client = app.test_client()
    resp = client.get('/panic')
    assert resp.status_code == 503
    assert b'Controlled panic message' in resp.data
    # Modal/overlay should NOT be rendered on the panic page itself
    assert b'id="panicModal"' not in resp.data
    assert b'id="panicOverlay"' not in resp.data

    # cleanup
    set_policy('maintenance.panic_mode', 'false', type_='bool', comment='test')
    invalidate_cache()


def test_modal_shows_on_other_pages_but_not_on_panic():
    set_policy('maintenance.panic_mode', 'true', type_='bool', comment='test')
    set_policy('maintenance.panic_message', 'Controlled panic message', type_='string', comment='test')
    invalidate_cache()

    client = app.test_client()

    # On login page, modal should NOT be present so users can log in
    resp = client.get('/auth/login')
    assert resp.status_code == 200
    assert b'id="panicModal"' not in resp.data

    # On panic page, modal must not be present
    resp2 = client.get('/panic')
    assert resp2.status_code == 503
    assert b'id="panicModal"' not in resp2.data

    # The panic page contains a link allowing admins to reach login (no bypass token required)
    assert b'href="/auth/login"' in resp2.data

    # Visiting the login URL should be allowed
    resp3 = client.get('/auth/login')
    assert resp3.status_code == 200

    # cleanup
    set_policy('maintenance.panic_mode', 'false', type_='bool', comment='test')
    invalidate_cache()

def test_non_admin_post_blocked_with_503():
    set_policy('maintenance.panic_mode', 'true', type_='bool', comment='test')
    set_policy('maintenance.panic_message', 'Controlled panic message', type_='string', comment='test')
    invalidate_cache()

    client = app.test_client()
    # POST to a write endpoint should be blocked with 503 even if resource does not exist
    resp = client.post('/operations/depot/1', data={'montant': '10'})
    assert resp.status_code == 503
    assert b'Controlled panic message' in resp.data

    # cleanup
    set_policy('maintenance.panic_mode', 'false', type_='bool', comment='test')
    invalidate_cache()


def test_auth_login_still_accessible():
    set_policy('maintenance.panic_mode', 'true', type_='bool', comment='test')
    invalidate_cache()

    client = app.test_client()
    resp = client.get('/auth/login')
    assert resp.status_code == 200
    # Login page must not render the panic modal so users (including non-admins) can sign in
    assert b'id="panicModal"' not in resp.data

    # cleanup
    set_policy('maintenance.panic_mode', 'false', type_='bool', comment='test')
    invalidate_cache()


def test_admin_bypass_allows_dashboard():
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

    resp = client.get('/dashboard')
    # admin should be allowed to reach dashboard
    assert resp.status_code == 200

    # cleanup
    set_policy('maintenance.panic_mode', 'false', type_='bool', comment='test')
    invalidate_cache()
