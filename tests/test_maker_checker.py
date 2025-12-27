from src.db import obtenir_session
from src.models import Utilisateur, Compte, OperationEnAttente, StatutAttente, RoleUtilisateur
from src.checker import soumettre_approbation, executer_approbation
from decimal import Decimal

def test_maker_checker():
    session = obtenir_session()
    print("--- Test Maker-Checker ---")
    
    # 1. Rechercher un opérateur et un admin
    operateur = session.query(Utilisateur).filter_by(role=RoleUtilisateur.OPERATEUR).first()
    admin = session.query(Utilisateur).filter_by(role=RoleUtilisateur.ADMIN).first()
    compte = session.query(Compte).first()
    
    if not (operateur and admin and compte):
        print("Erreur : Données manquantes (besoin d'un opérateur, d'un admin et d'un compte).")
        session.close()
        return

    print(f"Opérateur : {operateur.nom_utilisateur}")
    print(f"Admin : {admin.nom_utilisateur}")
    print(f"Compte : {compte.numero_compte} (Solde : {compte.solde})")

    # Identifiants pour plus tard
    compte_id = compte.id
    operateur_id = operateur.id

    # 2. Maker : Soumettre une demande
    payload = {
        'compte_id': compte_id,
        'montant': '350.000',
        'description': 'Test Maker-Checker'
    }
    demande = soumettre_approbation(session, 'RETRAIT_EXCEPTIONNEL', payload, operateur_id)
    session.commit()
    demande_id = demande.id
    print(f"Demande créée ID : {demande_id}")

    # 3. Checker : Approuver la demande
    success, msg = executer_approbation(demande_id, admin.id)
    print(f"Résultat Approbation : {success} - {msg}")

    # 4. Vérifier l'impact (avec une nouvelle session)
    session_verify = obtenir_session()
    compte_verify = session_verify.query(Compte).get(compte_id)
    print(f"Nouveau solde : {compte_verify.solde}")

    # Check last operation recorded and ensure it's attributed to the maker (operateur)
    last_op = session_verify.query(Operation).filter_by(compte_id=compte_id).order_by(Operation.id.desc()).first()
    if last_op:
        print(f"Dernière opération: id={last_op.id}, utilisateur_id={last_op.utilisateur_id}, montant={last_op.montant}, valide_par_id={last_op.valide_par_id}")
        assert int(last_op.utilisateur_id) == int(operateur_id), "La dernière opération devrait être attribuée à l'opérateur (maker)."
        assert int(last_op.valide_par_id) == int(admin.id), "La dernière opération devrait enregistrer l'admin comme validateur (valide_par_id)."
    else:
        print("Aucune opération trouvée pour vérifier.")

    session_verify.close()
    
    # --- New test: self-approval should be refused and audited ---
    # Maker is the same as checker
    demande_self = soumettre_approbation(session, 'RETRAIT_EXCEPTIONNEL', payload, admin.id)
    session.commit()
    success2, msg2 = executer_approbation(demande_self.id, admin.id)
    print(f"Tentative auto-approbation : {success2} - {msg2}")
    assert success2 is False
    assert "Checker" in msg2 or "Checker'" in msg2 or "4 yeux" in msg2

    # Check audit log for ACCES_REFUSE
    import json
    from src.models import Journal
    session.expire_all()
    audit = session.query(Journal).filter_by(action='ACCES_REFUSE').order_by(Journal.id.desc()).first()
    assert audit is not None
    details = json.loads(audit.details) if audit.details else {}
    assert details.get('demande_id') == demande_self.id
    assert details.get('attempt') == 'self_approval'

    # cleanup the self-approval request
    d = session.query(OperationEnAttente).get(demande_self.id)
    if d:
        session.delete(d)
        session.commit()

    session.close()

if __name__ == "__main__":
    test_maker_checker()
