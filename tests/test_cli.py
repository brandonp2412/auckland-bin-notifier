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
