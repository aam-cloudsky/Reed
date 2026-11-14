"""The README Quick Start must run and print exactly its documented output."""

from __future__ import annotations

import contextlib
import io
import re
import sys
import types
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"


def _quick_start_section() -> str:
    text = README.read_text(encoding="utf-8")
    start = text.index("## Quick Start")
    end = text.index("\n## ", start + 1)
    return text[start:end]


def test_readme_quick_start_runs_and_prints_documented_output():
    section = _quick_start_section()
    code = re.search(r"```python\n(.*?)```", section, re.S).group(1)
    expected = re.search(r"Output:\s*```text\n(.*?)```", section, re.S).group(1)

    # dataclasses resolve annotations through sys.modules, so the snippet
    # runs as a real (temporary) module rather than in a bare namespace.
    module = types.ModuleType("readme_quick_start")
    sys.modules[module.__name__] = module
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            exec(compile(code, str(README), "exec"), module.__dict__)
    finally:
        sys.modules.pop(module.__name__, None)

    assert buffer.getvalue() == expected


def test_readme_has_no_retired_api():
    text = README.read_text(encoding="utf-8")
    for retired in ("publish(", "flow.run(", "pip install reed\n"):
        assert retired not in text
