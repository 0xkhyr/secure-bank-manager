import pytest
import werkzeug.exceptions

from src.policy import set_policy, invalidate_cache
from src.policy_helpers import get_policy_int, get_policy_bool, require_policy_max, enforce_withdrawal_limit


def test_get_policy_conversions():
    # store using explicit types to match validation rules
    set_policy('test.int', 42, type_='int')
    invalidate_cache()
    assert get_policy_int('test.int', default=0) == 42

    set_policy('test.bool.true', 'true', type_='bool')
    invalidate_cache()
    assert get_policy_bool('test.bool.true', default=False) is True

    set_policy('test.bool.false', 'false', type_='bool')
    invalidate_cache()
    assert get_policy_bool('test.bool.false', default=True) is False


def test_decorator_blocks_over_limit():
    set_policy('retrait.limite_journaliere', 100, type_='int', comment='test')
    invalidate_cache()

    @require_policy_max('retrait.limite_journaliere', lambda amount: amount)
    def do_withdraw(amount):
        return "ok"

    with pytest.raises(werkzeug.exceptions.HTTPException) as excinfo:
        do_withdraw(200)
    assert excinfo.value.code == 403

    assert do_withdraw(50) == "ok"


def test_enforce_withdrawal_limit():
    set_policy('retrait.limite_journaliere', 123, type_='int', comment='test')
    invalidate_cache()
    assert enforce_withdrawal_limit('100') is True
    assert enforce_withdrawal_limit('200') is False
