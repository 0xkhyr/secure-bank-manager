# Configuration du Système - Résumé Technique

## 📝 Objectif

Rendre les règles métier bancaires configurables via des variables d'environnement, permettant à la banque de modifier ces valeurs sans toucher au code source.

## 🎯 Règles Métier Configurables

### Devise
- **Variable**: `DEVISE`
- **Valeur par défaut**: `TND` (Dinar Tunisien)
- **Description**: Code de la devise utilisée dans toute l'application

### Solde Minimum Initial
- **Variable**: `SOLDE_MINIMUM_INITIAL`
- **Valeur par défaut**: `250.000` TND
- **Description**: Montant minimum requis lors de l'ouverture d'un nouveau compte bancaire
- **Utilisation**: Vérifié dans `Compte.valider_creation()`

### Solde Minimum Après Opérations
- **Variable**: `SOLDE_MINIMUM_COMPTE`
- **Valeur par défaut**: `0.000` TND
- **Description**: Solde minimum autorisé après un retrait
- **Utilisation**: Vérifié dans `Compte.peut_retirer()`

### Retrait Maximum
- **Variable**: `RETRAIT_MAXIMUM`
- **Valeur par défaut**: `500.000` TND
- **Description**: Montant maximum autorisé pour un seul retrait
- **Utilisation**: Vérifié dans `Compte.peut_retirer()` et `Operation.validate_business_rules()`

## 🏗️ Architecture de Configuration

### Module `src/config.py`
Centralise toutes les variables d'environnement et les expose via la classe `Config`.

```python
from src.config import Config

# Accéder aux valeurs configurées
devise = Config.DEVISE
solde_min = Config.SOLDE_MINIMUM_INITIAL
retrait_max = Config.RETRAIT_MAXIMUM
```

### Fichiers de Configuration
- **`.env`**: Fichier réel avec les valeurs (git ignoré, contient les secrets)
- **`.env.example`**: Template avec valeurs par défaut (versionné dans git)

### Intégration dans les Modèles

#### `Compte.valider_creation(depot_initial)`
```python
def valider_creation(self, depot_initial):
    depot_initial = Decimal(str(depot_initial))
    return depot_initial >= Config.SOLDE_MINIMUM_INITIAL
```

#### `Compte.peut_retirer(montant)`
```python
def peut_retirer(self, montant):
    montant = Decimal(str(montant))
    if montant <= 0:
        return False
    if montant > Config.RETRAIT_MAXIMUM:
        return False
    return (self.solde - montant) >= Config.SOLDE_MINIMUM_COMPTE
```

#### `Operation.validate_business_rules()`
```python
def validate_business_rules(self):
    if self.type_operation == TypeOperation.RETRAIT:
        if not self.compte.peut_retirer(self.montant):
            raise ValueError(
                f"Retrait non autorisé : limite {Config.RETRAIT_MAXIMUM} {Config.DEVISE} "
                f"ou solde insuffisant (minimum {Config.SOLDE_MINIMUM_COMPTE} {Config.DEVISE})"
            )
```

## 🧪 Tests de Configuration

Le script `tests/test_config.py` vérifie que :
1. ✅ La configuration se charge correctement depuis `.env`
2. ✅ Les dépôts initiaux insuffisants sont refusés
3. ✅ Les dépôts initiaux valides sont acceptés
4. ✅ Les retraits excessifs sont refusés
5. ✅ Les retraits valides sont acceptés
6. ✅ Les retraits causant solde négatif sont refusés
7. ✅ La devise est correctement configurée

### Exécution des Tests
```bash
source .venv/bin/activate
PYTHONPATH=/home/mohamed/Documents/projects/secure-bank-manager python tests/test_config.py
```

## 📊 Résultats des Tests

```
╔════════════════════════════════════════════════════════════╗
║  Test du système de configuration                         ║
╚════════════════════════════════════════════════════════════╝

=== Test 1: Chargement de la configuration ===
✓ Configuration chargée avec succès

=== Test 2: Règles métier des comptes ===
✓ Dépôt insuffisant (200.000 TND) correctement refusé
✓ Dépôt initial valide (250.000 TND) accepté
✓ Retrait excessif (600.000 TND) correctement refusé (max: 500.000 TND)
✓ Retrait valide (450.000 TND) accepté
✓ Retrait causant solde insuffisant correctement refusé
✓ Toutes les règles métier utilisent bien la configuration

=== Test 3: Configuration de la devise ===
✓ Devise correctement configurée: TND

╔════════════════════════════════════════════════════════════╗
║  ✓ TOUS LES TESTS RÉUSSIS                                 ║
╚════════════════════════════════════════════════════════════╝
```

## 🔄 Modifier les Règles Métier

### Scénario: La banque décide d'augmenter le retrait maximum à 1000 TND

1. **Modifier le fichier `.env`**:
```bash
RETRAIT_MAXIMUM=1000.000
```

2. **Redémarrer l'application**:
```bash
./stop.sh
./start.sh
```

3. **Vérifier la nouvelle configuration**:
```bash
python src/config.py
```

**Aucune modification de code n'est nécessaire** ! 🎉

## 📚 Documentation

- ✅ Ajout section configuration dans `README.md`
- ✅ Documentation des variables dans `.env.example`
- ✅ Commentaires en français dans `config.py`
- ✅ Tests automatisés pour valider le comportement

## ✅ Checklist de Complétion

- [x] Créer `src/config.py` avec classe `Config`
- [x] Importer `Config` dans tous les modèles
- [x] Remplacer valeurs hardcodées par `Config.*`
- [x] Ajouter variables dans `.env` et `.env.example`
- [x] Mettre à jour `db.py` pour utiliser `Config.DATABASE_PATH`
- [x] Mettre à jour `app.py` pour utiliser `Config.SECRET_KEY`
- [x] Créer tests automatisés dans `tests/test_config.py`
- [x] Mettre à jour la documentation dans `README.md`
- [x] Recréer la base de données avec les nouveaux modèles
- [x] Valider tous les tests passent

## 🎓 Justification Académique

Cette approche démontre plusieurs compétences importantes :

1. **Séparation des responsabilités** : Configuration séparée du code métier
2. **Principe DRY** : Une seule source de vérité pour les constantes
3. **Maintenabilité** : Changements de règles sans modification de code
4. **Sécurité** : Secrets dans `.env` (non versionnés)
5. **Tests** : Validation automatisée du comportement
6. **Documentation** : Instructions claires pour modifier la configuration

Cette architecture respecte les bonnes pratiques professionnelles et facilite la maintenance future de l'application.
