
import pytest

from auckland_bin_notifier import beszel_dm
from auckland_bin_notifier.matrix import MatrixError


def test_beszel_sdk_uses_verified_account_and_room(monkeypatch, tmp_path):
    env = tmp_path / "beszel.env"
    env.write_text(
        "MATRIX_TRANSPORT=nio\n"
        "MATRIX_HOMESERVER=https://matrix.example.org\n"
        "MATRIX_USER_ID=@beszel:matrix.example.org\n"
        "MATRIX_DEVICE_ID=DEVICE\n"
        "MATRIX_ACCESS_TOKEN=private\n"
        "MATRIX_SDK_STORE_PATH=/tmp/beszel-store\n"
        "MATRIX_ROOM_ID=!dm:matrix.example.org\n"
    )
    seen = {}

    async def fake_send(body, **kwargs):
        seen.update(kwargs)
        seen["body"] = body
        return "$confirmed"

    monkeypatch.setattr(beszel_dm, "send_async", fake_send)
    beszel_dm.send_message(
        "Bins tomorrow", config_path=env,
        expected_user="@beszel:matrix.example.org",
        expected_room="!dm:matrix.example.org",
    )
    assert seen["body"] == "Bins tomorrow"
    assert seen["user_id"] == "@beszel:matrix.example.org"
    assert seen["room_id"] == "!dm:matrix.example.org"
    assert not seen["allow_unverified"]

    beszel_dm.send_message(
        "Bins tomorrow",
        config_path=env,
        expected_user="@beszel:matrix.example.org",
        expected_room="!dm:matrix.example.org",
        allow_unverified=True,
    )
    assert seen["allow_unverified"]


def test_beszel_refuses_wrong_target(monkeypatch, tmp_path):
    env = tmp_path / "beszel.env"
    env.write_text(
        "MATRIX_TRANSPORT=nio\n"
        "MATRIX_USER_ID=@beszel:matrix.example.org\n"
        "MATRIX_ROOM_ID=!different:matrix.example.org\n"
    )
    async def must_not_send(*args, **kwargs):
        raise AssertionError("wrong room was sent to")

    monkeypatch.setattr(beszel_dm, "send_async", must_not_send)
    with pytest.raises(MatrixError, match="verified identities"):
        beszel_dm.send_message(
            "Bins tomorrow", config_path=env,
            expected_user="@beszel:matrix.example.org",
            expected_room="!dm:matrix.example.org",
        )
