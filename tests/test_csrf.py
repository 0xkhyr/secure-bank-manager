import unittest
import sys
import os
from pathlib import Path

# Add project to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.app import app

class TestCSRF(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = True
        cls.client = app.test_client()

    def test_login_post_without_csrf_rejected(self):
        resp = self.client.post('/auth/login', data={'username': 'foo', 'password': 'bar'})
        # When CSRF is enabled, the request should be rejected (400 Bad Request)
        self.assertIn(resp.status_code, (400, 403))

    def test_login_with_csrf_succeeds(self):
        get = self.client.get('/auth/login')
        text = get.get_data(as_text=True)
        # extract token (meta or input)
        import re
        m = re.search(r'<meta name="csrf-token" content="([^"]+)">', text)
        token = None
        if m:
            token = m.group(1)
        else:
            m2 = re.search(r'<input[^>]+name="csrf_token"[^>]+value="([^"]+)"', text)
            if m2:
                token = m2.group(1)
        self.assertIsNotNone(token)

        resp = self.client.post('/auth/login', data={'username': 'admin', 'password': 'admin123', 'csrf_token': token}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

if __name__ == '__main__':
    unittest.main()
