from src.policy import set_policy, invalidate_cache


from src.app import app


def test_maintenance_banner_shows_on_public_pages():
    set_policy('maintenance.enabled', 'true', type_='bool', comment='test')
    set_policy('maintenance.message', 'Maintenance planifiée: mise à jour à 02:00 UTC.', type_='string', comment='test')
    invalidate_cache()

    client = app.test_client()
    resp = client.get('/auth/login')
    assert resp.status_code == 200
    assert b'Maintenance planifi' in resp.data


def test_maintenance_banner_default_message_when_missing():
    # Ensure disabling doesn't crash templates
    set_policy('maintenance.enabled', 'false', type_='bool', comment='test')
    invalidate_cache()
    client = app.test_client()
    resp = client.get('/auth/login')
    assert resp.status_code == 200
    # Banner should not be present
    assert b'Site en maintenance' not in resp.data
