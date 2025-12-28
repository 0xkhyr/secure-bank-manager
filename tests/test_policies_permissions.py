import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import app
from src.db import obtenir_session
from src.models import Utilisateur, RoleUtilisateur
import src.auth as auth_mod

class TestPoliciesPermissions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        session = obtenir_session()
        # Ensure an ADMIN user exists
        admin = session.query(Utilisateur).filter_by(nom_utilisateur='perm_admin').first()
        if not admin:
            admin = Utilisateur(nom_utilisateur='perm_admin', mot_de_passe_hash='x', role=RoleUtilisateur.ADMIN)
            session.add(admin)
            session.commit()
        session.close()

    def setUp(self):
        self.client = app.test_client()
        session = obtenir_session()
        admin = session.query(Utilisateur).filter_by(nom_utilisateur='perm_admin').first()
        self.admin_id = admin.id
        session.close()

    def test_admin_without_permission_cannot_view_policies(self):
        # Ensure ADMIN does not have the policies.view permission for this assertion
        orig = auth_mod.PERMISSION_MAP.get(RoleUtilisateur.ADMIN.name, set()).copy()
        if 'policies.view' in auth_mod.PERMISSION_MAP.get(RoleUtilisateur.ADMIN.name, set()):
            auth_mod.PERMISSION_MAP[RoleUtilisateur.ADMIN.name].discard('policies.view')
        try:
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.admin_id

            resp = self.client.get('/admin/policies/', follow_redirects=False)
            # Should be redirected away (permission_required redirects to home)
            self.assertEqual(resp.status_code, 302)
        finally:
            auth_mod.PERMISSION_MAP[RoleUtilisateur.ADMIN.name] = orig

    def test_grant_view_permission_allows_access(self):
        # Give ADMIN the policies.view permission temporarily
        orig = auth_mod.PERMISSION_MAP.get(RoleUtilisateur.ADMIN.name, set()).copy()
        auth_mod.PERMISSION_MAP[RoleUtilisateur.ADMIN.name].add('policies.view')
        try:
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.admin_id
            resp = self.client.get('/admin/policies/')
            self.assertEqual(resp.status_code, 200)
        finally:
            auth_mod.PERMISSION_MAP[RoleUtilisateur.ADMIN.name] = orig

    def test_edit_requires_edit_permission(self):
        # Create a dummy policy to edit
        session = obtenir_session()
        from src.models import Politique
        p = session.query(Politique).filter_by(cle='perm.test.edit').first()
        if not p:
            p = Politique(cle='perm.test.edit', valeur='1', type='int', active=True)
            session.add(p)
            session.commit()
        pid = p.id
        session.close()

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id

        # Without edit permission, POST should redirect to index (no change)
        resp = self.client.post(f'/admin/policies/{p.cle}', data={'value': '2', 'type': 'int'}, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)

        # Grant edit and retry
        orig = auth_mod.PERMISSION_MAP.get(RoleUtilisateur.ADMIN.name, set()).copy()
        auth_mod.PERMISSION_MAP[RoleUtilisateur.ADMIN.name].add('policies.edit')
        try:
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.admin_id
            resp2 = self.client.post(f'/admin/policies/{p.cle}', data={'value': '2', 'type': 'int'}, follow_redirects=True)
            self.assertEqual(resp2.status_code, 200)
        finally:
            auth_mod.PERMISSION_MAP[RoleUtilisateur.ADMIN.name] = orig

if __name__ == '__main__':
    unittest.main()
