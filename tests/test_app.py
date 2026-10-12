import datetime as dt

from auckland_bin_notifier import app


def test_default_target_is_tomorrow():
    today = dt.datetime.now(app.TIMEZONE).date()
    assert app.default_target_date() == today + dt.timedelta(days=1)


def test_morning_catchup_targets_today(monkeypatch):
    monkeypatch.setenv("AUCKLAND_BIN_CHECK_TODAY", "1")
    assert app.default_target_date() == dt.datetime.now(app.TIMEZONE).date()


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


def test_e2e_sends_only_to_distinct_test_room(monkeypatch):
    monkeypatch.setenv("MATRIX_E2E_TEST_ROOM_ID", "!test:matrix.example.org")
    monkeypatch.setenv("MATRIX_ROOM_ID", "!production:matrix.example.org")
    monkeypatch.setattr(app, "_fetch_with_retries", lambda _date: {"rubbish"})
    calls = []
    monkeypatch.setattr(
        app, "_send_with_retries",
        lambda message, *, room_id: calls.append((message, room_id)),
    )
    app.run_e2e(dt.date(2030, 1, 2))
    assert len(calls) == 1
    assert "E2E test" in calls[0][0]
    assert calls[0][1] == "!test:matrix.example.org"


def test_e2e_refuses_production_or_missing_room(monkeypatch):
    import pytest

    monkeypatch.setenv("MATRIX_ROOM_ID", "!production:matrix.example.org")
    monkeypatch.setattr(app, "_fetch_with_retries", lambda _date: {"rubbish"})
    monkeypatch.setattr(
        app, "_send_with_retries",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("A send was attempted")),
    )
    monkeypatch.delenv("MATRIX_E2E_TEST_ROOM_ID", raising=False)
    with pytest.raises(app.matrix.MatrixError, match="must be configured"):
        app.run_e2e(dt.date(2030, 1, 2))
    monkeypatch.setenv("MATRIX_E2E_TEST_ROOM_ID", "!production:matrix.example.org")
    with pytest.raises(app.matrix.MatrixError, match="must differ"):
        app.run_e2e(dt.date(2030, 1, 2))
