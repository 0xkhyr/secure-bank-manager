import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import app
from src.db import obtenir_session
from src.models import Utilisateur, RoleUtilisateur, OperationEnAttente, StatutAttente
from src.auth import login_required


class TestCheckerUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        session = obtenir_session()
        # ensure an admin and operator exist
        admin = session.query(Utilisateur).filter_by(nom_utilisateur='ui_admin').first()
        if not admin:
            admin = Utilisateur(nom_utilisateur='ui_admin', mot_de_passe_hash='x', role=RoleUtilisateur.ADMIN)
            session.add(admin)
            session.commit()
        op = session.query(Utilisateur).filter_by(nom_utilisateur='ui_op').first()
        if not op:
            op = Utilisateur(nom_utilisateur='ui_op', mot_de_passe_hash='x', role=RoleUtilisateur.OPERATEUR)
            session.add(op)
            session.commit()
        session.close()

    def setUp(self):
        self.client = app.test_client()
        # login as admin (bypass actual auth for tests)
        with self.client.session_transaction() as sess:
            # simple session mimic: store user id and role
            session = obtenir_session()
            admin = session.query(Utilisateur).filter_by(nom_utilisateur='ui_admin').first()
            sess['user_id'] = admin.id
            session.close()

    def test_withdraw_button_and_filter(self):
        session = obtenir_session()
        admin = session.query(Utilisateur).filter_by(nom_utilisateur='ui_admin').first()
        op = session.query(Utilisateur).filter_by(nom_utilisateur='ui_op').first()

        # create two demandes
        d1 = OperationEnAttente(type_operation='RETRAIT_EXCEPTIONNEL', payload={'foo': 'bar'}, cree_par_id=admin.id, statut=StatutAttente.PENDING)
        d2 = OperationEnAttente(type_operation='RETRAIT_EXCEPTIONNEL', payload={'foo': 'baz'}, cree_par_id=op.id, statut=StatutAttente.PENDING)
        session.add_all([d1, d2])
        session.commit()

        resp = self.client.get('/approbations')
        html = resp.data.decode('utf-8')

        # admin should see a Retirer button for their own demande
        self.assertIn('Retirer', html)
        # and should see Approuver/Rejeter for other's demandes
        self.assertIn('Approuver', html)
        self.assertIn('Rejeter', html)

        # server-side filter should show the "Voir toutes" link when ?filter=mine
        resp2 = self.client.get('/approbations?filter=mine')
        html2 = resp2.data.decode('utf-8')
        self.assertIn('Voir toutes', html2)

        # cleanup
        session.delete(d1)
        session.delete(d2)
        session.commit()
        session.close()


if __name__ == '__main__':
    unittest.main()
