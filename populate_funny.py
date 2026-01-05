import os
import vobject
import datetime
import uuid

def create_event(summary, dtstart, description="", location=""):
    cal = vobject.iCalendar()
    cal.add('vevent')
    
    # Generate a unique UID
    uid = str(uuid.uuid4())
    cal.vevent.add('uid').value = uid
    
    # Set dates
    # Assuming all-day events for simplicity, or specific times
    if isinstance(dtstart, datetime.date) and not isinstance(dtstart, datetime.datetime):
        cal.vevent.add('dtstart').value = dtstart
        # DTEND is non-inclusive for all-day events, usually next day
        cal.vevent.add('dtend').value = dtstart + datetime.timedelta(days=1)
        cal.vevent.dtstart.value_param = 'DATE'
        cal.vevent.dtend.value_param = 'DATE'
    else:
        cal.vevent.add('dtstart').value = dtstart
        cal.vevent.add('dtend').value = dtstart + datetime.timedelta(hours=1)
    
    cal.vevent.add('summary').value = summary
    if description:
        cal.vevent.add('description').value = description
    if location:
        cal.vevent.add('location').value = location
        
    # Use naive UTC time for dtstamp to avoid vobject TZID issues
    cal.vevent.add('dtstamp').value = datetime.datetime.utcnow()
    
    return uid, cal.serialize()

def main():
    username = "user"
    cal_name = "funny_dates"
    base_dir = "data"
    
    target_dir = os.path.join(base_dir, username, cal_name)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        print(f"Created calendar directory: {target_dir}")

    # List of funny/interesting events
    # Using current year or next occurrences relative to now (2026)
    year = 2026
    
    events = [
        {
            "summary": "International Talk Like a Pirate Day",
            "date": datetime.date(year, 9, 19),
            "desc": "Arrr, matey! Shiver me timbers!",
            "loc": "The Seven Seas"
        },
        {
            "summary": "May the 4th Be With You",
            "date": datetime.date(year, 5, 4),
            "desc": "Star Wars Day. Watch the trilogy.",
            "loc": "A Galaxy Far, Far Away"
        },
        {
            "summary": "Pi Day",
            "date": datetime.date(year, 3, 14),
            "desc": "Eat some pie at 1:59 PM.",
            "loc": "Math Class"
        },
        {
            "summary": "Towel Day",
            "date": datetime.date(year, 5, 25),
            "desc": "Don't Panic! Honor Douglas Adams.",
            "loc": "The Universe"
        },
        {
            "summary": "World UFO Day",
            "date": datetime.date(year, 7, 2),
            "desc": "Keep watching the skies.",
            "loc": "Roswell, NM"
        },
        {
            "summary": "Ninja Day",
            "date": datetime.date(year, 12, 5),
            "desc": "You won't even see this event coming.",
            "loc": "Hidden"
        },
        {
            "summary": "Rubber Duckie's Birthday",
            "date": datetime.date(year, 1, 13),
            "desc": "Sesame Street legend.",
            "loc": "Bathtub"
        },
        {
            "summary": "Zombie Awareness Month",
            "date": datetime.date(year, 5, 1),
            "desc": "Prepare your survival kit.",
            "loc": "Safe House"
        }
    ]

    for ev in events:
        uid, content = create_event(ev["summary"], ev["date"], ev["desc"], ev["loc"])
        filename = f"{uid}.ics"
        filepath = os.path.join(target_dir, filename)
        with open(filepath, "w") as f:
            f.write(content)
        print(f"Created event: {ev['summary']}")

    print("\nFunny dates populated! You can now sync.")

if __name__ == "__main__":
    main()
