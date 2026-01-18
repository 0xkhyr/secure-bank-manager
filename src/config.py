"""
# Configuration Globale et Hardening
# Sécurité : Centralise les secrets, les politiques de session et les réglages réseau.
# Règle métier : Définit les constantes monétaires (Dinar Tunisien) et les plafonds opérationnels.
"""

import os
from decimal import Decimal
from dotenv import load_dotenv

# Sécurité : Chargement des variables d'environnement pour l'isolation des secrets hors du code source.
load_dotenv()


class Config:
    """
    # Sécurité : Classe de configuration immutable pendant l'exécution.
    """
    
    # Sécurité : Clé secrète Flask pour la signature des cookies de session.
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', '0') == '1'
    
    # Règle métier : Emplacement de la persistance des données.
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/banque.db')
    
    # Sécurité : Clé pour le scellement des logs d'audit (HMAC-SHA256).
    HMAC_SECRET_KEY = os.getenv('HMAC_SECRET_KEY', 'change-this-hmac-key')
    # Sécurité : Protection contre les attaques par force brute sur l'authentification.
    MAX_LOGIN_ATTEMPTS = int(os.getenv('MAX_LOGIN_ATTEMPTS', '5'))
    # Sécurité : Durée d'inactivité avant invalidation de la session.
    SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', '3600'))
    
    # Audit : Hash de genèse pour l'ancrage de la chaîne de blocs d'audit.
    GENESIS_HASH = os.getenv('GENESIS_HASH', "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918")
    
    # Sécurité : Principe de Double Contrôle (Maker-Checker) au-delà de ce seuil.
    MAKER_CHECKER_THRESHOLD = Decimal(os.getenv('MAKER_CHECKER_THRESHOLD', '200.000'))
    
    # Règle métier : Localisation pour l'horodatage légal des transactions.
    TIMEZONE_OFFSET_HOURS = int(os.getenv('TIMEZONE_OFFSET_HOURS', '1'))
    # Sécurité : Délai de bannissement temporaire après échecs de connexion.
    LOCKOUT_MINUTES = int(os.getenv('LOCKOUT_MINUTES', '15'))

    # Sécurité : Limitation de débit (Rate Limiting) pour contrer le DoS de verrouillage de compte.
    LOGIN_RATE_LIMIT = os.getenv('LOGIN_RATE_LIMIT', '10 per minute')
    RATE_LIMIT_STORAGE_URI = os.getenv('RATE_LIMIT_STORAGE_URI', 'memory://')

    # Sécurité : Durcissement des cookies de session (Injection, CSRF, XSS).
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', '0') == '1'
    SESSION_COOKIE_HTTPONLY = os.getenv('SESSION_COOKIE_HTTPONLY', '1') == '1'
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    
    # Règle métier : Paramètres monétaires et réglementaires (Tunisie).
    DEVISE = os.getenv('DEVISE', 'TND')
    SOLDE_MINIMUM_INITIAL = Decimal(os.getenv('SOLDE_MINIMUM_INITIAL', '250.000'))
    SOLDE_MINIMUM_COMPTE = Decimal(os.getenv('SOLDE_MINIMUM_COMPTE', '0.000'))
    RETRAIT_MAXIMUM = Decimal(os.getenv('RETRAIT_MAXIMUM', '500.000'))
    
    @staticmethod
    def afficher_config():
        """
        # Audit : Diagnostic à l'initialisation pour validation des paramètres opérationnels.
        """
        print("=== Configuration de l'application ===")
        print(f"Devise : {Config.DEVISE}")
        print(f"Solde minimum initial : {Config.SOLDE_MINIMUM_INITIAL} {Config.DEVISE}")
        print(f"Solde minimum compte : {Config.SOLDE_MINIMUM_COMPTE} {Config.DEVISE}")
        print(f"Retrait maximum : {Config.RETRAIT_MAXIMUM} {Config.DEVISE}")
        print(f"Tentatives de connexion max : {Config.MAX_LOGIN_ATTEMPTS}")
        print("=" * 40)


if __name__ == '__main__':
    Config.afficher_config()
