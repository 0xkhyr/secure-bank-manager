import unittest
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import app
from src.db import obtenir_session
from src.models import Utilisateur, RoleUtilisateur, Journal
from src.config import Config
from passlib.hash import bcrypt

class TestUsersListLockTooltip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True

    def setUp(self):
        self.client = app.test_client()
        self.session = obtenir_session()

    def tearDown(self):
        # Clean any test users
        u = self.session.query(Utilisateur).filter_by(nom_utilisateur='tooltip_user').first()
        if u:
            self.session.delete(u)
            self.session.commit()
        self.session.close()

    def test_admin_sees_lock_tooltip(self):
        # create user locked
        unlock = datetime.utcnow() + timedelta(minutes=60)
        user = Utilisateur(nom_utilisateur='tooltip_user', mot_de_passe_hash=bcrypt.hash('pw'), role=RoleUtilisateur.OPERATEUR)
        user.verrouille_jusqu_a = unlock
        user.verrouille_raison = 'Investigation en cours'
        self.session.add(user)
        self.session.commit()

        # Mark session as admin (avoid reliance on login flow in tests)
        admin = self.session.query(Utilisateur).filter_by(nom_utilisateur='admin').first()
        with self.client.session_transaction() as sess:
            sess['user_id'] = admin.id
            sess['last_activity'] = datetime.utcnow().isoformat()

        res = self.client.get('/users/', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        # The page contains a tooltip attribute with the reason text for admins
        self.assertIn(b'Investigation', res.data)

if __name__ == '__main__':
    unittest.main()
