# 🎤 Script Présentation Technique (Version courte) — SecureBank (6–8 min)

> Objectif : présentation rapide + démonstration directe sans perdre du temps.
> Pas de partie “lancement du projet”.

---

## 1) Introduction (20–30 sec)

🎤 À dire :

Bonjour.  
Je présente mon projet **SecureBank** : un système bancaire interne sécurisé (prototype académique).  
Le projet se concentre sur :  
- le contrôle des opérations sensibles (**Maker–Checker**),  
- la traçabilité (**audit vérifiable** : hash chaining + HMAC),  
- et la sécurité d’accès (RBAC + protections anti-abus).

Je vais faire une démonstration directement via les rôles : Opérateur → Admin → SuperAdmin.

---

## 2) Connexion Opérateur (30 sec)

✅ Action :
- Login avec `operator1`

🎤 À dire :

Je commence avec le rôle **Opérateur**.  
Ce rôle est limité aux opérations métier uniquement (principe du moindre privilège).  
Dans mon système, la MFA n’est **pas obligatoire** pour l’Opérateur, car il n’a pas accès aux fonctions critiques de sécurité.

---

## 3) Démonstration Opérateur (2–3 min)

### 3.1 CRUD (Client + Compte) (40 sec)
✅ Action :
- Clients → Create (“Client Demo”)
- Accounts → Create (solde initial : 500)

🎤 À dire :

Ici la partie CRUD : création d’un client et ouverture d’un compte.

---

### 3.2 Opération sensible (Maker) : Retrait (1–2 min)
✅ Action :
- Transactions → Withdraw
- Montant : ex. 400 (ou volontairement élevé)

🎤 À dire :

Je crée un retrait.  
Comme c’est une opération sensible, elle n’est pas exécutée directement : elle passe par un workflow **Maker–Checker**.

✅ Action :
- montrer que l’opération est **PENDING**

🎤 À dire :

On voit que l’opération est en statut **Pending** : l’Opérateur ne peut pas valider sa propre transaction.

---

## 4) Passage Admin (Checker) + MFA obligatoire (1–2 min)

✅ Action :
- Logout `operator1`
- Login `admin1`
- (MFA step obligatoire)
- Pending approvals → Approve

🎤 À dire :

Je passe maintenant au rôle **Admin**.  
Ici la **MFA est obligatoire**, car c’est un rôle à privilèges : il peut valider des opérations sensibles.

Je valide donc la transaction en tant que **Checker**.

✅ Action :
- retour au compte / transactions
- montrer que transaction est Approved + solde mis à jour

---

## 5) Passage SuperAdmin (1–2 min)

✅ Action :
- Logout `admin1`
- Login `superadmin1`
- (MFA step obligatoire)

🎤 À dire (phrase importante) :

Le **SuperAdmin** peut faire tout ce que fait un Admin, **mais il a en plus** le contrôle global sécurité et pilotage système.

### 5.1 Policies (30–45 sec)
✅ Action :
- Policies → changer un paramètre (plafond, message, session timeout)

🎤 À dire :

Le Policy Layer permet de modifier les règles du système en temps réel, sans redémarrage.

### 5.2 Panic Mode (30–45 sec)
✅ Action :
- Panic Mode → Activer

🎤 À dire :

En cas d’incident, le SuperAdmin active le **Panic Mode** : les opérations sensibles sont gelées immédiatement.

*(Option rapide : revenir sur opérateur et tenter un retrait → bloqué.)*

---

## 6) Audit (preuve rapide) (45 sec – 1 min)

✅ Action :
- Audit logs → ouvrir log de la transaction
- Verify integrity (si bouton existe)

🎤 À dire :

Chaque action importante est enregistrée dans un journal d’audit.  
Ce journal est **vérifiable** : hash chaining + signature HMAC.  
Donc toute modification directe en base devient **détectable** (tamper-evident).

---

## 7) Conclusion (10–15 sec)

🎤 À dire :

Pour conclure : le projet démontre des mécanismes bancaires concrets :  
Maker–Checker, MFA obligatoire pour rôles privilégiés, policies dynamiques, panic mode et audit vérifiable.  
Merci, je suis prêt pour vos questions.

---

## Cheat-sheet (si stress)

Opérateur (CRUD + retrait Pending) → Admin (MFA + Approve) → SuperAdmin (MFA + Policies + Panic) → Audit
