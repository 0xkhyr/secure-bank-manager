# Cahier des Charges — Application Web de Gestion Interne Bancaire avec Audit Sécurisé

## 1. Présentation Générale du Projet

Ce projet consiste à développer une application web interne destinée aux employés d’une institution bancaire (Admin et Opérateur).  
L’application permet la gestion des clients, des comptes et des opérations financières (dépôts, retraits), tout en intégrant un système d’audit sécurisé pour garantir l’intégrité et la traçabilité des actions.

Technologies principales :
- **Flask (Python)** pour le backend
- **SQLite** pour la base de données
- **Bootstrap** pour l’interface utilisateur
- **Docker** pour le déploiement

---

## 2. Objectifs Fonctionnels

### 2.1. Gestion des Clients
- Ajouter un client  
- Modifier un client  
- Supprimer un client  
- Liste des clients  
- Détails d’un client  

### 2.2. Gestion des Comptes Bancaires
- Créer un compte (client existant)  
- Consulter un compte (solde, date, client associé)  
- Supprimer un compte (solde = 0)  
- Liste des comptes  

### 2.3. Opérations Bancaires
- Effectuer un dépôt  
- Effectuer un retrait  

**Règles métier :**
- Solde initial ≥ **250 DT**  
- Retrait ≤ **500 DT**  
- Retrait impossible si solde insuffisant  
- Historique des transactions obligatoire  

### 2.3. Gestion des Utilisateurs (Employés)
- Connexion + déconnexion  
- Rôles :  
  - **Admin** (accès total)  
  - **Opérateur** (accès limité)  
- Hashage sécurisé des mots de passe  
- **Politique d'Accès par Rôle :**

| Fonctionnalité | Admin | Opérateur |
|----------------|-------|-----------|
| **Clients** | | |
| - Voir la liste | ✓ | ✓ |
| - Créer un client | ✓ | ✓ |
| - Modifier un client | ✓ | ✗ |
| **Comptes** | | |
| - Voir les détails | ✓ | ✓ |
| - Créer un compte | ✓ | ✓ |
| - Clôturer un compte | ✓ | ✓ |
| **Opérations** | | |
| - Effectuer un dépôt | ✓ | ✓ |
| - Effectuer un retrait | ✓ | ✓ |
| - Voir l'historique | ✓ | ✓ |
| **Audit** | | |
| - Consulter le journal | ✓ | ✓ |
| - Vérifier l'intégrité | ✓ | ✗ |
| **Sécurité** | | |
| - Verrouillage après échecs | ✓ | ✓ |
| - Expiration de session | ✓ | ✓ |

---

## 3. Audit Sécurisé

Chaque action critique doit être journalisée.

### 3.1. Actions auditables
- Connexions  
- Création / modification / suppression clients  
- Création / suppression comptes  
- Dépôts / retraits  
- Modifications sensibles  

### 3.2. Données enregistrées
- Timestamp  
- Acteur  
- Action  
- Cible  
- Détails JSON  
- `prev_hash`  
- `current_hash`  
- HMAC signé  

### 3.3. Interface Audit
- Page de visualisation  
- Page de vérification d’intégrité  
- Alerte en cas d’altération  

---

## 4. Objectifs Non Fonctionnels

### 4.1. Sécurité
- Hashage (bcrypt / PBKDF2)  
- Validation des données  
- Chaîne de hash + HMAC  
- Variables d’environnement pour les clés  
- Option : verrouillage après plusieurs échecs  

### 4.2. Performance
- Temps de réponse local rapide  
- SQLAlchemy ou sqlite3 optimisé  

### 4.3. Déploiement (Docker)
- Build simple  
- Conteneur Flask + Gunicorn  
- Volume persistant `/data`  
- Fichier `.env` configurable  

### 4.4. Expérience Utilisateur
- UI claire et moderne  
- Navigation simple  
- Messages d’erreur visibles  
- Tableaux Bootstrap  

### 4.5. Maintenabilité
Code structuré en modules :

```
bank-app/
│
├── src/                    # Code source Python
│   ├── app.py
│   ├── models.py
│   ├── db.py
│   └── audit_logger.py
│
├── templates/
├── static/
├── data/
│   └── banque.db
│
├── Dockerfile
├── docs/
├── docker-compose.yml
├── .env
└── README.md
```

**Important :** Tous les fichiers Python doivent être **commentés en français** de manière claire et détaillée pour faciliter la compréhension et l'évaluation par l'enseignant. Les commentaires doivent expliquer :
- Le rôle de chaque module
- La logique des fonctions principales
- Les choix de sécurité implémentés
- Les règles métier appliquées

---

## 5. Architecture Logicielle

### 5.1. Structure interne
- Authentification & rôles  
- Gestion des clients  
- Gestion des comptes  
- Opérations (dépôt / retrait)  
- Audit sécurisé  
- Interface web Bootstrap  

### 5.2. Base de Données
Tables :
- `utilisateurs` : Employés de l'application
- `clients` : Clients de la banque
- `comptes` : Comptes bancaires
- `operations` : Opérations bancaires (dépôts/retraits)
- `journaux` : Journal d'audit sécurisé

---

## 6. Interface Utilisateur (Templates Jinja2)
Pages prévues :
- `login.html`  
- `dashboard.html`  
- `clients.html` (CRUD)  
- `accounts.html` (CRUD)  
- `operations.html`  
- `transactions.html`  
- `audit.html`  
- `audit_verify.html`  

Technologies :
- HTML5  
- Bootstrap 5  
- Jinja2  

---

## 7. Déploiement via Docker

### Dockerfile :
- Python 3.11-slim  
- Installation des dépendances  
- Gunicorn pour la prod  

### docker-compose :
- Volume : `./data:/app/data`  
- Port 5000  
- Variables d’environnement  

---

## 8. Livrables

- Code source complet  
- Dockerfile + docker-compose  
- Base SQLite  
- Interface Web  
- **Code commenté obligatoirement** : chaque module et fonction doit être commenté en français pour faciliter la compréhension par l'enseignant  
- Rapport PDF contenant :  
  - Cahier des charges  
  - Architecture  
  - Captures d'écran  
  - Logs d'audit  
  - Réultats de vérification d'intégrité  
- Présentation orale  
- README d'installation détaillé

---

## 9. Planning

| Semaine | Travail |
|--------|---------|
| 1 | Architecture + DB + modèles |
| 2 | Auth + CRUD clients |
| 3 | Comptes + opérations |
| 4 | Audit log sécurisé |
| 5 | UI Bootstrap + tests |
| 6 | Docker + rapport |
| 7 | Démonstration |

---

## 10. Critères de Réussite

- Fonctionnalités complètes  
- UI claire  
- Sécurité conforme  
- Audit fiable et vérifiable  
- Dockerisation fonctionnelle  
- **Code entièrement commenté en français** pour faciliter la compréhension de l'enseignant  
- Rapport professionnel  
- Documentation claire (README + commentaires)  
