
import unittest
import base64
from app import app
import shutil
import os

class FixVerificationTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.app = app.test_client()
        self.username = 'user'
        self.password = 'password'
        self.auth_headers = {
            'Authorization': 'Basic ' + base64.b64encode(f"{self.username}:{self.password}".encode('utf-8')).decode('utf-8')
        }
        # Setup temporary storage for tests
        from app import storage
        self.original_storage_root = storage.root_dir
        self.test_data_dir = 'test_data_fixes'
        storage.root_dir = self.test_data_dir
        if not os.path.exists(self.test_data_dir):
            os.makedirs(self.test_data_dir)

    def tearDown(self):
         # Restore storage and clean up
        from app import storage
        storage.root_dir = self.original_storage_root
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_well_known_redirect_propfind(self):
        """Verify .well-known/caldav handles PROPFIND and redirects correctly."""
        # Unauthenticated -> 401
        resp = self.app.open('/.well-known/caldav', method='PROPFIND')
        self.assertEqual(resp.status_code, 401)

        # Authenticated -> 301 to /user/
        resp = self.app.open('/.well-known/caldav', method='PROPFIND', headers=self.auth_headers)
        self.assertEqual(resp.status_code, 301)
        self.assertIn(f'/{self.username}/', resp.headers['Location'])

    def test_principals_redirect_propfind(self):
        """Verify /principals/ handles PROPFIND and redirects correctly."""
        # Unauthenticated -> 401
        resp = self.app.open('/principals/', method='PROPFIND')
        self.assertEqual(resp.status_code, 401)

        # Authenticated -> 301 to /user/
        resp = self.app.open('/principals/', method='PROPFIND', headers=self.auth_headers)
        self.assertEqual(resp.status_code, 301)
        self.assertIn(f'/{self.username}/', resp.headers['Location'])

    def test_proppatch_forbidden(self):
        """Verify PROPPATCH returns 403 Forbidden instead of 405 Method Not Allowed."""
        resp = self.app.open(f'/{self.username}/', method='PROPPATCH', headers=self.auth_headers)
        self.assertEqual(resp.status_code, 403)

    def test_security_isolation(self):
        """Verify users cannot access other users' calendars."""
        other_user_headers = {
            'Authorization': 'Basic ' + base64.b64encode(b"other:password").decode('utf-8')
        }
        # We need to temporarily add 'other' to the auth provider's user list for this test to pass auth check
        from auth import auth_provider
        original_users = auth_provider.users.copy()
        auth_provider.users['other'] = 'password'
        
        try:
            # 'other' tries to access 'user' -> 403
            resp = self.app.open(f'/{self.username}/', method='PROPFIND', headers=other_user_headers)
            self.assertEqual(resp.status_code, 403)
        finally:
            auth_provider.users = original_users

if __name__ == '__main__':
    unittest.main()
