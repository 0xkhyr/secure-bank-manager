from src.db import obtenir_session
from src.models import Utilisateur, Client, Compte, TypeOperation, Operation
from src.operations import effectuer_operation
from src.policy import set_policy, invalidate_cache
from decimal import Decimal
from unittest.mock import patch

def test_retrait_velocity_db_blocks_after_limit():
    # Mocking policies instead of relying on DB/cache state which can be flaky in tests
    with patch('src.policy_helpers.get_policy_bool') as mock_bool, \
         patch('src.policy_helpers.get_policy_int') as mock_int, \
         patch('src.policy_helpers.get_policy') as mock_get:
        
        mock_bool.side_effect = lambda k, default=False: True if k == 'velocity.actif' else default
        mock_int.side_effect = lambda k, default=None: 2 if k == 'velocity.retrait.max_par_minute' else default
        mock_get.side_effect = lambda k, default=None: 'db' if k == 'velocity.methode' else default

        session = obtenir_session()
        try:
            # Use a unique CIN to avoid IntegrityError
            import secrets
            unique_cin = f'VELO_{secrets.token_hex(4)}'

            # Use an existing user or create one
            user = session.query(Utilisateur).filter_by(nom_utilisateur='admin').first()
            if not user:
                user = Utilisateur(nom_utilisateur='velotest', mot_de_passe_hash='x')
                session.add(user)
                session.commit()
    
            # Create a client and account for the withdrawal
            client = Client(nom='TestVelo', prenom='Client', cin=unique_cin, telephone='12345678')
            session.add(client)
            session.commit()
            compte = Compte(numero_compte='VT' + str(client.id), client_id=client.id, solde=Decimal('1000.00'))
            session.add(compte)
            session.commit()
    
            # We clear transactions for this user first to ensure count starts at 0
            session.query(Operation).filter_by(utilisateur_id=user.id, type_operation=TypeOperation.RETRAIT).delete()
            session.commit()

            # First two withdrawals should succeed
            ok1, _ = effectuer_operation(compte.id, Decimal('10'), TypeOperation.RETRAIT, user.id)
            ok2, _ = effectuer_operation(compte.id, Decimal('20'), TypeOperation.RETRAIT, user.id)
            assert ok1 is True
            assert ok2 is True
    
            # Third within the minute should be blocked by velocity
            ok3, msg = effectuer_operation(compte.id, Decimal('5'), TypeOperation.RETRAIT, user.id)
            assert ok3 is False
            assert "limite de fréquence" in msg or "Trop de retraits" in msg
        finally:
            session.close()
