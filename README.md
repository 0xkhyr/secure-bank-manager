#  Application de Gestion Bancaire Sécurisée

Application web interne pour la gestion des clients, comptes et opérations bancaires avec système d'audit sécurisé.

##  Prérequis

- Docker
- Docker Compose

##  Installation et Lancement

### 1. Cloner le projet
```bash
git clone https://github.com/khyrr/secure-bank-manager.git
cd secure-bank-manager
```

### 2. Configurer les variables d'environnement
```bash
cp .env.example .env
```

**Modifier obligatoirement en production** :
- `SECRET_KEY` et `HMAC_SECRET_KEY` : Générer avec `python -c "import secrets; print(secrets.token_hex(32))"`

**Configuration des règles métier (Tunisie - Dinar Tunisien)** :
- `DEVISE=TND` : Devise du système bancaire
- `SOLDE_MINIMUM_INITIAL=250.000` : Dépôt minimum à l'ouverture de compte
- `RETRAIT_MAXIMUM=500.000` : Montant maximum par retrait

Ces valeurs peuvent être ajustées selon les politiques de la banque.

### 3. Lancer l'application avec Docker
```bash
# Utiliser la version V2 de Docker Compose
docker compose up --build
```

L'application sera accessible sur : **http://localhost:5000**

## Structure du Projet

```
secure-bank-manager/
│
├── src/                    # Code source Python
│   ├── app.py              # Application Flask principale
│   ├── models.py           # Modèles de base de données
│   ├── db.py               # Configuration et initialisation DB
│   ├── auth.py             # Authentification et gestion des rôles
│   ├── audit_logger.py     # Système d'audit sécurisé (HMAC + chain hash)
│   └── ...                  # Autres modules
│
├── templates/              # Templates HTML (Jinja2)
├── static/                 # Fichiers CSS, JS, images
│   ├── css/
│   └── js/
│
├── data/                   # Base de données SQLite (volume Docker)
│   └── banque.db
│
├── docs/                   # Documentation
│   └── CAHIER_DES_CHARGES.md
│
├── tests/                  # Tests unitaires
│
├── Dockerfile              # Configuration Docker
├── docker-compose.yml      # Orchestration Docker
├── requirements.txt        # Dépendances Python
├── .env.example            # Template variables d'environnement
└── README.md               # Ce fichier
```

##  Utilisateurs par Défaut

En développement, vous pouvez créer des comptes de démonstration via le script suivant (local uniquement) :

```
python scripts/seed_dev_users.py --force
```

**Important** : changez les mots de passe avant toute utilisation hors développement !

##  Fonctionnalités

### Gestion des Clients
- Ajouter, modifier, supprimer des clients
- Consulter la liste et les détails des clients

### Gestion des Comptes
- Créer un compte pour un client existant
- Consulter le solde et l'historique
- Supprimer un compte (solde = 0)

### Opérations Bancaires & Workflow
- Dépôt d'argent (aucune limite) et retraits contrôlés.
- **Workflow Maker-Checker (Quatre-Yeux)** : Toute opération sensible ou modification de politique nécessite l'approbation d'un second utilisateur (Admin/Checker).
- **Limites Dynamiques** : Vérification en temps réel du solde minimum, du plafond de retrait et de la vélocité.
- Devise : Dinar Tunisien (TND) par défaut.

### Contrôles de Sécurité Avancés
- **MFA (Multi-Factor Authentication)** : Support TOTP (Google Authenticator) pour tous les comptes.
- **Panic Mode (Maintenance)** : Capacité de verrouiller l'application en lecture seule ou de bloquer toutes les transactions en cas d'attaque.
- **Protection Brute-Force** : Verrouillage temporaire de compte et Rate Limiting (Flask-Limiter) par adresse IP.
- **Hardening HTTP** : Protection CSRF globale, en-têtes de sécurité (HSTS, CSP, XSS protection) et cookies sécurisés (SameSite=Lax, HttpOnly).

