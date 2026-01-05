
import caldav
from datetime import datetime
import uuid

# Configuration
CALDAV_URL = "https://127.0.0.1:5001/.well-known/caldav"
USERNAME = "user"
PASSWORD = "password"

def run_client_test():
    print(f"Connecting to {CALDAV_URL} as {USERNAME}...")
    
    try:
        # 1. Connect and Discovery
        # This tests the .well-known redirect and PROPFIND handling
        client = caldav.DAVClient(
            url=CALDAV_URL,
            username=USERNAME,
            password=PASSWORD,
            ssl_verify_cert=False
        )
        
        principal = client.principal()
        print(f"✓ Principal discovered: {principal.url}")
        
        calendars = principal.calendars()
        if not calendars:
            print("✗ No calendars found!")
            return
            
        print(f"✓ Found {len(calendars)} calendar(s)")
        calendar = calendars[0]
        print(f"  - Using calendar: {calendar.name} ({calendar.url})")

        # 2. Create Event
        # This tests PUT handling
        summary = f"Test Event {uuid.uuid4().hex[:8]}"
        start = datetime(2026, 1, 4, 15, 0, 0)
        end = datetime(2026, 1, 4, 16, 0, 0)
        
        print(f"Creating event: '{summary}'...")
        event = calendar.save_event(
            dtstart=start,
            dtend=end,
            summary=summary
        )
        print(f"✓ Event created. URL: {event.url}")

        # 3. Read Event (verify persistence)
        # This tests GET/PROPFIND logic for resources
        print("Refetching event...")
        event.load()
        print(f"✓ Event loaded. Summary: {event.instance.vevent.summary.value}")
        
        if event.instance.vevent.summary.value != summary:
            print(f"✗ Summary mismatch! Expected '{summary}'")
            return

        # 4. Search/Report (Optional)
        # This tests REPORT
        print("Searching for events in time range...")
        results = calendar.date_search(
            start=datetime(2026, 1, 4, 0, 0, 0),
            end=datetime(2026, 1, 5, 0, 0, 0)
        )
        found = any(e.instance.vevent.summary.value == summary for e in results)
        if found:
            print("✓ Event found via date search (REPORT)")
        else:
            print("✗ Event NOT found via date search")

        # 5. Cleanup
        print("Deleting event...")
        event.delete()
        print("✓ Event deleted")

    except Exception as e:
        print(f"✗ Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_client_test()
