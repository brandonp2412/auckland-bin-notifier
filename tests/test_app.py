import datetime as dt

from auckland_bin_notifier import app


def test_default_target_is_tomorrow():
    today = dt.datetime.now(app.TIMEZONE).date()
    assert app.default_target_date() == today + dt.timedelta(days=1)


def test_tomorrow_messages_are_casual_and_use_collection_emojis():
    tomorrow = dt.datetime.now(app.TIMEZONE).date() + dt.timedelta(days=1)

    assert app.message_for({"rubbish", "recycling"}, tomorrow) == (
        "🗑️♻️ Heads up — rubbish + recycling tomorrow. Pop both bins out tonight!"
    )
    assert app.message_for({"rubbish"}, tomorrow) == (
        "🗑️ Heads up — rubbish tomorrow. Pop the bin out tonight!"
    )
    assert app.message_for({"recycling"}, tomorrow) == (
        "♻️ Heads up — recycling tomorrow. Pop the bin out tonight!"
    )


def test_e2e_message_is_clearly_marked():
    message = app.e2e_message_for(
        {"rubbish", "recycling"},
        dt.date(2030, 1, 2),
    )
    assert "E2E test" in message
    assert "rubbish + recycling" in message
    assert "state is unchanged" in message
