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


def test_run_retries_transient_matrix_failure(monkeypatch, tmp_path):
    target = dt.date(2030, 1, 2)
    attempts = 0

    monkeypatch.setattr(app, "_fetch_with_retries", lambda _target: {"rubbish"})
    monkeypatch.setattr(app, "state_path", lambda: tmp_path / "state.json")
    monkeypatch.setattr(app.time, "sleep", lambda _seconds: None)

    def send_message(_message):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise app.matrix.MatrixError("temporary network failure")

    monkeypatch.setattr(app.matrix, "send_message", send_message)

    message = app.run(target)

    assert attempts == 2
    assert message == app.message_for({"rubbish"}, target)
