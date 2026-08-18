from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import inspect
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import unquote, urljoin, urlsplit


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "https://xn--9p4bn5e1r987b.com"
HOST = "xn--9p4bn5e1r987b.com"
PARENT = "과목별학원"
EXISTING_CATEGORIES = (
    "중2수학학원",
    "중2영어학원",
    "중3수학학원",
    "중3영어학원",
)
NEW_CATEGORIES = (
    "고1수학학원",
    "고1영어학원",
    "고2수학학원",
    "고2영어학원",
)
EXPECTED_SOURCE_STATUS = {
    "고1수학학원": (354, 17),
    "고1영어학원": (362, 9),
    "고2수학학원": (325, 46),
    "고2영어학원": (332, 39),
}
ALL_SUBJECT_CATEGORIES = EXISTING_CATEGORIES + NEW_CATEGORIES
BASELINE_PAGE_COUNT = 2609
RELEASE_PAGE_COUNT = 4097
LOCALITY_COUNT = 371
PROJECTED_DOCUMENT_COUNT = 1491
RELEASE_DATE = "2026-08-18"
APPROVED_GENERATOR_RELATIVE = "tools/generate_high_grade_pages.py"
APPROVED_GENERATOR_SHA256 = "d248ba72cf49cec4e6bb206e338fb7aa1cef070207bf79a57c7dccc9c6843eed"
APPROVED_FACT_AUDITOR_RELATIVE = "tools/audit_high_grade_pages_release.py"
APPROVED_FACT_AUDITOR_SHA256 = "cff9377eb9e22ffebf6a39953370b5f241c6ccc4763083ae62e231c5290c6584"
BASELINE_SITEMAP_NON_PARENT_MANIFEST = "110490be12df5546f823bca62e99dbadddb517179c7a530a4d75a9bcc2762db6"
EXPECTED_SCHEMA_TYPES = {
    "WebPage",
    "ImageObject",
    "BreadcrumbList",
    "Article",
    "FAQPage",
}
BROWSER_WIDTHS = (320, 390, 1440)
IGNORED_SCHEMES = ("tel:", "sms:", "mailto:", "javascript:", "data:")
FORBIDDEN_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
TERMINAL_COMMA_RE = re.compile(r"[,，]\s*$")
ADJACENT_KOREAN_TOKEN_RE = re.compile(r"(?<![가-힣])([가-힣]{2,})\s+\1(?![가-힣])")
PRUNED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    "tmp",
    ".grade-pages-transaction",
}


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def strip_tags(value: str) -> str:
    return clean(re.sub(r"<[^>]*>", " ", value))


def posix_relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def route_for_relative(relative: str | PurePosixPath) -> str:
    value = PurePosixPath(relative)
    if value.name != "index.html":
        raise ValueError(f"not an index page: {value}")
    parent = value.parent.as_posix()
    return "/" if parent == "." else f"/{parent}/"


def normalize_route(value: str, *, base_route: str | None = None) -> str | None:
    value = html.unescape(value.strip())
    if not value or value.startswith(("#", *IGNORED_SCHEMES)):
        return None
    if base_route is not None:
        value = urljoin(f"{DOMAIN}{base_route}", value)
    parts = urlsplit(value)
    if parts.scheme and parts.scheme not in {"http", "https"}:
        return None
    if parts.netloc and parts.netloc.lower() != HOST:
        return None
    path = unquote(parts.path or "/").replace("\\", "/")
    path = re.sub(r"/{2,}", "/", path)
    if path == "/index.html":
        return "/"
    if path.endswith("/index.html"):
        path = path[: -len("index.html")]
    if not path.startswith("/"):
        path = f"/{path}"
    if path != "/" and not path.endswith("/"):
        path += "/"
    return path


def normalized_absolute(value: str) -> str | None:
    route = normalize_route(value)
    return f"{DOMAIN}{route}" if route is not None else None


def sitemap_rows(raw: bytes) -> list[tuple[str, str, str, str]]:
    text = raw.decode("utf-8")
    rows: list[tuple[str, str, str, str]] = []
    for block in re.findall(r"<url>(.*?)</url>", text, re.S):
        def field(name: str) -> str:
            match = re.search(rf"<{name}>(.*?)</{name}>", block, re.S)
            return html.unescape(match.group(1)).strip() if match else ""

        route = normalize_route(field("loc"))
        if route is not None:
            rows.append((route, field("lastmod"), field("changefreq"), field("priority")))
    return rows


def sitemap_manifest(rows: Sequence[tuple[str, str, str, str]]) -> str:
    return sha256("\n".join("\0".join(row) for row in rows).encode("utf-8"))


def classes(attrs: Mapping[str, str | None]) -> set[str]:
    return set((attrs.get("class") or "").split())


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_chunks: list[str] = []
        self._in_title = False
        self.h1_chunks: list[list[str]] = []
        self._h1_depth = 0
        self.breadcrumb_chunks: list[list[str]] = []
        self._breadcrumb_depth = 0
        self._breadcrumb_root: str | None = None
        self.metas: list[dict[str, str | None]] = []
        self.links: list[dict[str, str | None]] = []
        self.anchors: list[dict[str, str | None]] = []
        self.images: list[dict[str, str | None]] = []
        self.mains: list[dict[str, str | None]] = []
        self.details: list[dict[str, str | None]] = []
        self.starts: list[tuple[str, dict[str, str | None]]] = []
        self.ld_scripts: list[str] = []
        self.other_scripts: list[str] = []
        self._script_chunks: list[str] | None = None
        self._script_is_ld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        self.starts.append((tag, data))
        if tag == "title":
            self._in_title = True
        if tag == "h1":
            self._h1_depth = 1
            self.h1_chunks.append([])
        elif self._h1_depth:
            self._h1_depth += 1
        is_breadcrumb = bool(classes(data) & {"breadcrumb", "breadcrumb-box", "subject-breadcrumb"})
        if is_breadcrumb and not self._breadcrumb_depth:
            self._breadcrumb_depth = 1
            self._breadcrumb_root = tag
            self.breadcrumb_chunks.append([])
        elif self._breadcrumb_depth:
            self._breadcrumb_depth += 1
        if tag == "meta":
            self.metas.append(data)
        elif tag == "link":
            self.links.append(data)
        elif tag == "a":
            self.anchors.append(data)
        elif tag == "img":
            self.images.append(data)
        elif tag == "main":
            self.mains.append(data)
        elif tag == "details":
            self.details.append(data)
        elif tag == "script":
            self._script_chunks = []
            self._script_is_ld = data.get("type") == "application/ld+json"

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if self._h1_depth:
            self._h1_depth -= 1
        if self._breadcrumb_depth:
            self._breadcrumb_depth -= 1
            if not self._breadcrumb_depth:
                self._breadcrumb_root = None
        if tag == "script" and self._script_chunks is not None:
            value = "".join(self._script_chunks)
            (self.ld_scripts if self._script_is_ld else self.other_scripts).append(value)
            self._script_chunks = None
            self._script_is_ld = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_chunks.append(data)
        if self._h1_depth and self.h1_chunks:
            self.h1_chunks[-1].append(data)
        if self._breadcrumb_depth and self.breadcrumb_chunks:
            self.breadcrumb_chunks[-1].append(data)
        if self._script_chunks is not None:
            self._script_chunks.append(data)


@dataclass
class Page:
    relative: str
    route: str
    raw: bytes
    text: str
    parsed: PageParser
    title: str
    h1: list[str]
    description: list[str]
    robots: list[str]
    canonical: list[str]
    og_url: list[str]
    og_title: list[str]
    og_image: list[str]
    twitter_title: list[str]
    twitter_image: list[str]
    json_values: list[Any]
    json_errors: list[str]


@dataclass
class Audit:
    errors: list[dict[str, Any]] = field(default_factory=list)
    observations: dict[str, Any] = field(default_factory=dict)

    def hard(self, condition: bool, code: str, detail: Any) -> None:
        if not condition:
            self.errors.append({"code": code, "detail": detail})

    def group(self, code: str, values: Sequence[Any], *, limit: int = 8) -> None:
        if values:
            self.errors.append(
                {"code": code, "count": len(values), "examples": list(values[:limit])}
            )


def meta_values(parser: PageParser, *, name: str | None = None, prop: str | None = None) -> list[str]:
    result: list[str] = []
    for item in parser.metas:
        if name is not None and (item.get("name") or "").lower() != name.lower():
            continue
        if prop is not None and item.get("property") != prop:
            continue
        result.append(item.get("content") or "")
    return result


