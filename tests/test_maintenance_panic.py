from src.app import app
from src.db import obtenir_session
from src.models import Client, Compte, StatutCompte, StatutClient, Utilisateur
from src.policy import set_policy, invalidate_cache
import secrets
from unittest.mock import patch


def create_closed_account():
    session = obtenir_session()
    try:
        # Create a valid client (required fields)
        unique = secrets.token_urlsafe(6)
        client = Client(nom='PanicTest', prenom='Auto', cin=f'PANIC{unique}', telephone='0000000000', email='panic@example.test', statut=StatutClient.ACTIF)
        session.add(client)
        session.flush()
        from src.models import gen_numero_compte
        compte = Compte(numero_compte=gen_numero_compte(), client_id=client.id, solde=0, statut=StatutCompte.FERME)
        session.add(compte)
        session.commit()
        return client.id, compte.id
    finally:
        session.close()


def get_user_id(username):
    session = obtenir_session()
    try:
        u = session.query(Utilisateur).filter_by(nom_utilisateur=username).first()
        return u.id if u else None
    finally:
        session.close()


def test_panic_blocks_non_admin_writes():
    with patch('src.policy_helpers.get_policy_bool') as mock_bool:
        mock_bool.side_effect = lambda k, default=False: True if k == 'maintenance.panic_mode' else default

        client_app = app.test_client()
        client_id, compte_id = create_closed_account()

        # Simulate a non-admin logged in (operateur)
        op_id = get_user_id('operateur')
        with client_app.session_transaction() as sess:
            sess['user_id'] = op_id

        # Disable CSRF fallback to avoid 400 from simple_csrf_protect
        app.config['WTF_CSRF_ENABLED'] = False

        from src.policy_helpers import get_policy_bool
        assert get_policy_bool('maintenance.panic_mode') is True

        resp = client_app.post(f'/accounts/{compte_id}/reopen')
        assert resp.status_code == 503

        app.config['WTF_CSRF_ENABLED'] = True


def test_panic_allows_admin_writes():
    with patch('src.policy_helpers.get_policy_bool') as mock_bool:
        mock_bool.side_effect = lambda k, default=False: True if k == 'maintenance.panic_mode' else default

        client_app = app.test_client()
        client_id, compte_id = create_closed_account()

        admin_id = get_user_id('admin')
        with client_app.session_transaction() as sess:
            sess['user_id'] = admin_id

        # Disable CSRF fallback to avoid 400 from simple_csrf_protect
        app.config['WTF_CSRF_ENABLED'] = False

        # Admin should be able to perform the reopen
        resp = client_app.post(f'/accounts/{compte_id}/reopen', follow_redirects=True)
        assert resp.status_code == 200

        app.config['WTF_CSRF_ENABLED'] = True