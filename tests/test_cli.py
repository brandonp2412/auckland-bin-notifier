from pathlib import Path

from auckland_bin_notifier.cli import load_default_env


def test_load_default_env(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.chdir(tmp_path)

    cfg = tmp_path / ".config/auckland-bin-notifier"
    cfg.mkdir(parents=True)
    (cfg / "config.env").write_text("AUCKLAND_BIN_PROPERTY_ID=00000000000\n")
    (cfg / "matrix.env").write_text(
        "MATRIX_HOMESERVER=https://matrix.example.org\n"
        "MATRIX_ROOM_ID=!example:matrix.example.org\n"
        "MATRIX_ACCESS_TOKEN=test-token\n"
    )

    for key in (
        "AUCKLAND_BIN_PROPERTY_ID",
        "MATRIX_HOMESERVER",
        "MATRIX_ROOM_ID",
        "MATRIX_ACCESS_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)

    load_default_env()

    import os

    assert os.environ["AUCKLAND_BIN_PROPERTY_ID"] == "00000000000"
    assert os.environ["MATRIX_HOMESERVER"] == "https://matrix.example.org"
    assert os.environ["MATRIX_ROOM_ID"] == "!example:matrix.example.org"
    assert os.environ["MATRIX_ACCESS_TOKEN"] == "test-token"


def test_local_dotenv_takes_precedence(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("AUCKLAND_BIN_PROPERTY_ID=11111111111\n")
    cfg = tmp_path / ".config/auckland-bin-notifier"
    cfg.mkdir(parents=True)
    (cfg / "config.env").write_text("AUCKLAND_BIN_PROPERTY_ID=22222222222\n")
    monkeypatch.delenv("AUCKLAND_BIN_PROPERTY_ID", raising=False)

    load_default_env()

    import os

    assert os.environ["AUCKLAND_BIN_PROPERTY_ID"] == "11111111111"


def test_sdk_credentials_override_legacy_when_provisioned(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / ".config/auckland-bin-notifier"
    cfg.mkdir(parents=True)
    (cfg / "matrix.env").write_text(
        "MATRIX_ACCESS_TOKEN=old-mcp-token\n"
        "MATRIX_MCP_URL=http://127.0.0.1:18116/mcp\n"
        "MATRIX_ROOM_ID=!bins:example.org\n"
    )
    (cfg / "matrix-sdk.env").write_text(
        "MATRIX_ACCESS_TOKEN=new-sdk-token\n"
        "MATRIX_DEVICE_ID=SDKDEVICE\n"
        "MATRIX_TRANSPORT=nio\n"
    )
    for key in (
        "MATRIX_ACCESS_TOKEN",
        "MATRIX_DEVICE_ID",
        "MATRIX_TRANSPORT",
        "MATRIX_MCP_URL",
        "MATRIX_ROOM_ID",
    ):
        # Force an undo record even when the variable was originally absent:
        # load_default_env writes to os.environ directly.
        monkeypatch.setenv(key, "test-placeholder")
        monkeypatch.delenv(key)
    load_default_env()

    import os

    assert "MATRIX_TRANSPORT" not in os.environ
    assert os.environ["MATRIX_ACCESS_TOKEN"] == "old-mcp-token"
    assert os.environ["MATRIX_ROOM_ID"] == "!bins:example.org"

    load_default_env(use_sdk=True)
    assert os.environ["MATRIX_TRANSPORT"] == "nio"
    assert os.environ["MATRIX_DEVICE_ID"] == "SDKDEVICE"
    assert os.environ["MATRIX_ACCESS_TOKEN"] == "new-sdk-token"
    assert os.environ["MATRIX_ROOM_ID"] == "!bins:example.org"
