import os
import unittest
from pathlib import Path

FORBIDDEN = [
    'admin / admin123',
    'operateur / operateur123',
    'superadmin / superadmin123',
]

INCLUDE_PATHS = [
    'templates',
    'static',
    'docs',
    'README.md',
    'TODO.md',
    'src',
]

class TestNoPlaintextCredentialsInRepo(unittest.TestCase):
    def test_no_forbidden_patterns_in_repo(self):
        repo_root = Path('.')
        content = ''
        for p in INCLUDE_PATHS:
            path = repo_root / p
            if path.is_file():
                try:
                    content += path.read_text()
                except Exception:
                    pass
            elif path.exists():
                for f in path.rglob('*'):
                    if f.is_file():
                        try:
                            # skip binaries
                            if f.suffix in ['.png', '.jpg', '.jpeg', '.gif', '.zip']:
                                continue
                            content += f.read_text()
                        except Exception:
                            pass
        for forbidden in FORBIDDEN:
            self.assertNotIn(forbidden, content)

if __name__ == '__main__':
    unittest.main()
