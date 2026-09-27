from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from urllib.parse import urljoin

import recurring_ical_events
from bs4 import BeautifulSoup
from curl_cffi import requests
from icalendar import Calendar

COUNCIL_DETAIL_URL = (
    "https://www.aucklandcouncil.govt.nz/en/rubbish-recycling/"
    "rubbish-recycling-collections/rubbish-recycling-collection-days/{property_id}.html"
)
MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}
ICON_TYPES = {"rubbish": "rubbish", "recycle": "recycling"}
RUBBISH_WORDS = ("rubbish", "garbage", "refuse", "general waste", "landfill")
RECYCLING_WORDS = ("recycling", "recycle", "recyclables")


class SourceError(RuntimeError):
    pass


def _session() -> requests.Session:
    # Auckland Council currently rejects ordinary HTTP/TLS clients with HTTP 406.
    return requests.Session(impersonate="chrome")


def fetch_bytes(url: str, timeout: int = 30) -> bytes:
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://") :]
    response = _session().get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


def fetch_text(url: str, timeout: int = 30) -> str:
    return fetch_bytes(url, timeout=timeout).decode("utf-8", errors="replace")


def classify_summary(summary: str) -> set[str]:
    text = re.sub(r"\s+", " ", summary.casefold()).strip()
    kinds: set[str] = set()
    if any(word in text for word in RUBBISH_WORDS):
        kinds.add("rubbish")
    if any(word in text for word in RECYCLING_WORDS):
        kinds.add("recycling")
    return kinds


def parse_ics_for_date(payload: bytes, target: dt.date) -> set[str]:
    try:
        calendar = Calendar.from_ical(payload)
    except Exception as exc:
        raise SourceError(f"invalid iCalendar payload: {exc}") from exc

    kinds: set[str] = set()
    try:
        events = recurring_ical_events.of(calendar).at(target)
    except Exception as exc:
        raise SourceError(f"could not expand iCalendar events: {exc}") from exc

    for event in events:
        summary = str(event.get("SUMMARY", ""))
        kinds.update(classify_summary(summary))
    return kinds


def discover_ics_url(html: str, page_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(href=True):
        href = str(tag.get("href", "")).strip()
        low = href.casefold()
        if low.startswith("webcal://") or ".ics" in low:
            return urljoin(page_url, href)
    return None


def _date_from_text(value: str, today: dt.date) -> dt.date | None:
    match = re.search(r"([A-Za-z]+),?\s+(\d{1,2})\s+([A-Za-z]+)", value)
    if not match:
        return None
    month = MONTHS.get(match.group(3))
    if not month:
        return None
    candidate = dt.date(today.year, month, int(match.group(2)))
    if candidate < today - dt.timedelta(days=90):
        candidate = candidate.replace(year=today.year + 1)
    return candidate


def parse_council_html_for_date(html: str, target: dt.date) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", class_="acpl-schedule-card")
    household = None
    for card in cards:
        title = card.find("h4", class_="card-title")
        if title and "household collection" in title.get_text(" ", strip=True).casefold():
            household = card
            break
    if household is None:
        raise SourceError("Auckland Council page did not contain a household collection card")

    kinds: set[str] = set()
    for paragraph in household.find_all("p", class_="mb-0 lead"):
        icon = paragraph.find("i", class_=lambda value: value and "acpl-icon" in value)
        if icon is None:
            continue
        kind = next(
            (ICON_TYPES[name] for name in (icon.get("class") or []) if name in ICON_TYPES),
            None,
        )
        if kind is None:
            continue
        bold = paragraph.find("b")
        if bold is None:
            continue
        collection_date = _date_from_text(bold.get_text(" ", strip=True), target)
        if collection_date == target:
            kinds.add(kind)
    return kinds


def collection_types_from_ics_url(
    ics_url: str,
    target: dt.date,
    cache_path: Path | None = None,
) -> set[str]:
    try:
        payload = fetch_bytes(ics_url)
        if b"BEGIN:VCALENDAR" not in payload.upper():
            raise SourceError("download did not look like an iCalendar file")
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(payload)
    except Exception as exc:
        if cache_path is None or not cache_path.exists():
            raise SourceError(f"could not download calendar: {exc}") from exc
        age = dt.datetime.now().timestamp() - cache_path.stat().st_mtime
        if age > 48 * 60 * 60:
            raise SourceError(f"calendar download failed and cache is older than 48 hours: {exc}") from exc
        payload = cache_path.read_bytes()
    return parse_ics_for_date(payload, target)


def collection_types_from_property(
    property_id: str,
    target: dt.date,
    cache_path: Path | None = None,
) -> set[str]:
    if not re.fullmatch(r"\d{11}", property_id):
        raise SourceError("Auckland Council property ID must be an 11-digit number")
    page_url = COUNCIL_DETAIL_URL.format(property_id=property_id)
    try:
        html = fetch_text(page_url)
    except Exception as exc:
        raise SourceError(f"could not fetch Auckland Council collection page: {exc}") from exc

    ics_url = discover_ics_url(html, page_url)
    if ics_url:
        return collection_types_from_ics_url(ics_url, target, cache_path)

    return parse_council_html_for_date(html, target)
