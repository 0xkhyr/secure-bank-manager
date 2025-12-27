import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import app
from src.db import obtenir_session
from src.models import Utilisateur, RoleUtilisateur, Policy

class TestPoliciesAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        session = obtenir_session()
        admin = session.query(Utilisateur).filter_by(nom_utilisateur='policy_admin').first()
        if not admin:
            admin = Utilisateur(nom_utilisateur='policy_admin', mot_de_passe_hash='x', role=RoleUtilisateur.ADMIN)
            session.add(admin)
            session.commit()
        session.close()

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            session = obtenir_session()
            admin = session.query(Utilisateur).filter_by(nom_utilisateur='policy_admin').first()
            sess['user_id'] = admin.id
            session.close()

    def test_create_and_toggle_policy(self):
        session = obtenir_session()
        # Ensure policy not exist
        p = session.query(Policy).filter_by(key='test.policy.x').first()
        if p:
            session.delete(p)
            session.commit()

        # Create via POST
        resp = self.client.post('/admin/policies/create', data={'key':'test.policy.x','value':'123','type':'int'})
        self.assertEqual(resp.status_code, 302)

        p2 = session.query(Policy).filter_by(key='test.policy.x').first()
        self.assertIsNotNone(p2)
        self.assertEqual(p2.value, '123')

        # Toggle
        resp2 = self.client.post(f'/admin/policies/toggle/{p2.id}', follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)
        session.refresh(p2)
        self.assertFalse(p2.active)

        # Cleanup
        session.delete(p2)
        session.commit()
        session.close()

if __name__ == '__main__':
    unittest.main()
