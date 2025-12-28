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
    # Use a *fresh* non-scoped session to avoid closing the request-scoped session
    from src.db import session_factory
    session = session_factory()
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


def valider_politique(key: str, value: Any, type_: str = 'string'):
    """Valide et normalise une politique selon son type et sa clé.

    Retourne (valeur_normalisee_str, type_field).
    Lève ValueError en cas d'erreur de validation.
    """
    # Normalisation par type
    if type_ == 'json' or isinstance(value, (dict, list)):
        # si c'est une chaîne, essayer de parser
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except Exception:
                raise ValueError("Valeur JSON invalide")
        else:
            parsed = value
        valeur_norm = json.dumps(parsed, ensure_ascii=False)
        type_field = 'json'
        python_value = parsed
    elif type_ == 'int':
        try:
            iv = int(value)
        except Exception:
            raise ValueError("Valeur entière attendue")
        valeur_norm = str(iv)
        type_field = 'int'
        python_value = iv
    elif type_ == 'bool':
        if isinstance(value, bool):
            bv = value
        elif isinstance(value, str):
            bv = value.lower() in ('1', 'true', 'yes', 'on')
        elif isinstance(value, int):
            bv = value != 0
        else:
            raise ValueError("Valeur booléenne attendue")
        valeur_norm = 'true' if bv else 'false'
        type_field = 'bool'
        python_value = bv
    else:
        s = str(value).strip()
        if len(s) == 0:
            raise ValueError("La valeur ne peut pas être vide")
        if len(s) > 2000:
            raise ValueError("La valeur est trop longue")
        valeur_norm = s
        type_field = 'string'
        python_value = s

    # Validation par clé (règles métiers)
    if key == 'mot_de_passe.duree_validite_jours':
        if not isinstance(python_value, int) or python_value < 1 or python_value > 365:
            raise ValueError('mot_de_passe.duree_validite_jours doit être un entier entre 1 et 365')
    if key == 'mot_de_passe.longueur_min':
        if not isinstance(python_value, int) or python_value < 6:
            raise ValueError('mot_de_passe.longueur_min doit être un entier >= 6')
    if key in ('retrait.limite_par_operation', 'retrait.limite_journaliere'):
        if not isinstance(python_value, int) or python_value < 0:
            raise ValueError(f"{key} doit être un entier positif")
    if key == 'mfa.roles_obligatoires':
        if not isinstance(python_value, (list, tuple)):
            raise ValueError('mfa.roles_obligatoires doit être une liste de rôles')
        allowed = {'admin', 'superadmin', 'operateur'}
        for r in python_value:
            if r not in allowed:
                raise ValueError(f"Rôle inconnu dans mfa.roles_obligatoires: {r}")

    return valeur_norm, type_field


def set_policy(key: str, value: Any, type_: str = 'string', description: Optional[str] = None, changed_by: Optional[int] = None, comment: Optional[str] = None):
    """Create or update a policy and log the change."""
    # Use a fresh non-scoped session so request-scoped session (g.user) is not closed while handling a request.
    from src.db import session_factory
    session = session_factory()
    try:
        # Validate and normalize
        valeur_str, type_field = valider_politique(key, value, type_)

        # Enforce comment when key requires approval
        try:
            requis = get_policy('changement_politique.requiert_approbation', [])
        except Exception:
            requis = []
        if isinstance(requis, (list, tuple)) and key in requis and (not comment or comment.strip() == ''):
            raise ValueError('Modification critique : un commentaire est requis pour cette clé')

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
