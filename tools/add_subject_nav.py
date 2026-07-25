from __future__ import annotations

import re
from pathlib import Path


SITE = Path(__file__).resolve().parents[1]
NAV_RE = re.compile(r'(<div class="nav-links">)(.*?)(</div>)', re.DOTALL)
NATIONWIDE_RE = re.compile(
    r'(?P<indent>[ \t]*)<a(?P<attrs>[^>]*)href="(?P<href>[^"]*전국학원[^"]*)"(?P<tail>[^>]*)>전국학원</a>'
)


def subject_href(nationwide_href: str) -> str:
    return nationwide_href.replace("전국학원", "과목별학원")


def update_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    match = NAV_RE.search(original)
    if not match or ">과목별학원</a>" in match.group(2):
        return False

    nav_body = match.group(2)
    nationwide = NATIONWIDE_RE.search(nav_body)
    if not nationwide:
        raise RuntimeError(f"전국학원 메뉴를 찾지 못했습니다: {path}")

    indent = nationwide.group("indent")
    href = subject_href(nationwide.group("href"))
    anchor = f'{indent}<a href="{href}">과목별학원</a>\n'
    insert_at = nationwide.end()
    updated_body = nav_body[:insert_at] + anchor + nav_body[insert_at:]
    updated = original[: match.start(2)] + updated_body + original[match.end(2):]
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    changed = 0
    for path in SITE.rglob("index.html"):
        if any(part in {".git", ".vercel", "node_modules"} for part in path.parts):
            continue
        changed += int(update_file(path))
    print(f"subject_nav_changed={changed}")


if __name__ == "__main__":
    main()
