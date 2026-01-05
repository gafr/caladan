import unittest
import os
import shutil
import base64
from app import app
from storage import FileSystemStorage

class CalDAVTestCase(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        self.client = app.test_client()
        
        # Use a temporary directory for storage
        self.test_data_dir = 'test_data'
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)
        
        # Inject test storage into the app's handler
        # We need to access the handler instance. 
        # Since app.py creates 'handler' globally, we can import it, 
        # but 'from app import handler' would work.
        # However, to be safe, let's just patch the storage used by the global handler.
        from app import handler, storage
        self.original_storage_root = storage.root_dir
        storage.root_dir = self.test_data_dir
        if not os.path.exists(self.test_data_dir):
            os.makedirs(self.test_data_dir)
            
        self.username = 'user'
        self.password = 'password'
        self.auth_header = {
            'Authorization': 'Basic ' + base64.b64encode(f"{self.username}:{self.password}".encode('utf-8')).decode('utf-8')
        }

    def tearDown(self):
        # Clean up
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)
        
        # Restore original storage path (though process ends anyway)
        from app import storage
        storage.root_dir = self.original_storage_root

    def test_auth_required(self):
        response = self.client.get(f'/{self.username}/')
        self.assertEqual(response.status_code, 401)

    def test_auth_success(self):
        response = self.client.get(f'/{self.username}/', headers=self.auth_header)
        # Assuming GET on root returns 404 in our logic (it does, listing is PROPFIND)
        # But wait, our code:
        # if method == 'GET':
        #   parts = ... if len(parts) == 3: ... else 404
        # So GET /user/ -> 404 is "correct" for authenticated user who requests a non-resource
        self.assertNotEqual(response.status_code, 401)
        self.assertEqual(response.status_code, 404) 

    def test_propfind_user_root(self):
        # Test discovery
        response = self.client.open(f'/{self.username}/', method='PROPFIND', headers=self.auth_header)
        self.assertEqual(response.status_code, 207)
        data = response.data.decode('utf-8')
        self.assertIn('<D:multistatus', data)
        self.assertIn('<D:displayname>user</D:displayname>', data)
        
        # Check for iOS specific discovery properties
        self.assertIn('current-user-principal', data)
        self.assertIn('calendar-home-set', data)

    def test_propfind_calendar_discovery(self):
        # Ensure 'default' calendar is auto-created
        # Trigger creation by hitting the route once
        self.client.open(f'/{self.username}/', method='PROPFIND', headers=self.auth_header)
        
        # Now PROPFIND with Depth: 1 to see children
        headers = self.auth_header.copy()
        headers['Depth'] = '1'
        response = self.client.open(f'/{self.username}/', method='PROPFIND', headers=headers)
        
        self.assertEqual(response.status_code, 207)
        data = response.data.decode('utf-8')
        
        # Should find 'default' calendar
        self.assertIn('/user/default/', data)
        self.assertIn('<C:calendar />', data)

    def test_crud_event(self):
        # 1. Create (PUT)
        uid = 'test-uid-123'
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//CalDean//Test//EN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:20230101T120000Z
DTSTART:20230101T120000Z
DTEND:20230101T130000Z
SUMMARY:Unit Test Event
END:VEVENT
END:VCALENDAR"""
        
        response = self.client.put(f'/{self.username}/default/{uid}.ics', 
                                   data=ics_content, 
                                   headers=self.auth_header)
        self.assertEqual(response.status_code, 201)
        self.assertIn('ETag', response.headers)

        # 2. Read (GET)
        response = self.client.get(f'/{self.username}/default/{uid}.ics', headers=self.auth_header)
        self.assertEqual(response.status_code, 200)
        self.assertIn('SUMMARY:Unit Test Event', response.data.decode('utf-8'))

        # 3. Delete (DELETE)
        response = self.client.delete(f'/{self.username}/default/{uid}.ics', headers=self.auth_header)
        self.assertEqual(response.status_code, 204)

        # 4. Verify Delete
        response = self.client.get(f'/{self.username}/default/{uid}.ics', headers=self.auth_header)
        self.assertEqual(response.status_code, 404)

    def test_well_known_redirect(self):
        response = self.client.get('/.well-known/caldav', headers=self.auth_header)
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response.location.endswith('/user/'))

    def test_principals_probe(self):
        # iOS checks this
        response = self.client.get('/principals/users/user', headers=self.auth_header)
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response.location.endswith('/user/'))

if __name__ == '__main__':
    unittest.main()
