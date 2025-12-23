import unittest
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import app
from src.db import obtenir_session, reinitialiser_base_donnees
from src.models import Utilisateur, RoleUtilisateur
from passlib.hash import bcrypt

class TestProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        # Ensure test database schema is up-to-date for these tests
        reinitialiser_base_donnees()

    def setUp(self):
        self.client = app.test_client()
        self.session = obtenir_session()
        # Ensure test user exists
        self.user = self.session.query(Utilisateur).filter_by(nom_utilisateur='profile_user').first()
        if self.user:
            self.session.delete(self.user)
            self.session.commit()
        self.user = Utilisateur(nom_utilisateur='profile_user', mot_de_passe_hash=bcrypt.hash('pw12345'), role=RoleUtilisateur.OPERATEUR)
        self.session.add(self.user)
        self.session.commit()

    def tearDown(self):
        u = self.session.query(Utilisateur).filter_by(nom_utilisateur='profile_user').first()
        if u:
            self.session.delete(u)
            self.session.commit()
        self.session.close()

    def test_profile_view_requires_login(self):
        res = self.client.get('/profile', follow_redirects=True)
        self.assertIn(b'Connexion', res.data)

    def test_update_display_name(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user.id
            sess['last_activity'] = datetime.utcnow().isoformat()

        # get csrf token
        resp_get = self.client.get('/profile')
        import re
        m = re.search(r'<meta name="csrf-token" content="([^"]+)">', resp_get.get_data(as_text=True))
        token = m.group(1) if m else None
        res = self.client.post('/profile', data={'action':'update_profile','display_name':'Pierre', 'csrf_token': token}, follow_redirects=True)
        self.assertIn(b'Profil mis', res.data)
        u = self.session.query(Utilisateur).filter_by(id=self.user.id).first()
        self.assertEqual(u.display_name, 'Pierre')

    def test_change_password_success_and_failure(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user.id
            sess['last_activity'] = datetime.utcnow().isoformat()

        # Wrong current password
        resp_get = self.client.get('/profile')
        import re
        m = re.search(r'<meta name="csrf-token" content="([^"]+)">', resp_get.get_data(as_text=True))
        token = m.group(1) if m else None
        res = self.client.post('/profile', data={'action':'change_password','current_password':'wrong','new_password':'newpass','confirm_password':'newpass', 'csrf_token': token}, follow_redirects=True)
        self.assertIn(b'Mot de passe actuel incorrect', res.data)

        # Correct current password, but weak new password
        resp_get = self.client.get('/profile')
        m = re.search(r'<meta name="csrf-token" content="([^"]+)">', resp_get.get_data(as_text=True))
        token = m.group(1) if m else None
        res = self.client.post('/profile', data={'action':'change_password','current_password':'pw12345','new_password':'123','confirm_password':'123', 'csrf_token': token}, follow_redirects=True)
        self.assertIn(b'nouveau mot de passe', res.data)

        # Correct change
        resp_get = self.client.get('/profile')
        m = re.search(r'<meta name="csrf-token" content="([^"]+)">', resp_get.get_data(as_text=True))
        token = m.group(1) if m else None
        res = self.client.post('/profile', data={'action':'change_password','current_password':'pw12345','new_password':'newsecure','confirm_password':'newsecure', 'csrf_token': token}, follow_redirects=True)
        self.assertIn(b'Mot de passe modifi', res.data)

if __name__ == '__main__':
    unittest.main()
