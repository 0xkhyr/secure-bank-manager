"""
Tests pour le module d'authentification

Teste :
- La connexion avec des identifiants valides
- La connexion avec des identifiants invalides
- La déconnexion
- Les décorateurs de protection des routes
"""

import unittest
import sys
import os
from unittest.mock import patch
from datetime import datetime, timedelta

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import app
from src.db import obtenir_session, reinitialiser_base_donnees
from src.models import Utilisateur, RoleUtilisateur
from src.config import Config
from passlib.hash import bcrypt

class TestAuthentification(unittest.TestCase):
    """Tests pour l'authentification."""
    
    @classmethod
    def setUpClass(cls):
        """Configuration initiale avant tous les tests."""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        
    def setUp(self):
        """Configuration avant chaque test."""
        self.client = app.test_client()
        
    def test_login_page_accessible(self):
        """Vérifie que la page de connexion est accessible."""
        response = self.client.get('/auth/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Connexion', response.data)
        
    def test_login_valide(self):
        """Teste la connexion avec des identifiants valides."""
        response = self.client.post('/auth/login', data={
            'username': 'admin',
            'password': 'admin123'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        # Vérifie qu'on est redirigé vers le tableau de bord
        self.assertIn(b'Tableau de Bord', response.data)
        
    def test_login_invalide_username(self):
        """Teste la connexion avec un nom d'utilisateur invalide."""
        response = self.client.post('/auth/login', data={
            'username': 'utilisateur_inexistant',
            'password': 'password123'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'incorrect', response.data)
        
    def test_login_invalide_password(self):
        """Teste la connexion avec un mot de passe invalide."""
        response = self.client.post('/auth/login', data={
            'username': 'admin',
            'password': 'mauvais_mot_de_passe'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'incorrect', response.data)
        
    def test_logout(self):
        """Teste la déconnexion."""
        # Se connecter d'abord
        self.client.post('/auth/login', data={
            'username': 'admin',
            'password': 'admin123'
        })
        
        # Se déconnecter
        response = self.client.get('/auth/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Connexion', response.data)
        
    def test_acces_protege_sans_connexion(self):
        """Vérifie qu'on ne peut pas accéder aux pages protégées sans connexion."""
        response = self.client.get('/clients/', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # Devrait rediriger vers la page de connexion
        self.assertIn(b'Connexion', response.data)

    def test_verrouillage_compte_apres_tentatives(self):
        """Teste le verrouillage de compte après plusieurs tentatives échouées."""
        session = obtenir_session()
        
        # Créer un utilisateur de test
        test_user = Utilisateur(
            nom_utilisateur='test_lock',
            mot_de_passe_hash=bcrypt.hash('password123'),
            role=RoleUtilisateur.OPERATEUR
        )
        session.add(test_user)
        session.commit()
        user_id = test_user.id
        session.close()
        
        # Faire MAX_LOGIN_ATTEMPTS tentatives échouées
        for i in range(Config.MAX_LOGIN_ATTEMPTS):
            response = self.client.post('/auth/login', data={
                'username': 'test_lock',
                'password': 'wrong_password'
            })
            self.assertIn(b'incorrect', response.data)
        
        # La prochaine tentative devrait indiquer un compte verrouillé
        response = self.client.post('/auth/login', data={
            'username': 'test_lock',
            'password': 'password123'
        })
        self.assertIn(b'verrouill', response.data.lower())
        
        # Nettoyer
        session = obtenir_session()
        session.delete(session.query(Utilisateur).filter_by(id=user_id).first())
        session.commit()
        session.close()

    def test_permissions_admin_acces_total(self):
        """Teste que l'admin a accès à toutes les fonctionnalités."""
        # Se connecter en tant qu'admin
        self.client.post('/auth/login', data={
            'username': 'admin',
            'password': 'admin123'
        })
        
        # Tester l'accès à audit (réservé admin)
        response = self.client.get('/audit/')
        self.assertEqual(response.status_code, 200)

    def test_permissions_operateur_acces_limite(self):
        """Teste que l'opérateur a un accès limité."""
        import time
        session = obtenir_session()
        
        # Créer un utilisateur opérateur de test avec un nom unique
        username = f'test_operateur_{int(time.time())}'
        test_user = Utilisateur(
            nom_utilisateur=username,
            mot_de_passe_hash=bcrypt.hash('password123'),
            role=RoleUtilisateur.OPERATEUR
        )
        session.add(test_user)
        session.commit()
        user_id = test_user.id
        session.close()
        
        # Se connecter en tant qu'opérateur
        self.client.post('/auth/login', data={
            'username': username,
            'password': 'password123'
        })
        
        # Tester l'accès à audit (devrait être autorisé pour voir)
        response = self.client.get('/audit/')
        self.assertEqual(response.status_code, 200)
        
        # Mais pas pour vérifier l'intégrité
        response = self.client.get('/audit/verifier', follow_redirects=True)
        self.assertIn(b'refus', response.data.lower())
        
        # Nettoyer
        session = obtenir_session()
        session.delete(session.query(Utilisateur).filter_by(id=user_id).first())
        session.commit()
        session.close()

if __name__ == '__main__':
    unittest.main()
