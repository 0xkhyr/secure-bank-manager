# Liste des Tâches - Secure Bank Manager

## Importants
- [x] comment le code en français

## 🔐 Noyau de Sécurité
- [x] **Module d'Authentification (`src/auth.py`)**
    - [x] Route & logique de connexion
    - [x] Route de déconnexion
    - [x] Gestion des sessions
    - [x] Décorateurs de rôles (`@login_required`, `@admin_required`, `@operator_required`)
- [x] **Système d'Audit (`src/audit_logger.py`)**
    - [x] Fonction `log_action`
    - [x] Génération de signature HMAC
    - [x] Calcul du hash chaîné (lien avec le log précédent)
    - [x] Outil de vérification d'intégrité

## 🏦 Logique Bancaire (Backend)
- [x] **Gestion des Clients**
    - [x] Lister les clients
    - [x] Ajouter un nouveau client
    - [x] Voir les détails du client
- [x] **Gestion des Comptes**
    - [x] Créer un compte pour un client
    - [x] Voir les détails & l'historique du compte
    - [x] Clôturer un compte
- [x] **Opérations**
    - [x] Dépôt
    - [x] Retrait - avec vérification des limites

## 💻 Frontend (Templates)
- [x] **Mise en page de base** (`base.html`)
- [x] **Pages d'Authentification**
    - [x] Connexion (`login.html`)
- [x] **Tableau de Bord**
    - [x] Tableau de bord Admin (`dashboard_admin.html`)
    - [x] Tableau de bord Opérateur (`dashboard_operator.html`)
- [x] **Pages Clients**
    - [x] Liste (`clients/list.html`)
    - [x] Création (`clients/create.html`)
    - [x] Détails (`clients/view.html`)
- [x] **Pages Comptes**
    - [x] Création (`accounts/create.html`)
    - [x] Détails (`accounts/view.html`)
- [x] **Pages Opérations**
    - [x] Formulaire Dépôt/Retrait (`operations/new.html`)

## 🎨 UI/UX
- [x] Styles CSS (Fichiers statiques)
- [x] Messages Flash pour erreurs/succès

## 🧪 Tests
- [x] Tests unitaires pour l'Authentification
- [x] Tests unitaires pour les Règles Bancaires
- [x] Tests unitaires pour l'Intégrité de l'Audit
## 🔐 Contrôles d'accès & Identité (Rôles)
- [x] **Définir la politique d'accès par rôle**
    - [x] Rédiger la matrice rôle ↔ permissions (Admin vs Opérateur)
    - [x] Documenter les exemples dans `docs/CAHIER_DES_CHARGES.md`
- [x] **Renforcer `src/auth.py`**
    - [x] Compléter le verrouillage de compte (usage de `Config.MAX_LOGIN_ATTEMPTS`)
    - [x] Gérer `verrouille_jusqu_a` et afficher le temps restant
    - [x] Implémenter expiration de session (`Config.SESSION_TIMEOUT`)
- [x] **Implémenter permissions fines**
    - [x] Ajouter `has_permission()` et `permission_required()` (ou `@admin_required`/`@operateur_required` améliorés)
    - [x] Appliquer aux blueprints : `clients`, `accounts`, `operations`, `audit_logger`
    - [x] Logger les accès refusés via `log_action`
- [x] **Tests & Validation**
    - [x] Tests unitaires pour verrouillage, accès refusé, et permissions
    - [x] Tests d'intégration minimaux (user admin vs opérateur)

## 🧾 Documentation
- [x] Mettre à jour `docs/CAHIER_DES_CHARGES.md` et `docs/CONFIGURATION.md` avec la politique d'accès

## Priorité et Prochaine Étape
- Priorité haute : sécurité (verrouillage + permission checks) puis documentation et tests.
- Prochaine action recommandée : implémenter le verrouillage complet dans `src/auth.py`.
