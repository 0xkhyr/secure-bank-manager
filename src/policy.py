"""Policy loader and cache

Provides simple functions to read and update policies stored in DB, with a memory cache
and TTL. Admin code should call `set_policy` to update and `invalidate_cache` to force
reload.
"""
import json
import threading
import time
from datetime import datetime
from typing import Any, Optional

from src.db import obtenir_session
from src.models import Policy, PolicyHistory
from src.audit_logger import log_action

# Cache settings
_CACHE = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 30  # seconds
_CACHE_LOADED_AT = 0


def _load_from_db():
    session = obtenir_session()
    try:
        rows = session.query(Policy).filter_by(active=True).all()
        data = {}
        for p in rows:
            # attempt to decode JSON values when type == json
            if p.type == 'json':
                try:
                    data[p.key] = json.loads(p.value)
                except Exception:
                    data[p.key] = p.value
            elif p.type == 'int':
                try:
                    data[p.key] = int(p.value)
                except Exception:
                    data[p.key] = p.value
            elif p.type == 'bool':
                data[p.key] = p.value.lower() in ('1', 'true', 'yes', 'on') if isinstance(p.value, str) else bool(p.value)
            else:
                data[p.key] = p.value
        return data
    finally:
        session.close()


def _ensure_cache():
    global _CACHE_LOADED_AT, _CACHE
    with _CACHE_LOCK:
        if time.time() - _CACHE_LOADED_AT > _CACHE_TTL:
            _CACHE = _load_from_db()
            _CACHE_LOADED_AT = time.time()


def get_policy(key: str, default: Any = None) -> Any:
    _ensure_cache()
    return _CACHE.get(key, default)


def invalidate_cache():
    global _CACHE_LOADED_AT
    with _CACHE_LOCK:
        _CACHE_LOADED_AT = 0


def set_policy(key: str, value: Any, type_: str = 'string', description: Optional[str] = None, changed_by: Optional[int] = None, comment: Optional[str] = None):
    """Create or update a policy and log the change."""
    session = obtenir_session()
    try:
        # normalize value to string
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value, ensure_ascii=False)
            type_field = 'json'
        else:
            value_str = str(value)
            type_field = type_

        policy = session.query(Policy).filter_by(key=key).first()
        old_value = None
        if policy:
            old_value = policy.value
            policy.value = value_str
            policy.type = type_field
            policy.description = description or policy.description
            policy.updated_at = datetime.utcnow()
        else:
            policy = Policy(key=key, value=value_str, type=type_field, description=description, created_by=changed_by)
            session.add(policy)
            session.flush()

        # Append history
        hist = PolicyHistory(policy_id=policy.id, key=policy.key, value=value_str, type=policy.type, changed_by=changed_by, comment=comment)
        session.add(hist)

        session.commit()

        # Audit log
        details = {"key": key, "old": old_value, "new": value_str}
        if comment:
            details['comment'] = comment
        try:
            log_action(changed_by, 'POLICY_CHANGE', key, details)
        except Exception:
            pass

        invalidate_cache()
        return True
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()
