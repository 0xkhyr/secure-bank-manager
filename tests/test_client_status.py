import unittest
import sys
import os
from passlib.hash import bcrypt

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import app
from src.db import obtenir_session, reinitialiser_base_donnees
from src.models import Utilisateur, RoleUtilisateur, Client, Compte, StatutClient, StatutCompte, Journal
from src.config import Config

class TestClientStatus(unittest.TestCase):
    """Tests pour la gestion du statut des clients."""
    
    @classmethod
    def setUpClass(cls):
        """Configuration initiale."""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        
        # S'assurer qu'un admin existe
        session = obtenir_session()
        admin = session.query(Utilisateur).filter_by(nom_utilisateur='admin_test').first()
        if not admin:
            admin = Utilisateur(
                nom_utilisateur='admin_test',
                mot_de_passe_hash=bcrypt.hash('admin123'),
                role=RoleUtilisateur.ADMIN
            )
            session.add(admin)
            session.commit()
        session.close()

    def setUp(self):
        """Avant chaque test."""
        self.client = app.test_client()
        # Connexion
        self.client.post('/auth/login', data={
            'username': 'admin_test',
            'password': 'admin123'
        })

    def test_client_deactivation_workflow(self):
        """Teste le cycle de vie du statut d'un client."""
        session = obtenir_session()
        
        # 1. Créer un client
        test_client = Client(
            nom='Status',
            prenom='Test',
            cin='STS001',
            telephone='12345678',
            statut=StatutClient.ACTIF
        )
        session.add(test_client)
        session.commit()
        client_id = test_client.id
        
        # 2. Vérifier statut initial
        self.assertEqual(test_client.statut, StatutClient.ACTIF)
        
        # 3. Tentative de désactivation (sans compte) -> Succès
        response = self.client.post(f'/clients/{client_id}/desactiver', data={
            'statut': 'inactif',
            'raison': 'Test de désactivation'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        # Recharger le client
        session.expire_all()
        test_client = session.query(Client).get(client_id)
        self.assertEqual(test_client.statut, StatutClient.INACTIF)
        
        # 4. Vérifier l'audit log
        # Note: Journal is already imported at the top of the file
        audit = session.query(Journal).filter_by(action='DESACTIVATION_CLIENT', cible=f"Client {client_id}").first()
        self.assertIsNotNone(audit)
        
        # 5. Réactivation
        response = self.client.post(f'/clients/{client_id}/reactiver', data={
            'raison': 'Reprise de la relation client'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        session.expire_all()
        test_client = session.query(Client).get(client_id)
        self.assertEqual(test_client.statut, StatutClient.ACTIF)

        # Vérifier l'audit de réactivation
        audit_react = session.query(Journal).filter_by(action='REACTIVATION_CLIENT', cible=f"Client {client_id}").first()
        self.assertIsNotNone(audit_react)
        self.assertIn('Reprise de la relation client', audit_react.details)

        # 6. Test blocage si compte ouvert
        compte = Compte(
            numero_compte='TEST001',
            client_id=client_id,
            solde=500.0,
            statut=StatutCompte.ACTIF
        )
        session.add(compte)
        session.commit()
        
        response = self.client.post(f'/clients/{client_id}/desactiver', data={
            'statut': 'inactif'
        }, follow_redirects=True)
        
        # Devrait échouer car compte actif
        if b'poss\xc3\xa8de encore 1 comptes actifs' not in response.data:
            print(f"DEBUG: Response data for failed block: {response.data.decode('utf-8')}")
        self.assertIn(b'poss\xc3\xa8de encore 1 comptes actifs', response.data)
        
        session.expire_all()
        test_client = session.query(Client).get(client_id)
        self.assertEqual(test_client.statut, StatutClient.ACTIF)
        
        # 7. Fermer le compte et ressayer
        session.expire_all()
        compte = session.query(Compte).filter_by(numero_compte='TEST001').first()
        compte.statut = StatutCompte.FERME
        session.commit()
        
        # Verify it's committed in a fresh session
        session.close()
        session = obtenir_session()
        
        response = self.client.post(f'/clients/{client_id}/desactiver', data={
            'statut': 'archive'
        }, follow_redirects=True)
        
        # Reload and check
        session.expire_all()
        test_client = session.query(Client).get(client_id)
        self.assertEqual(test_client.statut, StatutClient.ARCHIVE)

        # Nettoyage
        test_client = session.query(Client).get(client_id)
        if test_client:
            session.delete(test_client)
            session.commit()
        session.close()

if __name__ == '__main__':
    unittest.main()
