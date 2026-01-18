"""
Définition des modèles de données et des contraintes métier.

Ce module structure la base de données via SQLAlchemy, en intégrant les mécanismes de 
sécurité (RBAC, MFA), le workflow Maker-Checker et l'intégrité de l'audit (hash chaining).
"""

from datetime import datetime, timedelta, date as py_date
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, Enum, Boolean, Date, JSON
from sqlalchemy.orm import relationship, declarative_base
import enum
import secrets
from src.config import Config

Base = declarative_base()


class RoleUtilisateur(enum.Enum):
    """Rôles définissant les privilèges d'accès dans le système (RBAC)."""
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    OPERATEUR = "operateur"


class TypeOperation(enum.Enum):
    """Classification des mouvements de fonds."""
    DEPOT = "depot"
    RETRAIT = "retrait"


class StatutCompte(enum.Enum):
    """États du cycle de vie d'un compte bancaire."""
    ACTIF = "actif"
    FERME = "ferme"
    SUSPENDU = "suspendu"


class StatutClient(enum.Enum):
    """États administratifs d'un client."""
    ACTIF = "actif"
    INACTIF = "inactif"
    SUSPENDU = "suspendu"
    ARCHIVE = "archive"


class StatutAttente(enum.Enum):
    """États de validation pour le contrôle Maker-Checker (principe des 4 yeux)."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


def gen_numero_compte():
    """Génère un numéro de compte unique basé sur l'horodatage et l'entropie."""
    return f"CPT{datetime.utcnow().strftime('%y%m%d')}{secrets.randbelow(10**6):06d}"



class Utilisateur(Base):
    """
    Employé ou administrateur accédant au système.
    
    Sécurité : Gère le hachage des secrets, le verrouillage de compte (anti brute-force)
    et les paramètres de l'authentification multi-facteurs (MFA).
    """
    __tablename__ = 'utilisateurs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nom_utilisateur = Column(String(50), unique=True, nullable=False, index=True)
    mot_de_passe_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    role = Column(Enum(RoleUtilisateur), nullable=False, default=RoleUtilisateur.OPERATEUR)
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)
    derniere_connexion = Column(DateTime, nullable=True)
    tentatives_connexion = Column(Integer, default=0)
    
    # Sécurité : Contrôle du verrouillage temporaire pour prévenir les attaques de force brute.
    tentatives_echouees = Column(Integer, default=0, nullable=False)
    verrouille_jusqu_a = Column(DateTime, nullable=True)
    verrouille_raison = Column(String(500), nullable=True)
    verrouille_par_id = Column(Integer, ForeignKey('utilisateurs.id', ondelete='SET NULL'), nullable=True)
    verrouille_le = Column(DateTime, nullable=True)

    display_name = Column(String(100), nullable=True)

    # Sécurité : Paramètres TOTP et codes de secours pour l'authentification forte.
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(32), nullable=True)
    mfa_backup_codes = Column(Text, nullable=True)
    
    journaux = relationship('Journal', back_populates='utilisateur', lazy='dynamic')
    
    def est_verrouille(self):
        """Détermine si l'utilisateur est actuellement banni par le système anti-abus."""
        if self.verrouille_jusqu_a is None:
            return False
        return datetime.utcnow() < self.verrouille_jusqu_a
    
    def __repr__(self):
        return f"<Utilisateur(id={self.id}, nom_utilisateur='{self.nom_utilisateur}', role='{self.role.value}')>"


class Client(Base):
    """
    Représentation administrative d'un client bancaire.
    """
    __tablename__ = 'clients'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100), nullable=False)
    cin = Column(String(20), unique=True, nullable=False, index=True)
    telephone = Column(String(20), nullable=False)
    email = Column(String(100), nullable=True)
    adresse = Column(Text, nullable=True)
    statut = Column(Enum(StatutClient), default=StatutClient.ACTIF, nullable=False)
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)
    date_modification = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    comptes = relationship('Compte', back_populates='client', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<Client(id={self.id}, nom='{self.nom}', prenom='{self.prenom}', cin='{self.cin}')>"
    
    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}"


