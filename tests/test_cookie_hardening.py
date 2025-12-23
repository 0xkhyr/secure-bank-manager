import unittest
from src.app import app
from src.db import obtenir_session
from src.models import Utilisateur, RoleUtilisateur
from passlib.hash import bcrypt
from tests.test_auth import extract_csrf_token
import re

class TestCookieHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        # Ensure admin user exists
        session = obtenir_session()
        existing = session.query(Utilisateur).filter_by(nom_utilisateur='admin').first()
        if not existing:
            admin = Utilisateur(nom_utilisateur='admin', mot_de_passe_hash=bcrypt.hash('admin123'), role=RoleUtilisateur.ADMIN)
            session.add(admin)
            session.commit()
        else:
            existing.mot_de_passe_hash = bcrypt.hash('admin123')
            session.commit()
        session.close()

    def setUp(self):
        self.client = app.test_client()

    def test_session_cookie_flags_on_login(self):
        """When configured, the session cookie should include secure, httponly and samesite attributes."""
        # Temporarily set cookie config to secure values
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

        # Get CSRF token
        resp_get = self.client.get('/auth/login')
        token = extract_csrf_token(resp_get)

        # Perform login
        resp = self.client.post('/auth/login', data={'username': 'admin', 'password': 'admin123', 'csrf_token': token})
        # Follow redirect to collect Set-Cookie
        self.assertIn('Set-Cookie', resp.headers)
        cookies = resp.headers.get_all('Set-Cookie')
        cookie_text = '\n'.join(cookies)

        # Assert flags
        self.assertIn('HttpOnly', cookie_text)
        self.assertIn('SameSite=Lax', cookie_text)
        # Secure may not appear in non-HTTPS testing environments depending on WSGI, so assert presence only if set
        self.assertIn('secure', cookie_text.lower())

    def test_locked_account_does_not_expose_timestamp(self):
        """F-05: Ensure that locked account attempts do not expose exact unlock timestamps in the response."""
        session = obtenir_session()
        # create a locked user
        existing = session.query(Utilisateur).filter_by(nom_utilisateur='locked_timestamp_test').first()
        if existing:
            session.delete(existing)
            session.commit()
        from datetime import datetime, timedelta
        user = Utilisateur(nom_utilisateur='locked_timestamp_test', mot_de_passe_hash=bcrypt.hash('pw'), role=RoleUtilisateur.OPERATEUR)
        session.add(user)
        session.commit()
        user.verrouille_jusqu_a = datetime.utcnow() + timedelta(minutes=60)
        session.commit()
        session.close()

        # Attempt login
        resp_get = self.client.get('/auth/login')
        token = extract_csrf_token(resp_get)
        response = self.client.post('/auth/login', data={'username': 'locked_timestamp_test','password': 'pw', 'csrf_token': token}, follow_redirects=True)
        import html
        text = response.get_data(as_text=True)
        text_unescaped = html.unescape(text)

        # Should show generic message (unescaped)
        self.assertIn("Nom d'utilisateur ou mot de passe invalide.", text_unescaped)

        # Ensure no ISO-like timestamp is present
        # e.g., 2025-12-23T12:34:56 or similar
        iso_like = re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', text_unescaped)
        self.assertIsNone(iso_like, 'Unlock timestamp must not be displayed to end user')

if __name__ == '__main__':
    unittest.main()
