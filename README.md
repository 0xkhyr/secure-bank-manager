# 🏦 Application de Gestion Bancaire Sécurisée

Application web interne pour la gestion des clients, comptes et opérations bancaires avec système d'audit sécurisé.

## 📋 Prérequis

- Docker
- Docker Compose

## 🚀 Installation et Lancement

### 1. Cloner le projet
```bash
git clone https://github.com/khyarum/secure-bank-manager.git
cd secure-bank-manager
```

### 2. Configurer les variables d'environnement
```bash
cp .env.example .env
```

**⚠️ Modifier obligatoirement en production** :
- `SECRET_KEY` et `HMAC_SECRET_KEY` : Générer avec `python -c "import secrets; print(secrets.token_hex(32))"`

**Configuration des règles métier (Tunisie - Dinar Tunisien)** :
- `DEVISE=TND` : Devise du système bancaire
- `SOLDE_MINIMUM_INITIAL=250.000` : Dépôt minimum à l'ouverture de compte
- `RETRAIT_MAXIMUM=500.000` : Montant maximum par retrait

Ces valeurs peuvent être ajustées selon les politiques de la banque.

### 3. Lancer l'application avec Docker
```bash
docker-compose up --build
```

L'application sera accessible sur : **http://localhost:5000**

## 📁 Structure du Projet

```
secure-bank-manager/
│
├── src/                    # Code source Python
│   ├── app.py              # Application Flask principale
│   ├── models.py           # Modèles de base de données
│   ├── db.py               # Configuration et initialisation DB
│   ├── auth.py             # Authentification et gestion des rôles
│   └── audit_logger.py     # Système d'audit sécurisé (HMAC + chain hash)
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

## 👥 Utilisateurs par Défaut

En développement, vous pouvez créer des comptes de démonstration via le script suivant (local uniquement) :

```
python scripts/seed_dev_users.py --force
```

⚠️ **Important** : changez les mots de passe avant toute utilisation hors développement !

## 🔧 Fonctionnalités

### Gestion des Clients
- Ajouter, modifier, supprimer des clients
- Consulter la liste et les détails des clients

### Gestion des Comptes
- Créer un compte pour un client existant
- Consulter le solde et l'historique
- Supprimer un compte (solde = 0)

### Opérations Bancaires
- Dépôt d'argent (aucune limite)
- Retrait d'argent (limite configurable via `RETRAIT_MAXIMUM`)
- Solde minimum à l'ouverture configurable via `SOLDE_MINIMUM_INITIAL`
- Solde minimum après opérations configurable via `SOLDE_MINIMUM_COMPTE`
- Historique complet des transactions
- Devise : Dinar Tunisien (TND)

### Audit Sécurisé
- Journalisation de toutes les actions critiques
- Chain hash pour l'intégrité des logs
- HMAC pour détecter les falsifications
- Interface de vérification de l'intégrité

## ⚙️ Configuration

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

## 🔒 Sécurité

- Mots de passe hashés avec bcrypt
- Sessions sécurisées
- Validation des entrées utilisateur
- Gestion des rôles (Admin / Opérateur)
- Audit trail immuable
- Règles métier configurables sans modification du code

## 🛠️ Commandes Utiles

### Développement Local (sans Docker)

#### Démarrer l'application
```bash
./start.sh
```

#### Arrêter l'application
```bash
./stop.sh
```

### Docker

#### Arrêter l'application
```bash
docker-compose down
```

#### Voir les logs
```bash
docker-compose logs -f
```

#### Reconstruire l'image
```bash
docker-compose up --build
```

#### Accéder au conteneur
```bash
docker exec -it secure_bank_manager bash
```

## 📊 Base de Données

Tables principales :
- `utilisateurs` : Employés de l'application (Admin, Opérateur)
- `clients` : Clients de la banque
- `comptes` : Comptes bancaires
- `operations` : Historique des opérations (dépôts/retraits)
- `journaux` : Journal d'audit sécurisé

## 🧪 Tests

Pour exécuter les tests :
```bash
docker exec -it secure_bank_manager python -m pytest tests/
```

## 📝 Documentation

Voir le [Cahier des Charges](docs/CAHIER_DES_CHARGES.md) pour plus de détails sur l'architecture et les spécifications.

## 👨‍💻 Développement

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

## 📄 Licence

Projet académique - 2025

## 👤 Auteur

Développé dans le cadre d'un projet de cybersécurité bancaire.
