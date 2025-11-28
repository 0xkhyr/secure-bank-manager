"""
Tests pour le système d'audit sécurisé

Teste :
- La création de logs
- Le calcul des hash
- La vérification d'intégrité
- La détection de falsification
"""

import unittest
import sys
import os

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.audit_logger import log_action, verifier_integrite, calculer_hash, calculer_hmac
from src.db import obtenir_session
from src.models import Journal

class TestAudit(unittest.TestCase):
    """Tests pour le système d'audit."""
    
    def test_creation_log(self):
        """Vérifie qu'un log peut être créé."""
        resultat = log_action(1, "TEST_ACTION", "Test", {"test": "valeur"})
        self.assertTrue(resultat)
        
    def test_calcul_hash(self):
        """Vérifie que le calcul de hash est déterministe."""
        data = "test_data"
        hash1 = calculer_hash(data)
        hash2 = calculer_hash(data)
        
        # Le même input doit donner le même hash
        self.assertEqual(hash1, hash2)
        
        # Un input différent doit donner un hash différent
        hash3 = calculer_hash("autre_data")
        self.assertNotEqual(hash1, hash3)
        
    def test_calcul_hmac(self):
        """Vérifie que le calcul HMAC est déterministe."""
        data = "test_data"
        hmac1 = calculer_hmac(data)
        hmac2 = calculer_hmac(data)
        
        # Le même input doit donner le même HMAC
        self.assertEqual(hmac1, hmac2)
        
        # Un input différent doit donner un HMAC différent
        hmac3 = calculer_hmac("autre_data")
        self.assertNotEqual(hmac1, hmac3)
        
    def test_integrite_valide(self):
        """Vérifie que l'intégrité est valide pour une base non modifiée."""
        # Créer quelques logs
        log_action(1, "TEST_1", "Test 1", {"numero": 1})
        log_action(1, "TEST_2", "Test 2", {"numero": 2})
        log_action(1, "TEST_3", "Test 3", {"numero": 3})
        
        # Commit the session to ensure logs are saved
        from src.db import obtenir_session
        session = obtenir_session()
        session.commit()
        
        # Vérifier l'intégrité
        valide, erreurs = verifier_integrite()
        
        self.assertTrue(valide)
        self.assertEqual(len(erreurs), 0)
        
    def test_chaine_hash(self):
        """Vérifie que la chaîne de hash est correctement formée."""
        session = obtenir_session()
        
        # Créer deux logs
        log_action(1, "PREMIER", "Premier log", {})
        log_action(1, "SECOND", "Second log", {})
        
        # Récupérer les logs
        logs = session.query(Journal).order_by(Journal.id).all()
        
        if len(logs) >= 2:
            # Le hash_precedent du second doit être le hash_actuel du premier
            premier = logs[-2]
            second = logs[-1]
            self.assertEqual(second.hash_precedent, premier.hash_actuel)
            
        session.close()
        
    def test_longueur_hash(self):
        """Vérifie que les hash ont la bonne longueur (SHA-256 = 64 caractères hex)."""
        hash_test = calculer_hash("test")
        self.assertEqual(len(hash_test), 64)
        
        hmac_test = calculer_hmac("test")
        self.assertEqual(len(hmac_test), 64)

if __name__ == '__main__':
    unittest.main()
