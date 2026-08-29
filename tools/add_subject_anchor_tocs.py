#!/usr/bin/env python3
"""Add page-specific anchor contents to subject academy detail pages.

Only the 2,968 regional pages directly below the eight ``과목별학원``
category folders are changed. The subject hub and category hubs remain
untouched. Every TOC label is read from that page's existing H2 text, so the
visible copy, metadata, JSON-LD, images, and ALT text are not rewritten.

Run this idempotent postprocessor again after regenerating subject pages.
"""

from __future__ import annotations

import argparse
import html
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUBJECT_ROOT = ROOT / "과목별학원"
SUBJECT_CATEGORIES = (
    "고1수학학원",
    "고1영어학원",
    "고2수학학원",
    "고2영어학원",
    "중2수학학원",
    "중2영어학원",
    "중3수학학원",
    "중3영어학원",
)
EXPECTED_PER_CATEGORY = 371

STYLE_MARKER = "<!-- subject-page-anchor-toc:style -->"
STYLE_HREF = "../../../assets/subject-anchor-toc.css"
STYLE_LINK = f'<link rel="stylesheet" href="{STYLE_HREF}">'
TOC_START = "<!-- subject-page-anchor-toc:start -->"
TOC_END = "<!-- subject-page-anchor-toc:end -->"
TARGET_CLASS = "subject-page-anchor-target"

TOC_BLOCK_RE = re.compile(
    rf"^[ \t]*{re.escape(TOC_START)}\r?\n.*?"
    rf"^[ \t]*{re.escape(TOC_END)}\r?\n?",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)
