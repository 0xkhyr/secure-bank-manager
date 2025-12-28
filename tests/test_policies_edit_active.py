import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import app
from src.db import obtenir_session
from src.models import Politique, Utilisateur, RoleUtilisateur
from src.policy import invalidate_cache

class TestPoliciesEditActive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        session = obtenir_session()
        admin = session.query(Utilisateur).filter_by(nom_utilisateur='policy_admin').first()
        if not admin:
            admin = Utilisateur(nom_utilisateur='policy_admin', mot_de_passe_hash='x', role=RoleUtilisateur.SUPERADMIN)
            session.add(admin)
            session.commit()
        session.close()

    def setUp(self):
        self.client = app.test_client()
        session = obtenir_session()
        admin = session.query(Utilisateur).filter_by(nom_utilisateur='policy_admin').first()
        with self.client.session_transaction() as sess:
            sess['user_id'] = admin.id
        # Ensure policy exists and active
        session = obtenir_session()
        p = session.query(Politique).filter_by(cle='perm.test.active').first()
        if not p:
            p = Politique(cle='perm.test.active', valeur='1', type='int', active=True)
            session.add(p)
            session.commit()
        else:
            p.active = True
            session.commit()
        session.close()
        invalidate_cache()

    def test_unchecking_deactivates_policy(self):
        resp = self.client.post('/admin/policies/perm.test.active', data={'value': '1', 'type': 'int'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        session = obtenir_session()
        p = session.query(Politique).filter_by(cle='perm.test.active').first()
        self.assertFalse(p.active)
        session.close()

    def test_checking_activates_policy(self):
        # First ensure it's deactivated
        session = obtenir_session()
        p = session.query(Politique).filter_by(cle='perm.test.active').first()
        p.active = False
        session.commit()
        session.close()
        invalidate_cache()

        resp = self.client.post('/admin/policies/perm.test.active', data={'value': '1', 'type': 'int', 'active': 'on'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        session = obtenir_session()
        p = session.query(Politique).filter_by(cle='perm.test.active').first()
        self.assertTrue(p.active)
        session.close()

if __name__ == '__main__':
    unittest.main()
