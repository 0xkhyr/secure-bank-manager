# 🏦 Présentation du Projet : Système de Gestion Bancaire Sécurisée

> Ce document résume les fonctionnalités clés et la structure du projet pour la soutenance devant l'enseignant.

---

## 1. Vue d'Ensemble 🌟
Une application web bancaire interne conçue avec une priorité absolue sur la **sécurité**, la **traçabilité** et la **flexibilité**. Elle permet de gérer les clients et leurs finances tout en protégeant le système contre les fraudes et les erreurs humaines.

## 2. Piliers du Projet ✅

- **Gestion Bancaire (CRUD)** : Clients, Comptes et Transactions.
- **Sécurité Avancée** : Double validation (Maker-Checker), Authentification Multi-Facteurs (MFA), Mode Panique, Maintenance.
- **Transparence & Audit** : Registre immuable avec signatures cryptographiques (HMAC).
- **Flexibilité (Policy Layer)** : Paramétrage du système en temps réel sans redémarrage.
- **Qualité Logicielle** : Tests automatisés (Pytest) et déploiement conteneurisé (Docker).

---

## 3. Fonctionnalités Détaillées 🔧

### 📑 Gestion Administrative
- **Utilisateurs & Rôles** : Accès différencié pour les Administrateurs (contrôle total) et les Opérateurs (exécution).
- **Clients & Comptes** : Cycle de vie complet (ouverture, modification, clôture).
- **Authentification Multi-Facteurs (MFA)** : 
    - Support TOTP (Google Authenticator, Authy).
    - Système de codes de secours (Backup Codes) à usage unique, hachés en base de données pour plus de sécurité.

### 💸 Opérations & Contrôle de Fraude
- **Transactions** : Dépôts et retraits avec vérification du solde minimum et des plafonds.
- **Maker-Checker (Validation croisée)** : Les opérations sensibles doivent être approuvées par un second utilisateur (le "Checker").
- **Contrôle de Vélocité** : Limitation automatique du nombre de transactions par minute pour bloquer les robots ou les fraudes massives.

### ⚙️ Pilotage Dynamique (Policy Layer)
- **Tableau de Bord des Politiques** : Modification instantanée des plafonds de retrait, des délais de session ou des messages système.
- **Mode Panique** : Un "bouton rouge" pour geler toutes les activités sensibles instantanément en cas d'attaque suspectée.
- **Mode Maintenance** : Interface dédiée pour informer les utilisateurs des travaux en cours.

### 🔍 Audit & Intégrité des Données
- **Chaine de Confiance** : Chaque log d’audit est lié au précédent (Hash Chaining).
- **Signature HMAC** : Détection immédiate de toute tentative de modification directe dans la base de données.
- **Clôture Journalière** : Génération d'un "hash racine" quotidien signé, rendant le passé immuable (Proof of Intactness).

---

## 4. Guide de Démonstration (Script Suggéré) 🎯

1. **Connexion & MFA** : Se connecter, activer le MFA dans le profil, montrer le QR Code et la génération des codes de secours. Se déconnecter et montrer la seconde étape de validation. Simuler la perte de l'appareil en utilisant un **code de secours** via la page de récupération dédiée.
2. **Action Opérateur** : Créer un client et un compte. Tenter un retrait dépassant le plafond habituel.
3. **Flux Maker-Checker** : Montrer que le retrait est "En attente". Se déconnecter/reconnecter avec un autre compte pour approuver l'opération.
4. **Configuration en Direct** : Aller dans les "Policies", changer le message de bienvenue ou activer la maintenance, et montrer le changement immédiat.
5. **Preuve d'Audit** : Consulter le journal d'audit, expliquer la présence des hashs et lancer la vérification d'intégrité pour prouver que les données n'ont pas été altérées.

---

## 5. Commandes Utiles pour la Présentation ⛏️

- **Lancer le projet** :
  ```bash
  docker-compose up --build
  ```
- **Lancer la suite de tests (Preuve de stabilité)** :
  ```bash
  docker exec -it secure_bank_manager python -m pytest tests/
  ```
- **Peupler la base avec des données de test** :
  ```bash
  python scripts/seed_dev_users.py --force
  ```

---

## 6. Points Techniques pour la Discussion 🧠
- **Backend** : Flask (Python) pour la rapidité et la modularité.
- **Base de données** : SQLite avec une couche d'abstraction pour faciliter une future migration.
- **Sécurité & Crypto** : 
    - **Mots de passe & Backup Codes** : Bcrypt pour le hachage sécurisé.
    - **Audit** : HMAC-SHA256 pour garantir l'intégrité des logs.
    - **MFA** : Implémentation TOTP (RFC 6238) via `pyotp` et génération de QR Codes avec `qrcode`.
- **Front-end** : Bootstrap 5 pour une interface claire, moderne et responsive.

---

## 7. Checklist de Soutenance ✅
- [ ] Présentation du Dashboard
- [ ] Activation et test du MFA (TOTP + Codes de secours)
- [ ] Démonstration d'un retrait avec Maker-Checker
- [ ] Modification d'une politique en temps réel
- [ ] Activation du Mode Panique
- [ ] Validation de l'intégrité de l'Audit
- [ ] Passage des tests unitaires
