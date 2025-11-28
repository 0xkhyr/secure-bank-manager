"""
config.py - Configuration centrale de l'application

Ce module charge et centralise toutes les configurations depuis le fichier .env
incluant les règles métier bancaires spécifiques à la Tunisie (Dinar Tunisien).
"""

import os
from decimal import Decimal
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()


class Config:
    """Configuration de l'application bancaire."""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', '0') == '1'
    
    # Base de données
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/banque.db')
    
    # Sécurité
    HMAC_SECRET_KEY = os.getenv('HMAC_SECRET_KEY', 'change-this-hmac-key')
    MAX_LOGIN_ATTEMPTS = int(os.getenv('MAX_LOGIN_ATTEMPTS', '3'))
    SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', '3600'))  # en secondes
    # Durée du verrouillage après dépassement des tentatives (en minutes)
    LOCKOUT_MINUTES = int(os.getenv('LOCKOUT_MINUTES', '15'))
    
    # Règles métier bancaires (Tunisie - Dinar Tunisien)
    DEVISE = os.getenv('DEVISE', 'TND')
    SOLDE_MINIMUM_INITIAL = Decimal(os.getenv('SOLDE_MINIMUM_INITIAL', '250.000'))
    SOLDE_MINIMUM_COMPTE = Decimal(os.getenv('SOLDE_MINIMUM_COMPTE', '0.000'))
    RETRAIT_MAXIMUM = Decimal(os.getenv('RETRAIT_MAXIMUM', '500.000'))
    
    @staticmethod
    def afficher_config():
        """Affiche la configuration actuelle (pour debug)."""
        print("=== Configuration de l'application ===")
        print(f"Devise : {Config.DEVISE}")
        print(f"Solde minimum initial : {Config.SOLDE_MINIMUM_INITIAL} {Config.DEVISE}")
        print(f"Solde minimum compte : {Config.SOLDE_MINIMUM_COMPTE} {Config.DEVISE}")
        print(f"Retrait maximum : {Config.RETRAIT_MAXIMUM} {Config.DEVISE}")
        print(f"Tentatives de connexion max : {Config.MAX_LOGIN_ATTEMPTS}")
        print("=" * 40)


# Pour tester ce module directement
if __name__ == '__main__':
    Config.afficher_config()
