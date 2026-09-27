import datetime as dt

from auckland_bin_notifier.sources import (
    classify_summary,
    discover_ics_url,
    parse_council_html_for_date,
    parse_ics_for_date,
)


def test_classify_combined_summary():
    assert classify_summary("Rubbish & Recycling Collection") == {"rubbish", "recycling"}


def test_ics_events_on_same_day():
    payload = b"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:rubbish-1
DTSTART;VALUE=DATE:20260928
SUMMARY:Rubbish
END:VEVENT
BEGIN:VEVENT
UID:recycling-1
DTSTART;VALUE=DATE:20260928
SUMMARY:Recycling
END:VEVENT
END:VCALENDAR
"""
    assert parse_ics_for_date(payload, dt.date(2026, 9, 28)) == {"rubbish", "recycling"}
    assert parse_ics_for_date(payload, dt.date(2026, 9, 29)) == set()


def test_ics_recurring_event():
    payload = b"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:recycling-weekly
DTSTART;VALUE=DATE:20260914
RRULE:FREQ=WEEKLY;COUNT=4
SUMMARY:Recycling
END:VEVENT
END:VCALENDAR
"""
    assert parse_ics_for_date(payload, dt.date(2026, 9, 28)) == {"recycling"}


def test_discover_ics_url():
    html = '<a href="/calendar/bin-days.ics?x=1">Add to calendar</a>'
    assert discover_ics_url(html, "https://example.test/page") == "https://example.test/calendar/bin-days.ics?x=1"


def test_parse_council_household_card():
    html = """
    <div class="acpl-schedule-card">
      <h4 class="card-title">Household collection</h4>
      <p class="mb-0 lead"><i class="acpl-icon rubbish"></i><b>Monday, 28 September</b></p>
      <p class="mb-0 lead"><i class="acpl-icon recycle"></i><b>Monday, 28 September</b></p>
      <p class="mb-0 lead"><i class="acpl-icon food-waste"></i><b>Monday, 28 September</b></p>
    </div>
    """
    assert parse_council_html_for_date(html, dt.date(2026, 9, 28)) == {"rubbish", "recycling"}
