"""
# Utilitaires pour l'accès aux politiques de sécurité dynamiques.
# Sécurité : Centralise les helpers de validation et les décorateurs de contrôle de conformité.
"""
from functools import wraps
from typing import Callable, Any
from flask import abort

from src.policy import get_policy


def get_policy_int(key: str, default: Any = None) -> Any:
    """
    # Sécurité : Récupère une valeur de politique castée en entier avec gestion sécurisée des erreurs.
    """
    val = get_policy(key, default=default)
    try:
        return int(val)
    except Exception:
        return default


def get_policy_bool(key: str, default: bool = False) -> bool:
    """
    # Sécurité : Évalue une politique booléenne avec support des formats de chaînes standard.
    """
    val = get_policy(key, default=default)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("1", "true", "yes", "on")
    return bool(val)


def require_policy_max(key: str, amount_getter: Callable[..., Any]):
    """
    # Sécurité : Décorateur appliquant un plafond dynamique défini par les politiques de sécurité.
    # Limitation : Interrompt la requête (403 Forbidden) si le seuil configuré est dépassé.
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            limit = get_policy_int(key, default=None)
            if limit is None:
                return f(*args, **kwargs)
            amount = amount_getter(*args, **kwargs)
            try:
                amount = float(amount)
            except Exception:
                # Sécurité : Rejette les entrées malformées.
                abort(400)
            if amount > limit:
                # Limitation : Refus d'accès pour dépassement de quota ou seuil.
                abort(403)
            return f(*args, **kwargs)

        return wrapped

    return decorator


def enforce_withdrawal_limit(amount: Any) -> bool:
    """
    # Règle métier : Vérifie si le montant respecte le plafond de retrait journalier configuré.
    """
    limit = get_policy_int('retrait.limite_journaliere', default=None)
    if limit is None:
        return True
    try:
        return float(amount) <= limit
    except Exception:
        return False
