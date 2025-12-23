import unittest
from src.app import app
from tests.test_auth import extract_csrf_token
from src.db import obtenir_session
from src.models import Utilisateur, RoleUtilisateur
from passlib.hash import bcrypt
from src.config import Config

class TestRateLimiting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        # Disable CSRF enforcement for these specific rate-limit tests to avoid CSRF aborts
        app.config['WTF_CSRF_ENABLED'] = False
        # Enable rate limiting for this test suite (it's disabled by default during pytest)
        try:
            from src.app import limiter
            if limiter:
                limiter.enabled = True
        except Exception:
            pass
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

    def test_login_rate_limit_per_ip(self):
        """Repeated failed logins from same IP should trigger HTTP 429 when limit exceeded."""
        # Make repeated failed attempts from the same client (same remote addr)
        # Don't rely on an exact numeric value; assert that a 429 occurs within a reasonable number of attempts
        max_attempts = 20
        found_429 = False
        for i in range(max_attempts):
            resp_get = self.client.get('/auth/login')
            token = extract_csrf_token(resp_get)
            # Use a non-existent username to avoid per-user account lock interfering with rate-limit testing
            resp = self.client.post('/auth/login', data={
                'username': 'no_such_user', 'password': 'wrong_pw', 'csrf_token': token
            })
            if resp.status_code == 429:
                found_429 = True
                break
        self.assertTrue(found_429, "Expected at least one 429 Too Many Requests within %d attempts" % max_attempts)

    def test_rate_limit_separate_ips_independent(self):
        """Ensure different IPs have independent rate limits."""
        # Choose a limit
        try:
            limit = int(str(Config.LOGIN_RATE_LIMIT).split()[0])
        except Exception:
            limit = 10

        # Make 'limit' attempts from IP A
        for i in range(limit):
            resp_get = self.client.get('/auth/login')
            token = extract_csrf_token(resp_get)
            # Use a non-existent username to avoid per-user account lock interfering with rate-limit testing
            resp = self.client.post('/auth/login', data={'username': 'no_such_user', 'password': 'wrong_pw', 'csrf_token': token}, environ_overrides={'REMOTE_ADDR': '10.0.0.1'})
            self.assertNotEqual(resp.status_code, 429)

        # Same number from IP B should still be allowed
        for i in range(limit):
            resp_get = self.client.get('/auth/login')
            token = extract_csrf_token(resp_get)
            resp = self.client.post('/auth/login', data={'username': 'admin', 'password': 'wrong_pw', 'csrf_token': token}, environ_overrides={'REMOTE_ADDR': '10.0.0.2'})
            self.assertNotEqual(resp.status_code, 429)

if __name__ == '__main__':
    unittest.main()
