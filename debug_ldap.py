import os
from ldap3 import Server, Connection, ALL
from dotenv import load_dotenv

load_dotenv()

def debug_ldap():
    server_uri = os.environ.get('LDAP_SERVER')
    bind_dn = os.environ.get('LDAP_BIND_DN')
    bind_pass = os.environ.get('LDAP_BIND_PASSWORD')
    base_dn = os.environ.get('LDAP_BASE_DN')

    print(f"Connecting to: {server_uri}")
    print(f"Base DN: {base_dn}")
    print(f"Bind DN: {bind_dn}")

    try:
        server = Server(server_uri, get_info=ALL)
        conn = Connection(server, user=bind_dn, password=bind_pass, auto_bind=True)
        print("\n✅ Bind Successful!")
        
        print(f"\nSearching for ALL objects under {base_dn}...")
        # Search for everything with a 'cn' attribute
        # We only ask for 'cn' and 'uid' to be safe with Authentik
        conn.search(base_dn, '(objectClass=*)', attributes=['cn', 'uid', 'mail'])
        
        print(f"Found {len(conn.entries)} entries:\n")
        for entry in conn.entries:
            print(f"--- Entry ---")
            print(f"DN: {entry.entry_dn}")
            print(f"Attributes: {entry.entry_attributes_as_dict}")
            print("-------------")

    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    debug_ldap()
