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
    
    session.close()

if __name__ == "__main__":
    test_maker_checker()
