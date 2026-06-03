from pathlib import Path

import pytest

from codeagent.tools.basic import safe_path


def test_safe_path_allows_inside(tmp_path: Path):
    target = safe_path("a/b.txt", tmp_path)
    assert target == (tmp_path / "a" / "b.txt").resolve()


def test_safe_path_blocks_escape(tmp_path: Path):
    with pytest.raises(ValueError):
        safe_path("../escape.txt", tmp_path)
