import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db import obtenir_session, initialiser_base_donnees, reinitialiser_base_donnees
from src.models import Utilisateur, RoleUtilisateur, Politique
from src.app import app


class TestPoliciesValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        # Ensure DB seeded
        reinitialiser_base_donnees()
        initialiser_base_donnees()

        session = obtenir_session()
        admin = session.query(Utilisateur).filter_by(nom_utilisateur='policy_admin').first()
        if not admin:
            # Policy management tests use SUPERADMIN by default under the new fine-grained model
            admin = Utilisateur(nom_utilisateur='policy_admin', mot_de_passe_hash='x', role=RoleUtilisateur.SUPERADMIN)
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

    def test_invalid_integer_is_rejected(self):
        resp = self.client.post('/admin/policies/create', data={'key': 'mot_de_passe.duree_validite_jours', 'value': 'abc', 'type': 'int'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Erreur de validation', resp.data)

    def test_missing_comment_for_critical_key(self):
        # 'retrait.limite_journaliere' is in changement_politique.requiert_approbation by default
        resp = self.client.post('/admin/policies/create', data={'key': 'retrait.limite_journaliere', 'value': '5000', 'type': 'int'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Erreur de validation', resp.data)

    def test_bool_parsing_and_storage(self):
        resp = self.client.post('/admin/policies/create', data={'key': 'velocity.actif', 'value': 'True', 'type': 'bool', 'comment': 'test'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        session = obtenir_session()
        try:
            p = session.query(Politique).filter_by(cle='velocity.actif').first()
            self.assertIsNotNone(p)
            self.assertEqual(p.type, 'bool')
            self.assertIn(p.valeur.lower(), ('true', 'false'))
        finally:
            session.close()


if __name__ == '__main__':
    unittest.main()