TOC_CAPTURE_RE = re.compile(
    rf"{re.escape(TOC_START)}.*?{re.escape(TOC_END)}",
    re.IGNORECASE | re.DOTALL,
)
STYLE_BLOCK_RE = re.compile(
    rf"^[ \t]*{re.escape(STYLE_MARKER)}\r?\n"
    rf'[ \t]*<link\s+rel=["\']stylesheet["\']\s+'
    rf'href=["\']{re.escape(STYLE_HREF)}["\']\s*>\r?\n?',
    re.IGNORECASE | re.MULTILINE,
)
STYLE_HREF_RE = re.compile(
    r"\.\./\.\./\.\./assets/subject-anchor-toc\.css(?:\?v=[^\"']*)?",
    re.IGNORECASE,
)
SITE_CSS_RE = re.compile(
    r'(?P<indent>^[ \t]*)<link\s+rel=["\']stylesheet["\']\s+'
    r'href=["\']\.\./\.\./\.\./assets/site\.css(?:\?v=[^"\']*)?["\']\s*>',
    re.IGNORECASE | re.MULTILINE,
)
H2_RE = re.compile(
    r"<h2\b(?P<attrs>[^>]*)>(?P<body>.*?)</h2>",
    re.IGNORECASE | re.DOTALL,
)
ID_RE = re.compile(r'\bid\s*=\s*(["\'])(?P<id>[^"\']+)\1', re.IGNORECASE)
CLASS_RE = re.compile(
    r'\bclass\s*=\s*(["\'])(?P<classes>[^"\']*)\1', re.IGNORECASE
)
ANY_ID_RE = re.compile(
    r'\bid\s*=\s*(["\'])(?P<id>[^"\']+)\1', re.IGNORECASE
)
PAGE_HERO_RE = re.compile(
    r'<section\b(?=[^>]*\bclass=["\'][^"\']*\bpage-hero\b[^"\']*["\'])'
    r"[^>]*>.*?</section>",
    re.IGNORECASE | re.DOTALL,
)
SECTION_OPEN_RE = re.compile(r"<section\b[^>]*>", re.IGNORECASE)
MEDIA_ROW_RE = re.compile(
    r'<div\b(?=[^>]*\bclass=["\'][^"\']*\bmedia-row\b[^"\']*["\'])[^>]*>',
    re.IGNORECASE,
)
UNCONFIRMED_SECTION_RE = re.compile(
    r'<section\b(?=[^>]*\bclass=["\'][^"\']*'
    r'\bacademy-source-unconfirmed-note\b[^"\']*["\'])[^>]*>',
    re.IGNORECASE,
)
TOC_LINK_RE = re.compile(
    r'<a\s+href=["\']#(?P<id>[^"\']+)["\']>.*?'
    r'<span\s+class=["\']subject-page-toc-text["\']>'
    r"(?P<label>.*?)</span>\s*</a>",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class TocTarget:
    target_id: str
    text: str


def visible_text(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(html.unescape(text).split())


def detect_newline(source: str) -> str:
    if "\r\n" in source:
        if "\n" in source.replace("\r\n", ""):
            raise ValueError("Mixed newline styles")
        return "\r\n"
    return "\n"


def detail_pages() -> list[Path]:
    actual_categories = tuple(
        sorted(path.name for path in SUBJECT_ROOT.iterdir() if path.is_dir())
    )
    if actual_categories != tuple(sorted(SUBJECT_CATEGORIES)):
        raise ValueError(
            "Subject category folders differ from the expected eight: "
            f"{actual_categories}"
        )

    pages: list[Path] = []
    for category in SUBJECT_CATEGORIES:
        category_pages = sorted(
            path / "index.html"
            for path in (SUBJECT_ROOT / category).iterdir()
            if path.is_dir() and (path / "index.html").is_file()
        )
        if len(category_pages) != EXPECTED_PER_CATEGORY:
            raise ValueError(
                f"{category}: expected {EXPECTED_PER_CATEGORY} detail pages, "
                f"found {len(category_pages)}"
            )
        pages.extend(category_pages)
    return sorted(pages, key=lambda path: path.as_posix())


def ensure_style_link(source: str, newline: str) -> str:
    if STYLE_MARKER in source:
        source = STYLE_HREF_RE.sub(STYLE_HREF, source)
        if len(STYLE_BLOCK_RE.findall(source)) != 1:
            raise ValueError("Existing TOC stylesheet marker is malformed")
        return source
    matches = list(SITE_CSS_RE.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"Main stylesheet link count is {len(matches)}")
    match = matches[0]
    addition = (
        newline
        + match.group("indent")
        + STYLE_MARKER
        + newline
        + match.group("indent")
        + STYLE_LINK
    )
    return source[: match.end()] + addition + source[match.end() :]


def add_target_attributes(opening: str, target_id: str) -> str:
    id_match = ID_RE.search(opening)
    if id_match:
        if id_match.group("id") != target_id:
            raise ValueError(
                f"H2 {target_id} already has unexpected id {id_match.group('id')!r}"
            )
    else:
        opening = opening[:-1] + f' id="{target_id}">'

    class_match = CLASS_RE.search(opening)
    if class_match:
        classes = class_match.group("classes").split()
        if TARGET_CLASS not in classes:
            replacement = " ".join([*classes, TARGET_CLASS])
            opening = (
                opening[: class_match.start("classes")]
                + replacement
                + opening[class_match.end("classes") :]
            )
    else:
        opening = opening[:-1] + f' class="{TARGET_CLASS}">'
    return opening


def strip_owned_heading_attributes(source: str) -> str:
    """Remove only attributes owned by this postprocessor before rebuilding."""

    replacements: list[tuple[int, int, str]] = []
    for heading in H2_RE.finditer(source):
        opening_end = heading.start("body")
        opening = source[heading.start() : opening_end]
        cleaned = re.sub(
            r'\s+id=["\']subject-section-\d{2}["\']', "", opening, count=1
        )
        class_match = CLASS_RE.search(cleaned)
        if class_match:
            classes = [
                name
                for name in class_match.group("classes").split()
                if name != TARGET_CLASS
            ]
            if classes:
                cleaned = (
                    cleaned[: class_match.start("classes")]
                    + " ".join(classes)
                    + cleaned[class_match.end("classes") :]
                )
            else:
                left = cleaned[: class_match.start()].rstrip()
                right = cleaned[class_match.end() :]
                separator = " " if right and not right.startswith(">") else ""
                cleaned = left + separator + right
        cleaned = re.sub(r"<h2\s+>", "<h2>", cleaned, count=1, flags=re.IGNORECASE)
        if cleaned != opening:
            replacements.append((heading.start(), opening_end, cleaned))
    for start, end, replacement in reversed(replacements):
        source = source[:start] + replacement + source[end:]
    return source


def media_section_opening(source: str) -> re.Match[str]:
    media_rows = list(MEDIA_ROW_RE.finditer(source))
    if len(media_rows) != 1:
        raise ValueError(f"Media row count is {len(media_rows)}")
    openings = [
        opening
        for opening in SECTION_OPEN_RE.finditer(source, 0, media_rows[0].start())
    ]
    if not openings:
        raise ValueError("Section containing the media row is missing")
    return openings[-1]


def media_gap_newlines(source: str, media_position: int) -> int:
    """Return the generator's original gap before the media section."""

    prefix = source[:media_position].rstrip(" \t\r\n")
    previous_opening_start = prefix.rfind("<section")
    if previous_opening_start < 0:
        raise ValueError("Section before the media section is missing")
    previous_opening = SECTION_OPEN_RE.match(prefix, previous_opening_start)
    if not previous_opening:
        raise ValueError("Section before the media section is malformed")
    if "academy-source-unconfirmed-note" in previous_opening.group(0):
        return 1
    return 2


def normalize_disclosure_gap(source: str, newline: str) -> str:
    disclosures = list(UNCONFIRMED_SECTION_RE.finditer(source))
    if not disclosures:
        return source
    if len(disclosures) != 1:
        raise ValueError(f"Unconfirmed disclosure count is {len(disclosures)}")
    heroes = list(PAGE_HERO_RE.finditer(source))
    if len(heroes) != 1:
        raise ValueError(f"Page hero count is {len(heroes)}")
    hero = heroes[0]
    disclosure = disclosures[0]
    if disclosure.start() <= hero.end() or source[hero.end() : disclosure.start()].strip():
        raise ValueError("Unconfirmed disclosure does not directly follow the page hero")
    line_start = source.rfind(newline, hero.end(), disclosure.start())
    if line_start < 0:
        raise ValueError("Unconfirmed disclosure is not on its own line")
    indent = source[line_start + len(newline) : disclosure.start()]
    if indent.strip():
        raise ValueError("Unconfirmed disclosure indentation is malformed")
    return source[: hero.end()] + newline + indent + source[disclosure.start() :]


def ensure_heading_targets(
    source: str, first_target_position: int
) -> tuple[str, list[TocTarget]]:
    matches = [
        heading
        for heading in H2_RE.finditer(source)
        if heading.start() > first_target_position
    ]
    if not 2 <= len(matches) <= 30:
        raise ValueError(f"Unexpected H2 count: {len(matches)}")

    replacements: list[tuple[int, int, str]] = []
    targets: list[TocTarget] = []
    for index, heading in enumerate(matches, start=1):
        target_id = f"subject-section-{index:02d}"
        label = visible_text(heading.group("body"))
        if not label:
            raise ValueError(f"Empty H2 heading at position {index}")
        opening_end = heading.start("body")
        opening = source[heading.start() : opening_end]
        enhanced_opening = add_target_attributes(opening, target_id)
        if enhanced_opening != opening:
            replacements.append((heading.start(), opening_end, enhanced_opening))
        targets.append(TocTarget(target_id, label))

    for start, end, replacement in reversed(replacements):
        source = source[:start] + replacement + source[end:]
    return source, targets


def toc_markup(targets: list[TocTarget], indent: str, newline: str) -> str:
    child = indent + "  "
    grandchild = child + "  "
    item_indent = grandchild + "  "
    lines = [
        indent + TOC_START,
        indent
        + '<nav class="subject-page-toc" '
        + 'aria-labelledby="subject-page-toc-title">',
        child + '<div class="subject-page-toc-panel">',
        grandchild + '<div class="subject-page-toc-heading">',
        item_indent + '<p class="eyebrow">PAGE CONTENTS</p>',
        item_indent + '<strong id="subject-page-toc-title">페이지 목차</strong>',
        item_indent
        + "<p>원하는 항목을 누르면 해당 내용으로 바로 이동합니다.</p>",
        grandchild + "</div>",
        grandchild + '<ol class="subject-page-toc-list">',
    ]
    for index, target in enumerate(targets, start=1):
        lines.append(
            item_indent
            + "<li>"
            + f'<a href="#{html.escape(target.target_id, quote=True)}">'
            + f'<span class="subject-page-toc-number" aria-hidden="true">{index:02d}</span>'
            + f'<span class="subject-page-toc-text">{html.escape(target.text)}</span>'
            + "</a></li>"
        )
    lines.extend(
        [
            grandchild + "</ol>",
            child + "</div>",
            indent + "</nav>",
            indent + TOC_END,
        ]
    )
    return newline.join(lines) + newline


def render_page(original: str) -> tuple[str, int]:
    if original.count(TOC_START) != original.count(TOC_END):
        raise ValueError("Unbalanced TOC markers")
    if original.count(TOC_START) > 1:
        raise ValueError("Multiple TOC blocks found")

    source = TOC_BLOCK_RE.sub("", original, count=1)
    newline = detect_newline(source)
    source = ensure_style_link(source, newline)
    source = strip_owned_heading_attributes(source)
    source = normalize_disclosure_gap(source, newline)
    media_section = media_section_opening(source)
    source, targets = ensure_heading_targets(source, media_section.start())

    hero_matches = list(PAGE_HERO_RE.finditer(source))
    if len(hero_matches) != 1:
        raise ValueError(f"Page hero count is {len(hero_matches)}")
    hero = hero_matches[0]
    if media_section.start() <= hero.end():
        raise ValueError("Media section does not follow the page hero")
    line_start = source.rfind(newline, hero.end(), media_section.start())
    if line_start < 0:
        raise ValueError("First content section does not start on its own line")
    line_start += len(newline)
    indent = source[line_start : media_section.start()]
    if indent.strip():
        raise ValueError("First content section indentation is malformed")
    gap_start = len(source[: media_section.start()].rstrip(" \t\r\n"))
    gap_newlines = media_gap_newlines(source, media_section.start())
    rendered = (
        source[:gap_start]
        + (newline * gap_newlines)
        + toc_markup(targets, indent, newline)
        + newline
        + indent
        + source[media_section.start() :]
    )
    return rendered, len(targets)


def current_targets(source: str) -> list[TocTarget]:
    media_section = media_section_opening(source)
    targets: list[TocTarget] = []
    before = [
        heading
        for heading in H2_RE.finditer(source)
        if heading.start() < media_section.start()
    ]
    for heading in before:
        own_id = ID_RE.search(heading.group("attrs"))
        class_match = CLASS_RE.search(heading.group("attrs"))
        classes = class_match.group("classes").split() if class_match else []
        if (own_id and own_id.group("id").startswith("subject-section-")) or (
            TARGET_CLASS in classes
        ):
            raise ValueError("A heading before the TOC has owned anchor attributes")

    headings = [
        heading
        for heading in H2_RE.finditer(source)
        if heading.start() > media_section.start()
    ]
    for index, heading in enumerate(headings, start=1):
        target_id = f"subject-section-{index:02d}"
        id_match = ID_RE.search(heading.group("attrs"))
        class_match = CLASS_RE.search(heading.group("attrs"))
        classes = class_match.group("classes").split() if class_match else []
        if not id_match or id_match.group("id") != target_id:
            raise ValueError(f"H2 {index} target id is missing or incorrect")
        if TARGET_CLASS not in classes:
            raise ValueError(f"H2 {index} target class is missing")
        targets.append(TocTarget(target_id, visible_text(heading.group("body"))))
    return targets


def validate_page(source: str) -> list[str]:
    errors: list[str] = []
    if source.count(STYLE_MARKER) != 1 or source.count(STYLE_HREF) != 1:
        errors.append("TOC stylesheet marker or link count is not exactly one")
    if source.count(TOC_START) != 1 or source.count(TOC_END) != 1:
        errors.append("TOC marker count is not exactly one")
    toc = TOC_CAPTURE_RE.search(source)
    if not toc:
        errors.append("TOC block missing")
        return errors

    try:
        targets = current_targets(source)
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))
        return errors
    expected = [(target.target_id, target.text) for target in targets]
    links = [
        (match.group("id"), visible_text(match.group("label")))
        for match in TOC_LINK_RE.finditer(toc.group(0))
    ]
    if links != expected:
        errors.append("TOC links or labels do not match the page H2 headings")

    all_ids = [match.group("id") for match in ANY_ID_RE.finditer(source)]
    duplicate_ids = sorted(
        target_id
        for target_id, count in Counter(all_ids).items()
        if count > 1
    )
    if duplicate_ids:
        errors.append(f"Duplicate IDs found: {duplicate_ids}")
    if all_ids.count("subject-page-toc-title") != 1:
        errors.append("TOC title ID count is not exactly one")
    for target_id, _ in links:
        if all_ids.count(target_id) != 1:
            errors.append(
                f"Anchor target count for {target_id!r} is {all_ids.count(target_id)}"
            )

    hero = PAGE_HERO_RE.search(source)
    if not hero or not (hero.end() <= toc.start()):
        errors.append("TOC is not after the page hero")
    try:
        media_section = media_section_opening(source)
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))
    else:
        if toc.end() > media_section.start():
            errors.append("TOC is not before the media section")
        elif source[toc.end() : media_section.start()].strip():
            errors.append("Unexpected content appears between TOC and media section")
    return errors


