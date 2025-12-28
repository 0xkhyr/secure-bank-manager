from decimal import Decimal
from src.policy import set_policy, invalidate_cache
from src.db import obtenir_session
from src.operations import effectuer_operation
from src.models import Client, Compte, Utilisateur, TypeOperation


def test_retrait_velocity_db_blocks_after_limit():
    # Enable velocity and set limit to 2 per minute
    set_policy('velocity.actif', 'true', type_='bool', comment='test')
    set_policy('velocity.retrait.max_par_minute', 2, type_='int', comment='test')
    invalidate_cache()

    session = obtenir_session()
    try:
        # Use an existing user or create one
        user = session.query(Utilisateur).first()
        if not user:
            user = Utilisateur(nom_utilisateur='velotest', mot_de_passe_hash='x', is_active=True)
            session.add(user)
            session.commit()

        # Create a client and account for the withdrawal
        client = Client(nom='Test', prenom='Client', cin='CIN123')
        session.add(client)
        session.commit()
        compte = Compte(numero_compte='VT' + str(client.id), client_id=client.id, solde=Decimal('1000.00'))
        session.add(compte)
        session.commit()

        # First two withdrawals should succeed
        ok1, _ = effectuer_operation(compte.id, Decimal('10'), TypeOperation.RETRAIT, user.id)
        ok2, _ = effectuer_operation(compte.id, Decimal('20'), TypeOperation.RETRAIT, user.id)
        assert ok1 is True
        assert ok2 is True

        # Third within the minute should be blocked by velocity
        ok3, msg = effectuer_operation(compte.id, Decimal('5'), TypeOperation.RETRAIT, user.id)
        assert ok3 is False
        assert 'Trop de retraits' in msg
    finally:
        # Cleanup added records to keep DB tidy
        try:
            session.query(Compte).filter_by(id=compte.id).delete()
            session.query(Client).filter_by(id=client.id).delete()
            session.commit()
        except Exception:
            session.rollback()
        session.close()
