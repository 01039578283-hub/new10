#!/usr/bin/env python3
"""Audit subject-page anchor contents against a pre-change Git revision."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from add_subject_anchor_tocs import (
    ROOT,
    STYLE_BLOCK_RE,
    STYLE_HREF,
    SUBJECT_CATEGORIES,
    SUBJECT_ROOT,
    TOC_BLOCK_RE,
    detail_pages,
    detect_newline,
    media_gap_newlines,
    media_section_opening,
    normalize_disclosure_gap,
    strip_owned_heading_attributes,
    validate_hubs,
    validate_page,
)


class GitBatch:
    def __init__(self) -> None:
        self.process = subprocess.Popen(
            ["git", "cat-file", "--batch"],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("Could not open git cat-file pipes")

    def blob(self, revision: str, path: Path) -> bytes:
        relative = path.relative_to(ROOT).as_posix()
        request = f"{revision}:{relative}\n".encode("utf-8")
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.process.stdin.write(request)
        self.process.stdin.flush()
        header = self.process.stdout.readline().decode("ascii", errors="replace").strip()
        parts = header.split()
        if len(parts) == 2 and parts[1] == "missing":
            raise ValueError(f"Missing baseline blob: {relative}")
        if len(parts) != 3 or parts[1] != "blob":
            raise ValueError(f"Unexpected git cat-file response: {header}")
        size = int(parts[2])
        data = self.process.stdout.read(size)
        if self.process.stdout.read(1) != b"\n":
            raise ValueError("Malformed git cat-file record terminator")
        return data

    def close(self) -> None:
        if self.process.stdin:
            self.process.stdin.close()
        self.process.wait(timeout=10)


def strip_enhancement(source: str) -> str:
    source = STYLE_BLOCK_RE.sub("", source, count=1)
    source = TOC_BLOCK_RE.sub("", source, count=1)
    source = strip_owned_heading_attributes(source)
    newline = detect_newline(source)
    source = normalize_disclosure_gap(source, newline)
    media_section = media_section_opening(source)
    line_start = source.rfind(newline, 0, media_section.start())
    if line_start < 0:
        raise ValueError("Media section is not on its own line")
    line_start += len(newline)
    indent = source[line_start : media_section.start()]
    if indent.strip():
        raise ValueError("Media section indentation is malformed")
    gap_start = len(source[: media_section.start()].rstrip(" \t\r\n"))
    gap_newlines = media_gap_newlines(source, media_section.start())
    return (
        source[:gap_start]
        + (newline * gap_newlines)
        + indent
        + source[media_section.start() :]
    )


def normalized_newlines(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-ref",
        default="HEAD",
        help="Git revision before the TOC change (default: HEAD)",
    )
    args = parser.parse_args()

    pages = detail_pages()
    failures: list[str] = []
    exact_preserved = 0
    batch = GitBatch()
    try:
        for path in pages:
            relative = path.relative_to(ROOT).as_posix()
            try:
                current = path.read_bytes().decode("utf-8")
                errors = validate_page(current)
                if errors:
                    raise ValueError("; ".join(errors))
                stripped = strip_enhancement(current).encode("utf-8")
                baseline = batch.blob(args.baseline_ref, path)
                if normalized_newlines(stripped) != normalized_newlines(baseline):
                    raise ValueError(
                        "Non-TOC page content differs from the baseline revision"
                    )
                exact_preserved += 1
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{relative}: {exc}")

        hubs = [SUBJECT_ROOT / "index.html"] + [
            SUBJECT_ROOT / category / "index.html"
            for category in SUBJECT_CATEGORIES
        ]
        for hub in hubs:
            relative = hub.relative_to(ROOT).as_posix()
            try:
                if normalized_newlines(hub.read_bytes()) != normalized_newlines(
                    batch.blob(args.baseline_ref, hub)
                ):
                    raise ValueError("Hub differs from the baseline revision")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{relative}: {exc}")
    finally:
        batch.close()

    failures.extend(validate_hubs())
    stylesheet = ROOT / STYLE_HREF.removeprefix("../../../").split("?", 1)[0]
    if not stylesheet.is_file():
        failures.append("TOC stylesheet is missing")

    print(f"pages={len(pages)} exact_non_toc_preservation={exact_preserved}")
    print(f"hubs_checked={1 + len(SUBJECT_CATEGORIES)} baseline_ref={args.baseline_ref}")
    print(f"failures={len(failures)}")
    for failure in failures[:50]:
        print("ERROR", failure)
    if len(failures) > 50:
        print(f"ERROR ... and {len(failures) - 50} more")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
