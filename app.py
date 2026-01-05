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
@auth_provider.requires_auth
def well_known_caldav():
    # Redirect to the user root which acts as principal
    username = auth_provider.get_username()
    return redirect(f'/{username}/', code=301)

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

@app.route('/api/calendars')
@auth_provider.requires_auth
def api_calendars():
    username = auth_provider.get_username()
    # Only return own calendars for sharing management
    user_path = storage._user_dir(username)
    calendars = []
    if os.path.exists(user_path):
         calendars = [d for d in os.listdir(user_path) if os.path.isdir(os.path.join(user_path, d))]
    
    result = []
    for cal in calendars:
        result.append({
            'name': cal,
            'shares': storage.get_shares(username, cal)
        })
    
    shared_with_me = storage.list_shared_with_user(username)
    
    return jsonify({
        'my_calendars': result,
        'shared_with_me': shared_with_me
    })

@app.route('/api/create_calendar', methods=['POST'])
@auth_provider.requires_auth
def api_create_calendar():
    data = request.json
    name = data.get('name')
    if not name:
         return jsonify({'error': 'Missing name'}), 400
    
    # Simple validation
    if not name.replace('-', '').replace('_', '').isalnum():
         return jsonify({'error': 'Invalid name. Use only letters, numbers, dashes and underscores.'}), 400

    username = auth_provider.get_username()
    if storage.create_calendar(username, name):
        return jsonify({'status': 'ok'})
    else:
        return jsonify({'error': 'Calendar already exists'}), 409

@app.route('/api/users/search')
@auth_provider.requires_auth
def api_search_users():
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    
    users = auth_provider.search_users(query)
    return jsonify(users)

@app.route('/api/calendars/<calendar_name>/events')
@auth_provider.requires_auth
def api_calendar_events(calendar_name):
    username = auth_provider.get_username()
    events_raw = storage.get_calendar_events(username, calendar_name)
    parsed_events = []
    
    for ics in events_raw:
        try:
            cal = vobject.readOne(ics)
            if hasattr(cal, 'vevent_list'):
                for event in cal.vevent_list:
                    # Helper to serialise dates
                    def serialise(dt):
                        if isinstance(dt, datetime.datetime):
                            return dt.isoformat()
                        if isinstance(dt, datetime.date):
                            return dt.isoformat()
                        return str(dt)

                    evt_data = {
                        'title': event.summary.value if hasattr(event, 'summary') else 'No Title',
                        'start': serialise(event.dtstart.value) if hasattr(event, 'dtstart') else None,
                    }
                    if hasattr(event, 'dtend'):
                        evt_data['end'] = serialise(event.dtend.value)
                    
                    if hasattr(event, 'description'):
                        evt_data['description'] = event.description.value

                    parsed_events.append(evt_data)
        except Exception as e:
            print(f"Error parsing event: {e}")
            pass
            
    return jsonify(parsed_events)

@app.route('/api/share', methods=['POST'])
@auth_provider.requires_auth
def api_share():
    data = request.json
    owner = auth_provider.get_username()
    calendar = data.get('calendar')
    target_user = data.get('target_user')
    
    if not calendar or not target_user:
        return jsonify({'error': 'Missing data'}), 400
        
    storage.share_calendar(owner, calendar, target_user)
    return jsonify({'status': 'ok'})

@app.route('/api/unshare', methods=['POST'])
@auth_provider.requires_auth
def api_unshare():
    data = request.json
    owner = auth_provider.get_username()
    calendar = data.get('calendar')
    target_user = data.get('target_user')
    
    if not calendar or not target_user:
        return jsonify({'error': 'Missing data'}), 400
        
    storage.unshare_calendar(owner, calendar, target_user)
    return jsonify({'status': 'ok'})

@app.route('/<username>/', defaults={'path': ''}, methods=['GET', 'PUT', 'DELETE', 'PROPFIND', 'REPORT', 'OPTIONS', 'PROPPATCH'])
@app.route('/<username>/<path:path>', methods=['GET', 'PUT', 'DELETE', 'PROPFIND', 'REPORT', 'OPTIONS', 'PROPPATCH'])
@auth_provider.requires_auth
def dav_route(username, path):
    # Security: Ensure user can only access their own calendar
    # We must allow the user to access their own calendar
    # AND allow other users to access shared calendars if we implement that logic here.
    # For now, simplistic check:
    current_user = auth_provider.get_username()
    
    if username != current_user:
        # Check if they are accessing a shared calendar?
        # TODO: Implement shared access check in routing or handler
        return Response("Forbidden", 403)

    # Ensure user storage exists
    storage.ensure_user(username)

    method = request.method
    full_path = f"{username}/{path}"
    
    # Debug logging
    verbose = os.environ.get('APP_VERBOSE', 'false').lower() == 'true'
    if verbose:
        print(f"[{method}] {full_path}")
        if method in ['PROPFIND', 'REPORT']:
            try:
                print(request.data.decode('utf-8'))
            except:
                print("<binary data>")

    if method == 'OPTIONS':
        resp = Response("", 200)
        resp.headers['Allow'] = 'OPTIONS, GET, HEAD, POST, PUT, DELETE, TRACE, COPY, MOVE, PROPFIND, PROPPATCH, LOCK, UNLOCK, REPORT, ACL'
        resp.headers['DAV'] = '1, 2, calendar-access'
        return resp

    if method == 'PROPFIND':
        depth = request.headers.get('Depth', '0')
        return handler.handle_propfind(username, full_path, depth)

    if method == 'PROPPATCH':
        # Dummy implementation to satisfy clients that try to set properties
        # Real implementation would update storage properties
        return handler.handle_proppatch(username, full_path, request.data)

    if method == 'REPORT':
        return handler.handle_report(username, full_path, request.data)

    if method == 'PUT':
        return handler.handle_put(username, full_path, request.get_data())

    if method == 'DELETE':
        return handler.handle_delete(username, full_path)

    if method == 'GET':
        # Simple file retrieval
        parts = full_path.strip('/').split('/')
        if len(parts) == 3:
            content = storage.get_event(username, parts[1], parts[2].replace('.ics', ''))
            if content:
                return Response(content, 200, mimetype='text/calendar; charset=utf-8')
        return Response("Not Found", 404)

    return Response("Method Not Allowed", 405)

# Catch-all for debugging unknown client requests
@app.route('/', defaults={'path': ''}, methods=['GET', 'PUT', 'DELETE', 'PROPFIND', 'REPORT', 'OPTIONS', 'PROPPATCH'])
@app.route('/<path:path>', methods=['GET', 'PUT', 'DELETE', 'PROPFIND', 'REPORT', 'OPTIONS', 'PROPPATCH'])
def catch_all(path):
    # This route is lower priority than the specific routes defined below?
    # Actually Flask routes are matched in order or specificity.
    # We should place this AT THE END or ensure specific routes are matched first.
    # However, since the dav_route handles /<username>/..., this might catch 
    # things like /.well-known/ or /principals/
    
    verbose = os.environ.get('APP_VERBOSE', 'false').lower() == 'true'
    if verbose:
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
