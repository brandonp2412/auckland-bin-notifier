import datetime as dt

from auckland_bin_notifier import app


def test_default_target_is_tomorrow():
    today = dt.datetime.now(app.TIMEZONE).date()
    assert app.default_target_date() == today + dt.timedelta(days=1)


def test_message_for_tomorrow_mentions_tomorrow_and_tonight():
    tomorrow = dt.datetime.now(app.TIMEZONE).date() + dt.timedelta(days=1)
    message = app.message_for({"rubbish", "recycling"}, tomorrow)
    assert "due tomorrow" in message
    assert "rubbish and recycling" in message
    assert "tonight" in message


def test_e2e_message_is_clearly_marked():
    message = app.e2e_message_for(
        {"rubbish", "recycling"},
        dt.date(2030, 1, 2),
    )
    assert "E2E test" in message
    assert "rubbish + recycling" in message
    assert "state is unchanged" in message
