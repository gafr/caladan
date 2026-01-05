import vobject
import os
from flask import request, Response
from xml.etree.ElementTree import Element, SubElement, tostring, fromstring, QName
import datetime
from storage import storage

# XML Namespaces
NS_DAV = "DAV:"
NS_CAL = "urn:ietf:params:xml:ns:caldav"
NS_CS = "http://calendarserver.org/ns/"

def register_namespaces():
    try:
        from xml.etree import ElementTree
        ElementTree.register_namespace('D', NS_DAV)
        ElementTree.register_namespace('C', NS_CAL)
        ElementTree.register_namespace('CS', NS_CS)
    except:
        pass

register_namespaces()

class CalDAVHandler:
    def __init__(self, storage):
        self.storage = storage
        self.verbose = os.environ.get('APP_VERBOSE', 'false').lower() == 'true'

    def _create_multistatus_response(self, responses):
        root = Element(f'{{{NS_DAV}}}multistatus')
        for href, status, props in responses:
            resp = SubElement(root, f'{{{NS_DAV}}}response')
            SubElement(resp, f'{{{NS_DAV}}}href').text = href
            
            propstat = SubElement(resp, f'{{{NS_DAV}}}propstat')
            SubElement(propstat, f'{{{NS_DAV}}}status').text = status
            
            if props:
                prop_el = SubElement(propstat, f'{{{NS_DAV}}}prop')
                for p_name, p_val in props.items():
                    # Handle namespace prefix manually if needed or simple tag construction
                    # This is a simplified property writer
                    if isinstance(p_val, Element):
                        prop_el.append(p_val)
                    else:
                        # Assume simple text or tuple (namespace, tagname)
                        if isinstance(p_name, tuple):
                            ns, tag = p_name
                            el = SubElement(prop_el, f'{{{ns}}}{tag}')
                            if p_val: el.text = str(p_val)
                        else:
                            # Default to DAV:
                            el = SubElement(prop_el, f'{{{NS_DAV}}}{p_name}')
                            if p_val: el.text = str(p_val)

        return tostring(root, encoding='utf-8', xml_declaration=True)

    def handle_root_propfind(self, username):
        """
        Handles PROPFIND on the server root to discover current-user-principal.
        """
        # We need to construct a response that points to the user's principal URL.
        # In our simple server, /{username}/ acts as the principal URL.
        
        def make_href_prop(ns, name, value):
            el = Element(f'{{{ns}}}{name}')
            h = SubElement(el, f'{{{NS_DAV}}}href')
            h.text = value
            return el

        props = {
            (NS_DAV, 'resourcetype'): self._make_resourcetype(collection=True),
            (NS_DAV, 'current-user-principal'): make_href_prop(NS_DAV, 'current-user-principal', f"/{username}/"),
            # Some clients also look for this directly on root
            (NS_CAL, 'calendar-home-set'): make_href_prop(NS_CAL, 'calendar-home-set', f"/{username}/"),
        }
        
        responses = [('/', 'HTTP/1.1 200 OK', props)]
        return Response(self._create_multistatus_response(responses), 207, mimetype='application/xml; charset=utf-8')

    def handle_propfind(self, username, path, depth='0'):
        # Simplified PROPFIND handler
        # path is like /username/calendar_name/ or /username/
        
        parts = path.strip('/').split('/')
        # parts: [username], [username, cal_name], [username, cal_name, resource]
        
        responses = []
        
        base_url = f"/{path.strip('/')}"
        
        if len(parts) == 1 and parts[0] == username:
            # User root - List calendars
            # Self
            
            # Construct href for self. Important for principal discovery.
            # We treat /username/ as the principal URL AND the calendar home set for simplicity.
            
            def make_href_prop(ns, name, value):
                el = Element(f'{{{ns}}}{name}')
                h = SubElement(el, f'{{{NS_DAV}}}href')
                h.text = value
                return el

            props = {
                (NS_DAV, 'resourcetype'): self._make_resourcetype(collection=True, principal=True),
                (NS_DAV, 'displayname'): username,
                (NS_DAV, 'current-user-principal'): make_href_prop(NS_DAV, 'current-user-principal', f"/{username}/"),
                (NS_CAL, 'calendar-home-set'): make_href_prop(NS_CAL, 'calendar-home-set', f"/{username}/"),
            }
            responses.append((base_url + '/', 'HTTP/1.1 200 OK', props))
            
            if depth == '1':
                # Children (Calendars)
                calendars = self.storage.list_calendars(username)
                for cal in calendars:
                    c_props = {
                        (NS_DAV, 'resourcetype'): self._make_resourcetype(collection=True, calendar=True),
                        (NS_DAV, 'displayname'): cal,
                        (NS_CAL, 'supported-calendar-component-set'): self._make_comp_set(['VEVENT']),
                        (NS_CS, 'getctag'): self.storage.get_calendar_ctag(username, cal)
                    }
                    responses.append((f"{base_url}/{cal}/", 'HTTP/1.1 200 OK', c_props))

        elif len(parts) == 2:
            # Calendar root
            cal_name = parts[1]
            props = {
                (NS_DAV, 'resourcetype'): self._make_resourcetype(collection=True, calendar=True),
                (NS_DAV, 'displayname'): cal_name,
                (NS_CAL, 'supported-calendar-component-set'): self._make_comp_set(['VEVENT']),
                # CTag is important for clients to know if sync is needed
                (NS_CS, 'getctag'): self.storage.get_calendar_ctag(username, cal_name) 
            }
            responses.append((base_url + '/', 'HTTP/1.1 200 OK', props))

            if depth == '1':
                # List events
                # Getting all events might be heavy, but for filesystem proto it's fine
                # Real server would only return etags/names usually unless propfind asked for content
                # For minimal proto, let's list ics files
                # Note: We can't easily get etags without stat-ing files.
                pass 
                # Implementation Detail: Clients usually use REPORT for querying events or PROPFIND with specific props
                # We will support listing resources if they exist
                
                # Check storage for raw files
                # This part requires storage to list file names
                cal_dir = self.storage._resolve_calendar_path(username, cal_name)
                import os, glob
                if os.path.exists(cal_dir):
                     for fpath in glob.glob(os.path.join(cal_dir, '*.ics')):
                        fname = os.path.basename(fpath)
                        f_props = {
                            (NS_DAV, 'resourcetype'): self._make_resourcetype(collection=False),
                            (NS_DAV, 'getcontenttype'): 'text/calendar; charset=utf-8',
                            (NS_DAV, 'getetag'): f'"{os.path.getmtime(fpath)}"',
                        }
                        responses.append((f"{base_url}/{fname}", 'HTTP/1.1 200 OK', f_props))

        elif len(parts) == 3:
             # Specific Resource
             # Return properties for the file
             cal_name = parts[1]
             resource = parts[2]
             
             # Check if exists
             content = self.storage.get_event(username, cal_name, resource.replace('.ics', ''))
             if content:
                 f_props = {
                    (NS_DAV, 'resourcetype'): self._make_resourcetype(collection=False),
                    (NS_DAV, 'getcontenttype'): 'text/calendar; charset=utf-8',
                    # ETag should be robust
                    (NS_DAV, 'getetag'): '"12345"', 
                 }
                 responses.append((base_url, 'HTTP/1.1 200 OK', f_props))
             else:
                 return Response("Not Found", 404)

        return Response(self._create_multistatus_response(responses), 207, mimetype='application/xml; charset=utf-8')

    def _make_resourcetype(self, collection=False, calendar=False, principal=False):
        rt = Element(f'{{{NS_DAV}}}resourcetype')
        if collection:
            SubElement(rt, f'{{{NS_DAV}}}collection')
        if calendar:
            SubElement(rt, f'{{{NS_CAL}}}calendar')
        if principal:
            SubElement(rt, f'{{{NS_DAV}}}principal')
        return rt
    
    def _make_comp_set(self, comps):
        sccs = Element(f'{{{NS_CAL}}}supported-calendar-component-set')
        for c in comps:
            comp = SubElement(sccs, f'{{{NS_CAL}}}comp')
            comp.set('name', c)
        return sccs

    def handle_proppatch(self, username, path, data):
        # We do not support property updates in this simple file-based storage.
        # Returning 403 is a valid response when the server refuses to modify properties.
        return Response("Forbidden", 403)

    def handle_report(self, username, path, data):
        # Simplified REPORT handler
        # Mostly handles calendar-query for time-range
        # For this prototype, we'll return ALL events in the calendar
        # A real server must filter by time-range
        
        parts = path.strip('/').split('/')
        if len(parts) < 2:
            return Response("Bad Request", 400)
            
        cal_name = parts[1]
        
        # Parse XML to see what they want (calendar-query vs calendar-multiget)
        # Assuming calendar-query for now which asks for events
        
        events = self.storage.get_calendar_events(username, cal_name)
        
        responses = []
        base_url = f"/{path.strip('/')}"
        
        # We need to map events back to filenames or UIDs?
        # Storage.get_calendar_events currently returns content strings.
        # We should probably change storage to return (filename, content)
        
        # Let's fix storage usage locally here
        cal_dir = self.storage._resolve_calendar_path(username, cal_name)
        import os, glob
        if os.path.exists(cal_dir):
            for fpath in glob.glob(os.path.join(cal_dir, '*.ics')):
                fname = os.path.basename(fpath)
                with open(fpath, 'r') as f:
                    content = f.read()
                
                # ETag
                etag = f'"{os.path.getmtime(fpath)}"'
                
                props = {
                    (NS_DAV, 'getetag'): etag,
                    (NS_DAV, 'getcontenttype'): 'text/calendar; charset=utf-8'
                }
                
                # If the report asked for calendar-data, we include it.
                # Usually it does. We'll cheat and always include it for this proto.
                # Constructing the calendar-data element
                cdata = Element(f'{{{NS_CAL}}}calendar-data')
                cdata.text = content
                props[(NS_CAL, 'calendar-data')] = cdata
                
                responses.append((f"{base_url}/{fname}", 'HTTP/1.1 200 OK', props))
                
        return Response(self._create_multistatus_response(responses), 207, mimetype='application/xml; charset=utf-8')

    def handle_put(self, username, path, data):
        if self.verbose: print(f"DEBUG: PUT request for {path}")
        parts = path.strip('/').split('/')
        if len(parts) != 3:
             if self.verbose: print("DEBUG: Invalid path structure")
             return Response("Forbidden", 403)
        
        cal_name = parts[1]
        resource = parts[2]
        uid = resource.replace('.ics', '')
        
        # Validation: Is it valid ics?
        try:
            if isinstance(data, bytes):
                data_str = data.decode('utf-8')
            else:
                data_str = data
            
            if self.verbose: print(f"DEBUG: Received {len(data_str)} bytes of data")
            
            v = vobject.readOne(data_str)
            if v.name != 'VCALENDAR':
                if self.verbose: print("DEBUG: Content is not VCALENDAR")
                raise ValueError("Not a VCALENDAR")
        except Exception as e:
            if self.verbose: print(f"DEBUG: VObject parsing error: {e}")
            return Response(f"Invalid Calendar Data: {e}", 400)
        
        if self.storage.save_event(username, cal_name, uid, data_str):
            if self.verbose: print(f"DEBUG: Event saved successfully for {username}/{cal_name}/{uid}")
            # Return ETag
            resp = Response("", 201)
            resp.headers['ETag'] = '"' + str(datetime.datetime.now().timestamp()) + '"'
            return resp
        else:
            if self.verbose: print(f"DEBUG: Failed to save event (storage returned False)")
            return Response("Internal Server Error", 500)

    def handle_delete(self, username, path):
        parts = path.strip('/').split('/')
        if len(parts) != 3:
             return Response("Forbidden", 403)

        cal_name = parts[1]
        resource = parts[2]
        uid = resource.replace('.ics', '')
        
        if self.storage.delete_event(username, cal_name, uid):
            return Response("", 204)
        return Response("Not Found", 404)

