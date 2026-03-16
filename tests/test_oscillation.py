"""Tests for oscillation detector (FR-006)."""

from mobiusforge.intelligence.oscillation import OscillationDetector, LoopSnapshot


def test_no_oscillation_initially():
    det = OscillationDetector(threshold=3, window_size=5)
    result = det.detect()
    assert not result.detected


def test_detect_repeated_hash():
    det = OscillationDetector(threshold=3, window_size=5)

    # Manually inject snapshots with same hash
    for i in range(3):
        det._history.append(LoopSnapshot(i + 1, "abc123", ["file.py"]))

    result = det.detect()
    assert result.detected
    assert result.repeat_count >= 3
    assert "file.py" in result.oscillating_files


def test_detect_pingpong():
    det = OscillationDetector(threshold=3, window_size=5)

    # A→B→A→B pattern
    det._history.append(LoopSnapshot(1, "hash_a", ["a.py"]))
    det._history.append(LoopSnapshot(2, "hash_b", ["a.py"]))
    det._history.append(LoopSnapshot(3, "hash_a", ["a.py"]))
    det._history.append(LoopSnapshot(4, "hash_b", ["a.py"]))

    result = det.detect()
    assert result.detected
    assert "pingpong" in result.pattern_hash


def test_no_oscillation_different_hashes():
    det = OscillationDetector(threshold=3, window_size=5)

    for i in range(5):
        det._history.append(LoopSnapshot(i + 1, f"unique_{i}", [f"file_{i}.py"]))

    result = det.detect()
    assert not result.detected


def test_reset():
    det = OscillationDetector(threshold=3, window_size=5)
    det._history.append(LoopSnapshot(1, "abc", ["f.py"]))
    det.reset()
    assert len(det._history) == 0