class Compte(Base):
    """
    Compte bancaire associé à un client.
    
    Règle métier : Maintien d'un solde minimum pour garantir la liquidité des comptes.
    """
    __tablename__ = 'comptes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    numero_compte = Column(String(20), unique=True, nullable=False, index=True)
    client_id = Column(Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    solde = Column(Numeric(12,3), default=250.000, nullable=False)
    statut = Column(Enum(StatutCompte), default=StatutCompte.ACTIF, nullable=False)
    date_ouverture = Column(DateTime, default=datetime.utcnow, nullable=False)
    date_modification = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    client = relationship('Client', back_populates='comptes')
    operations = relationship('Operation', back_populates='compte', lazy='dynamic', cascade='all, delete-orphan')
    
    def peut_retirer(self, montant):
        """Vérifie le respect du plafond de retrait et du solde minimum configurés."""
        from decimal import Decimal
        montant = Decimal(str(montant))
        
        if montant <= 0:
            return False
        if montant > Config.RETRAIT_MAXIMUM:
            return False
        return (self.solde - montant) >= Config.SOLDE_MINIMUM_COMPTE
    
    def valider_creation(self, depot_initial):
        """Vérifie que le dépôt initial respecte le seuil d'ouverture de compte."""
        from decimal import Decimal
        depot_initial = Decimal(str(depot_initial))
        return depot_initial >= Config.SOLDE_MINIMUM_INITIAL
    
    def valider_depot(self, montant):
        """Validation technique élémentaire du flux entrant."""
        from decimal import Decimal
        montant = Decimal(str(montant))
        return montant > 0
    
    def valider_retrait(self, montant):
        """Validation métier consolidée du flux sortant."""
        return self.peut_retirer(montant)
    
    def __repr__(self):
            return f"<Compte(id={self.id}, numero='{self.numero_compte}', solde={self.solde} DT)>"

class Operation(Base):
    """
    Historique des mouvements de fonds (Audit Trail métier).
    
    Règle métier : Application des limites de retrait et traçabilité de l'auteur.
    """
    __tablename__ = 'operations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    compte_id = Column(Integer, ForeignKey('comptes.id', ondelete='CASCADE'), nullable=False)
    utilisateur_id = Column(Integer, ForeignKey('utilisateurs.id', ondelete='SET NULL'), nullable=True)
    type_operation = Column(Enum(TypeOperation), nullable=False)
    montant = Column(Numeric(12,3), nullable=False)
    solde_avant = Column(Numeric(12,3), nullable=False)
    solde_apres = Column(Numeric(12,3), nullable=False)
    date_operation = Column(DateTime, default=datetime.utcnow, nullable=False)
    description = Column(Text, nullable=True)
    
    compte = relationship('Compte', back_populates='operations')
    utilisateur = relationship('Utilisateur', foreign_keys=[utilisateur_id])
    
    # Audit : Référence vers l'approbateur (Checker) pour le workflow de validation croisée.
    valide_par_id = Column(Integer, ForeignKey('utilisateurs.id'), nullable=True)
    valide_par = relationship('Utilisateur', foreign_keys=[valide_par_id])

    def validate_business_rules(self):
        """Applique les contraintes de retrait et de solde avant exécution."""
        if self.montant <= 0:
            raise ValueError("Le montant doit être > 0")
        
        if self.type_operation == TypeOperation.DEPOT:
            pass
        
        elif self.type_operation == TypeOperation.RETRAIT:
            if not self.compte.peut_retirer(self.montant):
                raise ValueError(
                    f"Retrait non autorisé : limite {Config.RETRAIT_MAXIMUM} {Config.DEVISE} "
                    f"ou solde insuffisant (minimum {Config.SOLDE_MINIMUM_COMPTE} {Config.DEVISE})"
                )

    def __repr__(self):
        return f"<Operation(id={self.id}, type='{self.type_operation.value}', montant={self.montant} DT)>"
    valide_par = relationship('Utilisateur', foreign_keys=[valide_par_id])

    def validate_business_rules(self):
        """
        Valide les règles métier bancaires selon la configuration.
        Utilise RETRAIT_MAXIMUM et SOLDE_MINIMUM_COMPTE de Config.
        """
        # 1. Le montant doit être strictement > 0
        if self.montant <= 0:
            raise ValueError("Le montant doit être > 0")
        
        # 2. Règles selon le type d'opération
        if self.type_operation == TypeOperation.DEPOT:
            # Aucun montant maximum pour les dépôts
            pass
        
        elif self.type_operation == TypeOperation.RETRAIT:
            # Vérification : montant <= RETRAIT_MAXIMUM et solde suffisant
            if not self.compte.peut_retirer(self.montant):
                raise ValueError(
                    f"Retrait non autorisé : limite {Config.RETRAIT_MAXIMUM} {Config.DEVISE} "
                    f"ou solde insuffisant (minimum {Config.SOLDE_MINIMUM_COMPTE} {Config.DEVISE})"
                )

    
    def __repr__(self):
        return f"<Operation(id={self.id}, type='{self.type_operation.value}', montant={self.montant} DT)>"


class Journal(Base):
    """
    Registre d'audit immuable (système tamper-evident).
    
    Audit : Implémente le chaînage par hash (SHA-256) et la signature HMAC-SHA256 
    pour garantir l'intégrité du journal et détecter toute modification a posteriori.
    """
    __tablename__ = 'journaux'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    horodatage = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    utilisateur_id = Column(Integer, ForeignKey('utilisateurs.id', ondelete='SET NULL'), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    cible = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    hash_precedent = Column(String(64), nullable=True)
    hash_actuel = Column(String(64), nullable=False, unique=True)
    signature_hmac = Column(String(64), nullable=False)
    
    utilisateur = relationship('Utilisateur', back_populates='journaux')
    
    def __repr__(self):
        return f"<Journal(id={self.id}, action='{self.action}', horodatage='{self.horodatage}')>"


class ClotureJournal(Base):
    """
    Point d'ancrage quotidien pour l'intégrité de l'audit.
    
    Audit : Scelle l'état de la chaîne de hash à une date donnée pour faciliter 
    la vérification par blocs temporels.
    """
    __tablename__ = 'clotures_journaux'
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    dernier_log_id = Column(Integer, ForeignKey('journaux.id'), nullable=False)
    hash_racine = Column(String(64), nullable=False)
    signature_hmac = Column(String(64), nullable=False)
    cloture_le = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    dernier_log = relationship('Journal')
    
    def __repr__(self):
        return f"<ClotureJournal(id={self.id}, date='{self.date}', hash='{self.hash_racine[:10]}...')>"


class OperationEnAttente(Base):
    """
    Système de validation à double commande (Maker-Checker).
    
    Audit : Isole les actions critiques (ex: retraits hors limites) en attente 
    d'une approbation par un second utilisateur (Checker).
    """
    __tablename__ = 'operations_en_attente'

    id = Column(Integer, primary_key=True, autoincrement=True)
    type_operation = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)

    cree_par_id = Column(Integer, ForeignKey('utilisateurs.id'), nullable=False)
    valide_par_id = Column(Integer, ForeignKey('utilisateurs.id'), nullable=True)

    statut = Column(Enum(StatutAttente), default=StatutAttente.PENDING, nullable=False)
    cree_le = Column(DateTime, default=datetime.utcnow, nullable=False)
    valide_le = Column(DateTime, nullable=True)
    
    decision_reason = Column(String(255), nullable=True)
    decision_comment = Column(Text, nullable=True)

    cree_par = relationship('Utilisateur', foreign_keys=[cree_par_id])
    valide_par = relationship('Utilisateur', foreign_keys=[valide_par_id])

    def __repr__(self):
        return f"<OperationEnAttente(id={self.id}, type='{self.type_operation}', statut='{self.statut.value}')>"


class Politique(Base):
    """
    Gestion dynamique des règles de gestion et de sécurité (Policy Layer).
    """
    __tablename__ = 'politiques'

    id = Column(Integer, primary_key=True, autoincrement=True)
    cle = Column(String(255), unique=True, nullable=False, index=True)
    valeur = Column(Text, nullable=False)
    type = Column(String(50), nullable=False, default='string')
    description = Column(Text, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    cree_par = Column(Integer, ForeignKey('utilisateurs.id'), nullable=True)
    cree_le = Column(DateTime, default=datetime.utcnow, nullable=False)
    modifie_le = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Politique(cle='{self.cle}', type='{self.type}', active={self.active})>"


class HistoriquePolitique(Base):
    """
    Trace de l'évolution des politiques de sécurité pour audit et traçabilité.
    """
    __tablename__ = 'historique_politiques'

    id = Column(Integer, primary_key=True, autoincrement=True)
    politique_id = Column(Integer, ForeignKey('politiques.id'), nullable=False)
    cle = Column(String(255), nullable=False)
    valeur = Column(Text, nullable=False)
    type = Column(String(50), nullable=False, default='string')
    modifie_par = Column(Integer, ForeignKey('utilisateurs.id'), nullable=True)
    modifie_le = Column(DateTime, default=datetime.utcnow, nullable=False)
    commentaire = Column(Text, nullable=True)

    def __repr__(self):
        return f"<HistoriquePolitique(politique_id={self.politique_id}, cle='{self.cle}', modifie_le='{self.modifie_le.isoformat()}')>"

# Alias pour maintenir la compatibilité avec les scripts de migration existants.
Policy = Politique
PolicyHistory = HistoriquePolitique