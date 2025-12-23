# Démonstration de Sécurité : Journal d'Audit Inviolable

Ce document détaille l'architecture de sécurité mise en place pour garantir l'intégrité absolue des journaux d'audit de l'application bancaire.

## 🛡️ Architecture de Sécurité

Notre système utilise une double couche de protection cryptographique pour empêcher toute falsification de l'historique des actions :

1.  **Chain Hash (Chaîne de Hachage)** : Lie mathématiquement chaque entrée à la précédente.
2.  **HMAC (Hash-based Message Authentication Code)** : Signe chaque entrée avec une clé secrète.

---

## 1. Le Principe de la "Hack Chain" (Chain Hash)

Chaque entrée du journal contient l'empreinte numérique (hash) de l'entrée qui la précède. Cela crée une chaîne ininterrompue depuis le tout premier événement (Genesis).

### Formule de Calcul

Pour chaque ligne, nous calculons un hash SHA-256 unique basé sur :
`Hash = SHA256( Date + Utilisateur + Action + Détails + Hash_Précédent )`

### Exemple de Chaîne Valide

Voici à quoi ressemble la base de données dans un état sain :

| ID | Action | Hash Précédent (Lien) | Hash Actuel (Empreinte) | État |
| :--- | :--- | :--- | :--- | :--- |
| **1** | `DEMARRAGE` | `GENESIS_HASH` | **`a1b2...`** | ✅ Valide |
| **2** | `CONNEXION` | **`a1b2...`** (Vient de l'ID 1) | **`c3d4...`** | ✅ Valide |
| **3** | `VIREMENT` | **`c3d4...`** (Vient de l'ID 2) | **`e5f6...`** | ✅ Valide |
| **4** | `DECONNEXION`| **`e5f6...`** (Vient de l'ID 3) | **`g7h8...`** | ✅ Valide |

> **Observation :** Si on modifie l'ID 2, son hash `c3d4...` change. L'ID 3 ne correspondra plus, car il s'attend à ce que le précédent soit `c3d4...`. La chaîne est brisée.

---

## 2. La Signature HMAC (Authentification)

Le hachage seul ne suffit pas (un pirate pourrait recalculer tous les hashs de la chaîne). C'est pourquoi nous utilisons **HMAC**.

Chaque ligne est signée avec une **clé secrète** connue uniquement du serveur (`Config.HMAC_SECRET_KEY`).

`Signature = HMAC_SHA256( Données, Clé_Secrète )`

Même si un attaquant (ex: un administrateur de base de données malveillant) modifie les données et recalcule les hashs, il ne pourra pas générer une signature valide sans la clé secrète.

---

## 3. Scénario d'Attaque : Tentative de Fraude

Imaginons qu'un attaquant essaie de modifier le montant d'un virement dans l'historique (ID 3).

### Avant l'attaque (État Intègre)

| ID | Action | Montant | Hash Actuel | Signature HMAC | Vérification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 3 | `VIREMENT` | **1000 €** | `hash_original` | `sign_originale` | ✅ OK |

### Après l'attaque (Modification en Base de Données)

L'attaquant change le montant de 1000 € à 10 € directement en SQL.

| ID | Action | Montant | Hash Stocké | Hash Réel (Recalculé) | Signature Stockée | Signature Réelle | Résultat |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 3 | `VIREMENT` | **10 €** 🔴 | `hash_original` | **`nouveau_hash`** | `sign_originale` | **`nouvelle_sign`** | 🚨 **ALERTE** |

### Conséquences Immédiates

Le système de vérification (`verifier_integrite()`) détectera **3 anomalies simultanées** :

1.  **Intégrité des données (Hash)** : Le hash stocké ne correspond plus au contenu (10 € vs 1000 €).
2.  **Authenticité (HMAC)** : La signature est invalide car l'attaquant n'a pas la clé secrète.
3.  **Chaînage (Chain)** : L'entrée suivante (ID 4) référence l'ancien hash (`hash_original`), créant une rupture visible.

### Exemple de Rapport d'Erreur

```text
[ALERTE DE SÉCURITÉ] Intégrité compromise !
---------------------------------------------------
ERREUR 1 : Log #3 : Données corrompues (Hash invalide)
ERREUR 2 : Log #3 : Signature falsifiée (HMAC invalide)
ERREUR 3 : Log #4 : Rupture de chaîne (Hash précédent invalide)
```

---

## Conclusion

Cette architecture garantit que :
1.  **Immutabilité** : On ne peut pas changer le passé.
2.  **Détection** : Toute modification est immédiatement visible.
3.  **Preuve** : Les logs peuvent servir de preuve légale grâce à la signature cryptographique.
