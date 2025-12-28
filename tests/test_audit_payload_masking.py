from src.db import obtenir_session
from src.checker import soumettre_approbation
from src.policy import invalidate_cache
from src.audit_logger import calculer_hmac
import json


def test_payload_masking_in_audit():
    session = obtenir_session()
    try:
        user = session.query(__import__('src.models', fromlist=['Utilisateur']).Utilisateur).first()
        assert user is not None

        payload = {
            'compte_id': 1,
            'montant': '205',
            'description': '',
            'date_demande': '2025-12-28T05:29:09.875662',
            'numero_compte': '12345678'
        }

        demande = soumettre_approbation(session, 'RETRAIT_EXCEPTIONNEL', payload, user.id)
        session.commit()

        # read latest journal entry
        from src.db import obtenir_session
        s2 = obtenir_session()
        from src.models import Journal
        last = s2.query(Journal).order_by(Journal.id.desc()).first()
        assert last is not None
        details = json.loads(last.details)
        assert 'payload' in details
        payload_logged = details['payload']
        assert payload_logged.get('numero_compte') is not None
        # masked form should hide all but last 4 chars
        assert payload_logged['numero_compte'].endswith('5678')
        assert payload_logged['numero_compte'].startswith('*')
    finally:
        # cleanup: remove the created OperationEnAttente if present
        try:
            if demande and demande.id:
                session = obtenir_session()
                session.query(__import__('src.models', fromlist=['OperationEnAttente']).OperationEnAttente).filter_by(id=demande.id).delete()
                session.commit()
        except Exception:
            pass
        s2.close()