def parse_page(relative: str, raw: bytes) -> Page:
    text = raw.decode("utf-8")
    parser = PageParser()
    parser.feed(text)
    canonical = [
        item.get("href") or ""
        for item in parser.links
        if "canonical" in (item.get("rel") or "").lower().split()
    ]
    json_values: list[Any] = []
    json_errors: list[str] = []
    for index, value in enumerate(parser.ld_scripts):
        try:
            json_values.append(json.loads(value))
        except Exception as exc:  # noqa: BLE001
            json_errors.append(f"block {index}: {exc}")
    return Page(
        relative=relative,
        route=route_for_relative(relative),
        raw=raw,
        text=text,
        parsed=parser,
        title=clean("".join(parser.title_chunks)),
        h1=[clean("".join(value)) for value in parser.h1_chunks],
        description=meta_values(parser, name="description"),
        robots=meta_values(parser, name="robots"),
        canonical=canonical,
        og_url=meta_values(parser, prop="og:url"),
        og_title=meta_values(parser, prop="og:title"),
        og_image=meta_values(parser, prop="og:image"),
        twitter_title=meta_values(parser, name="twitter:title"),
        twitter_image=meta_values(parser, name="twitter:image"),
        json_values=json_values,
        json_errors=json_errors,
    )


def top_level_nodes(page: Page) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for value in page.json_values:
        if not isinstance(value, dict):
            continue
        graph = value.get("@graph")
        if isinstance(graph, list):
            nodes.extend(node for node in graph if isinstance(node, dict))
        elif "@type" in value:
            nodes.append(value)
    return nodes


def node_types(node: Mapping[str, Any]) -> set[str]:
    value = node.get("@type")
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {item for item in value if isinstance(item, str)}
    return set()


def types_for(page: Page) -> set[str]:
    result: set[str] = set()
    for node in top_level_nodes(page):
        result.update(node_types(node))
    return result


def nodes_of_type(page: Page, expected: str) -> list[dict[str, Any]]:
    return [node for node in top_level_nodes(page) if expected in node_types(node)]


def iter_repo_files(root: Path) -> Iterable[Path]:
    # Prune at directory traversal time.  Merely filtering rglob() results still
    # walks large transient trees and makes the read-only freeze depend on tmp.
    for directory, names, files in os.walk(root, topdown=True):
        names[:] = sorted(name for name in names if name not in PRUNED_DIRS)
        base = Path(directory)
        for name in sorted(files):
            if name in {".grade-pages.lock"}:
                continue
            yield base / name


