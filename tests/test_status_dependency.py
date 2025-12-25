import unittest
from decimal import Decimal
from flask import url_for
from src.db import obtenir_session, reinitialiser_base_donnees
from src.models import Client, Compte, StatutClient, StatutCompte, Utilisateur
from src.app import app

class TestAccountClientStatusDependency(unittest.TestCase):
    def setUp(self):
        reinitialiser_base_donnees()
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1 

    def create_inactive_client(self):
        session = obtenir_session()
        client = Client(
            nom="Block", prenom="Test", cin="88887777", 
            telephone="22334455", email="block@test.com",
            statut=StatutClient.INACTIF
        )
        session.add(client)
        session.commit()
        client_id = client.id
        session.close()
        return client_id

    def test_01_blocked_create_account(self):
        client_id = self.create_inactive_client()
        response = self.client.post(f'/accounts/nouveau/{client_id}', data={
            'montant_initial': '100.000'
        }, follow_redirects=True)
        self.assertIn('Action impossible : le client est inactif', response.get_data(as_text=True))

    def test_02_blocked_depot(self):
        client_id = self.create_inactive_client()
        session = obtenir_session()
        compte = Compte(
            numero_compte="DEP-TEST-001", client_id=client_id,
            solde=Decimal('500.000'), statut=StatutCompte.ACTIF
        )
        session.add(compte)
        session.commit()
        compte_id = compte.id
        session.close()

        response = self.client.post(f'/operations/depot/{compte_id}', data={
            'montant': '50.000', 'description': 'Test'
        }, follow_redirects=True)
        self.assertIn('Opération impossible : le titulaire est inactif', response.get_data(as_text=True))

    def test_03_blocked_retrait(self):
        client_id = self.create_inactive_client()
        session = obtenir_session()
        compte = Compte(
            numero_compte="RET-TEST-001", client_id=client_id,
            solde=Decimal('500.000'), statut=StatutCompte.ACTIF
        )
        session.add(compte)
        session.commit()
        compte_id = compte.id
        session.close()

        response = self.client.post(f'/operations/retrait/{compte_id}', data={
            'montant': '50.000', 'description': 'Test'
        }, follow_redirects=True)
        self.assertIn('Opération impossible : le titulaire est inactif', response.get_data(as_text=True))

    def test_04_blocked_reopen(self):
        client_id = self.create_inactive_client()
        session = obtenir_session()
        compte = Compte(
            numero_compte="REO-TEST-001", client_id=client_id,
            solde=Decimal('500.000'), statut=StatutCompte.FERME
        )
        session.add(compte)
        session.commit()
        compte_id = compte.id
        session.close()

        response = self.client.post(f'/accounts/{compte_id}/reopen', data={
            'raison': 'Test'
        }, follow_redirects=True)
        self.assertIn('Action impossible : le titulaire du compte est inactif', response.get_data(as_text=True))

if __name__ == '__main__':
    unittest.main()