def validate_hubs() -> list[str]:
    hubs = [SUBJECT_ROOT / "index.html"] + [
        SUBJECT_ROOT / category / "index.html" for category in SUBJECT_CATEGORIES
    ]
    errors: list[str] = []
    for hub in hubs:
        source = hub.read_text(encoding="utf-8")
        if (
            STYLE_MARKER in source
            or STYLE_HREF in source
            or TOC_START in source
            or TOC_END in source
        ):
            errors.append(
                "Hub unexpectedly contains a detail TOC: "
                + hub.relative_to(ROOT).as_posix()
            )
    return errors


def enhance_detail_html(source: str) -> str:
    """Return one validated detail page with its anchor contents applied."""

    rendered, _ = render_page(source)
    errors = validate_page(rendered)
    if errors:
        raise ValueError("; ".join(errors))
    return rendered


def process(write: bool) -> int:
    try:
        pages = detail_pages()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {exc}")
        return 1

    changed = 0
    validated = 0
    distribution: Counter[int] = Counter()
    categories: Counter[str] = Counter()
    failures: list[str] = []

    for path in pages:
        try:
            raw = path.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                raise ValueError("UTF-8 BOM is not supported")
            original = raw.decode("utf-8")
            rendered, target_count = render_page(original)
            page_errors = validate_page(rendered)
            if page_errors:
                raise ValueError("; ".join(page_errors))
            if rendered != original:
                changed += 1
                if write:
                    path.write_bytes(rendered.encode("utf-8"))
            distribution[target_count] += 1
            categories[path.relative_to(SUBJECT_ROOT).parts[0]] += 1
            validated += 1
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{path.relative_to(ROOT).as_posix()}: {exc}")

    failures.extend(validate_hubs())
    print(f"pages={len(pages)} validated={validated}")
    print(
        "toc_link_distribution="
        + ",".join(
            f"{count}:{page_count}"
            for count, page_count in sorted(distribution.items())
        )
    )
    print(
        "toc_links_total="
        + str(sum(count * page_count for count, page_count in distribution.items()))
    )
    print(
        "categories="
        + ",".join(f"{name}:{count}" for name, count in sorted(categories.items()))
    )
    print(f"changed={changed} mode={'write' if write else 'check'}")
    for failure in failures[:50]:
        print("ERROR", failure)
    if len(failures) > 50:
        print(f"ERROR ... and {len(failures) - 50} more")
    if not write and changed:
        print("ERROR check mode found pages that need updating")
        return 1
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="Apply or refresh TOCs")
    mode.add_argument("--check", action="store_true", help="Validate idempotence")
    args = parser.parse_args()
    raise SystemExit(process(write=args.write))


if __name__ == "__main__":
    main()
