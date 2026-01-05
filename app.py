import os
import vobject
import datetime
from flask import Flask, request, Response, redirect, render_template, jsonify
from auth import auth_provider
from storage import storage
from caldav_handler import CalDAVHandler
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
handler = CalDAVHandler(storage)

@app.route('/')
def index():
    return redirect('/ui/')

@app.route('/ui/')
@auth_provider.requires_auth
def dashboard():
    return render_template('dashboard.html', username=auth_provider.get_username())

@app.route('/logout')
def logout():
    # Simple way to logout of Basic Auth is to send a 401 
    # but without the auth_provider wrapper to avoid infinite loops
    return Response(
        'Logged out.', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

# --- Service Discovery & Principal Handling ---

@app.route('/.well-known/caldav', methods=['GET', 'PROPFIND'])
def well_known_caldav():
    # Redirect to the root, where we handle principal discovery
    return redirect('/', code=301)

@app.route('/', methods=['PROPFIND', 'OPTIONS'])
@auth_provider.requires_auth
def root_discovery():
    username = auth_provider.get_username()
    
    if request.method == 'OPTIONS':
        resp = Response("", 200)
        resp.headers['Allow'] = 'OPTIONS, PROPFIND'
        resp.headers['DAV'] = '1, 2, calendar-access'
        return resp

    # PROPFIND on root to discover current-user-principal
    # This tells the client "Hey, I am user 'frieder', my details are at /frieder/"
    return handler.handle_root_propfind(username)

@app.route('/principals/', methods=['PROPFIND'])
@auth_provider.requires_auth
def principals_stub():
    # Some clients try to guess /principals/
    # We redirect them to the user's root which acts as their principal
    username = auth_provider.get_username()
    return redirect(f'/{username}/', code=301)

# Catch-all for debugging unknown client requests
@app.route('/', defaults={'path': ''}, methods=['GET', 'PUT', 'DELETE', 'PROPFIND', 'REPORT', 'OPTIONS', 'PROPPATCH'])
@app.route('/<path:path>', methods=['GET', 'PUT', 'DELETE', 'PROPFIND', 'REPORT', 'OPTIONS', 'PROPPATCH'])
def catch_all(path):
    # This route is lower priority than the specific routes defined below?
    # Actually Flask routes are matched in order or specificity.
    # We should place this AT THE END or ensure specific routes are matched first.
    # However, since the dav_route handles /<username>/..., this might catch 
    # things like /.well-known/ or /principals/
    
    print(f"DEBUG: Unhandled request to /{path} method={request.method}")
    # Still try to be helpful for discovery
    if path.startswith('.well-known'):
         return redirect(f'/{auth_provider.get_username()}/')

    return Response("Not Found", 404)

if __name__ == '__main__':
    # When behind a reverse proxy like Traefik, SSL is usually handled there.
    # We check if certs exist, otherwise run plain HTTP.
    ssl_context = None
    if os.path.exists('cert.pem') and os.path.exists('key.pem'):
        ssl_context = ('cert.pem', 'key.pem')
        print("Starting with SSL context")
    
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False, ssl_context=ssl_context)
