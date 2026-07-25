from __future__ import annotations

import re
from pathlib import Path


SITE = Path(__file__).resolve().parents[1]
MESSY_RE = re.compile(
    r'(>전국학원</a>)([ \t]+)(<a href="[^"]*">과목별학원</a>)\n\n(\s*)(</div>)'
)


def fix_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    match = MESSY_RE.search(original)
    if not match:
        return False
    updated = (
        original[: match.start()]
        + match.group(1)
        + "\n"
        + match.group(2).replace("\t", "        ")
        + match.group(3)
        + "\n"
        + match.group(4)
        + match.group(5)
        + original[match.end():]
    )
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    changed = 0
    for path in SITE.rglob("index.html"):
        if any(part in {".git", ".vercel", "node_modules"} for part in path.parts):
            continue
        changed += int(fix_file(path))
    print(f"format_fixed={changed}")


if __name__ == "__main__":
    main()
