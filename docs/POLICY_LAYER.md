# Policy Layer — Guide d'utilisation

Ce document explique la couche de politiques dynamiques (`Policy`) ajoutée à l'application.

## But
Permet aux administrateurs de modifier des règles (seuils, timeouts, flags) sans redéploiement.

## Table `policies`
- `key` : identifiant (ex: `password.max_age_days`)
- `value` : valeur (texte ou JSON encodé)
- `type` : `string|int|json|bool`
- `active` : active/inactive
- `created_by` / `updated_at` : traçabilité

## Accès
- URL admin: `/admin/policies` (Admin / SuperAdmin)

## Exemples de clés utiles
- `password.max_age_days` : expiry en jours
- `rate.withdraw.daily_limit` : limite quotidienne de retrait
- `mfa.enforce_roles` : `['admin','superadmin']`

## Bonnes pratiques
- Toujours ajouter un commentaire lors d’un changement critique.
- Utiliser `apply now` pour invalider le cache si nécessaire.
- Pour la production, utiliser Alembic pour versionner les migrations.

## Notes techniques
- Cache mémoire avec TTL 30s (facile à invalider depuis l'UI).
- Les changements sont historisés dans `policy_history` et audités (`POLICY_CHANGE`).
