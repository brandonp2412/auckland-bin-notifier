# Auckland Bin Notifier

A small open-source service that checks Auckland Council household collection data and sends a Matrix reminder the evening before rubbish or recycling is due.

It is unofficial and is not affiliated with or endorsed by Auckland Council.

## Features

- Checks the next day's rubbish and recycling schedule.
- Sends one Matrix reminder at 7:00 PM Pacific/Auckland.
- Supports direct iCalendar/webcal feeds, including recurring events.
- Supports Auckland Council property-specific collection pages.
- Prefers an official ICS link if one is exposed by the property page.
- Falls back to the live household collection cards when no calendar link is available.
- Handles the Council site's browser-like TLS requirements with curl-cffi.
- Deduplicates real reminders by date and collection type.
- Includes a live --e2e-test mode that does not consume the real reminder.
- Ignores food-scraps collections by design.

## Requirements

- Python 3.11+
- Linux with systemd for the included timer/service
- A Matrix account with permission to post to the target room
- Either an Auckland Council property ID or an iCalendar URL

## Install

Install uv, then clone the repository and create an isolated runtime environment:

    curl -LsSf https://astral.sh/uv/install.sh | sh
    uv venv ~/.local/share/auckland-bin-notifier/venv
    uv pip install --python ~/.local/share/auckland-bin-notifier/venv/bin/python /path/to/auckland-bin-notifier
    mkdir -p ~/.local/bin
    ln -sf ~/.local/share/auckland-bin-notifier/venv/bin/auckland-bin-notifier ~/.local/bin/auckland-bin-notifier

For development:

    uv venv .venv
    uv pip install --python .venv/bin/python -e '.[test]'
    .venv/bin/pytest -q

## Configure the collection source

Create the private configuration directory:

    mkdir -p ~/.config/auckland-bin-notifier
    cp config.env.example ~/.config/auckland-bin-notifier/config.env
    chmod 600 ~/.config/auckland-bin-notifier/config.env

Set either AUCKLAND_BIN_PROPERTY_ID or AUCKLAND_BIN_ICS_URL.

The property ID is the 11-digit identifier in the URL of the property-specific Auckland Council collection page after you search for your address on the Council website.

For local development, a .env file in the current working directory is also supported and is gitignored.

## Configure Matrix

Copy the Matrix example:

    cp matrix.env.example ~/.config/auckland-bin-notifier/matrix.env
    chmod 600 ~/.config/auckland-bin-notifier/matrix.env

Set MATRIX_ROOM_ID plus one Matrix transport:

- Direct Client API: set MATRIX_HOMESERVER and MATRIX_ACCESS_TOKEN. This is appropriate for unencrypted rooms.
- Existing Matrix MCP: install with the matrix-mcp optional extra and set MATRIX_MCP_URL to its Streamable HTTP endpoint. The notifier calls the MCP send_message tool, so encrypted rooms are sent through the MCP's logged-in Matrix client and encryption store.

Never commit an access token.

## Test

Check the configured live source without sending a message:

    auckland-bin-notifier --dry-run

Run the full live source -> parser -> Matrix path without changing reminder state:

    auckland-bin-notifier --e2e-test

A successful E2E message is clearly marked as a test and will not prevent the scheduled reminder from being sent later.

You can also check a specific date:

    auckland-bin-notifier --date 2026-09-29 --dry-run

## systemd

Install the user units:

    mkdir -p ~/.config/systemd/user
    cp systemd/auckland-bin-notifier.service ~/.config/systemd/user/
    cp systemd/auckland-bin-notifier.timer ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable --now auckland-bin-notifier.timer

The timer runs at 7:00 PM in Pacific/Auckland and checks the following day's collection. It is persistent across reboots.

Inspect it with:

    systemctl --user status auckland-bin-notifier.timer
    systemctl --user list-timers auckland-bin-notifier.timer
    journalctl --user -u auckland-bin-notifier.service

## Data-source behavior

The notifier can consume a direct iCalendar feed. When using an Auckland Council property ID, it fetches the public property-specific collection page. If that page exposes an ICS/webcal link, the calendar is used; otherwise the live household collection cards are parsed.

The Auckland Council website is an external dependency and its HTML/API behavior may change. Parser failures are surfaced as errors instead of silently reporting an empty schedule.

## Privacy

Personal addresses, property IDs, Matrix room IDs, homeserver credentials, and access tokens belong only in local configuration. The supplied examples contain placeholders, and the repository ignores common local configuration/secrets files.

## License

MIT. See LICENSE.
