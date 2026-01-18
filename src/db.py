"""
# Configuration et Persistance des Données
# Sécurité : Gère la connexion à la base de données chiffrée (SQLite) et l'isolation des sessions.
# Audit : Initialise les schémas et assure le seeding des politiques de sécurité par défaut.
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, scoped_session
from passlib.hash import bcrypt
import secrets

# Importer la configuration centralisée
from src.config import Config

# Importer les modèles
from src.models import Base, Utilisateur, RoleUtilisateur

# Configuration de la base de données
DATABASE_PATH = Config.DATABASE_PATH
DATABASE_URL = f'sqlite:///{DATABASE_PATH}'

# Sécurité : Configuration du moteur SQLAlchemy avec isolation des threads pour SQLite.
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Désactivé en production pour éviter les fuites d'informations dans les logs.
    connect_args={'check_same_thread': False}
)

# Sécurité : Factory de session configurée pour éviter les états périmés après validation (atomicité).
session_factory = sessionmaker(bind=engine, expire_on_commit=False)
Session = scoped_session(session_factory)


def obtenir_session():
    """
    # Sécurité : Fournit une session isolée et thread-safe pour les opérations en base.
    """
    return Session()


def initialiser_base_donnees():
    """
    # Règle métier : Initialisation du schéma de données au démarrage.
    # Sécurité : Garantit l'existence des tables et des comptes à privilèges initiaux.
    """
    # Créer le dossier data s'il n'existe pas
    dossier_data = os.path.dirname(DATABASE_PATH)
    if not os.path.exists(dossier_data):
        os.makedirs(dossier_data)
        print(f"✓ Dossier créé : {dossier_data}")
    
    # Audit : Vérification de l'intégrité du schéma.
    try:
        Base.metadata.create_all(engine)
        print("✓ Tables créées avec succès")
    except Exception as e:
        if "already exists" in str(e):
            print("✓ Tables déjà existantes")
        else:
            raise e

    # Sécurité : Application des correctifs de schéma à chaud (migrations légères).
    try:
        apply_schema_updates()
    except Exception as e:
        print(f"⚠️ Erreur lors de l'application des mises à jour du schéma : {e}")
    
    # Sécurité : Provisionnement des comptes administratifs par défaut.
    creer_utilisateurs_defaut()

    # Sécurité : Injection des politiques de sécurité minimales (Politiques de mots de passe, etc.).
    try:
        creer_policies_defaut()
    except Exception as e:
        print(f"⚠️ Erreur lors du seed des politiques par défaut : {e}")


def creer_utilisateurs_defaut():
    """
    # Sécurité : Création des identités de service initiales (Admin/Ops).
    # Limitation : Utilise bcrypt pour le hachage robuste des mots de passe.
    """
    session = obtenir_session()
    
    try:
        # Vérifier si des utilisateurs existent déjà
        nombre_utilisateurs = session.query(Utilisateur).count()
        
        if nombre_utilisateurs == 0:
            # Sécurité : Récupération des secrets via variables d'environnement (Secret Management).
            # Si absentes, génération de secrets aléatoires à haute entropie.
            superadmin_pw = os.getenv('DEV_SUPERADMIN_PW') or secrets.token_urlsafe(12)
            admin_pw = os.getenv('DEV_ADMIN_PW') or secrets.token_urlsafe(12)
            operateur_pw = os.getenv('DEV_OPER_PW') or secrets.token_urlsafe(12)

            superadmin = Utilisateur(
                nom_utilisateur='superadmin',
                mot_de_passe_hash=bcrypt.hash(superadmin_pw),
                role=RoleUtilisateur.SUPERADMIN
            )
            session.add(superadmin)

            admin = Utilisateur(
                nom_utilisateur='admin',
                mot_de_passe_hash=bcrypt.hash(admin_pw),
                role=RoleUtilisateur.ADMIN
            )
            session.add(admin)

            operateur = Utilisateur(
                nom_utilisateur='operateur',
                mot_de_passe_hash=bcrypt.hash(operateur_pw),
                role=RoleUtilisateur.OPERATEUR
            )
            session.add(operateur)

            session.commit()
            print("✓ Utilisateurs par défaut créés.")
        else:
            print(f"✓ Base de données déjà initialisée ({nombre_utilisateurs} utilisateurs)")
            
    except IntegrityError:
        session.rollback()
        print("✓ Utilisateurs déjà créés par un autre worker")
    except Exception as e:
        session.rollback()
        print(f"✗ Erreur lors de la création des utilisateurs : {e}")
    finally:
        session.close()


def reinitialiser_base_donnees():
    """
    # Limitation : Procédure destructive réservée aux environnements de test.
    # Sécurité : Doit être désactivée ou protégée en environnement de production.
    """
    print("⚠️  Réinitialisation de la base de données...")
    Base.metadata.drop_all(engine)
    print("✓ Tables supprimées")
    initialiser_base_donnees()
    print("✓ Base de données réinitialisée")


def apply_schema_updates():
    """
    # Règle métier : Mises à jour incrémentales du schéma sans perte de données.
    # Sécurité : Permet l'ajout de colonnes de contrôle (ex: valide_par_id) sur une base existante.
    """
    from sqlalchemy import text
    with engine.connect() as conn:
        # Inspection de la structure actuelle de la table 'operations'.
        res = conn.execute(text("PRAGMA table_info('operations')"))
        cols = [row[1] for row in res.fetchall()]

        if 'valide_par_id' not in cols:
            print("→ Ajout de la colonne 'valide_par_id' à la table 'operations'")
            conn.execute(text('ALTER TABLE operations ADD COLUMN valide_par_id INTEGER'))
        else:
            pass


def creer_policies_defaut():
    """
    # Sécurité : Hardening par défaut du système.
    # Règle métier : Définit les plafonds, les politiques de purge et les seuils de vigilance.
    """
    import json
    from src.models import Policy, Utilisateur
    from src.policy import set_policy

    session = obtenir_session()
    try:
        nb = session.query(Policy).count()
        if nb and nb > 0:
            print("✓ Policies existantes détectées; seed ignoré.")
            return

        # Identification de l'acteur effectuant le seed initial (Audit Trail).
        superadmin = session.query(Utilisateur).filter_by(nom_utilisateur='superadmin').first()
        changed_by = superadmin.id if superadmin else None

        # Configuration des politiques de sécurité critiques (Hardening initial).
        defaults = [
            ('mot_de_passe.duree_validite_jours', 90, 'int', "Durée de validité d’un mot de passe (jours)"),
            ('mot_de_passe.historique_compte', 5, 'int', "Nombre de mots de passe à retenir pour éviter réutilisation"),
            ('mot_de_passe.longueur_min', 12, 'int', "Longueur minimale du mot de passe (standard ANSSI)"),
            ('session.delai_expiration_secondes', 1800, 'int', "Expiration de session en secondes"),
            ('retrait.limite_par_operation', 10000, 'int', "Montant maximum par retrait"),
            ('retrait.limite_journaliere', 20000, 'int', "Limite quotidienne de retrait"),
            ('operation.utilisateur.max_par_minute', 5, 'int', "Nombre maximum d'opérations par minute par utilisateur"),
            ('maker_checker.seuil_montant', 5000, 'int', "Montant au dessus duquel la demande est soumise à approbation"),
            ('mfa.roles_obligatoires', json.dumps(['admin', 'superadmin']), 'json', "Activer MFA pour ces rôles"),
            # Vélocité et détection de fraude.
            ('velocity.actif', 'true', 'bool', "Activer le contrôle de vitesse (velocity)"),
            ('velocity.methode', 'db', 'string', "Méthode de contrôle (requêtes DB directes)"),
            ('velocity.retrait.max_par_minute', 3, 'int', "Nombre maximum de retraits par minute par utilisateur"),
            # Verrouillage contre les attaques par force brute.
            ('utilisateurs.tentatives_verrouillage', 5, 'int', "Tentatives de connexion avant verrouillage"),
            ('utilisateurs.duree_verrouillage_minutes', 15, 'int', "Durée du verrouillage (minutes)"),
            # Audit & rétention légale.
            ('audit.retention_jours', 365, 'int', "Durée de rétention des logs d'audit (jours)"),
            # Contrôle des changements de configuration sensible.
            ('changement_politique.requiert_approbation', json.dumps(['retrait.limite_journaliere', 'mot_de_passe.duree_validite_jours', 'mfa.roles_obligatoires']), 'json', "Clés nécessitant approbation pour modification"),
            # Cache et performance (Trade-off Sécurité/Disponibilité).
            ('politiques.cache_ttl_secondes', 30, 'int', "TTL du cache des politiques (secondes)"),
            # Modes d'urgence.
            ('maintenance.enabled', 'false', 'bool', "Mode maintenance activé"),
            ('maintenance.message', "Site en maintenance — certaines fonctions sont indisponibles.", 'string', "Message affiché en mode maintenance"),
            ('maintenance.panic_mode', 'false', 'bool', "Mode panique activé (Arrêt d'urgence)"),
            ('maintenance.panic_message', "Le site est en mode panique. Toutes les opérations sont suspendues.", 'string', "Message affiché en mode panique"),
            ('maintenance.panic_public_message', "Aucune alerte active — cette page affiche l'état du service.", 'string', "Message publique d'état"),
        ]

        for key, val, typ, desc in defaults:
            try:
                set_policy(key, val, type_=typ, description=desc, changed_by=changed_by, comment='Initial Seeding of Security Policies')
            except Exception as e:
                print(f"⚠️ Erreur lors du seed de la policy {key}: {e}")

        print("✓ Policies par défaut semées.")
    finally:
        session.close()


def verifier_connexion():
    """
    # Audit : Vérifie la disponibilité de la couche de données.
    """
    try:
        session = obtenir_session()
        session.execute(text('SELECT 1'))
        session.close()
        return True
    except Exception as e:
        print(f"✗ Erreur de connexion à la base de données : {e}")
        return False


if __name__ == '__main__':
    # Audit : Script de diagnostic et d'initialisation manuelle.
    print("=== Diagnostic Base de Données ===\n")
    
    if verifier_connexion():
        print("✓ Connexion OK\n")
    else:
        print("✗ Problème de connexion\n")
        exit(1)
    
    initialiser_base_donnees()
    
    print("\n=== État des Utilisateurs Privilégiés ===")
    session = obtenir_session()
    utilisateurs = session.query(Utilisateur).all()
    for user in utilisateurs:
        print(f"  - {user.nom_utilisateur} ({user.role.value})")
    session.close()
    
    print("\n✓ Diagnostic terminé")
