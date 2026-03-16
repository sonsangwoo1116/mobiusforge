"""Tests for activity logger and secret masking (FR-023)."""

from pathlib import Path

from mobiusforge.monitor.logger import ActivityLogger, mask_secrets


def test_mask_anthropic_key():
    text = "Key is sk-ant-api03-abcdefghijklmnop1234567890"
    masked = mask_secrets(text)
    assert "sk-ant" not in masked
    assert "[MASKED]" in masked


def test_mask_openai_key():
    text = "Key: sk-proj-abcdefghijklmnop1234567890"
    masked = mask_secrets(text)
    assert "sk-proj" not in masked


def test_mask_github_pat():
    text = "Token: ghp_abcdefghijklmnop1234567890abcdefghij"
    masked = mask_secrets(text)
    assert "ghp_" not in masked


def test_no_false_positive():
    text = "This is normal text without any secrets"
    assert mask_secrets(text) == text


def test_activity_logger_save(tmp_path):
    log_dir = tmp_path / "logs"
    al = ActivityLogger(log_dir)

    al.log("test_event", loop=1, task_id="T-001", detail="hello")
    al.log("test_event2", loop=2, task_id="T-002")
    al.save()

    files = list(log_dir.glob("activity_*.jsonl"))
    assert len(files) == 1

    content = files[0].read_text()
    assert "test_event" in content
    assert "T-001" in content


def test_logger_masks_secrets(tmp_path):
    log_dir = tmp_path / "logs"
    al = ActivityLogger(log_dir, mask=True)

    al.log("secret", data="key is sk-ant-api03-abcdefghij1234567890")
    assert "[MASKED]" in str(al._entries[0])
