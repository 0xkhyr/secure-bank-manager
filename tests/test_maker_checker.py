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

    # --- New test: self-reject should be refused and audited ---
    demande_reject = soumettre_approbation(session, 'RETRAIT_EXCEPTIONNEL', payload, operateur_id)
    session.commit()
    success_rej, msg_rej = rejeter_approbation(demande_reject.id, operateur_id)
    print(f"Tentative auto-rejet : {success_rej} - {msg_rej}")
    assert success_rej is False
    session.expire_all()
    audit_rej = session.query(Journal).filter_by(action='ACCES_REFUSE').order_by(Journal.id.desc()).first()
    assert audit_rej is not None
    details_rej = json.loads(audit_rej.details) if audit_rej.details else {}
    assert details_rej.get('demande_id') == demande_reject.id
    assert details_rej.get('attempt') == 'self_reject'

    # cleanup
    d2 = session.query(OperationEnAttente).get(demande_reject.id)
    if d2:
        session.delete(d2)
        session.commit()

    # --- New test: maker can withdraw their own request ---
    demande_withdraw = soumettre_approbation(session, 'RETRAIT_EXCEPTIONNEL', payload, operateur_id)
    session.commit()
    success_w, msg_w = retirer_approbation(demande_withdraw.id, operateur_id, 'Annulation volontaire', 'test comment')
    print(f"Retrait par maker : {success_w} - {msg_w}")
    assert success_w is True
    session.expire_all()
    d3 = session.query(OperationEnAttente).get(demande_withdraw.id)
    assert d3.statut == StatutAttente.CANCELLED

    # Check audit log for withdrawal
    audit_w = session.query(Journal).filter_by(action='SOUMISSION_RETRACTION').order_by(Journal.id.desc()).first()
    assert audit_w is not None
    details_w = json.loads(audit_w.details) if audit_w.details else {}
    assert details_w.get('demande_id') == demande_withdraw.id
    assert details_w.get('raison') == 'Annulation volontaire'
    assert details_w.get('commentaire') == 'test comment'

    # Unauthorized withdraw by someone else should be refused
    demande_unauth = soumettre_approbation(session, 'RETRAIT_EXCEPTIONNEL', payload, operateur_id)
    session.commit()
    success_unauth, msg_unauth = retirer_approbation(demande_unauth.id, admin.id)
    print(f"Tentative retrait non autorisée : {success_unauth} - {msg_unauth}")
    assert success_unauth is False
    session.expire_all()
    audit_una = session.query(Journal).filter_by(action='ACCES_REFUSE').order_by(Journal.id.desc()).first()
    assert audit_una is not None
    details_una = json.loads(audit_una.details) if audit_una.details else {}
    assert details_una.get('attempt') == 'unauthorized_withdraw'

    # cleanup
    d4 = session.query(OperationEnAttente).get(demande_unauth.id)
    if d4:
        session.delete(d4)
        session.commit()

    session.close()

if __name__ == "__main__":
    test_maker_checker()
