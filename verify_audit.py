from src.audit_logger import verifier_integrite, log_action
from src.db import reinitialiser_base_donnees

# 1. Reset DB for a clean state
reinitialiser_base_donnees()

# 2. Generate some logs
log_action(1, "TEST_1", "Test Target", {"key": "val1"})
log_action(2, "TEST_2", "Test Target", {"key": "val2"})

# 3. Verify integrity
valide, erreurs = verifier_integrite()

if valide:
    print("SUCCESS: Audit integrity is valid!")
else:
    print("FAILURE: Audit integrity is compromised!")
    for err in erreurs:
        print(f" - {err}")
