from src.db import obtenir_session
from src.policy import invalidate_cache

def login(client):
    # get csrf token
    resp = client.get('/auth/login')
    # CSRF is optional for tests, but include if needed
    resp = client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    assert resp.status_code == 200


def test_edit_policy_via_form(client):
    # login as admin
    login(client)
    session = obtenir_session()
    try:
        # ensure initial value is 43
        p = session.query(__import__('src.models', fromlist=['Politique']).Politique).filter_by(cle='velocity.retrait.max_par_minute').first()
        old = p.valeur
        new_value = '55' if old != '55' else '56'
        resp = client.post('/admin/policies/velocity.retrait.max_par_minute', data={'value': new_value, 'type': 'int', 'description': 'test edit', 'comment': 'test'}, follow_redirects=True)
        assert resp.status_code == 200
        # reload from DB
        session.expire_all()
        p = session.query(__import__('src.models', fromlist=['Politique']).Politique).filter_by(cle='velocity.retrait.max_par_minute').first()
        assert p.valeur == new_value
    finally:
        session.close()
        invalidate_cache()
