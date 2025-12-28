"""
Helpers for working with DB-backed policies and common policy-based decorators.
"""
from functools import wraps
from typing import Callable, Any
from flask import abort

from src.policy import get_policy


def get_policy_int(key: str, default: Any = None) -> Any:
    """Return policy value cast to int or `default` on failure."""
    val = get_policy(key, default=default)
    try:
        return int(val)
    except Exception:
        return default


def get_policy_bool(key: str, default: bool = False) -> bool:
    """Return policy as a boolean. Accepts common string representations."""
    val = get_policy(key, default=default)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("1", "true", "yes", "on")
    return bool(val)


def require_policy_max(key: str, amount_getter: Callable[..., Any]):
    """Decorator that aborts with 403 if the given amount exceeds the policy `key`.

    amount_getter is a callable that receives the same args/kwargs as the wrapped
    view/function and must return a numeric value (or a string parseable to float).
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
                # Invalid amount -> bad request
                abort(400)
            if amount > limit:
                abort(403)
            return f(*args, **kwargs)

        return wrapped

    return decorator


def enforce_withdrawal_limit(amount: Any) -> bool:
    """Return True if `amount` is within the configured daily withdrawal limit."""
    limit = get_policy_int('retrait.limite_journaliere', default=None)
    if limit is None:
        return True
    try:
        return float(amount) <= limit
    except Exception:
        return False
