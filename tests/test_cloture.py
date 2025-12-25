from src.audit_logger import log_action, cloturer_journee, verifier_clotures
from src.db import reinitialiser_base_donnees, obtenir_session
from src.models import Journal
from datetime import datetime, timedelta, date as py_date

# 1. Reset
reinitialiser_base_donnees()

# 2. Add logs for YESTERDAY
yesterday = py_date.today() - timedelta(days=1)
session = obtenir_session()

# Manual log creation to force yesterday's date
log1 = Journal(
    horodatage=datetime.combine(yesterday, datetime.min.time()) + timedelta(hours=10),
    utilisateur_id=1,
    action="TEST_HIER_1",
    hash_precedent="GENESIS_HASH", # Simple start for test
    hash_actuel="dummy_hash_1",
    signature_hmac="dummy_sig_1"
)
session.add(log1)
session.commit()

# Proper log via log_action (will use today's date usually, but we need yesterday's for the test)
# Since log_action uses datetime.utcnow(), we'll patch it or just create logs normally and then update their date for testing.
log2 = Journal(
    horodatage=datetime.combine(yesterday, datetime.min.time()) + timedelta(hours=14),
    utilisateur_id=1,
    action="TEST_HIER_2",
    cible="TEST_HIER_2",
    hash_precedent="dummy_hash_1",
    hash_actuel="8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918", # Real-looking hash
    signature_hmac="real_looking_hmac"
)
session.add(log2)
session.commit()
session.close()

print(f"--- Testing Closure for {yesterday} ---")

# 3. Trigger Closure
succes, message = cloturer_journee(yesterday)
print(f"Result: {succes} - {message}")

# 4. Verify
valide, erreurs = verifier_clotures()
if valide:
    print("SUCCESS: Daily closure is cryptographically valid!")
else:
    print("FAILURE: Daily closure verification failed!")
    for err in erreurs:
        print(f" - {err}")
