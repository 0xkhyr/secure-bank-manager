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
import re
import html


def extract_flash_message(response):
    """Helper to extract the first flash message text from HTML response and unescape HTML entities."""
    text = response.get_data(as_text=True)
    # Try to find the alert with a close button
    m = re.search(r'<div class="alert alert-[^\"]+ alert-dismissible fade show" role="alert">\s*(.*?)\s*<button', text, re.S)
    if m:
        return html.unescape(m.group(1).strip())
    # Fallback: any alert div
    m = re.search(r'<div class="alert [^\"]+">\s*(.*?)\s*</div>', text, re.S)
    return html.unescape(m.group(1).strip()) if m else ''


def extract_csrf_token(response):
    """Extract CSRF token from a response (meta tag or hidden input)."""
    text = response.get_data(as_text=True)
    # meta tag
    m = re.search(r'<meta name="csrf-token" content="([^"]+)">', text)
    if m:
        return m.group(1)
    # hidden input
    m = re.search(r'<input[^>]+name="csrf_token"[^>]+value="([^"]+)"', text)
    return m.group(1) if m else None

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

        # Ensure an admin user exists for tests (do not rely on printed dev credentials)
        session = obtenir_session()
        existing = session.query(Utilisateur).filter_by(nom_utilisateur='admin').first()
        if not existing:
            admin = Utilisateur(
                nom_utilisateur='admin',
                mot_de_passe_hash=bcrypt.hash('admin123'),
                role=RoleUtilisateur.ADMIN
            )
            session.add(admin)
            session.commit()
        else:
            # Ensure the admin has a known password for tests
            existing.mot_de_passe_hash = bcrypt.hash('admin123')
            session.commit()
        session.close()
        
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
        # Get CSRF token first
        resp_get = self.client.get('/auth/login')
        token = extract_csrf_token(resp_get)
        response = self.client.post('/auth/login', data={
            'username': 'admin',
            'password': 'admin123',
            'csrf_token': token
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        # Vérifie qu'on est redirigé vers le tableau de bord
        self.assertIn(b'Tableau de Bord', response.data)
        # Header should show avatar initials for the logged in user
        self.assertIn(b'class="avatar"', response.data)
        
    def test_login_invalide_username(self):
        """Teste la connexion avec un nom d'utilisateur invalide."""
        # include csrf token
        resp_get = self.client.get('/auth/login')
        token = extract_csrf_token(resp_get)
        response = self.client.post('/auth/login', data={
            'username': 'utilisateur_inexistant',
            'password': 'password123',
            'csrf_token': token
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        # Should show a generic failure message (no username enumeration)
        generic = "Nom d'utilisateur ou mot de passe invalide."
        self.assertEqual(extract_flash_message(response), generic)
        
    def test_login_invalide_password(self):
        """Teste la connexion avec un mot de passe invalide."""
        resp_get = self.client.get('/auth/login')
        token = extract_csrf_token(resp_get)
        response = self.client.post('/auth/login', data={
            'username': 'admin',
            'password': 'mauvais_mot_de_passe',
            'csrf_token': token
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        # Should show the same generic message as for unknown username
        generic = "Nom d'utilisateur ou mot de passe invalide."
        self.assertEqual(extract_flash_message(response), generic)
        
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
        
        # Remove any existing test user and create a new one
        existing = session.query(Utilisateur).filter_by(nom_utilisateur='test_lock').first()
        if existing:
            session.delete(existing)
            session.commit()
        test_user = Utilisateur(
            nom_utilisateur='test_lock',
            mot_de_passe_hash=bcrypt.hash('password123'),
            role=RoleUtilisateur.OPERATEUR
        )
        session.add(test_user)
        session.commit()
        user_id = test_user.id
        session.close()
        
        # Use a fresh test client to avoid interference from other test sessions
        client = app.test_client()

        # Faire MAX_LOGIN_ATTEMPTS tentatives échouées (we don't assert on individual responses)
        for i in range(Config.MAX_LOGIN_ATTEMPTS):
            resp_get = client.get('/auth/login')
            tok = extract_csrf_token(resp_get)
            client.post('/auth/login', data={
                'username': 'test_lock',
                'password': 'wrong_password',
                'csrf_token': tok
            }, follow_redirects=True)
        
        # Verify in DB that the account has been locked automatically
        session = obtenir_session()
        usr = session.query(Utilisateur).filter_by(id=user_id).first()
        self.assertIsNotNone(usr.verrouille_jusqu_a, "Account was not locked after repeated failed attempts")
        self.assertEqual(usr.verrouille_raison, 'trop_de_tentatives')
        self.assertIsNotNone(usr.verrouille_le)

        # The login attempt should show a generic failure message when trying to login after lock
        resp_get = client.get('/auth/login')
        tok = extract_csrf_token(resp_get)
        response = client.post('/auth/login', data={
            'username': 'test_lock',
            'password': 'password123',
            'csrf_token': tok
        }, follow_redirects=True)
        generic = "Nom d'utilisateur ou mot de passe invalide."
        self.assertEqual(extract_flash_message(response), generic)

        # Vérifier qu'un audit VERROUILLAGE_AUTO_UTILISATEUR a été créé
        from src.models import Journal
        entry = session.query(Journal).filter_by(action='VERROUILLAGE_AUTO_UTILISATEUR', utilisateur_id=user_id).first()
        self.assertIsNotNone(entry)

        # Nettoyer
        session.delete(usr)
        session.commit()
        session.close()

    def test_permissions_admin_acces_total(self):
        """Teste que l'admin a accès à toutes les fonctionnalités."""
        # Se connecter en tant qu'admin
        resp_get = self.client.get('/auth/login')
        tok = extract_csrf_token(resp_get)
        self.client.post('/auth/login', data={
            'username': 'admin',
            'password': 'admin123',
            'csrf_token': tok
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
        resp_get = self.client.get('/auth/login')
        tok = extract_csrf_token(resp_get)
        self.client.post('/auth/login', data={
            'username': username,
            'password': 'password123',
            'csrf_token': tok
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

    def test_login_failure_responses_uniform(self):
        """Ensure failure messages do not leak account state and are uniform."""
        # Unknown username
        resp_unknown = self.client.post('/auth/login', data={'username': 'no_such_user', 'password': 'x'}, follow_redirects=True)
        msg_unknown = extract_flash_message(resp_unknown)

        # Wrong password for existing admin
        resp_wrong_pw = self.client.post('/auth/login', data={'username': 'admin', 'password': 'bad_pw'}, follow_redirects=True)
        msg_wrong_pw = extract_flash_message(resp_wrong_pw)

        self.assertEqual(msg_unknown, msg_wrong_pw)

        # Locked account should show the same generic message
        session = obtenir_session()
        existing = session.query(Utilisateur).filter_by(nom_utilisateur='locked_test').first()
        if existing:
            session.delete(existing)
            session.commit()
        locked = Utilisateur(nom_utilisateur='locked_test', mot_de_passe_hash=bcrypt.hash('pw'), role=RoleUtilisateur.OPERATEUR)
        session.add(locked)
        session.commit()
        locked.verrouille_jusqu_a = datetime.utcnow() + timedelta(minutes=60)
        session.commit()
        session.close()

        resp_locked = self.client.post('/auth/login', data={'username': 'locked_test', 'password': 'pw'}, follow_redirects=True)
        msg_locked = extract_flash_message(resp_locked)
        self.assertEqual(msg_unknown, msg_locked)

        # Cleanup
        session = obtenir_session()
        session.delete(session.query(Utilisateur).filter_by(nom_utilisateur='locked_test').first())
        session.commit()
        session.close()

if __name__ == '__main__':
    unittest.main()
