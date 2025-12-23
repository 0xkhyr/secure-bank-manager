import os
import sys
import unittest
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.app import app

FORBIDDEN = [
    'admin / admin123',
    'operateur / operateur123',
    'superadmin / superadmin123',
]

class TestNoDevCredentials(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        cls.client = app.test_client()

    def test_login_page_does_not_show_credentials(self):
        resp = self.client.get('/auth/login')
        self.assertEqual(resp.status_code, 200)
        text = resp.get_data(as_text=True)
        for forbidden in FORBIDDEN:
            self.assertNotIn(forbidden, text)

    def test_templates_do_not_contain_credentials(self):
        # Scan template files for forbidden patterns
        tpl_root = Path('templates')
        all_html = tpl_root.rglob('*.html')
        content = ''
        for f in all_html:
            try:
                content += f.read_text()
            except Exception:
                # ignore unreadable files
                pass
        for forbidden in FORBIDDEN:
            self.assertNotIn(forbidden, content)

if __name__ == '__main__':
    unittest.main()
