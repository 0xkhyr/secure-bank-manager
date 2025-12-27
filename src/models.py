"""
modeles.py - Modèles de base de données pour l'application bancaire

Ce module définit tous les modèles SQLAlchemy pour l'application :
- Utilisateur : Employés utilisant l'application (Admin/Opérateur)
- Client : Clients de la banque
- Compte : Comptes bancaires
- Operation : Historique des opérations (dépôts/retraits)
- Journal : Journal d'audit sécurisé avec chaîne de hash et HMAC

Tous les modèles utilisent SQLAlchemy ORM pour faciliter les opérations CRUD
et garantir l'intégrité des données.
"""

from datetime import datetime, timedelta, date as py_date
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, Enum, Boolean, Date, JSON
from sqlalchemy.orm import relationship, declarative_base
import enum
import secrets
from src.config import Config

# Base pour tous les modèles SQLAlchemy
Base = declarative_base()


class RoleUtilisateur(enum.Enum):
    """
    Énumération des rôles utilisateurs.
    
    SUPERADMIN : Accès total - Peut gérer tous les utilisateurs (Admins + Opérateurs)
    ADMIN : Accès complet - Peut gérer uniquement les Opérateurs
    OPERATEUR : Accès limité - Consultation + opérations bancaires uniquement
    """
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    OPERATEUR = "operateur"


class TypeOperation(enum.Enum):
    """
    Énumération des types d'opérations bancaires.
    
    DEPOT : Ajout d'argent sur un compte
    RETRAIT : Retrait d'argent d'un compte
    """
    DEPOT = "depot"
    RETRAIT = "retrait"


class StatutCompte(enum.Enum):
    """
    Énumération des statuts possibles pour un compte bancaire.
    """
    ACTIF = "actif"
    FERME = "ferme"
    SUSPENDU = "suspendu"


class StatutClient(enum.Enum):
    """
    Énumération des statuts possibles pour un client.
    """
    ACTIF = "actif"
    INACTIF = "inactif"
    SUSPENDU = "suspendu"
    ARCHIVE = "archive"


class StatutAttente(enum.Enum):
    """
    Énumération des statuts pour le système Maker-Checker.
    """
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


# Générateur de numéro de compte unique
def gen_numero_compte():
    return f"CPT{datetime.utcnow().strftime('%y%m%d')}{secrets.randbelow(10**6):06d}"



