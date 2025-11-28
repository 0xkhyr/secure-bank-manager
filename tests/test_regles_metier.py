"""
Tests pour les règles métier bancaires

Teste :
- Le solde minimum initial
- Les limites de retrait
- Le solde minimum après opérations
- La validation des montants
"""

import unittest
import sys
import os
from decimal import Decimal

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models import Compte, Operation, TypeOperation
from src.config import Config

class TestReglesMetier(unittest.TestCase):
    """Tests pour les règles métier bancaires."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        # Créer un compte de test
        self.compte = Compte(
            numero_compte="TEST123456",
            client_id=1,
            solde=Decimal('1000.000')
        )
        
    def test_solde_minimum_initial(self):
        """Vérifie que le dépôt initial minimum est respecté."""
        # Dépôt valide
        self.assertTrue(self.compte.valider_creation(Decimal('250.000')))
        self.assertTrue(self.compte.valider_creation(Decimal('500.000')))
        
        # Dépôt invalide (trop petit)
        self.assertFalse(self.compte.valider_creation(Decimal('100.000')))
        self.assertFalse(self.compte.valider_creation(Decimal('0.000')))
        
    def test_retrait_maximum(self):
        """Vérifie que la limite de retrait est respectée."""
        # Retrait valide
        self.assertTrue(self.compte.peut_retirer(Decimal('100.000')))
        self.assertTrue(self.compte.peut_retirer(Decimal('500.000')))
        
        # Retrait invalide (trop grand)
        self.assertFalse(self.compte.peut_retirer(Decimal('600.000')))
        self.assertFalse(self.compte.peut_retirer(Decimal('1000.000')))
        
    def test_solde_minimum_apres_retrait(self):
        """Vérifie que le solde minimum est maintenu après retrait."""
        # Compte avec solde = 100 TND
        compte_petit = Compte(
            numero_compte="TEST789",
            client_id=1,
            solde=Decimal('100.000')
        )
        
        # Retrait qui laisserait le solde positif mais < minimum
        # Si SOLDE_MINIMUM_COMPTE = 0, tous les retraits <= solde sont valides
        self.assertTrue(compte_petit.peut_retirer(Decimal('50.000')))
        self.assertTrue(compte_petit.peut_retirer(Decimal('100.000')))
        
        # Retrait qui laisserait le solde négatif
        self.assertFalse(compte_petit.peut_retirer(Decimal('150.000')))
        
    def test_depot_valide(self):
        """Vérifie la validation des dépôts."""
        # Dépôts valides
        self.assertTrue(self.compte.valider_depot(Decimal('0.001')))
        self.assertTrue(self.compte.valider_depot(Decimal('100.000')))
        self.assertTrue(self.compte.valider_depot(Decimal('10000.000')))
        
        # Dépôts invalides
        self.assertFalse(self.compte.valider_depot(Decimal('0.000')))
        self.assertFalse(self.compte.valider_depot(Decimal('-100.000')))
        
    def test_montants_negatifs(self):
        """Vérifie que les montants négatifs sont rejetés."""
        self.assertFalse(self.compte.peut_retirer(Decimal('-100.000')))
        self.assertFalse(self.compte.valider_depot(Decimal('-50.000')))
        
    def test_montants_zero(self):
        """Vérifie que les montants zéro sont rejetés."""
        self.assertFalse(self.compte.peut_retirer(Decimal('0.000')))
        self.assertFalse(self.compte.valider_depot(Decimal('0.000')))

if __name__ == '__main__':
    unittest.main()