def repo_snapshot(root: Path) -> tuple[str, dict[str, str]]:
    items: dict[str, str] = {}
    digest = hashlib.sha256()
    for path in sorted(iter_repo_files(root), key=lambda value: value.as_posix()):
        relative = posix_relative(root, path)
        value = sha256(path.read_bytes())
        items[relative] = value
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(value.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest(), items


def git_status(root: Path) -> str:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        return f"ERROR:{completed.stderr.decode('utf-8', 'replace')}"
    return completed.stdout.decode("utf-8", "replace")


def load_module(path: Path) -> Any:
    name = f"high_grade_projection_{sha256(str(path).encode())[:12]}_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    tools = str(path.parent)
    sys.path.insert(0, tools)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(tools)
    return module


def document_mapping(
    root: Path,
    plan: Any,
    expected_before: Mapping[str, bytes | None] | None = None,
) -> tuple[dict[str, bytes], list[str]]:
    errors: list[str] = []
    documents = getattr(plan, "documents", None)
    if not isinstance(documents, (list, tuple)):
        return {}, ["BuildPlan.documents is not a list/tuple"]
    result: dict[str, bytes] = {}
    for index, document in enumerate(documents):
        path = getattr(document, "path", None)
        after = getattr(document, "after", None)
        before = getattr(document, "before", None)
        if not isinstance(path, Path):
            errors.append(f"document {index} path is not Path")
            continue
        absolute = path if path.is_absolute() else root / path
        try:
            relative = posix_relative(root, absolute)
        except Exception:
            errors.append(f"document {index} outside root: {path}")
            continue
        if relative in result:
            errors.append(f"duplicate document path: {relative}")
            continue
        if not isinstance(after, bytes):
            errors.append(f"document {index} after is not bytes: {relative}")
            continue
        actual = (
            expected_before.get(relative)
            if expected_before is not None and relative in expected_before
            else absolute.read_bytes() if absolute.exists() else None
        )
        if before != actual:
            errors.append(
                f"before mismatch {relative}: expected={sha256(actual) if actual is not None else None} "
                f"actual={sha256(before) if isinstance(before, bytes) else before!r}"
            )
        result[relative] = after
    return result, errors


def expected_projection_paths(localities: Sequence[str]) -> set[str]:
    paths = {
        f"{PARENT}/index.html",
        "sitemap.xml",
        "llms.txt",
    }
    for category in NEW_CATEGORIES:
        paths.add(f"{PARENT}/{category}/index.html")
        paths.update(f"{PARENT}/{category}/{locality}/index.html" for locality in localities)
    return paths


def projection_overrides(
    root: Path, script_path: Path, localities: Sequence[str], audit: Audit
) -> dict[str, bytes]:
    relative_script = posix_relative(root, script_path)
    script_digest = sha256(script_path.read_bytes())
    audit.hard(
        relative_script == APPROVED_GENERATOR_RELATIVE and script_digest == APPROVED_GENERATOR_SHA256,
        "approved_generator_pin",
        {
            "expected_path": APPROVED_GENERATOR_RELATIVE,
            "actual_path": relative_script,
            "expected_sha256": APPROVED_GENERATOR_SHA256,
            "actual_sha256": script_digest,
        },
    )
    if relative_script != APPROVED_GENERATOR_RELATIVE or script_digest != APPROVED_GENERATOR_SHA256:
        return {}
    before_sha, before_files = repo_snapshot(root)
    status_before = git_status(root)
    source_dir: Path | None = None
    common_dir: Path | None = None
    source_before: tuple[str, dict[str, str]] | None = None
    common_before: tuple[str, dict[str, str]] | None = None
    try:
        module = load_module(script_path)
        build_plan = getattr(module, "build_plan", None)
        if not callable(build_plan):
            audit.hard(False, "projection_api", "missing callable build_plan(root)")
            return {}
        signature = inspect.signature(build_plan)
        initial_kwargs: dict[str, Any] = {"root": root}
        initial_kwargs = {
            key: value for key, value in initial_kwargs.items() if key in signature.parameters
        }
        discover = getattr(module, "discover_reference_dirs", None)
        if callable(discover):
            source_dir, common_dir = discover(root, None, None)
            source_before = repo_snapshot(source_dir)
            common_before = repo_snapshot(common_dir)
            for key, value in (("source_dir", source_dir), ("common_dir", common_dir)):
                if key in signature.parameters:
                    initial_kwargs[key] = value
        plan = build_plan(**initial_kwargs)
        overrides, errors = document_mapping(root, plan)
        audit.group("projection_document_contract", errors)
        audit.hard(
            len(getattr(plan, "documents", [])) == PROJECTED_DOCUMENT_COUNT,
            "projection_document_count",
            {"expected": PROJECTED_DOCUMENT_COUNT, "actual": len(getattr(plan, "documents", []))},
        )
        expected = expected_projection_paths(localities)
        audit.hard(
            set(overrides) == expected,
            "projection_scope",
            {
                "missing_count": len(expected - set(overrides)),
                "missing": sorted(expected - set(overrides))[:8],
                "extra_count": len(set(overrides) - expected),
                "extra": sorted(set(overrides) - expected)[:8],
            },
        )
        declared = set()
        for value in getattr(plan, "authorized_paths", ()):
            path = Path(value)
            declared.add(posix_relative(root, path if path.is_absolute() else root / path))
        audit.hard(
            declared == expected,
            "projection_authorized_paths",
            {
                "declared": len(declared),
                "missing": sorted(expected - declared)[:8],
                "extra": sorted(declared - expected)[:8],
            },
        )
        plan_errors = getattr(plan, "errors", None)
        if plan_errors is not None:
            audit.hard(not plan_errors, "projection_plan_errors", list(plan_errors)[:8])
        plan_idempotent = getattr(plan, "idempotent", None)
        if plan_idempotent is not None:
            audit.hard(bool(plan_idempotent), "projection_plan_idempotent", plan_idempotent)

        second_plan = build_plan(**initial_kwargs)
        second_mapping, second_errors = document_mapping(root, second_plan)
        audit.group("projection_repeat_contract", second_errors)
        audit.hard(
            {key: sha256(value) for key, value in overrides.items()}
            == {key: sha256(value) for key, value in second_mapping.items()},
            "projection_deterministic",
            "two clean build_plan calls differ",
        )

        if "current_overrides" in signature.parameters:
            pass_kwargs = dict(initial_kwargs)
            pass_kwargs["current_overrides"] = {
                (root / relative).resolve(): value for relative, value in overrides.items()
            }
            candidate = build_plan(**pass_kwargs)
            candidate_mapping, candidate_errors = document_mapping(
                root, candidate, {relative: value for relative, value in overrides.items()}
            )
            audit.group("projection_second_pass_contract", candidate_errors)
            audit.hard(
                candidate_mapping == overrides,
                "projection_second_pass",
                {
                    "expected": len(overrides),
                    "actual": len(candidate_mapping),
                    "changed": [
                        relative
                        for relative in sorted(set(overrides) | set(candidate_mapping))
                        if overrides.get(relative) != candidate_mapping.get(relative)
                    ][:8],
                },
            )
            audit.hard(
                getattr(candidate, "idempotent", None) is True,
                "projection_second_declared_idempotency",
                getattr(candidate, "idempotent", None),
            )
            second_pass = {"supported": True, "documents": len(candidate_mapping), "changes": sum(
                overrides.get(relative) != candidate_mapping.get(relative)
                for relative in set(overrides) | set(candidate_mapping)
            )}
        else:
            second_pass = {"supported": False, "documents": 0, "changes": None}
            audit.hard(False, "projection_second_pass_api", "build_plan must accept current_overrides")
        audit.observations["projection"] = {
            "script": posix_relative(root, script_path),
            "script_sha256": sha256(script_path.read_bytes()),
            "documents": len(overrides),
            "changed": sum(
                1 for relative, value in overrides.items()
                if not (root / relative).exists() or (root / relative).read_bytes() != value
            ),
            "second_pass": second_pass,
        }
        return overrides
    finally:
        after_sha, after_files = repo_snapshot(root)
        status_after = git_status(root)
        audit.hard(
            before_sha == after_sha and before_files == after_files,
            "projection_repo_freeze",
            {"before": before_sha, "after": after_sha},
        )
        audit.hard(
            status_before == status_after,
            "projection_git_freeze",
            {"before": status_before, "after": status_after},
        )
        if source_dir is not None and source_before is not None:
            source_after = repo_snapshot(source_dir)
            audit.hard(
                source_before == source_after,
                "projection_source_freeze",
                {"before": source_before[0], "after": source_after[0]},
            )
        if common_dir is not None and common_before is not None:
            common_after = repo_snapshot(common_dir)
            audit.hard(
                common_before == common_after,
                "projection_common_freeze",
                {"before": common_before[0], "after": common_after[0]},
            )
        audit.observations["repo_freeze"] = {"before": before_sha, "after": after_sha}


def virtual_bytes(root: Path, relative: str, overrides: Mapping[str, bytes]) -> bytes:
    if relative in overrides:
        return overrides[relative]
    return (root / relative).read_bytes()


def discover_pages(root: Path, overrides: Mapping[str, bytes]) -> list[str]:
    paths = {
        posix_relative(root, path)
        for path in root.rglob("index.html")
        if ".git" not in path.relative_to(root).parts
    }
    paths.update(relative for relative in overrides if relative.endswith("/index.html") or relative == "index.html")
    return sorted(paths)


def localities_from_baseline(root: Path) -> list[str]:
    category = root / PARENT / EXISTING_CATEGORIES[0]
    return sorted(
        path.parent.name
        for path in category.glob("*/index.html")
        if path.parent != category
    )


def internal_asset_path(page: Page, value: str) -> str | None:
    value = html.unescape(value.strip())
    if not value or value.startswith(("data:", "blob:")):
        return None
    absolute = urljoin(f"{DOMAIN}{page.route}", value)
    parts = urlsplit(absolute)
    if parts.netloc and parts.netloc.lower() != HOST:
        return None
    path = unquote(parts.path).lstrip("/")
    return path or None


@lru_cache(maxsize=None)
def image_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.size
    except Exception:  # noqa: BLE001
        return None


def static_global_audit(
    root: Path,
    pages: Mapping[str, Page],
    overrides: Mapping[str, bytes],
    audit: Audit,
) -> set[str]:
    routes = {page.route for page in pages.values()}
    metadata_bad: list[Any] = []
    json_bad: list[Any] = []
    broken_links: list[Any] = []
    broken_images: list[Any] = []
    control_bad: list[Any] = []
    canonical_values: list[str] = []
    titles: list[str] = []
    for relative, page in pages.items():
        control = FORBIDDEN_CONTROL_RE.search(page.text)
        if control:
            control_bad.append(
                {"path": relative, "control_character": f"U+{ord(control.group()):04X}"}
            )
        expected = f"{DOMAIN}{page.route}"
        if (
            not page.title
            or len(page.h1) != 1
            or len(page.description) != 1
            or len(page.canonical) != 1
            or normalized_absolute(page.canonical[0]) != expected
            or not urlsplit(page.canonical[0]).path.endswith("/")
            or len(page.og_url) != 1
            or normalized_absolute(page.og_url[0]) != expected
            or not urlsplit(page.og_url[0]).path.endswith("/")
            or any("noindex" in value.lower() for value in page.robots)
        ):
            metadata_bad.append(
                {
                    "path": relative,
                    "title": bool(page.title),
                    "h1": len(page.h1),
                    "description": len(page.description),
                    "canonical": page.canonical,
                    "og_url": page.og_url,
                    "robots": page.robots,
                }
            )
        canonical_values.extend(normalized_absolute(value) or value for value in page.canonical)
        titles.append(page.title)
        if page.json_errors or not page.json_values:
            json_bad.append({"path": relative, "errors": page.json_errors, "blocks": len(page.json_values)})
        for anchor in page.parsed.anchors:
            href = anchor.get("href") or ""
            route = normalize_route(href, base_route=page.route)
            if route is not None and route not in routes:
                broken_links.append({"path": relative, "href": href, "resolved": route})
        for image in page.parsed.images:
            src = image.get("src") or ""
            target = internal_asset_path(page, src)
            if target is None:
                continue
            if target in overrides:
                exists = True
            else:
                exists = (root / target).is_file()
            if not exists:
                broken_images.append({"path": relative, "src": src, "resolved": target})
            srcset = image.get("srcset") or ""
            for item in srcset.split(","):
                candidate = item.strip().split(" ", 1)[0]
                if not candidate:
                    continue
                target = internal_asset_path(page, candidate)
                if target is not None and not (root / target).is_file() and target not in overrides:
                    broken_images.append({"path": relative, "srcset": candidate, "resolved": target})
    duplicates = [value for value, count in Counter(canonical_values).items() if count > 1]
    audit.group("global_metadata", metadata_bad)
    audit.group("html_control_characters", control_bad)
    audit.group("global_jsonld", json_bad)
    audit.group("broken_internal_links", broken_links)
    audit.group("broken_local_images", broken_images)
    audit.group("duplicate_canonical", duplicates)
    audit.hard(len(set(titles)) == len(titles), "duplicate_titles", len(titles) - len(set(titles)))

    sitemap_raw = virtual_bytes(root, "sitemap.xml", overrides)
    sitemap = sitemap_raw.decode("utf-8")
    sitemap_values = [normalize_route(value) for value in re.findall(r"<loc>(.*?)</loc>", sitemap, re.S)]
    sitemap_routes = [value for value in sitemap_values if value is not None]
    audit.hard(
        len(sitemap_values) == len(sitemap_routes) == len(set(sitemap_routes)),
        "sitemap_unique_valid",
        {"loc": len(sitemap_values), "valid": len(sitemap_routes), "unique": len(set(sitemap_routes))},
    )
    audit.hard(
        set(sitemap_routes) == routes,
        "sitemap_page_parity",
        {
            "missing_count": len(routes - set(sitemap_routes)),
            "missing": sorted(routes - set(sitemap_routes))[:8],
            "extra_count": len(set(sitemap_routes) - routes),
            "extra": sorted(set(sitemap_routes) - routes)[:8],
        },
    )
    rows = sitemap_rows(sitemap_raw)
    non_parent_rows = [row for row in rows if row[0] != f"/{PARENT}/"]
    # All pre-existing sitemap entries except the intentionally edited subject hub
    # must retain their order and metadata in both projection and materialized release.
    non_new_non_parent_rows = [
        row
        for row in non_parent_rows
        if not any(row[0].startswith(f"/{PARENT}/{category}/") for category in NEW_CATEGORIES)
    ]
    audit.hard(
        sitemap_manifest(non_new_non_parent_rows) == BASELINE_SITEMAP_NON_PARENT_MANIFEST,
        "sitemap_non_target_freeze",
        {
            "expected": BASELINE_SITEMAP_NON_PARENT_MANIFEST,
            "actual": sitemap_manifest(non_new_non_parent_rows),
            "rows": len(non_new_non_parent_rows),
        },
    )
    audit.observations["global"] = {
        "pages": len(pages),
        "routes": len(routes),
        "sitemap_urls": len(sitemap_routes),
        "sitemap_sha256": sha256(sitemap_raw),
        "sitemap_non_target_manifest": sitemap_manifest(non_new_non_parent_rows),
        "internal_hrefs": sum(len(page.parsed.anchors) for page in pages.values()),
        "images": sum(len(page.parsed.images) for page in pages.values()),
        "broken_links": len(broken_links),
        "broken_images": len(broken_images),
    }
    return routes


def schema_breadcrumb(page: Page) -> list[dict[str, Any]] | None:
    nodes = nodes_of_type(page, "BreadcrumbList")
    if len(nodes) != 1:
        return None
    values = nodes[0].get("itemListElement")
    return values if isinstance(values, list) and all(isinstance(item, dict) for item in values) else None


def visible_faq_pairs(page: Page) -> list[tuple[str, str, str]]:
    section = re.search(
        r'<div\b[^>]*class="[^"]*\bgrade-faq-list\b[^"]*"[^>]*>(.*?)</div>',
        page.text,
        re.S | re.I,
    )
    if not section:
        return []
    result: list[tuple[str, str, str]] = []
    for attrs, body in re.findall(r"<details\b([^>]*)>(.*?)</details>", section.group(1), re.S | re.I):
        topic_match = re.search(r'\bdata-faq-topic\s*=\s*(["\'])(.*?)\1', attrs, re.S | re.I)
        question = re.search(r"<summary\b[^>]*>(.*?)</summary>", body, re.S | re.I)
        answer = re.search(r"<p\b[^>]*>(.*?)</p>", body, re.S | re.I)
        if not (topic_match and question and answer):
            return []
        result.append((clean(topic_match.group(2)), strip_tags(question.group(1)), strip_tags(answer.group(1))))
    return result


def schema_faq_pairs(page: Page) -> list[tuple[str, str]]:
    nodes = nodes_of_type(page, "FAQPage")
    if len(nodes) != 1 or not isinstance(nodes[0].get("mainEntity"), list):
        return []
    result: list[tuple[str, str]] = []
    for item in nodes[0]["mainEntity"]:
        if not isinstance(item, dict) or item.get("@type") != "Question":
            return []
        accepted = item.get("acceptedAnswer")
        if not isinstance(accepted, dict) or accepted.get("@type") != "Answer":
            return []
        question, answer = item.get("name"), accepted.get("text")
        if not isinstance(question, str) or not isinstance(answer, str):
            return []
        result.append((clean(question), clean(answer)))
    return result


def visible_article_headings(page: Page) -> list[str]:
    section = re.search(
        r'<section\b[^>]*class="[^"]*\bgrade-main-article\b[^"]*"[^>]*>(.*?)</section>',
        page.text,
        re.S | re.I,
    )
    if not section:
        return []
    return [strip_tags(value) for value in re.findall(r"<h2\b[^>]*>(.*?)</h2>", section.group(1), re.S | re.I)]


def visible_location_guides(page: Page) -> list[str]:
    result: list[str] = []
    for attrs, body in re.findall(r"<p\b([^>]*)>(.*?)</p>", page.text, re.S | re.I):
        if re.search(r'\bdata-source-field\s*=\s*(["\'])location-guide\1', attrs, re.I):
            result.append(strip_tags(body))
    return result


def rendered_main_text(page: Page) -> str:
    main = re.search(r"<main\b[^>]*>(.*?)</main>", page.text, re.S | re.I)
    if not main:
        return ""
    value = re.sub(r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>", " ", main.group(1), flags=re.S | re.I)
    return strip_tags(value)


def rendered_authored_text(page: Page) -> str:
    values: list[str] = []
    for class_name in ("grade-main-article", "grade-faq-list"):
        block = re.search(
            rf'<(?:section|div)\b[^>]*class="[^"]*\b{class_name}\b[^"]*"[^>]*>(.*?)</(?:section|div)>',
            page.text,
            re.S | re.I,
        )
        if block:
            values.append(strip_tags(block.group(1)))
    return " ".join(values)


def visible_main_h2(page: Page) -> list[str]:
    main = re.search(r"<main\b[^>]*>(.*?)</main>", page.text, re.S | re.I)
    if not main:
        return []
    return [strip_tags(value) for value in re.findall(r"<h2\b[^>]*>(.*?)</h2>", main.group(1), re.S | re.I)]


def repeated_heading_tokens(heading: str) -> list[str]:
    tokens = re.findall(r"[가-힣]{2,}", heading)
    return sorted(token for token, count in Counter(tokens).items() if count > 1)


def resolved_anchor_routes(page: Page, *, attribute: str | None = None) -> list[str]:
    values: list[str] = []
    for anchor in page.parsed.anchors:
        if attribute is not None and attribute not in anchor:
            continue
        route = normalize_route(anchor.get("href") or "", base_route=page.route)
        if route is not None:
            values.append(route)
    return values


def detail_image_contract(root: Path, page: Page) -> list[str]:
    errors: list[str] = []
    images = page.parsed.images
    if len(images) != 2:
        return [f"image count={len(images)}"]
    reps = [item for item in images if "/representative/" in (item.get("src") or "")]
    maps = [item for item in images if "/maps/" in (item.get("src") or "")]
    bodies = [item for item in images if item not in reps and item not in maps]
    if (len(reps), len(bodies), len(maps)) != (0, 1, 1):
        return [f"role counts rep/body/map={(len(reps), len(bodies), len(maps))}"]
    body, map_image = bodies[0], maps[0]
    if body.get("decoding") != "async" or body.get("fetchpriority") != "high" or body.get("loading") != "eager":
        errors.append("body image policy")
    if map_image.get("loading") != "lazy" or map_image.get("decoding") != "async" or map_image.get("fetchpriority"):
        errors.append("map image policy")
    for role, item in (("body", body), ("map", map_image)):
        width, height = item.get("width"), item.get("height")
        if not (width and height and width.isdigit() and height.isdigit() and int(width) > 0 and int(height) > 0):
            errors.append(f"{role} missing intrinsic attributes")
            continue
        target = internal_asset_path(page, item.get("src") or "")
        if target is None:
            errors.append(f"{role} external image")
            continue
        actual = image_dimensions(root / target)
        if actual != (int(width), int(height)):
            errors.append(f"{role} intrinsic mismatch attr={(width, height)} actual={actual}")
    srcset_items = [item.strip().split() for item in (body.get("srcset") or "").split(",") if item.strip()]
    if len(srcset_items) != 2 or not body.get("sizes") or any(len(item) != 2 or not item[1].endswith("w") for item in srcset_items):
        errors.append("body responsive srcset/sizes contract")
    else:
        responsive: list[tuple[int, tuple[int, int] | None]] = []
        for source, descriptor in srcset_items:
            path = internal_asset_path(page, source)
            responsive.append((int(descriptor[:-1]), image_dimensions(root / path) if path else None))
        if sorted(width for width, _ in responsive)[0] != 720 or any(dimensions is None or width != dimensions[0] for width, dimensions in responsive):
            errors.append(f"body responsive dimensions={responsive}")
    if len(page.og_image) != 1:
        errors.append(f"og:image count={len(page.og_image)}")
    else:
        og_path = internal_asset_path(page, page.og_image[0])
        if og_path is None or not re.fullmatch(r"assets/representative/rep-[0-9]{3}\.(?:gif|jpe?g|png|webp)", og_path, re.I):
            errors.append(f"og:image representative contract={og_path}")
        elif not (root / og_path).is_file() or image_dimensions(root / og_path) is None:
            errors.append(f"og:image representative missing/invalid={og_path}")
        if page.twitter_image != page.og_image:
            errors.append(f"twitter:image != og:image ({page.twitter_image} != {page.og_image})")
        image_nodes = nodes_of_type(page, "ImageObject")
        image_paths = [internal_asset_path(page, str(node.get("url", ""))) for node in image_nodes]
        if image_paths != [og_path]:
            errors.append(f"ImageObject representative={image_paths} expected={[og_path]}")
        article_nodes = nodes_of_type(page, "Article")
        article_images = article_nodes[0].get("image") if len(article_nodes) == 1 else None
        article_paths = (
            [internal_asset_path(page, str(value)) for value in article_images]
            if isinstance(article_images, list)
            else []
        )
        body_path = internal_asset_path(page, body.get("src") or "")
        map_path = internal_asset_path(page, map_image.get("src") or "")
        if article_paths != [og_path, body_path, map_path]:
            errors.append(f"Article image parity={article_paths} expected={[og_path, body_path, map_path]}")
    return errors


def expected_detail_route(category: str, locality: str) -> str:
    return f"/{PARENT}/{category}/{locality}/"


def audit_new_detail(
    root: Path, page: Page, category: str, locality: str, audit: Audit
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    label = category.replace("수학학원", " 수학학원").replace("영어학원", " 영어학원")
    if len(page.parsed.mains) != 1 or "data-grade-page" not in page.parsed.mains[0]:
        errors.append("main[data-grade-page] != 1")
    main = page.parsed.mains[0] if page.parsed.mains else {}
    unsupported = main.get("data-source-status") == "unconfirmed-grade"
    if main.get("data-source-status") not in {None, "unconfirmed-grade"}:
        errors.append(f"invalid source status={main.get('data-source-status')}")
    if len(page.h1) != 1 or not page.h1[0].endswith(label):
        errors.append(f"H1 suffix expected={label!r} actual={page.h1}")
    h1 = page.h1[0] if len(page.h1) == 1 else ""
    if page.title != f"{h1} | 영수학원":
        errors.append(f"title mismatch={page.title!r}")
    if page.og_title != [page.title]:
        errors.append(f"og:title mismatch={page.og_title}")
    if page.twitter_title != [page.title]:
        errors.append(f"twitter:title mismatch={page.twitter_title}")
    if not (len(page.description) == 1 and 50 <= len(page.description[0]) <= 160):
        errors.append(f"description count/length={len(page.description)}/{[len(x) for x in page.description]}")
    description = page.description[0] if len(page.description) == 1 else ""
    expected_route = expected_detail_route(category, locality)
    if page.route != expected_route:
        errors.append(f"route={page.route} expected={expected_route}")
    visible_bc = [re.sub(r"[\s/›>]+", "", "".join(chunks)) for chunks in page.parsed.breadcrumb_chunks]
    if len(visible_bc) != 1:
        errors.append(f"visible breadcrumb count={len(visible_bc)}")
    else:
        expected_visible = "".join(("홈", PARENT, category, h1)).replace(" ", "")
        if visible_bc[0] != expected_visible:
            errors.append(f"visible breadcrumb={visible_bc[0]!r} expected={expected_visible!r}")
    structured = schema_breadcrumb(page)
    if structured is None or len(structured) != 4:
        errors.append(f"schema breadcrumb count={None if structured is None else len(structured)}")
    else:
        names = [clean(str(item.get("name", ""))) for item in structured]
        expected_names = ["홈", PARENT, category, h1]
        if [value.replace(" ", "") for value in names] != [value.replace(" ", "") for value in expected_names]:
            errors.append(f"schema breadcrumb names={names}")
        item_routes = [normalize_route(str(item.get("item", ""))) for item in structured]
        expected_routes = ["/", f"/{PARENT}/", f"/{PARENT}/{category}/", expected_route]
        if item_routes != expected_routes:
            errors.append(f"schema breadcrumb routes={item_routes}")

    types = types_for(page)
    missing = EXPECTED_SCHEMA_TYPES - types
    if missing:
        errors.append(f"missing schema types={sorted(missing)}")
    organizations = [
        node for node in top_level_nodes(page)
        if "EducationalOrganization" in node_types(node) or "LocalBusiness" in node_types(node)
    ]
    if len(organizations) != 1:
        errors.append(f"physical organization count={len(organizations)}")
    else:
        organization = organizations[0]
        identifier = str(organization.get("@id", ""))
        if not re.fullmatch(rf"{re.escape(DOMAIN)}/센터/[0-9a-f]{{20}}/#organization", unquote(identifier)):
            errors.append(f"unstable physical organization id={identifier}")
        address = organization.get("address")
        if not isinstance(address, dict):
            errors.append("physical organization address missing")
            address = {}
        physical_name = organization.get("name")
        legal_name = organization.get("legalName")
        street = address.get("streetAddress")
        registration = organization.get("identifier")
        if not all(isinstance(value, str) and clean(value) for value in (physical_name, legal_name, street)):
            errors.append("physical organization name/legalName/streetAddress blank")
        elif unquote(identifier) != (
            f"{DOMAIN}/센터/"
            f"{hashlib.sha256(f'{legal_name}{chr(0)}{street}'.encode('utf-8')).hexdigest()[:20]}/#organization"
        ):
            errors.append("physical organization ID/source identity mismatch")
        if (
            not isinstance(registration, dict)
            or registration.get("@type") != "PropertyValue"
            or registration.get("propertyID") != "교육지원청 등록번호"
            or not clean(str(registration.get("value", "")))
        ):
            errors.append("physical organization registration identifier missing")
        if address.get("@type") != "PostalAddress" or address.get("addressCountry") != "KR":
            errors.append("physical organization PostalAddress contract")
        unsupported_blanket_fields = {
            key: organization.get(key)
            for key in (
                "telephone",
                "contactPoint",
                "openingHours",
                "openingHoursSpecification",
                "url",
                "sameAs",
                "additionalProperty",
            )
            if key in organization
        }
        if unsupported_blanket_fields:
            errors.append(f"physical organization unsupported blanket fields={sorted(unsupported_blanket_fields)}")
        offers = organization.get("makesOffer")
        if not isinstance(offers, list):
            errors.append("physical organization source offers must be a list")
    service_count = len(nodes_of_type(page, "Service"))
    if unsupported and service_count:
        errors.append(f"unsupported page Service count={service_count}")
    if not unsupported and service_count != 1:
        errors.append(f"supported page Service count={service_count}")
    if nodes_of_type(page, "Offer"):
        errors.append("top-level Offer is forbidden")
    if unsupported and not re.search(r"미기재|기재되어 있지|확인되지|제공되지|상담.*확인", strip_tags(page.text)):
        errors.append("unsupported disclosure cue missing")
    article_nodes = nodes_of_type(page, "Article")
    if len(article_nodes) != 1:
        errors.append(f"Article count={len(article_nodes)}")
    else:
        article = article_nodes[0]
        if article.get("headline") != h1 or article.get("description") != description:
            errors.append("Article headline/description parity")
        if article.get("datePublished") != RELEASE_DATE or article.get("dateModified") != RELEASE_DATE:
            errors.append(f"Article dates={(article.get('datePublished'), article.get('dateModified'))}")
        if article.get("author") != {"@id": f"{DOMAIN}/#organization"} or article.get("publisher") != {"@id": f"{DOMAIN}/#organization"}:
            errors.append("Article root author/publisher references")
        if unsupported and "educationalLevel" in article:
            errors.append("unsupported Article educationalLevel")
        if unsupported and any(
            key in article for key in ("audience", "mainEntity", "provider", "serviceType", "offers")
        ):
            errors.append("unsupported Article service/audience claim")
        if not unsupported and not article.get("educationalLevel"):
            errors.append("supported Article educationalLevel missing")
        headings = visible_article_headings(page)
        article_sections = article.get("articleSection")
        has_part = article.get("hasPart")
        part_names = (
            [clean(str(item.get("name", ""))) for item in has_part if isinstance(item, dict)]
            if isinstance(has_part, list)
            else []
        )
        if not headings or article_sections != headings or part_names != headings:
            errors.append(
                f"Article visible section parity headings={headings} articleSection={article_sections} hasPart={part_names}"
            )
    webpage_nodes = nodes_of_type(page, "WebPage")
    if len(webpage_nodes) != 1 or (
        webpage_nodes[0].get("name") != h1
        or webpage_nodes[0].get("description") != description
        or normalize_route(str(webpage_nodes[0].get("url", ""))) != expected_route
    ):
        errors.append("WebPage title/description/url parity")
    faq_nodes = nodes_of_type(page, "FAQPage")
    schema_faq = schema_faq_pairs(page)
    if len(faq_nodes) != 1 or len(schema_faq) != 4:
        errors.append("FAQPage mainEntity missing")
    visible_faq = [
        item for item in page.parsed.details
        if "grade-faq-item" in classes(item)
    ]
    if len(visible_faq) != 4 or [item.get("data-faq-topic") for item in visible_faq] != ["grade", "schools", "location", "fee"]:
        errors.append("visible FAQ four-slot contract")
    visible_pairs = visible_faq_pairs(page)
    if len(visible_pairs) != 4 or [topic for topic, _, _ in visible_pairs] != ["grade", "schools", "location", "fee"]:
        errors.append("visible FAQ question/answer parse contract")
    elif [(question, answer) for _, question, answer in visible_pairs] != schema_faq:
        errors.append("visible FAQ/FAQPage exact parity")
    if unsupported and (
        visible_faq[0].get("data-source-status") if visible_faq else None
    ) != "unconfirmed-grade":
        errors.append("unsupported FAQ grade marker")
    if not unsupported and any(item.get("data-source-status") == "unconfirmed-grade" for item in visible_faq):
        errors.append("supported FAQ unexpected marker")
    guides = visible_location_guides(page)
    if len(guides) > 1:
        errors.append(f"location guide cardinality={len(guides)}")
    if any(TERMINAL_COMMA_RE.search(value) for value in guides):
        errors.append(f"location guide terminal comma={guides}")
    repeated = sorted(set(match.group(0) for match in ADJACENT_KOREAN_TOKEN_RE.finditer(rendered_authored_text(page))))
    if repeated:
        errors.append(f"adjacent repeated Korean token={repeated[:8]}")
    repeated_headings: list[dict[str, Any]] = []
    for heading in visible_main_h2(page):
        duplicated = repeated_heading_tokens(heading)
        if duplicated:
            repeated_headings.append({"heading": heading, "tokens": duplicated})
    if repeated_headings:
        errors.append(f"repeated Korean token within H2={repeated_headings[:4]}")
    errors.extend(detail_image_contract(root, page))
    required_links = {
        f"/{PARENT}/",
        f"/{PARENT}/{category}/",
    }
    page_links = set(resolved_anchor_routes(page))
    if not required_links <= page_links:
        errors.append(f"required internal links missing={sorted(required_links - page_links)}")
    if errors:
        audit.errors.append(
            {
                "code": "new_detail_contract",
                "path": page.relative,
                "errors": errors[:12],
            }
        )
    return unsupported, errors


def audit_new_hub(page: Page, category: str, localities: Sequence[str], audit: Audit) -> None:
    errors: list[str] = []
    if len(page.parsed.mains) != 1 or "data-grade-directory" not in page.parsed.mains[0]:
        errors.append("main[data-grade-directory] != 1")
    if page.h1 != [category]:
        errors.append(f"H1={page.h1} expected={[category]}")
    if page.title != f"{category} | 영수학원" or page.og_title != [page.title] or page.twitter_title != [page.title]:
        errors.append(f"title/OG/Twitter mismatch title={page.title!r} og={page.og_title} twitter={page.twitter_title}")
    visible_bc = [re.sub(r"[\s/›>]+", "", "".join(chunks)) for chunks in page.parsed.breadcrumb_chunks]
    expected_visible = "".join(("홈", PARENT, category)).replace(" ", "")
    if visible_bc != [expected_visible]:
        errors.append(f"visible breadcrumb={visible_bc} expected={[expected_visible]}")
    if len(page.canonical) != 1 or normalize_route(page.canonical[0]) != f"/{PARENT}/{category}/":
        errors.append(f"canonical={page.canonical}")
    towns = [item for item in page.parsed.anchors if "data-subject-town" in item]
    if len(towns) != LOCALITY_COUNT:
        errors.append(f"town count={len(towns)}")
    if any(not clean(item.get("data-search") or "") for item in towns):
        errors.append("blank data-search")
    actual_routes = [
        normalize_route(item.get("href") or "", base_route=page.route) for item in towns
    ]
    expected_routes = [expected_detail_route(category, locality) for locality in localities]
    if set(actual_routes) != set(expected_routes) or len(set(actual_routes)) != LOCALITY_COUNT:
        errors.append(
            f"town route parity missing={len(set(expected_routes)-set(actual_routes))} "
            f"extra={len(set(actual_routes)-set(expected_routes))} unique={len(set(actual_routes))}"
        )
    search_inputs = [attrs for tag, attrs in page.parsed.starts if tag == "input" and "data-subject-search" in attrs]
    statuses = [attrs for _, attrs in page.parsed.starts if "data-subject-search-status" in attrs]
    resets = [attrs for _, attrs in page.parsed.starts if "data-subject-search-reset" in attrs]
    if len(search_inputs) != 1 or len(statuses) != 1 or len(resets) != 1:
        errors.append(f"search hooks input/status/reset={(len(search_inputs), len(statuses), len(resets))}")
    scripts = "\n".join(page.parsed.other_scripts)
    if not all(token in scripts for token in ("data-subject-search", "data-subject-town", "addEventListener")):
        errors.append("search runtime contract missing")
    types = types_for(page)
    required_types = {"CollectionPage", "BreadcrumbList", "ItemList"}
    if required_types - types:
        errors.append(f"missing schema types={sorted(required_types-types)}")
    itemlists = nodes_of_type(page, "ItemList")
    matching = [node for node in itemlists if node.get("numberOfItems") == LOCALITY_COUNT]
    if len(matching) != 1 or len(matching[0].get("itemListElement", [])) != LOCALITY_COUNT:
        errors.append("ItemList 371 contract")
    structured = schema_breadcrumb(page)
    if structured is None or len(structured) != 3:
        errors.append(f"schema breadcrumb count={None if structured is None else len(structured)}")
    else:
        names = [clean(str(item.get("name", ""))).replace(" ", "") for item in structured]
        routes = [normalize_route(str(item.get("item", ""))) for item in structured]
        if names != ["홈", PARENT, category] or routes != ["/", f"/{PARENT}/", f"/{PARENT}/{category}/"]:
            errors.append(f"schema breadcrumb names/routes={names}/{routes}")
    if errors:
        audit.errors.append({"code": "new_hub_contract", "path": page.relative, "errors": errors[:12]})


def strict_release_audit(
    root: Path,
    pages: Mapping[str, Page],
    overrides: Mapping[str, bytes],
    localities: Sequence[str],
    audit: Audit,
) -> list[dict[str, Any]]:
    audit.hard(len(pages) == RELEASE_PAGE_COUNT, "release_page_count", {"expected": RELEASE_PAGE_COUNT, "actual": len(pages)})
    release_sitemap_rows = sitemap_rows(virtual_bytes(root, "sitemap.xml", overrides))
    release_sitemap_by_route = {row[0]: row for row in release_sitemap_rows}
    expected_target_routes = {
        f"/{PARENT}/{category}/"
        for category in NEW_CATEGORIES
    } | {
        expected_detail_route(category, locality)
        for category in NEW_CATEGORIES
        for locality in localities
    }
    target_sitemap_rows = [release_sitemap_by_route.get(route) for route in expected_target_routes]
    audit.hard(
        all(row is not None and row[1] == RELEASE_DATE for row in target_sitemap_rows),
        "new_sitemap_freshness",
        {
            "expected_routes": len(expected_target_routes),
            "present": sum(row is not None for row in target_sitemap_rows),
            "wrong_lastmod": sum(row is not None and row[1] != RELEASE_DATE for row in target_sitemap_rows),
        },
    )
    parent_sitemap = release_sitemap_by_route.get(f"/{PARENT}/")
    audit.hard(
        parent_sitemap is not None and parent_sitemap[1] == RELEASE_DATE,
        "parent_sitemap_freshness",
        parent_sitemap,
    )
    browser_cases: list[dict[str, Any]] = []
    target_titles: list[str] = []
    target_descriptions: list[str] = []
    physical_definitions: dict[str, set[str]] = defaultdict(set)
    category_metrics: dict[str, Any] = {}
    for category in NEW_CATEGORIES:
        hub_relative = f"{PARENT}/{category}/index.html"
        detail_relatives = [f"{PARENT}/{category}/{locality}/index.html" for locality in localities]
        present = [relative for relative in detail_relatives if relative in pages]
        audit.hard(
            len(present) == LOCALITY_COUNT,
            "new_category_detail_count",
            {"category": category, "expected": LOCALITY_COUNT, "actual": len(present), "missing": [x for x in detail_relatives if x not in pages][:5]},
        )
        if hub_relative not in pages:
            audit.hard(False, "new_category_hub_missing", hub_relative)
            category_metrics[category] = {"details": len(present), "supported": 0, "unsupported": 0}
            continue
        hub = pages[hub_relative]
        audit_new_hub(hub, category, localities, audit)
        browser_cases.append({"kind": "hub", "category": category, "path": hub.route})
        supported_pages: list[Page] = []
        unsupported_pages: list[Page] = []
        for relative in present:
            page = pages[relative]
            unsupported, _ = audit_new_detail(root, page, category, PurePosixPath(relative).parent.name, audit)
            (unsupported_pages if unsupported else supported_pages).append(page)
            target_titles.append(page.title)
            if page.description:
                target_descriptions.append(page.description[0])
            organizations = [
                node for node in top_level_nodes(page)
                if "EducationalOrganization" in node_types(node) or "LocalBusiness" in node_types(node)
            ]
            if len(organizations) == 1:
                identifier = str(organizations[0].get("@id", ""))
                physical_definitions[identifier].add(
                    json.dumps(organizations[0], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                )
        audit.hard(bool(supported_pages), "supported_sample_missing", category)
        audit.hard(bool(unsupported_pages), "unsupported_sample_missing", category)
        audit.hard(
            (len(supported_pages), len(unsupported_pages)) == EXPECTED_SOURCE_STATUS[category],
            "source_status_counts",
            {
                "category": category,
                "expected": EXPECTED_SOURCE_STATUS[category],
                "actual": (len(supported_pages), len(unsupported_pages)),
            },
        )
        if supported_pages:
            browser_cases.append(
                {"kind": "detail", "category": category, "state": "supported", "path": supported_pages[0].route}
            )
        if unsupported_pages:
            browser_cases.append(
                {"kind": "detail", "category": category, "state": "unsupported", "path": unsupported_pages[0].route}
            )
        category_metrics[category] = {
            "details": len(present),
            "supported": len(supported_pages),
            "unsupported": len(unsupported_pages),
            "hub_towns": len([x for x in hub.parsed.anchors if "data-subject-town" in x]),
        }
    audit.hard(
        len(target_titles) == len(set(target_titles)),
        "new_detail_title_duplicates",
        len(target_titles) - len(set(target_titles)),
    )
    audit.hard(
        len(target_descriptions) == len(set(target_descriptions)),
        "new_detail_description_duplicates",
        len(target_descriptions) - len(set(target_descriptions)),
    )
    audit.hard(
        len(physical_definitions) == 188,
        "physical_entity_count",
        {"expected": 188, "actual": len(physical_definitions)},
    )
    drift = {identifier: len(values) for identifier, values in physical_definitions.items() if len(values) != 1}
    audit.hard(not drift, "physical_entity_definition_drift", dict(list(drift.items())[:8]))
    parent_relative = f"{PARENT}/index.html"
    if parent_relative in pages:
        parent_page = pages[parent_relative]
        links = Counter(resolved_anchor_routes(parent_page))
        expected = [f"/{PARENT}/{category}/" for category in ALL_SUBJECT_CATEGORIES]
        bad = {route: links[route] for route in expected if links[route] != 1}
        audit.hard(not bad, "parent_hub_category_links", bad)
        itemlists = nodes_of_type(parent_page, "ItemList")
        category_items = [
            node for node in itemlists
            if isinstance(node.get("itemListElement"), list) and len(node["itemListElement"]) == len(ALL_SUBJECT_CATEGORIES)
        ]
        audit.hard(len(category_items) == 1, "parent_hub_schema_categories", len(category_items))
    else:
        audit.hard(False, "parent_hub_missing", parent_relative)
    llms = virtual_bytes(root, "llms.txt", overrides).decode("utf-8")
    llms_routes = {
        normalize_route(value)
        for value in re.findall(r"https?://[^\s)>]+", llms)
    }
    expected_hubs = {f"/{PARENT}/{category}/" for category in NEW_CATEGORIES}
    audit.hard(expected_hubs <= llms_routes, "llms_new_hubs", sorted(expected_hubs - llms_routes))
    audit.observations["new_categories"] = category_metrics
    audit.observations["browser_contract"] = {
        "detail_cases": sum(case["kind"] == "detail" for case in browser_cases),
        "hub_cases": sum(case["kind"] == "hub" for case in browser_cases),
        "widths": list(BROWSER_WIDTHS),
        "detail_tests": sum(case["kind"] == "detail" for case in browser_cases) * len(BROWSER_WIDTHS),
        "hub_tests": sum(case["kind"] == "hub" for case in browser_cases) * len(BROWSER_WIDTHS),
    }
    return browser_cases


def find_node_path(root: Path) -> str:
    configured = os.environ.get("NODE_PATH", "")
    if configured:
        return configured
    candidates = [root / "node_modules", root.parent / "node_modules"]
    candidates.extend(
        path / "node_modules"
        for path in sorted(root.parent.iterdir(), key=lambda value: value.name)
        if path.is_dir() and path.name not in PRUNED_DIRS
    )
    for candidate in candidates:
        if (candidate / "playwright").is_dir():
            return str(candidate)
    return ""


def run_browser(root: Path, base: str, cases: Sequence[Mapping[str, Any]], timeout: int) -> dict[str, Any]:
    script = r'''
const { chromium } = require('playwright');
const base = process.argv[2].replace(/\/$/, '');
const production = process.argv[3].replace(/\/$/, '');
const cases = JSON.parse(process.argv[4]);
const widths = JSON.parse(process.argv[5]);
(async()=>{
 const browser=await chromium.launch({headless:true}); const rows=[];
 for(const width of widths){
  const context=await browser.newContext({viewport:{width,height:900},locale:'ko-KR'});
  for(const testCase of cases){
   const page=await context.newPage(); const errors=[]; const network=[]; const imageRequests=[];
   page.on('pageerror',e=>errors.push(e.message));
   page.on('console',m=>m.type()==='error'&&errors.push(m.text()));
   page.on('requestfailed',r=>network.push(`failed ${r.url()}`));
   page.on('response',r=>r.status()>=400&&network.push(`${r.status()} ${r.url()}`));
   page.on('request',r=>r.resourceType()==='image'&&imageRequests.push(r.url()));
   let response=null;
   try{response=await page.goto(base+testCase.path,{waitUntil:'networkidle',timeout:30000});}
   catch(e){errors.push(String(e));}
   const search={initial:null,query:null,reset:null,status:'',resetStatus:'',value:null,focused:false};
    if(testCase.kind==='hub'){
    const input=page.locator('[data-subject-search]');
    search.initial=await page.locator('[data-subject-town]:not([hidden])').count();
    if(await input.count()===1){
     await input.fill('명일동'); await page.waitForTimeout(80);
     search.query=await page.locator('[data-subject-town]:not([hidden])').count();
     search.status=await page.locator('[data-subject-search-status]').innerText().catch(()=> '');
     const reset=page.locator('[data-subject-search-reset]');
     if(await reset.count()===1) await reset.click(); else await input.fill('');
     await page.waitForTimeout(80);
     search.reset=await page.locator('[data-subject-town]:not([hidden])').count();
     search.resetStatus=await page.locator('[data-subject-search-status]').innerText().catch(()=> '');
     search.value=await input.inputValue();
      search.focused=await input.evaluate(node=>document.activeElement===node);
     }
    }
    if(testCase.kind==='detail'){
     const lazyMap=page.locator('img[src*="/maps/"]');
     if(await lazyMap.count()===1) await lazyMap.scrollIntoViewIfNeeded();
    }
    await page.evaluate(async()=>{
    const visible=[...document.images].filter(img=>{const s=getComputedStyle(img);return s.display!=='none'&&s.visibility!=='hidden'});
    await Promise.race([Promise.all(visible.map(img=>img.complete?Promise.resolve():new Promise(resolve=>{
      img.addEventListener('load',resolve,{once:true});img.addEventListener('error',resolve,{once:true});
    }))),new Promise(resolve=>setTimeout(resolve,3000))]);
   });
   const dom=await page.evaluate(()=>{
    const images=[...document.images].map(img=>{const s=getComputedStyle(img);return {
      src:img.getAttribute('src')||'',hidden:img.hidden||s.display==='none'||s.visibility==='hidden',
      complete:img.complete,naturalWidth:img.naturalWidth,naturalHeight:img.naturalHeight,
      width:Number(img.getAttribute('width')),height:Number(img.getAttribute('height')),
      loading:img.getAttribute('loading'),decoding:img.getAttribute('decoding'),fetchpriority:img.getAttribute('fetchpriority')
    }});
    return {h1:document.querySelectorAll('h1').length,canonical:document.querySelector('link[rel="canonical"]')?.href||'',
      noindex:/noindex/i.test(document.querySelector('meta[name="robots"]')?.content||''),
      overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth+1,
      marker:document.querySelector('main[data-grade-page]')?.getAttribute('data-source-status')||'',
      gradeMain:document.querySelectorAll('main[data-grade-page]').length,
      gradeDirectory:document.querySelectorAll('main[data-grade-directory]').length,images};
   });
   const visible=dom.images.filter(x=>!x.hidden); const rep=dom.images.filter(x=>x.src.includes('/representative/'));
   const body=visible.filter(x=>!x.src.includes('/maps/')); const map=visible.filter(x=>x.src.includes('/maps/'));
   const ratioMismatch=(x)=>!x||!x.width||!x.height||!x.naturalWidth||!x.naturalHeight||
     Math.abs((x.width/x.height)-(x.naturalWidth/x.naturalHeight))>0.002;
   const imageBad=testCase.kind==='detail'&&(
     dom.images.length!==2||visible.length!==2||rep.length!==0||body.length!==1||map.length!==1||
     visible.some(x=>!x.complete||!x.naturalWidth||!x.width||!x.height)||ratioMismatch(body[0])||ratioMismatch(map[0])||
     body[0]?.decoding!=='async'||body[0]?.fetchpriority!=='high'||body[0]?.loading!=='eager'||
     map[0]?.decoding!=='async'||map[0]?.loading!=='lazy'||map[0]?.fetchpriority!==null||
     imageRequests.some(url=>url.includes('/representative/')));
   const canonicalMatch=(()=>{try{return decodeURI(dom.canonical)===decodeURI(production+testCase.path)}catch{return false}})();
   const bad=response?.status()!==200||errors.length||network.length||dom.h1!==1||dom.noindex||dom.overflow||
     !canonicalMatch||imageBad||
     (testCase.kind==='detail'&&(dom.gradeMain!==1||(testCase.state==='unsupported'?(dom.marker!=='unconfirmed-grade'):(dom.marker!==''))))||
     (testCase.kind==='hub'&&(dom.gradeDirectory!==1||search.initial!==371||search.query!==1||search.reset!==371||
       !search.status||!search.resetStatus||search.value!==''||!search.focused));
   rows.push({width,...testCase,status:response&&response.status(),errors,network,imageRequests,search,dom,canonicalMatch,imageBad,bad});
   await page.close();
  }
  await context.close();
 }
 await browser.close();
 const bad=rows.filter(x=>x.bad);
 process.stdout.write(JSON.stringify({tests:rows.length,failures:bad.length,bad:bad.slice(0,12),rows}));
})().catch(e=>{process.stderr.write(String(e));process.exit(2)});
'''
    environment = os.environ.copy()
    node_path = find_node_path(root)
    if node_path:
        environment["NODE_PATH"] = node_path
    try:
        result = subprocess.run(
            [
                "node", "-", base.rstrip("/"), DOMAIN,
                json.dumps(list(cases), ensure_ascii=False), json.dumps(BROWSER_WIDTHS),
            ],
            input=script,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=environment,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"tests": 0, "failures": 1, "error": "browser timeout"}
    if result.returncode:
        return {"tests": 0, "failures": 1, "returncode": result.returncode, "error": result.stderr[-2000:]}
    try:
        return json.loads(result.stdout)
    except Exception as exc:  # noqa: BLE001
        return {"tests": 0, "failures": 1, "error": f"invalid browser JSON: {exc}: {result.stdout[-1000:]}"}


def self_tests() -> list[str]:
    errors: list[str] = []
    if normalize_route("../index.html", base_route=f"/{PARENT}/x/") != f"/{PARENT}/":
        errors.append("relative index resolution")
    encoded = "/%EA%B3%BC%EB%AA%A9%EB%B3%84%ED%95%99%EC%9B%90/"
    if normalize_route(encoded) != f"/{PARENT}/":
        errors.append("percent-decoded route")
    synthetic = '''<!doctype html><html><head><title>x</title><meta name="description" content="y"><link rel="canonical" href="https://xn--9p4bn5e1r987b.com/"><meta property="og:url" content="https://xn--9p4bn5e1r987b.com/"><script type="application/ld+json">{"@context":"https://schema.org","@type":"WebPage"}</script></head><body><main data-grade-page><p class="breadcrumb"><a href="/">홈</a></p><h1>x</h1><img src="/a.gif"></main></body></html>'''.encode("utf-8")
    page = parse_page("index.html", synthetic)
    if page.h1 != ["x"] or page.route != "/" or len(page.parsed.images) != 1 or page.json_errors:
        errors.append("HTML inventory")
    guide = parse_page(
        "index.html",
        synthetic.replace(b'<h1>x</h1>', b'<h1>x</h1><p data-source-field="location-guide">guide,</p>'),
    )
    if visible_location_guides(guide) != ["guide,"] or not TERMINAL_COMMA_RE.search("guide,"):
        errors.append("location-guide terminal punctuation")
    if not FORBIDDEN_CONTROL_RE.search("x\x08y") or FORBIDDEN_CONTROL_RE.search("x\r\n\ty"):
        errors.append("forbidden control-character detector")
    if not ADJACENT_KOREAN_TOKEN_RE.search("오답 기록 기록 확인") or ADJACENT_KOREAN_TOKEN_RE.search("오답 기록표 확인"):
        errors.append("adjacent Korean-token detector")
    if repeated_heading_tokens("상담 자료를 비교한 뒤 상담 질문 정리") != ["상담"]:
        errors.append("repeated H2 token detector")
    return errors


def audit_site(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    audit = Audit()
    started = time.monotonic()
    fact_auditor = root / APPROVED_FACT_AUDITOR_RELATIVE
    fact_digest = sha256(fact_auditor.read_bytes()) if fact_auditor.is_file() else None
    audit.hard(
        fact_digest == APPROVED_FACT_AUDITOR_SHA256,
        "approved_fact_auditor_pin",
        {
            "path": APPROVED_FACT_AUDITOR_RELATIVE,
            "expected_sha256": APPROVED_FACT_AUDITOR_SHA256,
            "actual_sha256": fact_digest,
        },
    )
    test_errors = self_tests()
    audit.group("semantic_self_test", test_errors)
    localities = localities_from_baseline(root)
    audit.hard(
        len(localities) == LOCALITY_COUNT and len(set(localities)) == LOCALITY_COUNT,
        "baseline_localities",
        {"expected": LOCALITY_COUNT, "actual": len(localities), "unique": len(set(localities))},
    )
    overrides: dict[str, bytes] = {}
    projection_failed = False
    if args.projection_script:
        script_path = args.projection_script
        if not script_path.is_absolute():
            script_path = root / script_path
        audit.hard(script_path.is_file(), "projection_script_missing", str(script_path))
        projection_failed = not script_path.is_file()
        if script_path.is_file():
            try:
                overrides = projection_overrides(root, script_path.resolve(), localities, audit)
                projection_failed = not overrides
            except Exception as exc:  # noqa: BLE001
                projection_failed = True
                audit.hard(False, "projection_exception", f"{type(exc).__name__}: {exc}")
    relatives = discover_pages(root, overrides)
    pages: dict[str, Page] = {}
    decode_errors: list[Any] = []
    for relative in relatives:
        try:
            pages[relative] = parse_page(relative, virtual_bytes(root, relative, overrides))
        except Exception as exc:  # noqa: BLE001
            decode_errors.append({"path": relative, "error": str(exc)})
    audit.group("html_parse", decode_errors)
    static_global_audit(root, pages, overrides, audit)
    expected_count = (
        BASELINE_PAGE_COUNT
        if args.baseline_only or projection_failed
        else RELEASE_PAGE_COUNT
    )
    audit.hard(len(pages) == expected_count, "mode_page_count", {"expected": expected_count, "actual": len(pages)})
    browser_cases: list[dict[str, Any]] = []
    if not args.baseline_only and not projection_failed:
        browser_cases = strict_release_audit(root, pages, overrides, localities, audit)
    browser_report: dict[str, Any] | None = None
    if not args.baseline_only and not args.projection_script and not overrides:
        audit.hard(
            bool(args.browser_base),
            "materialized_release_browser_required",
            "actual release requires --browser-base and the full 12-case × 3-width runtime gate",
        )
    if args.browser_base:
        audit.hard(not overrides, "browser_materialized_release", "browser is forbidden for an in-memory projection")
        if not overrides and not args.baseline_only:
            expected_cases = 12
            audit.hard(len(browser_cases) == expected_cases, "browser_case_inventory", {"expected": expected_cases, "actual": len(browser_cases)})
            browser_report = run_browser(root, args.browser_base, browser_cases, args.browser_timeout)
            audit.hard(browser_report.get("failures") == 0, "browser_contract", {k: v for k, v in browser_report.items() if k != "rows"})
    manifest = hashlib.sha256()
    for relative in sorted(pages):
        manifest.update(relative.encode("utf-8"))
        manifest.update(b"\0")
        manifest.update(sha256(pages[relative].raw).encode("ascii"))
        manifest.update(b"\n")
    result = {
        "ok": not audit.errors,
        "mode": (
            "baseline" if args.baseline_only
            else "projection-failed" if projection_failed
            else "projected-release" if overrides
            else "actual-release"
        ),
        "root": str(root),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "error_count": len(audit.errors),
        "errors": audit.errors[: args.max_errors],
        "observations": audit.observations,
        "release_manifest_sha256": manifest.hexdigest(),
        "git_status_sha256": sha256(git_status(root).encode("utf-8")),
        "browser": browser_report,
    }
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Read-only 영수학원 고1·고2 category release auditor")
    value.add_argument("--root", type=Path, default=ROOT)
    value.add_argument("--baseline-only", action="store_true", help="validate the current 2,609-page baseline")
    value.add_argument("--projection-script", type=Path, help="pure generator exposing build_plan(root)")
    value.add_argument("--browser-base", help="materialized local/preview/live base URL")
    value.add_argument("--browser-timeout", type=int, default=300_000)
    value.add_argument("--json", action="store_true")
    value.add_argument("--max-errors", type=int, default=100)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.baseline_only and args.projection_script:
        raise SystemExit("--baseline-only and --projection-script are mutually exclusive")
    result = audit_site(args)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"{'PASS' if result['ok'] else 'HOLD'} mode={result['mode']} "
            f"errors={result['error_count']} manifest={result['release_manifest_sha256']}"
        )
        for error in result["errors"]:
            print(json.dumps(error, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
