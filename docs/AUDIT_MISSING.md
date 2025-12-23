# Actions Manquantes - Journal d'Audit

Ce document recense toutes les actions qui devraient être auditées mais qui ne le sont pas actuellement, organisées par priorité.

---

## 🔴 CRITIQUE (Sécurité) - Phase 1 ✅ TERMINÉ

### 1. Tentatives d'opérations échouées (operations.py)
- [x] Dépôt échoué - validation
- [x] Dépôt échoué - exception
- [x] Retrait échoué - validation
- [x] Retrait échoué - exception

**Fichier:** `src/operations.py`  
**Impact:** Détection de fraude, surveillance des activités suspectes  
**Statut:** ✅ Implémenté

---

### 2. Expiration de session (auth.py)
- [x] Logger SESSION_EXPIREE avant session.clear()

**Fichier:** `src/auth.py`  
**Ligne:** 146-149  
**Impact:** Surveillance de sécurité, détection d'anomalies  
**Statut:** ✅ Implémenté

---

### 3. Accès au journal d'audit (audit_logger.py)
- [x] Logger consultation liste audit (index)
- [x] Logger consultation entrée audit (view)
- [x] Logger vérification d'intégrité (verify)

**Fichier:** `src/audit_logger.py`  
**Impact:** "Qui surveille les surveillants" - traçabilité des accès aux logs  
**Statut:** ✅ Implémenté

---

### 4. Consultation de données sensibles
- [x] Logger consultation détails client (clients.view)
- [x] Logger consultation liste clients (clients.index)
- [x] Logger consultation compte + historique (accounts.view)
- [x] Logger consultation détails utilisateur (users.view)
- [x] Logger consultation liste utilisateurs (users.index)

**Impact:** Conformité RGPD/réglementaire, traçabilité des accès  
**Statut:** ✅ Implémenté

---
## 🟠 IMPORTANT (Détection d'escalade de privilèges)

## 🟠 IMPORTANT (Détection d'escalade de privilèges) - Phase 2 ✅ TERMINÉ

### 5. Tentatives de gestion utilisateurs échouées (users.py)
- [x] Logger création utilisateur échouée
- [x] Logger modification utilisateur échouée
- [x] Logger activation/désactivation échouée
- [x] Logger reset password échoué

**Fichier:** `src/users.py`  
**Impact:** Détection de tentatives d'escalade de privilèges  
**Statut:** ✅ Implémenté

**Actions auditées:**
- ECHEC_CREATION_UTILISATEUR (nom_utilisateur_vide, mot_de_passe_vide, mot_de_passe_faible, role_non_autorise, role_invalide, nom_utilisateur_deja_existant, exception_systeme)
- ECHEC_MODIFICATION_UTILISATEUR (permission_refusee, nom_utilisateur_vide, auto_modification_role, role_non_autorise, role_invalide, exception_systeme)
- ECHEC_ACTIVATION_UTILISATEUR (permission_refusee, auto_desactivation, exception_systeme)
- ECHEC_RESET_PASSWORD_UTILISATEUR (permission_refusee, mot_de_passe_faible, exception_systeme)

---

### 6. Vérification d'intégrité du journal
- [x] Logger résultat vérification (succès)
- [x] Logger résultat vérification (échec avec détails)

**Fichier:** `src/audit_logger.py`  
**Impact:** Surveillance de l'intégrité du système d'audit  
**Statut:** ✅ Implémenté (dans Phase 1)

**Action auditée:** VERIFICATION_INTEGRITE_AUDIT avec résultat (valide/compromis) et détails

---

**Fichier:** `src/audit_logger.py`  
**Impact:** Surveillance de l'inté - Phase 3

### 7. Accès aux formulaires d'opérations (operations.py)
- [ ] Logger accès formulaire dépôt (GET)
- [ ] Logger accès formulaire retrait (GET)
**Fichier:** `src/operations.py`  
**Impact:** Analyse comportementale, détection d'intentions

- **Formulaire dépôt** (GET `/operations/depot/<compte_id>`) - ligne 21
- **Formulaire retrait** (GET `/operations/retrait/<compte_id>`) - ligne 96

**Action recommandée:** Logger ACCES_FORMULAIRE_DEPOT/RETRAIT avec compte_id

---

### 8. Déverrouillage automatique de compte
**Fichier:** `src/auth.py`  
**Impact:** Traçabilité des verrouillages/déverrouillages
- [ ] Logger déverrouillage automatique

**Fichier:** `src/auth.py`  
**Impact:** Traçabilité des verrouillages/déverrouillages

## ⚪ FONCTIONNALITÉS MANQUANTES

Ces opérations n'existent pas encore mais devraient être auditées lors de leur implémentation :

### Clients (clients.py)
- ❌ **Modification client** - Route `/clients/<id>/edit` (n'existe pas)
- ❌ **Suppression client** - Route `/clients/<id>/delete` (n'existe pas)

### Comptes (accounts.py)
- ❌ **Modification compte** - Route `/accounts/<id>/edit` (n'existe pas)
- ❌ **Suppression compte** - Route `/accounts/<id>/delete` (n'existe pas)

**Note:** Ces routes doivent inclure l'audit dès leur création.

---

## 📊 Résumé des Priorités

| Priorité | Actions | Impact Sécurité | Impact Conformité |
|----------|---------|-----------------|-------------------|
| 🔴 Critique | 4 catégories | ⭐⭐⭐ | ⭐⭐⭐ |
| 🟠 Important | 2 catégories | ⭐⭐⭐ | ⭐⭐ |
| 🟡 Utile | 2 catégories | ⭐ | ⭐⭐ |
| ⚪ Futur | 4 routes | N/A | N/A |

**Total estimé:** ~25-30 points d'audit manquants

---

## 🎯 Plan d'Implémentation Recommandé

### Phase 1 - Sécurité (Priorité Critique)
1. Tentatives d'opérations échouées
2. Expiration de session
3. Accès au journal d'audit
4. Consultation de données sensibles

### Phase 2 - Privilèges (Priorité Importante)
5. Tentatives de gestion utilisateurs échouées
6. Vérification d'intégrité

### Phase 3 - Analyse (Priorité Utile)
7. Accès aux formulaires
8. Déverrouillage automatique

### Phase 4 - Futur
Implémenter les routes manquantes avec audit intégré

---

## 📝 Notes Techniques

### Format d'audit recommandé

```python
# Succès
log_action(user_id, "ACTION", "Cible", {"key": "value"})

# Échec
log_action(user_id, "ECHEC_ACTION", "Cible", {
    "raison": "description_courte",
    "details": "information_supplementaire"
})
```

### Actions suggérées

- `CONSULTATION_CLIENT` / `CONSULTATION_COMPTE` / `CONSULTATION_UTILISATEUR`
- `ECHEC_DEPOT` / `ECHEC_RETRAIT`
- `SESSION_EXPIREE`
- `CONSULTATION_AUDIT` / `VERIFICATION_INTEGRITE_AUDIT`
- `ECHEC_CREATION_UTILISATEUR` / `ECHEC_MODIFICATION_UTILISATEUR`
- `ACCES_FORMULAIRE_DEPOT` / `ACCES_FORMULAIRE_RETRAIT`
- `DEVERROUILLAGE_AUTO`

---

**Dernière mise à jour:** 22 décembre 2025  
**Statut actuel:** Phases 1, 2 et 3 ✅ terminées (~75% d'audit coverage)