class Utilisateur(Base):
    """
    Modèle Utilisateur : Représente un employé de la banque utilisant l'application.
    
    Attributs :
        id : Identifiant unique
        nom_utilisateur : Nom d'utilisateur (unique)
        mot_de_passe_hash : Mot de passe hashé avec bcrypt
        role : Rôle (SUPERSADMIN, ADMIN ou OPERATEUR)
        date_creation : Date de création du compte
        derniere_connexion : Dernière connexion
        tentatives_connexion : Nombre de tentatives de connexion échouées (pour verrouillage)
    
    Relations :
        journaux : Liste des actions effectuées par cet utilisateur
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
    
    # Champs pour le verrouillage après tentatives échouées
    tentatives_echouees = Column(Integer, default=0, nullable=False)
    verrouille_jusqu_a = Column(DateTime, nullable=True)  # Date de fin de verrouillage (UTC)
    verrouille_raison = Column(String(500), nullable=True)  # Raison du verrouillage
    verrouille_par_id = Column(Integer, ForeignKey('utilisateurs.id', ondelete='SET NULL'), nullable=True)  # Admin qui a verrouillé
    verrouille_le = Column(DateTime, nullable=True)  # Date du verrouillage (UTC)

    # Profile: display name (optional)
    display_name = Column(String(100), nullable=True)
    
    # Relations
    journaux = relationship('Journal', back_populates='utilisateur', lazy='dynamic')
    
    def est_verrouille(self):
        """
        Vérifie si le compte utilisateur est actuellement verrouillé.
        
        Returns:
            bool : True si le compte est verrouillé, False sinon
        """
        if self.verrouille_jusqu_a is None:
            return False
        return datetime.utcnow() < self.verrouille_jusqu_a
    
    def __repr__(self):
        return f"<Utilisateur(id={self.id}, nom_utilisateur='{self.nom_utilisateur}', role='{self.role.value}')>"


class Client(Base):
    """
    Modèle Client : Représente un client de la banque.
    
    Attributs :
        id : Identifiant unique
        nom : Nom de famille du client
        prenom : Prénom du client
        cin : Numéro de carte d'identité nationale (unique)
        telephone : Numéro de téléphone
        email : Adresse email (optionnel)
        adresse : Adresse postale
        date_creation : Date de création du profil client
        date_modification : Date de dernière modification
    
    Relations :
        comptes : Liste des comptes bancaires du client
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
    
    # Relations
    comptes = relationship('Compte', back_populates='client', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<Client(id={self.id}, nom='{self.nom}', prenom='{self.prenom}', cin='{self.cin}')>"
    
    @property
    def nom_complet(self):
        """Retourne le nom complet du client."""
        return f"{self.prenom} {self.nom}"


class Compte(Base):
    """
    Modèle Compte : Représente un compte bancaire.
    
    Attributs :
        id : Identifiant unique
        numero_compte : Numéro de compte (généré automatiquement, unique)
        client_id : Référence vers le client propriétaire
        solde : Solde actuel du compte (doit être >= 250 DT)
        date_ouverture : Date d'ouverture du compte
        date_modification : Date de dernière modification
    
    Relations :
        client : Client propriétaire du compte
        operations : Historique des opérations du compte
    
    Règles métier :
        - Solde initial minimum : 250 DT
        - Un client peut avoir plusieurs comptes
    """
    __tablename__ = 'comptes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    numero_compte = Column(String(20), unique=True, nullable=False, index=True)
    client_id = Column(Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    solde = Column(Numeric(12,3), default=250.000, nullable=False)
    statut = Column(Enum(StatutCompte), default=StatutCompte.ACTIF, nullable=False)
    date_ouverture = Column(DateTime, default=datetime.utcnow, nullable=False)
    date_modification = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relations
    client = relationship('Client', back_populates='comptes')
    operations = relationship('Operation', back_populates='compte', lazy='dynamic', cascade='all, delete-orphan')
    
    
    # Règles métier (utilise les configurations de .env)
    def peut_retirer(self, montant):
        """
        Vérifie si un retrait est possible.
        Utilise RETRAIT_MAXIMUM depuis la configuration.
        """
        from decimal import Decimal
        montant = Decimal(str(montant))
        
        if montant <= 0:
            return False
        if montant > Config.RETRAIT_MAXIMUM:
            return False
        return (self.solde - montant) >= Config.SOLDE_MINIMUM_COMPTE
    
    def valider_creation(self, depot_initial):
        """
        Valide qu'un dépôt initial respecte SOLDE_MINIMUM_INITIAL.
        """
        from decimal import Decimal
        depot_initial = Decimal(str(depot_initial))
        return depot_initial >= Config.SOLDE_MINIMUM_INITIAL
    
    def valider_depot(self, montant):
        """Valide qu'un montant de dépôt est positif."""
        from decimal import Decimal
        montant = Decimal(str(montant))
        return montant > 0
    
    def valider_retrait(self, montant):
        """Valide qu'un retrait est possible."""
        return self.peut_retirer(montant)
    
    def __repr__(self):
            return f"<Compte(id={self.id}, numero='{self.numero_compte}', solde={self.solde} DT)>"

class Operation(Base):
    """
    Modèle Operation : Représente une opération bancaire (dépôt ou retrait).
    
    Attributs :
        id : Identifiant unique
        compte_id : Référence vers le compte concerné
        utilisateur_id : Référence vers l'utilisateur qui a effectué l'opération
        type_operation : Type d'opération (DEPOT ou RETRAIT)
        montant : Montant de l'opération
        solde_avant : Solde avant l'opération
        solde_apres : Solde après l'opération
        date_operation : Date et heure de l'opération
        description : Description optionnelle
    
    Relations :
        compte : Compte bancaire concerné
        utilisateur : Utilisateur qui a effectué l'opération
    
    Règles métier :
        - Dépôt : aucune limite
        - Retrait : maximum 500 DT
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
    
    # Relations
    compte = relationship('Compte', back_populates='operations')
    # Disambiguate foreign key because there is also valide_par_id pointing to utilisateurs
    utilisateur = relationship('Utilisateur', foreign_keys=[utilisateur_id])
    
    # Champ pour enregistrer qui a validé (checker) l'opération si applicable
    valide_par_id = Column(Integer, ForeignKey('utilisateurs.id'), nullable=True)
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
    Modèle Journal : Journal d'audit sécurisé pour tracer toutes les actions critiques.
    
    Ce modèle implémente un système de chaîne de hash (chain hash) et HMAC
    pour garantir l'intégrité du journal d'audit et détecter toute falsification.
    
    Attributs :
        id : Identifiant unique (séquentiel pour la chaîne)
        horodatage : Date et heure de l'action
        utilisateur_id : Référence vers l'utilisateur qui a effectué l'action
        action : Type d'action (CONNEXION, CREATION_CLIENT, DEPOT, etc.)
        cible : Cible de l'action (ex: client_id, compte_id)
        details : Détails JSON de l'action
        hash_precedent : Hash de l'entrée précédente (chaîne de hash)
        hash_actuel : Hash de cette entrée (SHA-256)
        signature_hmac : Signature HMAC pour détecter les falsifications
    
    Relations :
        utilisateur : Utilisateur qui a effectué l'action
    
    Sécurité :
        - Chaîne de hash : chaque entrée contient le hash de l'entrée précédente
        - HMAC : signature cryptographique avec clé secrète
        - Intégrité vérifiable : toute modification casse la chaîne
    """
    __tablename__ = 'journaux'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    horodatage = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    utilisateur_id = Column(Integer, ForeignKey('utilisateurs.id', ondelete='SET NULL'), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    cible = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)  # JSON
    hash_precedent = Column(String(64), nullable=True)  # SHA-256 hash (64 caractères hex)
    hash_actuel = Column(String(64), nullable=False, unique=True)
    signature_hmac = Column(String(64), nullable=False)
    
    # Relations
    utilisateur = relationship('Utilisateur', back_populates='journaux')
    
    def __repr__(self):
        return f"<Journal(id={self.id}, action='{self.action}', horodatage='{self.horodatage}')>"


class ClotureJournal(Base):
    """
    Modèle ClotureJournal : Checkpoint quotidien pour l'intégrité de l'audit.
    
    Ce modèle représente une signature consolidée de tous les logs d'une journée.
    Il permet de valider l'intégrité temporelle par blocs (jours).
    
    Attributs :
        id : Identifiant unique
        date : Date de la clôture (YYYY-MM-DD)
        dernier_log_id : ID du dernier log inclus dans cette clôture
        hash_racine : Hash consolidé (hash_actuel du dernier log)
        signature_hmac : Signature HMAC du hash racine pour garantir l'origine
        cloture_le : Date et heure de création de la clôture
    """
    __tablename__ = 'clotures_journaux'
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    dernier_log_id = Column(Integer, ForeignKey('journaux.id'), nullable=False)
    hash_racine = Column(String(64), nullable=False)
    signature_hmac = Column(String(64), nullable=False)
    cloture_le = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relation
    dernier_log = relationship('Journal')
    
    def __repr__(self):
        return f"<ClotureJournal(id={self.id}, date='{self.date}', hash='{self.hash_racine[:10]}...')>"


class OperationEnAttente(Base):
    """
    Modèle OperationEnAttente : Système Maker-Checker (Principe des 4 yeux).
    Stocke une opération en attente de validation par un administrateur.
    """
    __tablename__ = 'operations_en_attente'

    id = Column(Integer, primary_key=True, autoincrement=True)
    type_operation = Column(String(50), nullable=False) # ex: 'RETRAIT_IMPORTANT', 'OUVERTURE_COMPTE'
    payload = Column(JSON, nullable=False) # Données de l'opération en format JSON

    cree_par_id = Column(Integer, ForeignKey('utilisateurs.id'), nullable=False)
    valide_par_id = Column(Integer, ForeignKey('utilisateurs.id'), nullable=True)

    statut = Column(Enum(StatutAttente), default=StatutAttente.PENDING, nullable=False)
    cree_le = Column(DateTime, default=datetime.utcnow, nullable=False)
    valide_le = Column(DateTime, nullable=True)
    
    # Détails de la décision
    decision_reason = Column(String(255), nullable=True)
    decision_comment = Column(Text, nullable=True)

    # Relations
    cree_par = relationship('Utilisateur', foreign_keys=[cree_par_id])
    valide_par = relationship('Utilisateur', foreign_keys=[valide_par_id])

    def __repr__(self):
        return f"<OperationEnAttente(id={self.id}, type='{self.type_operation}', statut='{self.statut.value}')>"


class Politique(Base):
    """
    Table de configuration dynamique pour les politiques.
    Clé/valeur où `valeur` peut être un JSON encodé pour des structures complexes.
    Exemples de clés : 'mot_de_passe.duree_validite_jours', 'rate.retrait.limite_journaliere'
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
    Historique des changements de politique pour audit et rollbacks simples.
    Contient une copie de la valeur et un message de changement.
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