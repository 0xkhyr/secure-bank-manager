from src.app import inject_policies
from src.policy import set_policy, invalidate_cache


def test_injects_keys_and_respects_overrides():
    # Override some policies and ensure the context processor reflects them
    set_policy('maker_checker.seuil_montant', 7777, type_='int', comment='test')
    set_policy('velocity.actif', 'true', type_='bool', comment='test')
    set_policy('velocity.retrait.max_par_minute', 9, type_='int', comment='test')
    set_policy('mfa.roles_obligatoires', ["admin", "operateur"], type_='json', comment='test')
    invalidate_cache()

    ctx = inject_policies()
    assert ctx.get('MAKER_CHECKER_THRESHOLD') == 7777
    assert ctx.get('VELOCITY_ACTIVE') is True
    assert ctx.get('VELOCITY_RETRAIT_MAX_PER_MIN') == 9
    assert isinstance(ctx.get('MFA_ROLES'), (list, tuple))
    assert 'admin' in ctx.get('MFA_ROLES')


def test_defaults_present_when_missing():
    # Ensure defaults exist (no exception thrown) and have reasonable types
    invalidate_cache()
    ctx = inject_policies()
    assert isinstance(ctx.get('RETRAIT_LIMIT'), int)
    assert isinstance(ctx.get('SESSION_TIMEOUT'), int)
    assert isinstance(ctx.get('POLICY_CACHE_TTL'), int)
    assert isinstance(ctx.get('MAINTENANCE_MODE'), bool)
