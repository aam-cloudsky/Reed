"""Every `docs/*.md` path cited in the source must exist (issue #34)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = re.compile(r"docs/[A-Za-z0-9_./-]+\.md")


def test_cited_docs_exist():
    missing = sorted(
        {
            f"{source.relative_to(ROOT)}: {match}"
            for source in (ROOT / "src").rglob("*.py")
            for match in DOC_PATH.findall(source.read_text(encoding="utf-8"))
            if not (ROOT / match).is_file()
        }
    )
    assert missing == []
