"""
db.py - Configuration et initialisation de la base de données

Ce module gère :
- La connexion à la base de données SQLite
- La création de toutes les tables
- L'initialisation avec des données par défaut (utilisateurs admin)
- Les fonctions utilitaires pour interagir avec la base

La base de données est stockée dans le dossier /data pour être persistante
dans le conteneur Docker.
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from passlib.hash import bcrypt

# Importer la configuration centralisée
from src.config import Config

# Importer les modèles
from src.models import Base, Utilisateur, RoleUtilisateur

# Configuration de la base de données
DATABASE_PATH = Config.DATABASE_PATH
DATABASE_URL = f'sqlite:///{DATABASE_PATH}'

# Créer le moteur SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Mettre à True pour voir les requêtes SQL (debug)
    connect_args={'check_same_thread': False}  # Nécessaire pour SQLite avec Flask
)

# Créer une session factory
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)


def obtenir_session():
    """
    Retourne une nouvelle session de base de données.
    
    Returns:
        Session : Session SQLAlchemy pour effectuer des requêtes
    
    Utilisation :
        session = obtenir_session()
        try:
            # Faire des opérations
            session.commit()
        except:
            session.rollback()
        finally:
            session.close()
    """
    return Session()


def initialiser_base_donnees():
    """
    Initialise la base de données :
    1. Crée le dossier /data s'il n'existe pas
    2. Crée toutes les tables définies dans models.py
    3. Ajoute les utilisateurs par défaut si la table est vide
    
    Cette fonction est appelée au démarrage de l'application.
    """
    # Créer le dossier data s'il n'existe pas
    dossier_data = os.path.dirname(DATABASE_PATH)
    if not os.path.exists(dossier_data):
        os.makedirs(dossier_data)
        print(f"✓ Dossier créé : {dossier_data}")
    
    # Créer toutes les tables
    try:
        Base.metadata.create_all(engine)
        print("✓ Tables créées avec succès")
    except Exception as e:
        # Ignorer l'erreur si la table existe déjà (race condition avec plusieurs workers)
        if "already exists" in str(e):
            print("✓ Tables déjà existantes")
        else:
            raise e
    
    # Ajouter les utilisateurs par défaut
    creer_utilisateurs_defaut()


def creer_utilisateurs_defaut():
    """
    Crée les utilisateurs par défaut si la table utilisateurs est vide.
    
    Utilisateurs créés :
    - admin / admin123 (rôle ADMIN)
    - operateur / operateur123 (rôle OPERATEUR)
    
    Les mots de passe sont hashés avec bcrypt pour la sécurité.
    
    """
    session = obtenir_session()
    
    try:
        # Vérifier si des utilisateurs existent déjà
        nombre_utilisateurs = session.query(Utilisateur).count()
        
        if nombre_utilisateurs == 0:
            # Créer l'administrateur
            admin = Utilisateur(
                nom_utilisateur='admin',
                mot_de_passe_hash=bcrypt.hash('admin123'),
                role=RoleUtilisateur.ADMIN
            )
            session.add(admin)
            
            # Créer l'opérateur
            operateur = Utilisateur(
                nom_utilisateur='operateur',
                mot_de_passe_hash=bcrypt.hash('operateur123'),
                role=RoleUtilisateur.OPERATEUR
            )
            session.add(operateur)
            
            session.commit()
            print("✓ Utilisateurs par défaut créés :")
            print("  - admin / admin123 (ADMIN)")
            print("  - operateur / operateur123 (OPERATEUR)")
            print("  ⚠️  Changez ces mots de passe en production !")
        else:
            print(f"✓ Base de données déjà initialisée ({nombre_utilisateurs} utilisateurs)")
            
    except Exception as e:
        session.rollback()
        print(f"✗ Erreur lors de la création des utilisateurs : {e}")
    finally:
        session.close()


def reinitialiser_base_donnees():
    """
    ⚠️ ATTENTION : Supprime toutes les tables et les recrée.
    
    Utilisé uniquement pour le développement ou les tests.
    Toutes les données seront perdues !
    """
    print("⚠️  Réinitialisation de la base de données...")
    Base.metadata.drop_all(engine)
    print("✓ Tables supprimées")
    initialiser_base_donnees()
    print("✓ Base de données réinitialisée")


def verifier_connexion():
    """
    Vérifie que la connexion à la base de données fonctionne.
    
    Returns:
        bool : True si la connexion fonctionne, False sinon
    """
    try:
        session = obtenir_session()
        # Tester une requête simple
        session.execute(text('SELECT 1'))
        session.close()
        return True
    except Exception as e:
        print(f"✗ Erreur de connexion à la base de données : {e}")
        return False


# Pour tester ce module directement
if __name__ == '__main__':
    print("=== Test du module db.py ===\n")
    
    # Tester la connexion
    if verifier_connexion():
        print("✓ Connexion à la base de données OK\n")
    else:
        print("✗ Problème de connexion\n")
        exit(1)
    
    # Initialiser la base
    initialiser_base_donnees()
    
    # Afficher les utilisateurs
    print("\n=== Utilisateurs dans la base ===")
    session = obtenir_session()
    utilisateurs = session.query(Utilisateur).all()
    for user in utilisateurs:
        print(f"  - {user.nom_utilisateur} ({user.role.value})")
    session.close()
    
    print("\n✓ Test terminé avec succès")
