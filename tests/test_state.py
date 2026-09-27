from pathlib import Path

from auckland_bin_notifier.state import mark_sent, was_sent


def test_state_deduplicates(tmp_path: Path):
    path = tmp_path / "state.json"
    assert not was_sent(path, "2026-09-28:rubbish")
    mark_sent(path, "2026-09-28:rubbish")
    assert was_sent(path, "2026-09-28:rubbish")
    assert not was_sent(path, "2026-09-28:recycling,rubbish")
