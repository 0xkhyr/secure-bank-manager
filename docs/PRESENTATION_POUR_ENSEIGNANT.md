# 🎤 Script de Présentation Technique — SecureBank (10–12 min)

> **Objectif :** présenter le projet de manière fluide, sans se perdre, avec démonstration **step-by-step**.  
> **Style :** pas de blabla, phrases courtes, démonstration guidée.

---

## 0) Préparation (AVANT d’entrer)

✅ Tout doit être prêt :

- Projet déjà lancé (Docker)
- Navigateur ouvert sur **Login**
- **Deux sessions séparées** (recommandé) :
  - Fenêtre / Profil 1 : `operator1` (Maker)
  - Fenêtre / Profil 2 : `admin1` ou `superadmin1` (Checker)
- MFA prêt (Google Authenticator / Authy) si possible

🎯 Objectif : zéro perte de temps pendant la soutenance.

---

## 1) Introduction (45–60 sec)

🎤 **À dire :**

Bonjour.  
Aujourd’hui je vais présenter mon projet : un système bancaire interne sécurisé, réalisé comme **prototype académique**.  
L’objectif n’est pas seulement de faire du CRUD, mais surtout de démontrer des mécanismes de sécurité et de traçabilité proches du domaine bancaire.

Les mécanismes clés sont :  
1) **MFA** (TOTP + backup codes),  
2) **Maker–Checker** pour sécuriser les opérations sensibles,  
3) **Audit vérifiable** basé sur hash chaining + HMAC pour détecter toute altération,  
4) **Protection contre les attaques** : anti brute-force (limitation des tentatives de login) et mitigation anti-abus / anti-DDoS au niveau application via rate limiting.

Je vais maintenant faire une démonstration complète étape par étape.

---

## 2) Lancement / Environnement reproductible (20–30 sec)

🎤 **À dire :**

Je lance l’application via Docker pour garantir un environnement reproductible.

✅ **Action (Terminal) :**
```bash
docker-compose up --build
```

(Si déjà lancé : juste montrer que Docker tourne, pas besoin de rebuild.)

---

## 3) Connexion + RBAC (1 min)

✅ **Action :** se connecter dans la fenêtre Opérateur (operator1)

🎤 **À dire :**

Le système utilise un contrôle d’accès RBAC avec trois rôles : Opérateur, Admin et SuperAdmin, selon le principe du moindre privilège.
Ici je suis connecté en tant qu’Opérateur : je peux exécuter les opérations métier, mais je ne peux pas modifier la sécurité ni les policies globales.

✅ **Action :**

Montrer sur le dashboard que les pages sensibles ne sont pas accessibles à l’opérateur (policies, panic mode, gestion roles).

---

## 4) MFA (2 min)

🎯 Premier “effet sécurité”.

### 4A) Activation MFA

✅ **Action :**

Aller dans Profile / Security / MFA

🎤 **À dire :**

Je vais activer la MFA basée sur TOTP, compatible Google Authenticator / Authy.

✅ **Action :**

- Montrer QR Code
- Scanner / entrer code OTP

### 4B) Backup Codes

✅ **Action :**

Afficher backup codes

🎤 **À dire :**

En plus du TOTP, le système génère des backup codes à usage unique pour la récupération.
Ils sont stockés hachés en base, comme un mot de passe, donc ils ne sont pas lisibles même avec un accès direct à la base.

### 4C) Seconde étape login

✅ **Action :**

- Logout/login rapide
- Montrer l’écran OTP

🎤 **À dire :**

On voit ici la deuxième étape MFA obligatoire après le mot de passe.

---

## 5) CRUD rapide (client + compte) (1 min)

✅ **Action :**

- Clients → Create : “Client Demo”
- Accounts → Create : solde initial (ex : 500)

🎤 **À dire :**

Ici on a la partie CRUD : création d’un client puis ouverture d’un compte bancaire.

---

## 6) Transaction sensible + Maker–Checker (3 min)

🎯 Partie la plus importante après audit.

### 6A) Initier un retrait (Maker)

✅ **Action (Opérateur) :**

- Transactions → Withdraw
- Montant : (ex : 400 ou supérieur au plafond)

🎤 **À dire :**

Maintenant je crée un retrait. Cette opération est sensible : elle ne sera pas exécutée directement.
Elle passe par Maker–Checker.

✅ **Action :**

Confirmer

### 6B) Statut Pending

✅ **Action :**

Pending approvals / Transactions pending

🎤 **À dire :**

On voit que l’opération est en statut Pending.
L’Opérateur ne peut pas valider sa propre opération.

### 6C) Validation (Checker)

✅ **Action (Fenêtre Admin/SuperAdmin) :**

- Ouvrir Pending approvals
- Approve

🎤 **À dire :**

Je valide maintenant l’opération en tant qu’Admin (Checker).
Le fait qu’un second utilisateur valide réduit fortement les risques de fraude interne.

✅ **Action :**

Retour au compte, montrer le solde mis à jour.

---

## 7) Policy Layer (1–2 min)

✅ **Action (SuperAdmin de préférence) :**

Policies → Changer une règle :
- Withdrawal limit OU
- Welcome message OU
- Session timeout

🎤 **À dire :**

Le Policy Layer permet de modifier les règles du système en temps réel, sans redémarrage.
C’est utile dans un contexte bancaire : limites, sécurité, messages.

✅ **Action :**

Revenir au dashboard et montrer que le changement s’applique immédiatement.

---

## 8) Panic Mode (1 min)

✅ **Action (SuperAdmin) :**

Security → Panic Mode → Activate

🎤 **À dire :**

En cas d’attaque suspectée, le SuperAdmin peut activer le Panic Mode :
toutes les opérations sensibles sont gelées immédiatement.

✅ **Action :**

Sur fenêtre opérateur, tenter un retrait → bloqué

🎤 **À dire :**

Ici on voit que le système bloque l’action : c’est une réponse rapide aux incidents.

(Désactiver si nécessaire.)

---

## 9) Audit & Integrity Proof (2–3 min)

🎯 Partie “niveau ingénieur”.

✅ **Action :**

Audit logs → Afficher log du retrait

🎤 **À dire :**

Chaque action importante génère un audit log.
Mais ici l’objectif n’est pas seulement d’enregistrer : c’est de garantir l’intégrité du journal.

✅ **Action :**

Montrer `previous_hash` + `hash` + `hmac`

🎤 **À dire :**

Chaque log contient le hash du log précédent (hash chaining) et une signature HMAC-SHA256.
Donc si quelqu’un modifie un log directement dans la base, la vérification échoue.

✅ **Action :**

Verify integrity / Audit verification

🎤 **À dire :**

Je lance maintenant la vérification automatique : le système prouve que l’historique n’a pas été modifié.

⚠️ **Phrase importante :**
Ce n’est pas “physiquement immuable”, mais c’est tamper-evident : toute altération devient détectable.

---

## 10) Tests (45 sec – 1 min)

✅ **Action (Terminal) :**
```bash
docker exec -it secure_bank_manager python -m pytest tests/
```

🎤 **À dire :**

Et pour la qualité, j’ai une suite de tests Pytest sur les parties critiques.

---

## Conclusion (15–20 sec)

🎤 **À dire :**

Pour conclure, ce projet démontre des mécanismes bancaires réels :
MFA, Maker–Checker, policies dynamiques, panic mode et audit vérifiable.
Merci. Je suis prêt pour vos questions.

---

## Cheat-sheet (si stress)

**Ordre à retenir :**
Login → MFA → CRUD → Withdraw Pending → Approve → Policies → Panic → Audit Verify → Pytest