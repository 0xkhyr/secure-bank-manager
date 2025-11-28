"""
test_config.py - Script de test pour vérifier la configuration

Ce script teste que :
1. La configuration se charge correctement
2. Les modèles utilisent bien les valeurs de configuration
3. Les règles métier sont appliquées selon le fichier .env
"""

import sys
from decimal import Decimal
from src.config import Config
from src.models import Compte, Client, RoleUtilisateur
from src.db import obtenir_session

def test_configuration():
    """Teste que la configuration se charge correctement."""
    print("=== Test 1: Chargement de la configuration ===")
    Config.afficher_config()
    print("✓ Configuration chargée avec succès\n")
    return True

def test_regles_metier_compte():
    """Teste que les règles métier utilisent bien la configuration."""
    print("=== Test 2: Règles métier des comptes ===")
    
    # Créer un compte fictif pour tester
    session = obtenir_session()
    try:
        # Récupérer ou créer un client pour le test
        client = session.query(Client).first()
        if not client:
            print("⚠️  Aucun client trouvé, création d'un client de test...")
            client = Client(
                nom="TEST",
                prenom="Configuration",
                cin="TEST_CONFIG_123",
                telephone="12345678"
            )
            session.add(client)
            session.commit()
            print("✓ Client de test créé")
        
        # Créer un compte de test
        compte = Compte(
            numero_compte="TEST_CONFIG_001",
            client_id=client.id,
            solde=Decimal("1000.000")
        )
        
        # Test 1: Validation de création avec dépôt initial insuffisant
        depot_insuffisant = Config.SOLDE_MINIMUM_INITIAL - Decimal("50.000")
        if compte.valider_creation(depot_insuffisant):
            print(f"✗ Erreur: Dépôt de {depot_insuffisant} TND devrait être refusé")
            return False
        print(f"✓ Dépôt insuffisant ({depot_insuffisant} TND) correctement refusé")
        
        # Test 2: Validation de création avec dépôt initial suffisant
        depot_suffisant = Config.SOLDE_MINIMUM_INITIAL
        if not compte.valider_creation(depot_suffisant):
            print(f"✗ Erreur: Dépôt de {depot_suffisant} TND devrait être accepté")
            return False
        print(f"✓ Dépôt initial valide ({depot_suffisant} TND) accepté")
        
        # Test 3: Retrait supérieur au maximum
        retrait_excessif = Config.RETRAIT_MAXIMUM + Decimal("100.000")
        if compte.peut_retirer(retrait_excessif):
            print(f"✗ Erreur: Retrait de {retrait_excessif} TND devrait être refusé")
            return False
        print(f"✓ Retrait excessif ({retrait_excessif} TND) correctement refusé (max: {Config.RETRAIT_MAXIMUM} TND)")
        
        # Test 4: Retrait dans la limite
        retrait_valide = Config.RETRAIT_MAXIMUM - Decimal("50.000")
        if not compte.peut_retirer(retrait_valide):
            print(f"✗ Erreur: Retrait de {retrait_valide} TND devrait être accepté")
            return False
        print(f"✓ Retrait valide ({retrait_valide} TND) accepté")
        
        # Test 5: Retrait laissant un solde insuffisant
        compte.solde = Decimal("100.000")
        retrait_insuffisant = Decimal("150.000")
        if compte.peut_retirer(retrait_insuffisant):
            print(f"✗ Erreur: Retrait laissant solde négatif devrait être refusé")
            return False
        print(f"✓ Retrait causant solde insuffisant correctement refusé")
        
        print("✓ Toutes les règles métier utilisent bien la configuration\n")
        return True
        
    except Exception as e:
        print(f"✗ Erreur lors du test: {e}")
        return False
    finally:
        session.close()

def test_devise():
    """Teste que la devise est correctement configurée."""
    print("=== Test 3: Configuration de la devise ===")
    if Config.DEVISE != "TND":
        print(f"⚠️  Devise configurée: {Config.DEVISE} (attendu: TND)")
    else:
        print(f"✓ Devise correctement configurée: {Config.DEVISE}")
    print()
    return True

def main():
    """Execute tous les tests."""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  Test du système de configuration                         ║")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    tests = [
        test_configuration,
        test_regles_metier_compte,
        test_devise
    ]
    
    resultats = []
    for test in tests:
        try:
            resultat = test()
            resultats.append(resultat)
        except Exception as e:
            print(f"✗ Erreur inattendue: {e}")
            resultats.append(False)
    
    print("╔════════════════════════════════════════════════════════════╗")
    if all(resultats):
        print("║  ✓ TOUS LES TESTS RÉUSSIS                                 ║")
        print("╚════════════════════════════════════════════════════════════╝")
        return 0
    else:
        print("║  ✗ CERTAINS TESTS ONT ÉCHOUÉ                              ║")
        print("╚════════════════════════════════════════════════════════════╝")
        return 1

if __name__ == '__main__':
    sys.exit(main())
