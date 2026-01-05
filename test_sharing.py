
import unittest
import base64
from app import app
import shutil
import os
import xml.etree.ElementTree as ET
from app import storage

class SharingTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.app = app.test_client()
        
        # Setup users
        from auth import auth_provider
        self.original_users = auth_provider.users.copy()
        auth_provider.users['alice'] = 'password'
        auth_provider.users['bob'] = 'password'
        
        # Auth headers
        self.alice_auth = {
            'Authorization': 'Basic ' + base64.b64encode(b"alice:password").decode('utf-8')
        }
        self.bob_auth = {
            'Authorization': 'Basic ' + base64.b64encode(b"bob:password").decode('utf-8')
        }
        
        # Setup temporary storage
        self.original_storage_root = storage.root_dir
        self.test_data_dir = 'test_data_sharing'
        storage.root_dir = self.test_data_dir
        if not os.path.exists(self.test_data_dir):
            os.makedirs(self.test_data_dir)
            
        # Initialize storage
        storage._load_shares() # Reset shares
        storage.shares = {} 
        storage._save_shares()

    def tearDown(self):
        from auth import auth_provider
        auth_provider.users = self.original_users
        
        from app import storage
        storage.root_dir = self.original_storage_root
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_sharing_visibility(self):
        # 1. Alice creates 'work' calendar
        # In our simple server, ensuring the user folder exists is enough, 
        # and create_calendar is called on demand or explicitly.
        # Let's manually create it via storage for setup speed, or just assume it exists 
        # (the implementation currently creates default on ensure_user).
        # We want a SPECIFIC calendar 'work'.
        
        # Manually create for Alice
        storage.ensure_user('alice')
        storage.create_calendar('alice', 'work')
        
        # 2. Alice shares 'work' with 'bob'
        storage.share_calendar('alice', 'work', 'bob')
        
        # 3. Bob lists calendars (PROPFIND /bob/ depth 1)
        headers = self.bob_auth.copy()
        headers['Depth'] = '1'
        resp = self.app.open('/bob/', method='PROPFIND', headers=headers)
        
        print("\n--- Bob's PROPFIND Response ---")
        print(resp.data.decode('utf-8'))
        print("-------------------------------\n")
        
        self.assertEqual(resp.status_code, 207)
        
        # Parse XML to find if 'alice-work' is listed
        root = ET.fromstring(resp.data)
        namespaces = {
            'd': 'DAV:',
            'c': 'urn:ietf:params:xml:ns:caldav'
        }
        
        found_shared = False
        for response in root.findall('d:response', namespaces):
            href = response.find('d:href', namespaces).text
            if 'alice-work' in href:
                found_shared = True
                print(f"Found shared calendar at: {href}")
                
                # Check display name
                propstat = response.find('d:propstat', namespaces)
                prop = propstat.find('d:prop', namespaces)
                displayname = prop.find('d:displayname', namespaces).text
                print(f"Display Name: {displayname}")
                
                # Check CTag
                cs_ns = "http://calendarserver.org/ns/"
                getctag = prop.find(f"{{{cs_ns}}}getctag")
                if getctag is not None:
                     print(f"CTag found: {getctag.text}")
                else:
                     print("CTag NOT found")
                     self.fail("CTag missing for shared calendar")

        self.assertTrue(found_shared, "Shared calendar 'alice-work' not found in Bob's calendar list")

if __name__ == '__main__':
    unittest.main()
