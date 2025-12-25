from src.db import obtenir_session
from src.models import Client, Compte, StatutClient, StatutCompte, gen_numero_compte
from decimal import Decimal

def seed_test_data():
    session = obtenir_session()
    
    # Check if client exists
    client = session.query(Client).filter_by(cin="00000000").first()
    if not client:
        client = Client(
            nom="TEST",
            prenom="User",
            cin="00000000",
            telephone="00000000",
            statut=StatutClient.ACTIF
        )
        session.add(client)
        session.flush()
        print("Client créé.")
    
    # Check if account exists
    compte = session.query(Compte).filter_by(client_id=client.id).first()
    if not compte:
        compte = Compte(
            numero_compte=gen_numero_compte(),
            client_id=client.id,
            solde=Decimal("1000.000"),
            statut=StatutCompte.ACTIF
        )
        session.add(compte)
        print(f"Compte créé : {compte.numero_compte}")
    
    session.commit()
    session.close()

if __name__ == "__main__":
    seed_test_data()