### Audit Sécurisé
- Journalisation de toutes les actions critiques (Connexion, Erreurs, Accès aux données).
- **Chain Hash** (HMAC-SHA256) pour l'intégrité absolue des logs.
- **Visualisation Localisée** : Interface graphique de vérification en français.
- **Mode Démonstration** : Simulateur de falsification pour prouver la détection d'altération.

### Outils de Maintenance & Dev (Zone Nucléaire)
- **Console SQL Brute** : Exécution de requêtes directement depuis l'interface dev.
- **Modification Directe** : Correction rapide de données via un éditeur intégré.
- **Log Breaker** : Outil d'altération furtive pour tester la résistance de l'audit.

##  Configuration

L'application utilise un système de configuration centralisé via le fichier `.env` et le module `src/config.py`.

### Variables d'environnement disponibles

**Sécurité** :
- `SECRET_KEY` : Clé de chiffrement Flask pour les sessions
- `HMAC_SECRET_KEY` : Clé HMAC pour signer les entrées du journal d'audit
- `MAX_LOGIN_ATTEMPTS` : Nombre maximum de tentatives de connexion (défaut: 3)
- `SESSION_TIMEOUT` : Durée de vie de la session en secondes (défaut: 3600)
- `LOGIN_RATE_LIMIT` : Limite par-IP pour le endpoint `/auth/login` (format Flask-Limiter, ex: `10 per minute`). Implemented via `Flask-Limiter` (add dependency in `requirements.txt`).

**Base de données** :
- `DATABASE_PATH` : Chemin vers le fichier SQLite (défaut: `data/banque.db`)

**Règles métier bancaires (Tunisie)** :
- `DEVISE` : Code de la devise (défaut: `TND` - Dinar Tunisien)
- `SOLDE_MINIMUM_INITIAL` : Dépôt minimum requis à l'ouverture d'un compte (défaut: `250.000`)
- `SOLDE_MINIMUM_COMPTE` : Solde minimum autorisé après opérations (défaut: `0.000`)
- `RETRAIT_MAXIMUM` : Montant maximum autorisé par retrait (défaut: `500.000`)

### Tester la configuration

```bash
source .venv/bin/activate
python src/config.py
```

Affichera toutes les valeurs configurées.

##  Sécurité & Conformité

- **Audit Trail** : Journal immuable avec chaînage de hash et signature HMAC.
- **RBAC** : Gestion fine des accès par rôles (Operateur, Admin, SuperAdmin).
- **Maker-Checker** : Séparation des tâches pour les approbations.
- **Brute-Force** : Détection et blocage automatique après tentatives infructueuses.
- **Data Protection** : Mots de passe hashés avec bcrypt, protection contre l'énumération d'utilisateurs.
- **Règles métier** : Configurables à chaud via variables d'environnement.

##  Commandes Utiles
### Développement Local (sans Docker)

```bash
# Lancer l'application
./scripts/start.sh

# Arrêter l'application
./scripts/stop.sh
```

### Docker (Recommandé)

```bash
# Lancer avec Docker Compose (V2 obligatoire)
docker compose up --build

# Voir les journaux d'exécution
docker compose logs -f

# Accéder au conteneur
docker exec -it secure_bank_manager bash
```

##  Tests
L'application dispose d'une suite de **25 tests de sécurité critiques**.

```bash
docker exec -it secure_bank_manager pytest tests/
```

##  Documentation
La documentation détaillée est disponible dans le dossier `docs/`, notamment le guide de [Démonstration de Sécurité](docs/DEMONSTRATION_SECURITE.md).
```

##  Documentation

Voir le [Cahier des Charges](docs/CAHIER_DES_CHARGES.md) pour plus de détails sur l'architecture et les spécifications.

##  Développement

Pour le développement local sans Docker :

```bash
# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python app.py
```

##  Licence

Projet académique - 2025

##  Auteur
Développé dans le cadre d'un projet de cybersécurité bancaire.
