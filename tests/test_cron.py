from datetime import datetime

from codeagent.tasks.cron import cron_matches, validate_cron


def test_validate_cron_ok():
    assert validate_cron("*/5 * * * *") is None


def test_validate_cron_bad():
    assert "out of bounds" in validate_cron("99 * * * *")


def test_cron_matches_step():
    assert cron_matches("*/5 * * * *", datetime(2026, 6, 3, 10, 15))
    assert not cron_matches("*/5 * * * *", datetime(2026, 6, 3, 10, 16))
