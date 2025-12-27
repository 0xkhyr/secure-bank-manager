import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db import reinitialiser_base_donnees, initialiser_base_donnees
from src.db import obtenir_session
from src.models import Politique

class TestPolicySeed(unittest.TestCase):
    def test_seed_policies(self):
        # Recreate DB (dev only) to ensure clean state
        reinitialiser_base_donnees()
        initialiser_base_donnees()
        session = obtenir_session()
        try:
            p = session.query(Politique).filter_by(cle='mot_de_passe.duree_validite_jours').first()
            self.assertIsNotNone(p)
            self.assertEqual(p.type, 'int')
            p2 = session.query(Politique).filter_by(cle='mfa.roles_obligatoires').first()
            self.assertIsNotNone(p2)
            self.assertEqual(p2.type, 'json')
        finally:
            session.close()

if __name__ == '__main__':
    unittest.main()
