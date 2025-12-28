from src.app import app
from src.policy import set_policy, invalidate_cache


def test_panic_page_shows_public_message_when_inactive():
    set_policy('maintenance.panic_mode', 'false', type_='bool', comment='test')
    set_policy('maintenance.panic_public_message', 'Public info: all good', type_='string', comment='test')
    invalidate_cache()

    client = app.test_client()
    resp = client.get('/panic')
    assert resp.status_code == 200
    assert b'Public info: all good' in resp.data
    assert b'name="robots" content="noindex' in resp.data

    # cleanup: reset to a harmless non-empty default (empty values are rejected by validation)
    set_policy('maintenance.panic_public_message', 'Aucune alerte active — cette page affiche l\'état du service.', type_='string', comment='test')
    invalidate_cache()


def test_panic_page_still_503_when_active_and_shows_admin_link():
    set_policy('maintenance.panic_mode', 'true', type_='bool', comment='test')
    set_policy('maintenance.panic_message', 'Active panic message', type_='string', comment='test')
    invalidate_cache()

    client = app.test_client()
    resp = client.get('/panic')
    assert resp.status_code == 503
    assert b'Active panic message' in resp.data
    # Login link should be present (no bypass token required since login is accessible)
    assert b'href="/auth/login"' in resp.data

    # cleanup
    set_policy('maintenance.panic_mode', 'false', type_='bool', comment='test')
    invalidate_cache()
