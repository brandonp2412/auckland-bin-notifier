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


def test_run_sends_only_once_on_matrix_failure(monkeypatch, tmp_path):
    target = dt.date(2030, 1, 2)
    attempts = 0

    monkeypatch.setattr(app, "_fetch_with_retries", lambda _target: {"rubbish"})
    monkeypatch.setattr(app, "state_path", lambda: tmp_path / "state.json")

    def send_message(_message):
        nonlocal attempts
        attempts += 1
        raise app.matrix.MatrixError("temporary network failure")

    monkeypatch.setattr(app.matrix, "send_message", send_message)

    import pytest

    with pytest.raises(app.matrix.MatrixError, match="temporary network failure"):
        app.run(target)
    assert attempts == 1
    assert not (tmp_path / "state.json").exists()


def test_e2e_sends_only_to_distinct_test_room(monkeypatch):
    monkeypatch.setenv("MATRIX_E2E_TEST_ROOM_ID", "!test:matrix.example.org")
    monkeypatch.setenv("MATRIX_ROOM_ID", "!production:matrix.example.org")
    monkeypatch.setattr(app, "_fetch_with_retries", lambda _date: {"rubbish"})
    calls = []
    monkeypatch.setattr(
        app, "_send_once",
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
        app, "_send_once",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("A send was attempted")),
    )
    monkeypatch.delenv("MATRIX_E2E_TEST_ROOM_ID", raising=False)
    with pytest.raises(app.matrix.MatrixError, match="must be configured"):
        app.run_e2e(dt.date(2030, 1, 2))
    monkeypatch.setenv("MATRIX_E2E_TEST_ROOM_ID", "!production:matrix.example.org")
    with pytest.raises(app.matrix.MatrixError, match="must differ"):
        app.run_e2e(dt.date(2030, 1, 2))


def test_group_and_beszel_dm_send_once_each(monkeypatch, tmp_path):
    target = dt.date(2030, 1, 2)
    calls = []
    monkeypatch.setenv("AUCKLAND_BIN_DM_ENV", "/secure/beszel.env")
    monkeypatch.setenv("AUCKLAND_BIN_DM_USER_ID", "@beszel:matrix.example.org")
    monkeypatch.setenv("AUCKLAND_BIN_DM_ROOM_ID", "!dm:matrix.example.org")
    monkeypatch.setenv("AUCKLAND_BIN_DM_IGNORE_UNVERIFIED_DEVICES", "true")
    monkeypatch.setattr(app, "_fetch_with_retries", lambda _date: {"rubbish"})
    monkeypatch.setattr(app, "state_path", lambda: tmp_path / "state.json")
    monkeypatch.setattr(app, "_send_once", lambda msg: calls.append(("group", msg)))
    monkeypatch.setattr(
        app.beszel_dm, "send_message",
        lambda msg, **kwargs: calls.append(("dm", msg, kwargs["expected_user"], kwargs["expected_room"], kwargs["allow_unverified"])),
    )

    app.run(target)
    app.run(target)

    assert len(calls) == 2
    assert calls[0][0] == "group"
    assert calls[1][0] == "dm"
    assert calls[1][2:] == ("@beszel:matrix.example.org", "!dm:matrix.example.org", True)
    from auckland_bin_notifier.state import was_sent
    assert was_sent(tmp_path / "state.json", "2030-01-02:rubbish")
    assert was_sent(tmp_path / "state.json", "2030-01-02:rubbish", recipient="dm")


def test_dm_failure_does_not_duplicate_group(monkeypatch, tmp_path):
    import pytest

    target = dt.date(2030, 1, 2)
    calls = []
    monkeypatch.setenv("AUCKLAND_BIN_DM_ENV", "/secure/beszel.env")
    monkeypatch.setenv("AUCKLAND_BIN_DM_USER_ID", "@beszel:matrix.example.org")
    monkeypatch.setenv("AUCKLAND_BIN_DM_ROOM_ID", "!dm:matrix.example.org")
    monkeypatch.setattr(app, "_fetch_with_retries", lambda _date: {"recycling"})
    monkeypatch.setattr(app, "state_path", lambda: tmp_path / "state.json")
    monkeypatch.setattr(app, "_send_once", lambda msg: calls.append("group"))

    def dm_send(*args, **kwargs):
        calls.append("dm")
        if calls.count("dm") == 1:
            raise app.matrix.MatrixError("temporarily unavailable")

    monkeypatch.setattr(app.beszel_dm, "send_message", dm_send)
    with pytest.raises(app.matrix.MatrixError, match="Beszel DM"):
        app.run(target)
    app.run(target)
    assert calls == ["group", "dm", "dm"]


def test_group_failure_still_delivers_dm(monkeypatch, tmp_path):
    import pytest

    target = dt.date(2030, 1, 2)
    calls = []
    monkeypatch.setenv("AUCKLAND_BIN_DM_ENV", "/secure/beszel.env")
    monkeypatch.setenv("AUCKLAND_BIN_DM_USER_ID", "@beszel:matrix.example.org")
    monkeypatch.setenv("AUCKLAND_BIN_DM_ROOM_ID", "!dm:matrix.example.org")
    monkeypatch.setattr(app, "_fetch_with_retries", lambda _date: {"rubbish"})
    monkeypatch.setattr(app, "state_path", lambda: tmp_path / "state.json")

    def group_send(message):
        calls.append("group")
        if calls.count("group") == 1:
            raise app.matrix.MatrixError("temporarily unavailable")

    monkeypatch.setattr(app, "_send_once", group_send)
    monkeypatch.setattr(app.beszel_dm, "send_message", lambda *a, **kw: calls.append("dm"))
    with pytest.raises(app.matrix.MatrixError, match="group"):
        app.run(target)
    app.run(target)
    assert calls == ["group", "dm", "group"]


def test_dual_destination_dry_run_does_not_send(monkeypatch, tmp_path):
    monkeypatch.setenv("AUCKLAND_BIN_DM_ENV", "/secure/beszel.env")
    monkeypatch.setattr(app, "_fetch_with_retries", lambda _date: {"rubbish"})
    monkeypatch.setattr(app, "state_path", lambda: tmp_path / "state.json")
    monkeypatch.setattr(app, "_send_once", lambda *a: (_ for _ in ()).throw(AssertionError("sent")))
    monkeypatch.setattr(app.beszel_dm, "send_message", lambda *a, **k: (_ for _ in ()).throw(AssertionError("sent")))
    app.run(dt.date(2030, 1, 2), dry_run=True)
    assert not (tmp_path / "state.json").exists()
