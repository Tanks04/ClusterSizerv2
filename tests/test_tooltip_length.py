"""Guards against tooltip text creeping back up to unreadable lengths -
reported directly ("Hint button... waaaaay to long"). Scans every
setToolTip() call in src/ and fails if any exceeds a reasonable length
for a hover tooltip (roughly 2 short sentences).
"""

import re
from pathlib import Path

TOOLTIP_MAX_LENGTH = 150


def _find_long_tooltips(src_root: Path) -> list[tuple[int, str, int]]:
    results = []
    for path in src_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        content = path.read_text(encoding="utf-8")
        for m in re.finditer(r'setToolTip\(\s*((?:"[^"]*"\s*)+)\)', content):
            strings = re.findall(r'"([^"]*)"', m.group(1))
            full = "".join(strings)
            if len(full) > TOOLTIP_MAX_LENGTH:
                line_no = content[: m.start()].count("\n") + 1
                results.append((len(full), str(path), line_no))
    return results


def test_no_tooltip_exceeds_the_length_limit():
    src_root = Path(__file__).resolve().parent.parent / "src"

    long_tooltips = _find_long_tooltips(src_root)

    assert long_tooltips == [], (
        f"{len(long_tooltips)} tooltip(s) exceed {TOOLTIP_MAX_LENGTH} chars - "
        "keep hover tooltips to a sentence or two:\n"
        + "\n".join(f"  {length} chars  {path}:{line}" for length, path, line in long_tooltips)
    )
