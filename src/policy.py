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
from src.models import Politique, HistoriquePolitique
from src.audit_logger import log_action

# Cache settings
_CACHE = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 30  # seconds
_CACHE_LOADED_AT = 0


def _load_from_db():
    session = obtenir_session()
    try:
        rows = session.query(Politique).filter_by(active=True).all()
        data = {}
        for p in rows:
            # tenter de décoder JSON lorsque type == json
            if p.type == 'json':
                try:
                    data[p.cle] = json.loads(p.valeur)
                except Exception:
                    data[p.cle] = p.valeur
            elif p.type == 'int':
                try:
                    data[p.cle] = int(p.valeur)
                except Exception:
                    data[p.cle] = p.valeur
            elif p.type == 'bool':
                data[p.cle] = p.valeur.lower() in ('1', 'true', 'yes', 'on') if isinstance(p.valeur, str) else bool(p.valeur)
            else:
                data[p.cle] = p.valeur
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
        # normaliser la valeur en chaîne
        if isinstance(value, (dict, list)):
            valeur_str = json.dumps(value, ensure_ascii=False)
            type_field = 'json'
        else:
            valeur_str = str(value)
            type_field = type_

        politique = session.query(Politique).filter_by(cle=key).first()
        ancienne_valeur = None
        if politique:
            ancienne_valeur = politique.valeur
            politique.valeur = valeur_str
            politique.type = type_field
            politique.description = description or politique.description
            politique.modifie_le = datetime.utcnow()
        else:
            politique = Politique(cle=key, valeur=valeur_str, type=type_field, description=description, cree_par=changed_by)
            session.add(politique)
            session.flush()

        # Ajouter à l'historique
        hist = HistoriquePolitique(politique_id=politique.id, cle=politique.cle, valeur=valeur_str, type=politique.type, modifie_par=changed_by, commentaire=comment)
        session.add(hist)

        session.commit()

        # Audit log
        details = {"cle": key, "old": ancienne_valeur, "new": valeur_str}
        if comment:
            details['commentaire'] = comment
        try:
            log_action(changed_by, 'CHANGEMENT_POLITIQUE', key, details)
        except Exception:
            pass

        invalidate_cache()
        return True
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()
