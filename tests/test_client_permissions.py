import unittest
import sys
import os
from passlib.hash import bcrypt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import app
from src.db import obtenir_session
from src.models import Utilisateur, RoleUtilisateur, Client, Journal, StatutClient


class TestClientPermissions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        session = obtenir_session()
        op = session.query(Utilisateur).filter_by(nom_utilisateur='op_test').first()
        if not op:
            op = Utilisateur(nom_utilisateur='op_test', mot_de_passe_hash=bcrypt.hash('op123'), role=RoleUtilisateur.OPERATEUR)
            session.add(op)
            session.commit()
        session.close()

    def setUp(self):
        self.client = app.test_client()
        # login as operator
        self.client.post('/auth/login', data={'username': 'op_test', 'password': 'op123'})

    def test_suspend_logs_access_refuse(self):
        session = obtenir_session()
        c = Client(nom='PermTest', prenom='User', cin='PERM001', telephone='000', statut=StatutClient.ACTIF)
        session.add(c)
        session.commit()
        client_id = c.id

        # Attempt suspend (operator shouldn't have suspend permission)
        response = self.client.post(f'/clients/{client_id}/desactiver', data={'statut': 'suspendu'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'permission insuffisante', response.data)

        # Check audit log for ACCES_REFUSE
        session.expire_all()
        audit = session.query(Journal).filter_by(action='ACCES_REFUSE').order_by(Journal.id.desc()).first()
        self.assertIsNotNone(audit)
        self.assertIn('suspend', (audit.details or ''))

        # cleanup
        client = session.query(Client).get(client_id)
        if client:
            session.delete(client)
            session.commit()
        session.close()


if __name__ == '__main__':
    unittest.main()
