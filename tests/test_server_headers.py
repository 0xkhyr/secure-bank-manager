import unittest
from src.app import app

class TestServerHeaders(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_server_headers_stripped_on_root(self):
        resp = self.client.get('/')
        # The response should not include a Server or X-Powered-By header
        self.assertNotIn('Server', resp.headers)
        self.assertNotIn('X-Powered-By', resp.headers)

    def test_server_headers_stripped_on_login(self):
        resp = self.client.get('/auth/login')
        self.assertNotIn('Server', resp.headers)
        self.assertNotIn('X-Powered-By', resp.headers)

if __name__ == '__main__':
    unittest.main()
