import functools
import os
from flask import request, Response, current_app

try:
    from ldap3 import Server, Connection, ALL
    LDAP_AVAILABLE = True
except ImportError:
    LDAP_AVAILABLE = False

class AuthProvider:
    def __init__(self):
        # Configuration for default user
        self.enable_default_user = os.environ.get('ENABLE_DEFAULT_USER', 'true').lower() == 'true'
        self.default_username = os.environ.get('DEFAULT_USER', 'user')
        self.default_password = os.environ.get('DEFAULT_PASSWORD', 'password')
        
        self.users = {}
        if self.enable_default_user:
            self.users[self.default_username] = self.default_password

    def _check_ldap(self, username, password):
        verbose = os.environ.get('LDAP_VERBOSE', 'false').lower() == 'true'
        
        if not LDAP_AVAILABLE:
            if verbose: print("LDAP DEBUG: ldap3 library not available")
            return False
            
        ldap_server = os.environ.get('LDAP_SERVER')
        if not ldap_server:
            if verbose: print("LDAP DEBUG: LDAP_SERVER not set")
            return False

        base_dn = os.environ.get('LDAP_BASE_DN', 'dc=ldap,dc=goauthentik,dc=io')
        bind_dn = os.environ.get('LDAP_BIND_DN')
        bind_pass = os.environ.get('LDAP_BIND_PASSWORD')
        user_filter = os.environ.get('LDAP_USER_FILTER', '(uid={0})')

        if verbose:
            print(f"LDAP DEBUG: Connecting to {ldap_server}")
            print(f"LDAP DEBUG: Bind DN: {bind_dn}")
            print(f"LDAP DEBUG: Base DN: {base_dn}")

        try:
            # 1. Connect and Bind (Service Account or Anonymous)
            server = Server(ldap_server, get_info=ALL)
            conn = Connection(server, user=bind_dn, password=bind_pass, auto_bind=True)
            if verbose: print("LDAP DEBUG: Service bind successful")
            
            # 2. Search for the user
            search_filter = user_filter.format(username)
            if verbose: print(f"LDAP DEBUG: Searching with filter {search_filter}")
            
            conn.search(base_dn, search_filter, attributes=['dn'])
            
            if not conn.entries:
                if verbose: print(f"LDAP DEBUG: User {username} not found")
                return False
            
            user_dn = conn.entries[0].entry_dn
            if verbose: print(f"LDAP DEBUG: Found user DN: {user_dn}")
            
            # 3. Verify password by rebinding
            user_conn = Connection(server, user=user_dn, password=password)
            if user_conn.bind():
                if verbose: print(f"LDAP DEBUG: User {username} authenticated successfully")
                return True
            else:
                if verbose: print(f"LDAP DEBUG: Password verification failed for {username}")
                return False
                
        except Exception as e:
            print(f"LDAP Error: {e}")
            return False

    def check_auth(self, username, password):
        """This function is called to check if a username /
        password combination is valid."""
        
        # 1. Try LDAP if configured
        if os.environ.get('LDAP_SERVER'):
            if self._check_ldap(username, password):
                return True

        # 2. Fallback to local test users
        return username in self.users and self.users[username] == password

    def authenticate(self):
        """Sends a 401 response that enables basic auth"""
        return Response(
            'Could not verify your access level for that URL.\n'
            'You have to login with proper credentials', 401,
            {'WWW-Authenticate': 'Basic realm="Login Required"'})

    def get_username(self):
        """Returns the username from Authentik header or Basic Auth."""
        if 'X-authentik-username' in request.headers:
            return request.headers['X-authentik-username']
        if request.authorization:
            return request.authorization.username
        return None

    def requires_auth(self, f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            username = self.get_username()
            if not username:
                return self.authenticate()

            # If not using Authentik header, verify Basic Auth password
            if 'X-authentik-username' not in request.headers:
                auth = request.authorization
                if not auth or not self.check_auth(auth.username, auth.password):
                    return self.authenticate()
            
            return f(*args, **kwargs)
        return decorated

# Singleton instance
auth_provider = AuthProvider()

