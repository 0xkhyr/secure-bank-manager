from src.app import app
from src.policy import set_policy, invalidate_cache
from src.db import obtenir_session
from src.models import Utilisateur


def test_panic_modal_for_anonymous():
    set_policy('maintenance.panic_mode', 'true', type_='bool', comment='test')
    set_policy('maintenance.panic_message', "Panic modal test message", type_='string', comment='test')
    invalidate_cache()

    client = app.test_client()
    resp = client.get('/auth/login')
    assert resp.status_code == 200
    # Login page should not show the panic modal so anonymous users can sign in
    assert b'Panic modal test message' not in resp.data
    assert b'id="panicModal"' not in resp.data
    # Ensure admin-only button not visible
    assert b"Continuer en tant" not in resp.data

    # cleanup
    set_policy('maintenance.panic_mode', 'false', type_='bool', comment='test')
    invalidate_cache()


def test_panic_modal_shows_admin_bypass():
    set_policy('maintenance.panic_mode', 'true', type_='bool', comment='test')
    set_policy('maintenance.panic_message', "Panic modal admin test", type_='string', comment='test')
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

    # follow redirects because logged in user is redirected from /auth/login
    resp = client.get('/auth/login', follow_redirects=True)
    assert resp.status_code == 200
    assert b'Panic modal admin test' in resp.data
    assert b"Continuer en tant" in resp.data

    # cleanup
    set_policy('maintenance.panic_mode', 'false', type_='bool', comment='test')
    invalidate_cache()