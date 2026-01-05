import os
import glob
import json
import vobject

class FileSystemStorage:
    def __init__(self, root_dir='data'):
        self.root_dir = root_dir
        if not os.path.exists(self.root_dir):
            os.makedirs(self.root_dir)
        self.shares_file = os.path.join(self.root_dir, 'shares.json')
        self._load_shares()
        self.verbose = os.environ.get('APP_VERBOSE', 'false').lower() == 'true'

    def _load_shares(self):
        if os.path.exists(self.shares_file):
            try:
                with open(self.shares_file, 'r') as f:
                    self.shares = json.load(f)
            except:
                self.shares = {}
        else:
            self.shares = {}

    def _save_shares(self):
        with open(self.shares_file, 'w') as f:
            json.dump(self.shares, f, indent=2)

    def _user_dir(self, username):
        return os.path.join(self.root_dir, username)

    def _resolve_calendar_path(self, username, calendar_name):
        """
        Resolves the actual filesystem path for a calendar.
        Handles both local calendars and shared calendars (e.g., 'alice-work').
        """
        # 1. Check for local calendar first
        local_path = os.path.join(self._user_dir(username), calendar_name)
        if os.path.exists(local_path):
            return local_path

        # 2. Check if it's a shared calendar (format: owner-calname)
        if '-' in calendar_name:
            # Try to split on the first hyphen to find potential owner
            parts = calendar_name.split('-', 1)
            owner = parts[0]
            original_cal_name = parts[1]
            
            # Verify if this share exists
            if self.is_shared_with(owner, original_cal_name, username):
                return os.path.join(self._user_dir(owner), original_cal_name)
        
        # Log failure
        if self.verbose: print(f"DEBUG: Could not resolve path for {username}/{calendar_name}. Checked {local_path}")
        return local_path

    def is_shared_with(self, owner, calendar_name, target_user):
        """Check if owner has shared calendar_name with target_user"""
        if owner not in self.shares:
            return False
        if calendar_name not in self.shares[owner]:
            return False
        return target_user in self.shares[owner][calendar_name]

    def share_calendar(self, owner, calendar_name, target_user):
        if owner not in self.shares:
            self.shares[owner] = {}
        if calendar_name not in self.shares[owner]:
            self.shares[owner][calendar_name] = []
        
        if target_user not in self.shares[owner][calendar_name]:
            self.shares[owner][calendar_name].append(target_user)
            self._save_shares()
            return True
        return False

    def unshare_calendar(self, owner, calendar_name, target_user):
        if owner in self.shares and calendar_name in self.shares[owner]:
            if target_user in self.shares[owner][calendar_name]:
                self.shares[owner][calendar_name].remove(target_user)
                self._save_shares()
                return True
        return False

    def get_shares(self, owner, calendar_name):
        return self.shares.get(owner, {}).get(calendar_name, [])

    def list_shared_with_user(self, username):
        """Returns list of {owner, calendar_name, local_name} shared with username"""
        shared = []
        for owner, calendars in self.shares.items():
            for cal_name, users in calendars.items():
                if username in users:
                    shared.append({
                        'owner': owner,
                        'calendar_name': cal_name,
                        'local_name': f"{owner}-{cal_name}"
                    })
        return shared

    def ensure_user(self, username):
        user_path = self._user_dir(username)
        if not os.path.exists(user_path):
            os.makedirs(user_path)
            # Create default calendar
            self.create_calendar(username, 'default')

    def create_calendar(self, username, calendar_name):
        cal_path = os.path.join(self._user_dir(username), calendar_name)
        if not os.path.exists(cal_path):
            os.makedirs(cal_path)
            return True
        return False
    
    def list_calendars(self, username):
        # Local calendars
        user_path = self._user_dir(username)
        calendars = []
        if os.path.exists(user_path):
             calendars = [d for d in os.listdir(user_path) if os.path.isdir(os.path.join(user_path, d))]
        
        # Add shared calendars
        shared = self.list_shared_with_user(username)
        for s in shared:
            calendars.append(s['local_name'])
            
        return calendars

    def get_calendar_events(self, username, calendar_name):
        cal_path = self._resolve_calendar_path(username, calendar_name)
        if not os.path.exists(cal_path):
            return []
        
        events = []
        for file_path in glob.glob(os.path.join(cal_path, '*.ics')):
            try:
                with open(file_path, 'r') as f:
                    events.append(f.read())
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
        return events

    def get_event(self, username, calendar_name, event_uid):
        # Sanitize filename to prevent traversal
        filename = f"{event_uid}.ics" 
        cal_path = self._resolve_calendar_path(username, calendar_name)
        path = os.path.join(cal_path, filename)
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read()
        return None

    def save_event(self, username, calendar_name, event_uid, ics_data):
        cal_path = self._resolve_calendar_path(username, calendar_name)
        if not os.path.exists(cal_path):
            if self.verbose: print(f"DEBUG: save_event failed. Calendar path does not exist: {cal_path}")
            return False
        
        filename = f"{event_uid}.ics"
        path = os.path.join(cal_path, filename)
        if self.verbose: print(f"DEBUG: Saving event to {path}")
        try:
            with open(path, 'w') as f:
                f.write(ics_data)
            return True
        except Exception as e:
            if self.verbose: print(f"DEBUG: Error writing file {path}: {e}")
            return False

    def delete_event(self, username, calendar_name, event_uid):
        cal_path = self._resolve_calendar_path(username, calendar_name)
        filename = f"{event_uid}.ics"
        path = os.path.join(cal_path, filename)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

storage = FileSystemStorage()