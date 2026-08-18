"""Independent read-only release audit for the four high-school grade routes.

This auditor deliberately does not import any of the older page generators or
validators.  It re-derives its facts from the authoritative CSV and manuscript
archives, then checks either the materialized tree or a generator ``build_plan``
projection entirely in memory.  It never writes repository files.

The audited release adds these categories to 영수학원.com:

* 고2수학학원
* 고2영어학원
* 고1수학학원
* 고1영어학원

Run without ``--projected-content-script`` to audit the current tree.  Pass the
frozen generator to validate its 1,491-document projection before applying it.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import importlib.util
import inspect
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Iterator, Mapping, Sequence

from PIL import Image


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT.parent / "참고자료" / "사용한 원고" / "영수학원.com 추가 원고"
COMMON_DIR = ROOT.parent / "참고자료" / "공통자료"
BASE_URL = "https://xn--9p4bn5e1r987b.com"
ROOT_ORG_ID = f"{BASE_URL}/#organization"
RELEASE_DATE = "2026-08-18"

EXPECTED_SOURCE_ROWS = 371
EXPECTED_PHYSICAL = 188
EXPECTED_EXISTING_URLS = 2609
EXPECTED_NEW_DETAILS = 1484
EXPECTED_NEW_HUBS = 4
EXPECTED_FINAL_URLS = 4097
EXPECTED_PLAN_DOCUMENTS = 1491
EXPECTED_SUPPORTED = 1373
EXPECTED_UNSUPPORTED = 111

# These independently measured baselines protect every pre-existing page except
# the one explicitly extended subject hub, plus every asset and the source files.
BASELINE_EXISTING_HTML_COUNT = 2608
BASELINE_EXISTING_HTML_BYTES = 97_182_412
BASELINE_EXISTING_HTML_MANIFEST = (
    "afef881c31711fb351dc2783e96cc328d08f73273b05e89504b164a5c3d405a3"
)
BASELINE_ASSET_COUNT = 2239
BASELINE_ASSET_BYTES = 411_564_766
BASELINE_ASSET_MANIFEST = (
    "4c24be6de47485487098d7e4b0dd7143d45075d546697c8c20451676b8955d8e"
)
BASELINE_SITEMAP_SHA256 = (
    "6006d510928bab27e0841a08338af383369c12a8fcaadd1ec21b5ab0bd561c54"
)
BASELINE_OLD_SITEMAP_RECORD_MANIFEST = (
    "2ea59aa3e883092fd4b23180f6e75f48f0a7e29a48d105e6a7e85c8b3fb396f0"
)
BASELINE_NONPARENT_SITEMAP_RECORD_MANIFEST = (
    "3ad7a2af0031f56c9cd73386b962d520d10c1e62b0b8db0506caac8b7f2c3bdd"
)
BASELINE_ROBOTS_SHA256 = (
    "cc09b26589e6060c8ac60050a233ed560bcfc49ae45f9b77836c8b80dca6c2d6"
)
BASELINE_LLMS_SHA256 = (
    "97d5ddaba140199a4581514c270ea9cb7534bf3676a0a84a9bef08a9c7f05e59"
)
BASELINE_ROOT_SHA256 = (
    "8032824a614dbc1969193031ec04b3a6cbe7465650a8707a6a30f916a37a03b9"
)
BASELINE_PARENT_HUB_SHA256 = (
    "c4d6bf53530186c73737a963b73f513551b37c7826930729ac4b54e6be1d928b"
)
BASELINE_CENTER_CSV_SHA256 = (
    "3ffbd7b70273b6dc1c8435c53a3a25e32d2a173ba1bf51840654389bd8954e1a"
)
BASELINE_EDU_ORG_CSV_SHA256 = (
    "e44c9a78c8b272781d5c078e38b466f9d438127a76219661ff43ee2604766c22"
)

COMMON_FILE_SHA256 = {
    "센터정보 정리.csv": BASELINE_CENTER_CSV_SHA256,
    "EducationalOrganization.csv": BASELINE_EDU_ORG_CSV_SHA256,
    "FAQ.txt": "60887d65c26bef62129fdd7c858f602d0c75d6862255659c5c2d1843ce83f669",
    "상담방식.txt": "d0bce32967e3802c2eb5a3191f91f7fb8479ffb6abba0e1832b9896abe49ef10",
    "센터 정보 및 교육비 371개 코드.csv": "06787f04954a7e65dd64be1e0f10ccdd26652cd565aab2eb52c8412975dabe3f",
    "이미지링크.csv": "c1b4f87b2b62f659107dbf0a79a1d566e213e008fc4b7f30cfa656ffae814100",
    "타깃학교.csv": "08c73da41d47ed76bdfa318ff30c238cc12ba92a73b40e0ca2feacec9610ac0f",
    "학부모 후기.txt": "b64b65e0c35051ec041132aae484af129b6a38c5675076f0a736c415f27d11e2",
}

MANUSCRIPT_SHA256 = {
    "고1 수학학원.zip": "5fd763925514e50e0aa8c1caf1247d04c24944963a841201c6aa5e72c5df16c2",
    "고1 영어학원.zip": "a7935dde7ae4853fb20272913aa3a13d5537e070294185469148331aa5a04580",
    "고2 수학학원.zip": "a238c5555772d1a6eb6b7fb3f3c759b68c73ab0c4bfdb01a7d6dfc1838e878c6",
    "고2 영어학원.zip": "7eadf035911ae0ad5b626d122eac6dcf076817e78e808e38fb0c0531347c8629",
}

SOURCE_MARKERS = (
    "[페이지타이틀]",
    "[메타설명]",
    "[본문]",
    "[FAQ]",
    "[학부모후기]",
    "[JSON-LD 요약]",
)


@dataclass(frozen=True)
class Category:
    slug: str
    label: str
    grade: str
    subject: str
    zip_name: str
    supported_expected: int
    unsupported_expected: int

    @property
    def query_suffix(self) -> str:
        return f"{self.label}학원"

    @property
    def audience_label(self) -> str:
        number = "1" if self.grade == "고1" else "2"
        return f"고등학교 {number}학년 학생"


CATEGORIES = (
    Category("고1수학학원", "고1 수학", "고1", "수학", "고1 수학학원.zip", 354, 17),
    Category("고1영어학원", "고1 영어", "고1", "영어", "고1 영어학원.zip", 362, 9),
    Category("고2수학학원", "고2 수학", "고2", "수학", "고2 수학학원.zip", 325, 46),
    Category("고2영어학원", "고2 영어", "고2", "영어", "고2 영어학원.zip", 332, 39),
)
CATEGORY_BY_SLUG = {item.slug: item for item in CATEGORIES}

PARENT_HUB_ROUTE = "/과목별학원/"
NEW_ROUTE_PREFIXES = tuple(f"/과목별학원/{item.slug}/" for item in CATEGORIES)

PARENT_PROTECTED = {
    "title": "과목별학원 | 영수학원",
    "h1": "과목별학원",
    "canonical": f"{BASE_URL}/과목별학원/",
    "description": (
        "영수학원 과목별학원 허브입니다. 학년과 과목을 선택한 뒤 "
        "371개 동네별 학습관리 안내를 확인할 수 있습니다."
    ),
}

MAX_CROSS_DOCUMENT_FREQUENCY = 34
MAX_H2_FREQUENCY = 40
MAX_LOCALITY_MENTIONS = 12
MAX_EXACT_QUERY_MENTIONS = 3
MIN_AUTHORED_CHARS = 2000
MAX_AUTHORED_CHARS = 7500
MIN_H2 = 5
MAX_H2 = 8
MIN_META_CHARS = 50
MAX_META_CHARS = 160
MAX_EDITORIAL_SENTENCE_CHARS = 180

MISSING_CUE_RE = re.compile(
    r"(?:원자료|제공\s*자료|교육지원청\s*자료).{0,35}"
    r"(?:미기재|없(?:습니다|는\s*상태)|확인되지|제공되지|제공받지|누락)|"
    r"(?:미기재|확인되지|제공되지|제공받지|누락).{0,35}(?:원자료|제공\s*자료)|"
    r"미기재\s*상태|기재되어\s*있지",
    re.I,
)
GRADE_TOKEN_RE = re.compile(r"(?<![가-힣A-Za-z0-9])(?:초[1-6]|중[1-3]|고[1-3])(?![가-힣A-Za-z0-9])")
POSITIVE_GRADE_RE = re.compile(
    r"(?:고등학교\s*[12]학년|고[12]).{0,45}"
    r"(?:수업|지도|대상\s*학년|수업\s*가능|지원\s*대상|개설|모집|운영|등록)|"
    r"(?:수업|지도|대상\s*학년|수업\s*가능|지원\s*대상|개설|모집|운영|등록).{0,45}"
    r"(?:고등학교\s*[12]학년|고[12])",
    re.I,
)
NEGATIVE_GRADE_RE = re.compile(
    r"미기재|확인되지|제공되지|제공받지|기재(?:되어\s*있지|되지)|단정(?:할\s*수\s*없|하지)|"
    r"상담(?:에서|\s*전)\s*확인|확인(?:이|을)?\s*필요|확정(?:되지|할\s*수\s*없)|"
    r"확정해서는\s*안|개설\s*여부|실제\s*운영|가능\s*여부",
    re.I,
)
PHONE_VALUE_RE = re.compile(r"(?:\+82[-\s]?10|010)(?:[-\s]?\d){7,9}")

SEARCH_META_RE = re.compile(r"검색|(?<![A-Za-z])SEO(?![A-Za-z])|키워드", re.I)
IRRELEVANT_SEED_RE = re.compile(
    r"학원\s*(?:개원|창업|전자\s*계약|매니저|운영(?:자)?|재\s*등록|휴원|"
    r"개인\s*정보\s*관리|매출\s*관리|수납\s*관리|고객\s*관리|회원\s*관리|"
    r"문서\s*관리|데이터\s*관리|예약\s*관리|상담\s*관리|결제\s*관리|"
    r"미납\s*관리|관리\s*(?:프로그램|솔루션|앱)|출결\s*앱|직원|코디네이터|"
    r"데스크|행정|프로모션|이벤트|온라인\s*등록|문자\s*발송|알림\s*톡|"
    r"할인|혜택)|온라인\s*수업|참여형\s*수업|토론형\s*수업|학원\s*자습실",
    re.I,
)
STRONG_CLAIM_RE = re.compile(
    r"(?:합격|성적\s*상승|등급\s*상승).{0,25}(?:보장|확실)|"
    r"(?:보장|확실).{0,25}(?:합격|성적\s*상승|등급\s*상승)|"
    r"(?:무조건|반드시).{0,35}(?:오릅|향상|상승|합격)|100\s*%",
    re.I,
)
NEGATED_CLAIM_RE = re.compile(r"보장하지\s*않|보장할\s*수\s*없|단정하지\s*않|확정할\s*수\s*없")
FEE_AMOUNT_RE = re.compile(r"(?<![0-9])\d[\d,]*(?:\s*)(?:원|만원)(?![가-힣])")
KNOWN_BAD_COPY_RE = re.compile(
    r"고2(?:이|은|을)(?=\s)|영어(?:은|을)(?=\s)|수학(?:는|가|를)(?=\s)|"
    r"학교을|주소을|비용를|학년를|정보을|자료을|내용을\s*내용으로|기준을\s*기준으로"
)
ADJACENT_WORD_REPEAT_RE = re.compile(
    r"(?<![가-힣])([가-힣]{2,})\s+\1(?:은|는|이|가|을|를|과|와|의|도|만|에서|으로|로)?(?![가-힣])"
)

FAQ_TOPIC_RE = {
    "grade": re.compile(r"학년|고등학교\s*[12]학년|고[12]|대상"),
    "schools": re.compile(r"학교|고교|고등학교|내신\s*범위"),
    "location": re.compile(r"주소|위치|방문|오시는\s*길|출입|건물|주차"),
    "fee": re.compile(r"교습비|수강료|비용|학원비|금액|링크"),
}
FAQ_TOPICS = ("grade", "schools", "location", "fee")

SKIP_DIRS = {".git", "tmp", "__pycache__", "node_modules", ".vercel"}
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def normalized_literal(value: object) -> str:
    value = unicodedata.normalize("NFKC", clean(value)).casefold()
    return re.sub(r"[^0-9a-z가-힣]+", "", value)


def unique_order(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        value = clean(value)
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def manifest_entries(entries: Iterable[tuple[str, bytes]]) -> tuple[int, int, str]:
    hasher = hashlib.sha256()
    count = 0
    total = 0
    for relative, data in sorted(entries, key=lambda item: item[0]):
        key = relative.encode("utf-8")
        hasher.update(len(key).to_bytes(8, "big"))
        hasher.update(key)
        hasher.update(len(data).to_bytes(8, "big"))
        hasher.update(data)
        count += 1
        total += len(data)
    return count, total, hasher.hexdigest()


def record_manifest(records: Iterable[Sequence[str]]) -> str:
    hasher = hashlib.sha256()
    for record in records:
        for field_value in record:
            data = str(field_value).encode("utf-8")
            hasher.update(len(data).to_bytes(8, "big"))
            hasher.update(data)
    return hasher.hexdigest()


def iter_files_pruned(root: Path) -> Iterator[Path]:
    """Yield files without ever entering tmp or other excluded directories."""
    if not root.exists():
        return
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name not in SKIP_DIRS)
        base = Path(current)
        for name in sorted(files):
            yield base / name


def tree_manifest(root: Path, *, exclude: set[Path] | None = None) -> tuple[int, int, str]:
    excluded = {path.resolve() for path in (exclude or set())}
    entries: list[tuple[str, bytes]] = []
    for path in iter_files_pruned(root):
        if path.resolve() in excluded:
            continue
        entries.append((path.relative_to(root).as_posix(), path.read_bytes()))
    return manifest_entries(entries)


def asset_manifest(root: Path) -> tuple[int, int, str]:
    return manifest_entries(
        (path.relative_to(root).as_posix(), path.read_bytes())
        for path in iter_files_pruned(root / "assets")
    )


def decode_utf8(data: bytes, path: Path) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path}: invalid UTF-8: {exc}") from exc


def encode_like(value: object, before: bytes, path: Path) -> bytes:
    if isinstance(value, bytes):
        return value
    if not isinstance(value, str):
        raise TypeError(f"{path}: projected after must be str/bytes, got {type(value).__name__}")
    prefix = b"\xef\xbb\xbf" if before.startswith(b"\xef\xbb\xbf") else b""
    return prefix + value.encode("utf-8")


def slug_for(locality: str) -> str:
    return re.sub(r"\s+", "", clean(locality))


def url_key(value: str) -> str:
    parsed = urllib.parse.urlsplit(clean(value))
    scheme = (parsed.scheme or "https").lower()
    host = (parsed.hostname or "").lower()
    path = urllib.parse.unquote(parsed.path or "/")
    path = re.sub(r"/+", "/", path)
    if path.endswith("/index.html"):
        path = path[:-10]
    if not path.endswith("/") and "." not in Path(path).name:
        path += "/"
    quoted = urllib.parse.quote(path, safe="/-._~")
    return urllib.parse.urlunsplit((scheme, host, quoted, "", ""))


def route_for_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(clean(value))
    path = urllib.parse.unquote(parsed.path or "/")
    path = re.sub(r"/+", "/", path)
    if path.endswith("/index.html"):
        path = path[:-10]
    if not path.endswith("/") and "." not in Path(path).name:
        path += "/"
    return path


def page_path_for_route(root: Path, route: str) -> Path:
    route = urllib.parse.unquote(route).split("?", 1)[0].split("#", 1)[0]
    route = route.strip("/")
    if not route:
        return root / "index.html"
    if route.endswith("index.html"):
        return root / Path(route)
    return root / Path(route) / "index.html"


class Node:
    __slots__ = ("tag", "attrs", "parent", "children")

    def __init__(self, tag: str, attrs: Mapping[str, str], parent: Node | None = None):
        self.tag = tag.lower()
        self.attrs = {str(k).lower(): str(v or "") for k, v in attrs.items()}
        self.parent = parent
        self.children: list[Node | str] = []

    def descendants(self, tag: str | None = None) -> Iterator[Node]:
        for child in self.children:
            if not isinstance(child, Node):
                continue
            if tag is None or child.tag == tag:
                yield child
            yield from child.descendants(tag)

    def text(self) -> str:
        pieces: list[str] = []

        def walk(node: Node) -> None:
            for child in node.children:
                if isinstance(child, str):
                    pieces.append(child)
                elif child.tag not in {"script", "style", "template"}:
                    walk(child)

        walk(self)
        return clean(" ".join(pieces))

    def has_class(self, name: str) -> bool:
        return name in self.attrs.get("class", "").split()

    def find_all(
        self,
        tag: str | None = None,
        *,
        attr: str | None = None,
        value: str | None = None,
        cls: str | None = None,
    ) -> list[Node]:
        result: list[Node] = []
        for node in self.descendants(tag):
            if attr is not None and attr not in node.attrs:
                continue
            if attr is not None and value is not None and node.attrs.get(attr) != value:
                continue
            if cls is not None and not node.has_class(cls):
                continue
            result.append(node)
        return result

    def first(self, tag: str | None = None, **kwargs: str) -> Node | None:
        values = self.find_all(tag, **kwargs)
        return values[0] if values else None

    def direct_children(self, tag: str | None = None, cls: str | None = None) -> list[Node]:
        result = []
        for child in self.children:
            if not isinstance(child, Node):
                continue
            if tag is not None and child.tag != tag:
                continue
            if cls is not None and not child.has_class(cls):
                continue
            result.append(child)
        return result


class TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("document", {})
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {key: value or "" for key, value in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag.lower() not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def parse_html(value: str) -> Node:
    parser = TreeParser()
    parser.feed(value)
    parser.close()
    return parser.root


def raw_node_text(node: Node) -> str:
    pieces: list[str] = []

    def walk(current: Node) -> None:
        for child in current.children:
            if isinstance(child, str):
                pieces.append(child)
            else:
                walk(child)

    walk(node)
    return "".join(pieces)


def meta_value(dom: Node, *, name: str | None = None, prop: str | None = None) -> str:
    for node in dom.find_all("meta"):
        if name is not None and node.attrs.get("name", "").lower() == name.lower():
            return clean(node.attrs.get("content"))
        if prop is not None and node.attrs.get("property", "").lower() == prop.lower():
            return clean(node.attrs.get("content"))
    return ""


def canonical_value(dom: Node) -> str:
    for node in dom.find_all("link"):
        if "canonical" in node.attrs.get("rel", "").lower().split():
            return clean(node.attrs.get("href"))
    return ""


def json_graph(dom: Node) -> tuple[list[dict[str, Any]], list[Any]]:
    graph: list[dict[str, Any]] = []
    payloads: list[Any] = []
    for script in dom.find_all("script"):
        if script.attrs.get("type", "").lower() != "application/ld+json":
            continue
        raw = raw_node_text(script).strip()
        if not raw:
            raise ValueError("empty JSON-LD script")
        payload = json.loads(raw)
        payloads.append(payload)
        if isinstance(payload, dict) and isinstance(payload.get("@graph"), list):
            graph.extend(item for item in payload["@graph"] if isinstance(item, dict))
        elif isinstance(payload, list):
            graph.extend(item for item in payload if isinstance(item, dict))
        elif isinstance(payload, dict):
            graph.append(payload)
    return graph, payloads


def node_types(node: Mapping[str, Any]) -> set[str]:
    value = node.get("@type")
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {str(item) for item in value}
    return set()


def graph_nodes(graph: Sequence[dict[str, Any]], expected_type: str) -> list[dict[str, Any]]:
    return [node for node in graph if expected_type in node_types(node)]


def json_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            if key != "@context":
                yield from json_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from json_strings(child)


@dataclass(frozen=True)
class SourceRow:
    locality: str
    slug: str
    region: str
    city: str
    center_name: str
    fee_url: str
    registration_name: str
    registration_name_hash_source: str
    registration_number: str
    address: str
    address_hash_source: str
    guide_raw: str
    guide_clean: str
    high_schools_raw: str
    high_schools: tuple[str, ...]
    english_grades_raw: str
    english_grades: tuple[str, ...]
    math_grades_raw: str
    math_grades: tuple[str, ...]

    @property
    def physical_key(self) -> tuple[str, str]:
        return self.registration_name_hash_source, self.address_hash_source

    @property
    def physical_id(self) -> str:
        payload = f"{self.registration_name_hash_source}\0{self.address_hash_source}".encode("utf-8")
        token = hashlib.sha256(payload).hexdigest()[:20]
        return f"{BASE_URL}/센터/{token}/#organization"

    def grades(self, subject: str) -> tuple[str, ...]:
        return self.english_grades if subject == "영어" else self.math_grades

    def grades_raw(self, subject: str) -> str:
        return self.english_grades_raw if subject == "영어" else self.math_grades_raw


@dataclass(frozen=True)
class ManuscriptFact:
    locality: str
    raw: str
    sha256: str
    sections: Mapping[str, str]


@dataclass(frozen=True)
class PhysicalFact:
    key: tuple[str, str]
    physical_id: str
    center_name: str
    address: str
    areas: tuple[str, ...]
    english_grades: tuple[str, ...]
    math_grades: tuple[str, ...]
    source_region: str
    source_city: str
    address_region: str
    address_locality: str


def split_grades(value: str) -> tuple[str, ...]:
    return unique_order(part for part in re.split(r"[,/\s]+", clean(value)) if part)


def split_high_schools(value: str) -> tuple[str, ...]:
    raw = clean(value)
    if not raw or normalized_literal(raw) == normalized_literal("지역내 모든 고등학교 가능"):
        return ()
    return unique_order(part for part in re.split(r"[,/\.\s]+", raw) if part)


def clean_location_guide(raw: str) -> str:
    value = html.unescape(raw or "")
    value = re.sub(r"(?:https?://|www\.)[^\s<>()]+", " ", value, flags=re.I)
    value = re.sub(r"학원\s*위치\s*안내드립니다", " ", value)
    value = re.sub(r"\^{2,}", "", value)
    value = value.replace("엘레베이터", "엘리베이터")
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", value)
    value = re.sub(r"^[\s~\U0001F000-\U0001FAFF\u2600-\u27BF]+", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"^[~\s]+|[~\s]+$", "", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    value = re.sub(r",(?=\S)", ", ", value)
    value = re.sub(r",\s*$", "", value)
    value = re.sub(r"\(\s*\)", " ", value)
    return re.sub(r"\s+", " ", value).strip()


ADDRESS_REGION_ALIASES = {
    "서울": "서울특별시", "서울특별시": "서울특별시",
    "경기": "경기도", "경기도": "경기도",
    "인천": "인천광역시", "인천광역시": "인천광역시",
    "대전": "대전광역시", "대전광역시": "대전광역시",
    "충남": "충청남도", "충청남도": "충청남도",
    "충북": "충청북도", "충청북도": "충청북도",
    "대구": "대구광역시", "대구광역시": "대구광역시",
    "울산": "울산광역시", "울산광역시": "울산광역시",
    "부산": "부산광역시", "부산광역시": "부산광역시",
    "경남": "경상남도", "경상남도": "경상남도",
    "경북": "경상북도", "경상북도": "경상북도",
    "광주": "광주광역시", "광주광역시": "광주광역시",
    "전북특별자치도": "전북특별자치도", "전북": "전북특별자치도",
    "강원특별자치도": "강원특별자치도", "강원": "강원특별자치도",
    "제주특별자치도": "제주특별자치도", "제주": "제주특별자치도",
    "세종특별자치시": "세종특별자치시", "세종": "세종특별자치시",
}


def official_address_parts(address: str) -> tuple[str, str]:
    parts = clean(address).split()
    if not parts:
        return "", ""
    region = ADDRESS_REGION_ALIASES.get(parts[0], parts[0])
    if region == "세종특별자치시":
        return region, "새롬동"
    return region, parts[1] if len(parts) > 1 else ""


def load_sources(common_dir: Path) -> tuple[dict[str, SourceRow], dict[tuple[str, str], PhysicalFact], dict[str, Any]]:
    center_path = common_dir / "센터정보 정리.csv"
    if sha256_bytes(center_path.read_bytes()) != BASELINE_CENTER_CSV_SHA256:
        raise ValueError("authoritative center CSV SHA mismatch")
    with center_path.open("r", encoding="utf-8-sig", newline="") as handle:
        raw = list(csv.reader(handle))
    if len(raw) != EXPECTED_SOURCE_ROWS + 1 or len(raw[0]) != 20:
        raise ValueError(f"center CSV shape {len(raw) - 1}x{len(raw[0]) if raw else 0}")

    by_slug: dict[str, SourceRow] = {}
    group_rows: dict[tuple[str, str], list[SourceRow]] = defaultdict(list)
    for cells in raw[1:]:
        if len(cells) != 20:
            raise ValueError(f"center CSV row width {len(cells)}")
        row = SourceRow(
            locality=clean(cells[0]),
            slug=slug_for(cells[0]),
            region=clean(cells[2]),
            city=clean(cells[4]),
            center_name=clean(cells[6]),
            fee_url=clean(cells[7]),
            registration_name=clean(cells[8]),
            registration_name_hash_source=cells[8].strip(),
            registration_number=clean(cells[9]),
            address=clean(cells[10]),
            address_hash_source=cells[10].strip(),
            guide_raw=clean(cells[11]),
            guide_clean=clean_location_guide(cells[11]),
            high_schools_raw=clean(cells[14]),
            high_schools=split_high_schools(cells[14]),
            english_grades_raw=clean(cells[16]),
            english_grades=split_grades(cells[16]),
            math_grades_raw=clean(cells[17]),
            math_grades=split_grades(cells[17]),
        )
        if not all((row.locality, row.slug, row.center_name, row.registration_name, row.registration_number, row.address)):
            raise ValueError(f"required source field blank: {row.locality!r}")
        if row.slug in by_slug:
            raise ValueError(f"duplicate locality slug: {row.slug}")
        by_slug[row.slug] = row
        group_rows[row.physical_key].append(row)

    physical: dict[tuple[str, str], PhysicalFact] = {}
    for key, members in group_rows.items():
        center_names = unique_order(item.center_name for item in members)
        if len(center_names) != 1:
            raise ValueError(f"conflicting physical name {key!r}: {center_names!r}")
        source_regions = unique_order(item.region for item in members)
        source_cities = unique_order(item.city for item in members)
        if len(source_regions) != 1 or len(source_cities) != 1:
            raise ValueError(f"conflicting physical region/city {key!r}")
        region, locality = official_address_parts(members[0].address)
        physical[key] = PhysicalFact(
            key=key,
            physical_id=members[0].physical_id,
            center_name=center_names[0],
            address=members[0].address,
            areas=unique_order(item.locality for item in members),
            english_grades=unique_order(grade for item in members for grade in item.english_grades),
            math_grades=unique_order(grade for item in members for grade in item.math_grades),
            source_region=source_regions[0],
            source_city=source_cities[0],
            address_region=region,
            address_locality=locality,
        )

    metrics = {
        "rows": len(by_slug),
        "physical": len(physical),
        "blank_fee": sum(not row.fee_url for row in by_slug.values()),
        "blank_guide": sum(not row.guide_raw for row in by_slug.values()),
        "blank_high_schools": sum(not row.high_schools_raw for row in by_slug.values()),
        "generic_high_schools": sum(
            normalized_literal(row.high_schools_raw) == normalized_literal("지역내 모든 고등학교 가능")
            for row in by_slug.values()
        ),
        "blank_english_grades": sum(not row.english_grades for row in by_slug.values()),
        "blank_math_grades": sum(not row.math_grades for row in by_slug.values()),
    }
    return by_slug, physical, metrics


def validate_manuscripts(
    source_dir: Path, sources: Mapping[str, SourceRow]
) -> tuple[dict[str, Any], dict[str, dict[str, ManuscriptFact]]]:
    metrics: dict[str, Any] = {"archives": {}, "members": 0}
    facts: dict[str, dict[str, ManuscriptFact]] = {}
    expected_localities = {row.locality for row in sources.values()}
    for category in CATEGORIES:
        path = source_dir / category.zip_name
        archive_digest = sha256_bytes(path.read_bytes()) if path.is_file() else "missing"
        if archive_digest != MANUSCRIPT_SHA256[category.zip_name]:
            raise ValueError(f"manuscript SHA mismatch: {category.zip_name}: {archive_digest}")
        names: list[str] = []
        payload_hashes: set[str] = set()
        normalized_hashes: set[str] = set()
        bom_count = 0
        category_facts: dict[str, ManuscriptFact] = {}
        search_pages = 0
        search_occurrences = 0
        literal_search_pages = 0
        literal_search_occurrences = 0
        seed_pages = 0
        meta_over_160 = 0
        with zipfile.ZipFile(path) as archive:
            infos = [item for item in archive.infolist() if not item.is_dir()]
            if len(infos) != EXPECTED_SOURCE_ROWS:
                raise ValueError(f"{category.zip_name}: {len(infos)} members")
            for info in infos:
                member = info.filename.replace("\\", "/")
                if member.startswith("/") or ".." in Path(member).parts or not member.endswith(".txt"):
                    raise ValueError(f"unsafe manuscript member: {member}")
                data = archive.read(info)
                bom_count += data.startswith(b"\xef\xbb\xbf")
                text = decode_utf8(data, Path(member))
                if "\x00" in text or "\ufffd" in text or "\r" in text:
                    raise ValueError(f"invalid manuscript encoding/newline: {member}")
                positions = [text.find(marker) for marker in SOURCE_MARKERS]
                if any(pos < 0 for pos in positions) or positions != sorted(positions):
                    raise ValueError(f"manuscript marker contract: {member}")
                suffix = f" {category.query_suffix}.txt"
                if not Path(member).name.endswith(suffix):
                    raise ValueError(f"manuscript filename contract: {member}")
                locality = Path(member).name[: -len(suffix)]
                sections: dict[str, str] = {}
                for marker_index, marker in enumerate(SOURCE_MARKERS):
                    start = positions[marker_index] + len(marker)
                    end = positions[marker_index + 1] if marker_index + 1 < len(positions) else len(text)
                    section = clean(text[start:end])
                    if not section:
                        raise ValueError(f"blank manuscript section: {member}: {marker}")
                    sections[marker.strip("[]")] = section
                if sections["페이지타이틀"] != f"{locality} {category.query_suffix}":
                    raise ValueError(f"manuscript title mismatch: {member}")
                names.append(locality)
                member_digest = sha256_bytes(data)
                payload_hashes.add(member_digest)
                normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()
                normalized_hashes.add(sha256_bytes(normalized.encode("utf-8")))
                category_facts[locality] = ManuscriptFact(
                    locality, text, sha256_bytes(text.encode("utf-8")), sections
                )
                search_pages += bool(SEARCH_META_RE.search(text))
                search_occurrences += len(SEARCH_META_RE.findall(text))
                literal_search_pages += "검색" in text
                literal_search_occurrences += text.count("검색")
                seed_pages += bool(IRRELEVANT_SEED_RE.search(text))
                meta_over_160 += len(sections["메타설명"]) > MAX_META_CHARS
        if set(names) != expected_localities or len(names) != len(set(names)):
            raise ValueError(f"manuscript locality coverage: {category.zip_name}")
        if len(payload_hashes) != EXPECTED_SOURCE_ROWS or len(normalized_hashes) != EXPECTED_SOURCE_ROWS:
            raise ValueError(f"manuscript duplicate: {category.zip_name}")
        metrics["archives"][category.slug] = {
            "sha256": archive_digest,
            "members": len(names),
            "bom": bom_count,
            "exact_duplicates": len(names) - len(payload_hashes),
            "normalized_duplicates": len(names) - len(normalized_hashes),
            "search_pages": search_pages,
            "search_occurrences": search_occurrences,
            "literal_search_pages": literal_search_pages,
            "literal_search_occurrences": literal_search_occurrences,
            "irrelevant_seed_pages": seed_pages,
            "meta_over_160": meta_over_160,
        }
        metrics["members"] += len(names)
        facts[category.slug] = category_facts
    metrics["search_pages"] = sum(item["search_pages"] for item in metrics["archives"].values())
    metrics["search_occurrences"] = sum(item["search_occurrences"] for item in metrics["archives"].values())
    metrics["literal_search_pages"] = sum(item["literal_search_pages"] for item in metrics["archives"].values())
    metrics["literal_search_occurrences"] = sum(item["literal_search_occurrences"] for item in metrics["archives"].values())
    metrics["irrelevant_seed_pages"] = sum(item["irrelevant_seed_pages"] for item in metrics["archives"].values())
    metrics["meta_over_160"] = sum(item["meta_over_160"] for item in metrics["archives"].values())
    return metrics, facts


@dataclass
class Audit:
    errors: list[dict[str, str]] = field(default_factory=list)
    counts: Counter[str] = field(default_factory=Counter)
    samples_per_code: int = 5

    def check(self, condition: bool, code: str, detail: object = "") -> bool:
        if condition:
            return True
        self.counts[code] += 1
        if sum(item["code"] == code for item in self.errors) < self.samples_per_code:
            self.errors.append({"code": code, "detail": clean(detail)[:1000]})
        return False

    def add(self, code: str, detail: object = "") -> None:
        self.check(False, code, detail)


def import_script(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("high_grade_projected_generator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import projection script: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def expected_paths(root: Path, sources: Mapping[str, SourceRow]) -> tuple[set[Path], set[Path], set[Path]]:
    details = {
        (root / "과목별학원" / category.slug / row.slug / "index.html").resolve()
        for category in CATEGORIES for row in sources.values()
    }
    hubs = {(root / "과목별학원" / category.slug / "index.html").resolve() for category in CATEGORIES}
    authorized = details | hubs | {
        (root / "과목별학원" / "index.html").resolve(),
        (root / "sitemap.xml").resolve(),
        (root / "llms.txt").resolve(),
    }
    return details, hubs, authorized


def doc_bytes(doc: object, field_name: str, path: Path, before: bytes) -> bytes:
    if not hasattr(doc, field_name):
        raise AttributeError(f"{path}: projection document missing {field_name}")
    value = getattr(doc, field_name)
    if value is None and field_name == "before":
        return b""
    return encode_like(value, before, path)


def load_projection(
    script_path: Path | None,
    root: Path,
    source_dir: Path,
    common_dir: Path,
    authorized: set[Path],
    audit: Audit,
) -> tuple[dict[Path, bytes], dict[str, Any]]:
    if script_path is None:
        return {}, {"enabled": False, "documents": 0, "idempotent": None}
    script_path = script_path.resolve()
    audit.check(script_path.is_file(), "projection_script_missing", script_path)
    if not script_path.is_file():
        return {}, {"enabled": True, "documents": 0, "idempotent": False}

    before_repo = tree_manifest(root)
    before_source = tree_manifest(source_dir)
    before_common = tree_manifest(common_dir)
    module = import_script(script_path)
    build_plan = getattr(module, "build_plan", None)
    audit.check(callable(build_plan), "projection_build_plan_missing", script_path)
    if not callable(build_plan):
        return {}, {"enabled": True, "documents": 0, "idempotent": False}

    kwargs: dict[str, Any] = {"root": root, "source_dir": source_dir, "common_dir": common_dir}
    signature = inspect.signature(build_plan)
    kwargs = {key: value for key, value in kwargs.items() if key in signature.parameters}
    plan = build_plan(**kwargs)
    def resolve_plan_path(value: object) -> Path:
        candidate = Path(value)
        return (candidate if candidate.is_absolute() else root / candidate).resolve()

    documents = list(getattr(plan, "documents", ()))
    plan_paths = [resolve_plan_path(getattr(doc, "path")) for doc in documents]
    audit.check(len(documents) == EXPECTED_PLAN_DOCUMENTS, "projection_document_count", len(documents))
    audit.check(len(plan_paths) == len(set(plan_paths)), "projection_duplicate_path", len(plan_paths) - len(set(plan_paths)))
    declared = {resolve_plan_path(path) for path in getattr(plan, "authorized_paths", ())}
    audit.check(declared == authorized, "projection_authorized_paths", f"declared={len(declared)} expected={len(authorized)}")
    audit.check(set(plan_paths) == authorized, "projection_scope", f"docs={len(set(plan_paths))} expected={len(authorized)}")
    audit.check(bool(getattr(plan, "idempotent", False)), "projection_declared_idempotency", getattr(plan, "idempotent", None))

    overrides: dict[Path, bytes] = {}
    projection_sources = load_sources(common_dir)[0]
    for doc, path in zip(documents, plan_paths):
        disk = path.read_bytes() if path.is_file() else b""
        try:
            before = doc_bytes(doc, "before", path, disk)
            after = doc_bytes(doc, "after", path, before)
        except Exception as exc:
            audit.add("projection_document_shape", f"{path}: {exc}")
            continue
        audit.check(before == disk, "projection_stale_before", path.relative_to(root).as_posix())
        overrides[path] = after
        relative = path.relative_to(root).as_posix()
        parts = Path(relative).parts
        if len(parts) == 4 and parts[0] == "과목별학원" and parts[1] in CATEGORY_BY_SLUG:
            category = CATEGORY_BY_SLUG[parts[1]]
            audit.check(clean(getattr(doc, "role", "")) == "detail", "projection_detail_role", relative)
            audit.check(clean(getattr(doc, "category", "")) == category.slug, "projection_detail_category", relative)
            expected_locality = projection_sources.get(parts[2]).locality if parts[2] in projection_sources else ""
            audit.check(clean(getattr(doc, "locality", "")) == expected_locality, "projection_detail_locality", relative)
        elif len(parts) == 3 and parts[0] == "과목별학원" and parts[1] in CATEGORY_BY_SLUG:
            audit.check(clean(getattr(doc, "role", "")) == "hub", "projection_hub_role", relative)
            audit.check(clean(getattr(doc, "category", "")) == parts[1], "projection_hub_category", relative)
            audit.check(not clean(getattr(doc, "locality", "")), "projection_hub_locality", relative)
        else:
            expected_roles = {
                "과목별학원/index.html": "parent-hub",
                "sitemap.xml": "sitemap",
                "llms.txt": "llms",
            }
            if relative in expected_roles:
                audit.check(clean(getattr(doc, "role", "")) == expected_roles[relative],
                            "projection_nonpage_role", f"{relative}: {getattr(doc, 'role', '')}")
                audit.check(not clean(getattr(doc, "category", "")) and not clean(getattr(doc, "locality", "")),
                            "projection_nonpage_metadata", relative)

    second_pass = {"supported": False, "changes": None}
    if "current_overrides" in signature.parameters and len(overrides) == len(authorized):
        kwargs2 = dict(kwargs)
        kwargs2["current_overrides"] = overrides
        try:
            second = build_plan(**kwargs2)
            second_docs = list(getattr(second, "documents", ()))
            second_map: dict[Path, bytes] = {}
            for doc in second_docs:
                path = resolve_plan_path(getattr(doc, "path"))
                upstream = overrides.get(path, path.read_bytes() if path.is_file() else b"")
                try:
                    second_map[path] = doc_bytes(doc, "after", path, upstream)
                except Exception as exc:
                    audit.add("projection_second_document_shape", f"{path}: {exc}")
            second_pass = {
                "supported": True,
                "documents": len(second_docs),
                "changes": sum(second_map.get(path) != value for path, value in overrides.items()),
            }
            audit.check(set(second_map) == authorized, "projection_second_scope", len(second_map))
            audit.check(second_map == overrides, "projection_second_pass", second_pass["changes"])
            audit.check(bool(getattr(second, "idempotent", False)), "projection_second_declared_idempotency", None)
        except Exception as exc:
            second_pass = {"supported": True, "documents": 0, "changes": None, "error": f"{type(exc).__name__}: {exc}"}
            audit.add("projection_second_pass_exception", second_pass["error"])
    else:
        audit.add("projection_second_pass_api", "build_plan must accept current_overrides")

    audit.check(tree_manifest(root) == before_repo, "projection_wrote_repository", script_path)
    audit.check(tree_manifest(source_dir) == before_source, "projection_wrote_manuscripts", script_path)
    audit.check(tree_manifest(common_dir) == before_common, "projection_wrote_common", script_path)
    return overrides, {
        "enabled": True,
        "script": str(script_path),
        "script_sha256": sha256_bytes(script_path.read_bytes()),
        "documents": len(documents),
        "authorized": len(declared),
        "idempotent": bool(getattr(plan, "idempotent", False)),
        "second_pass": second_pass,
    }


def bytes_for(path: Path, overrides: Mapping[Path, bytes]) -> bytes:
    resolved = path.resolve()
    if resolved in overrides:
        return overrides[resolved]
    return path.read_bytes()


def exists_for(path: Path, overrides: Mapping[Path, bytes]) -> bool:
    resolved = path.resolve()
    return resolved in overrides or path.is_file()


@dataclass(frozen=True)
class SitemapRecord:
    loc: str
    lastmod: str
    changefreq: str
    priority: str

    def tuple(self) -> tuple[str, str, str, str]:
        return self.loc, self.lastmod, self.changefreq, self.priority


def parse_sitemap(data: bytes, audit: Audit) -> list[SitemapRecord]:
    try:
        root = ET.fromstring(data)
    except Exception as exc:
        audit.add("sitemap_xml", exc)
        return []
    records: list[SitemapRecord] = []
    for index, url_node in enumerate(root):
        if str(url_node.tag).rsplit("}", 1)[-1] != "url":
            audit.add("sitemap_non_url_child", f"{index}: {url_node.tag}")
            continue
        children: dict[str, list[str]] = defaultdict(list)
        for child in url_node:
            children[str(child.tag).rsplit("}", 1)[-1]].append(clean(child.text))
        audit.check(
            set(children) == {"loc", "lastmod", "changefreq", "priority"}
            and all(len(value) == 1 for value in children.values()),
            "sitemap_child_cardinality",
            f"{index}: {dict(children)}",
        )
        records.append(
            SitemapRecord(
                children.get("loc", [""])[0],
                children.get("lastmod", [""])[0],
                children.get("changefreq", [""])[0],
                children.get("priority", [""])[0],
            )
        )
    return records


def expected_new_records(sources: Mapping[str, SourceRow]) -> list[SitemapRecord]:
    result: list[SitemapRecord] = []
    for category in CATEGORIES:
        hub = f"{BASE_URL}/과목별학원/{category.slug}/"
        result.append(SitemapRecord(hub, RELEASE_DATE, "weekly", "0.8"))
        for source in sources.values():
            loc = f"{BASE_URL}/과목별학원/{category.slug}/{source.slug}/"
            result.append(SitemapRecord(loc, RELEASE_DATE, "monthly", "0.7"))
    return result


def is_new_route(route: str) -> bool:
    return any(route.startswith(prefix) for prefix in NEW_ROUTE_PREFIXES)


def audit_sitemap_and_immutability(
    root: Path,
    sources: Mapping[str, SourceRow],
    overrides: Mapping[Path, bytes],
    audit: Audit,
) -> tuple[list[SitemapRecord], set[str], dict[str, Any]]:
    sitemap_path = root / "sitemap.xml"
    sitemap_data = bytes_for(sitemap_path, overrides)
    records = parse_sitemap(sitemap_data, audit)
    for record in records:
        parsed = urllib.parse.urlsplit(record.loc)
        audit.check(
            parsed.scheme == "https"
            and parsed.hostname == urllib.parse.urlsplit(BASE_URL).hostname
            and not parsed.query and not parsed.fragment and parsed.path.endswith("/"),
            "sitemap_url_shape",
            record.loc,
        )
    expected_new = expected_new_records(sources)
    old_records = [record for record in records if not is_new_route(route_for_url(record.loc))]
    new_records = [record for record in records if is_new_route(route_for_url(record.loc))]

    audit.check(len(records) == EXPECTED_FINAL_URLS, "sitemap_url_count", len(records))
    keys = [url_key(record.loc) for record in records]
    audit.check(len(keys) == len(set(keys)), "sitemap_duplicate_url", len(keys) - len(set(keys)))
    audit.check(len(old_records) == EXPECTED_EXISTING_URLS, "sitemap_existing_count", len(old_records))
    audit.check(len(new_records) == EXPECTED_NEW_DETAILS + EXPECTED_NEW_HUBS, "sitemap_new_count", len(new_records))
    audit.check(
        all(not is_new_route(route_for_url(record.loc)) for record in records[:EXPECTED_EXISTING_URLS])
        and all(is_new_route(route_for_url(record.loc)) for record in records[EXPECTED_EXISTING_URLS:]),
        "sitemap_new_not_appended",
        f"total={len(records)}",
    )
    parent_records = [record for record in old_records if route_for_url(record.loc) == PARENT_HUB_ROUTE]
    nonparent_records = [record for record in old_records if route_for_url(record.loc) != PARENT_HUB_ROUTE]
    audit.check(len(parent_records) == 1, "sitemap_parent_record_count", len(parent_records))
    audit.check(
        record_manifest(record.tuple() for record in nonparent_records)
        == BASELINE_NONPARENT_SITEMAP_RECORD_MANIFEST,
        "sitemap_existing_records_changed",
        record_manifest(record.tuple() for record in nonparent_records),
    )
    if len(parent_records) == 1:
        parent = parent_records[0]
        audit.check(
            (parent.lastmod, parent.changefreq, parent.priority) == (RELEASE_DATE, "weekly", "0.9"),
            "sitemap_parent_freshness",
            parent.tuple(),
        )
    audit.check(
        [url_key(record.loc) for record in new_records]
        == [url_key(record.loc) for record in expected_new],
        "sitemap_new_order",
        f"actual={len(new_records)} expected={len(expected_new)}",
    )
    if len(new_records) == len(expected_new):
        for actual, expected in zip(new_records, expected_new):
            audit.check(
                actual.tuple()[1:] == expected.tuple()[1:],
                "sitemap_new_metadata",
                f"{actual.loc}: {actual.tuple()[1:]} != {expected.tuple()[1:]}",
            )

    # Reconstruct the immutable 2,608-page baseline only from old sitemap URLs;
    # this never enumerates tmp and works in both projected and applied states.
    existing_entries: list[tuple[str, bytes]] = []
    missing_existing = 0
    for record in old_records:
        route = route_for_url(record.loc)
        if route == PARENT_HUB_ROUTE:
            continue
        path = page_path_for_route(root, route)
        if not exists_for(path, overrides):
            missing_existing += 1
            continue
        existing_entries.append((path.relative_to(root).as_posix(), bytes_for(path, overrides)))
    existing_manifest = manifest_entries(existing_entries)
    audit.check(missing_existing == 0, "existing_page_missing", missing_existing)
    audit.check(existing_manifest[0] == BASELINE_EXISTING_HTML_COUNT, "existing_page_count", existing_manifest[0])
    audit.check(existing_manifest[1] == BASELINE_EXISTING_HTML_BYTES, "existing_page_bytes", existing_manifest[1])
    audit.check(existing_manifest[2] == BASELINE_EXISTING_HTML_MANIFEST, "existing_page_manifest", existing_manifest[2])

    assets = asset_manifest(root)
    audit.check(assets[0] == BASELINE_ASSET_COUNT, "asset_count", assets[0])
    audit.check(assets[1] == BASELINE_ASSET_BYTES, "asset_bytes", assets[1])
    audit.check(assets[2] == BASELINE_ASSET_MANIFEST, "asset_manifest", assets[2])
    audit.check(sha256_bytes((root / "robots.txt").read_bytes()) == BASELINE_ROBOTS_SHA256, "robots_changed", None)
    audit.check(sha256_bytes((root / "index.html").read_bytes()) == BASELINE_ROOT_SHA256, "root_page_changed", None)

    # Every sitemap URL must resolve to exactly one projected/materialized HTML.
    missing_paths = []
    for record in records:
        path = page_path_for_route(root, route_for_url(record.loc))
        if not exists_for(path, overrides):
            missing_paths.append(path.relative_to(root).as_posix())
    audit.check(not missing_paths, "sitemap_missing_html", f"{len(missing_paths)}: {missing_paths[:5]}")

    return records, set(keys), {
        "total": len(records),
        "unique": len(set(keys)),
        "existing": len(old_records),
        "new": len(new_records),
        "existing_manifest": {
            "count": existing_manifest[0], "bytes": existing_manifest[1], "sha256": existing_manifest[2]
        },
        "asset_manifest": {"count": assets[0], "bytes": assets[1], "sha256": assets[2]},
        "sitemap_sha256": sha256_bytes(sitemap_data),
        "old_record_manifest": record_manifest(record.tuple() for record in old_records),
        "nonparent_record_manifest": record_manifest(record.tuple() for record in nonparent_records),
    }


def audit_llms(root: Path, overrides: Mapping[Path, bytes], audit: Audit) -> dict[str, Any]:
    path = root / "llms.txt"
    data = bytes_for(path, overrides)
    text = decode_utf8(data, path)
    expected_urls = [f"{BASE_URL}/과목별학원/{category.slug}/" for category in CATEGORIES]
    lines = text.splitlines(keepends=True)
    matching_indexes: list[int] = []
    matching_lines: list[str] = []
    for index, line in enumerate(lines):
        if any(url in line for url in expected_urls):
            matching_indexes.append(index)
            matching_lines.append(line)
    audit.check(len(matching_lines) == EXPECTED_NEW_HUBS, "llms_new_line_count", len(matching_lines))
    for url in expected_urls:
        audit.check(sum(url in line for line in matching_lines) == 1, "llms_hub_url", url)
    if len(matching_indexes) == EXPECTED_NEW_HUBS:
        audit.check(
            matching_indexes == list(range(matching_indexes[0], matching_indexes[0] + EXPECTED_NEW_HUBS)),
            "llms_new_lines_not_contiguous",
            matching_indexes,
        )
        actual_order = [next((url for url in expected_urls if url in line), "") for line in matching_lines]
        audit.check(actual_order == expected_urls, "llms_new_order", actual_order)
        previous = lines[matching_indexes[0] - 1] if matching_indexes[0] else ""
        audit.check("중3영어학원" in previous, "llms_insertion_anchor", previous)
    stripped = b"".join(
        line.encode("utf-8") for index, line in enumerate(lines) if index not in set(matching_indexes)
    )
    audit.check(sha256_bytes(stripped) == BASELINE_LLMS_SHA256, "llms_existing_bytes_changed", sha256_bytes(stripped))
    return {"sha256": sha256_bytes(data), "new_lines": len(matching_lines), "existing_sha256": sha256_bytes(stripped)}


def title_value(dom: Node) -> str:
    nodes = dom.find_all("title")
    return nodes[0].text() if len(nodes) == 1 else ""


def first_h1(dom: Node) -> str:
    nodes = dom.find_all("h1")
    return nodes[0].text() if len(nodes) == 1 else ""


def audit_parent_hub(root: Path, overrides: Mapping[Path, bytes], audit: Audit) -> dict[str, Any]:
    path = root / "과목별학원" / "index.html"
    data = bytes_for(path, overrides)
    dom = parse_html(decode_utf8(data, path))
    values = {
        "title": title_value(dom),
        "h1": first_h1(dom),
        "canonical": canonical_value(dom),
        "description": meta_value(dom, name="description"),
    }
    for key, expected in PARENT_PROTECTED.items():
        if key == "canonical":
            audit.check(url_key(values[key]) == url_key(expected), f"parent_{key}", values[key])
        else:
            audit.check(values[key] == expected, f"parent_{key}", values[key])
    hrefs = [clean(node.attrs.get("href")) for node in dom.find_all("a")]
    canonical = PARENT_PROTECTED["canonical"]
    resolved = [url_key(urllib.parse.urljoin(canonical, href)) for href in hrefs if href]
    expected_new = [url_key(f"{BASE_URL}/과목별학원/{item.slug}/") for item in CATEGORIES]
    expected_old = [
        url_key(f"{BASE_URL}/과목별학원/{slug}/")
        for slug in ("중2수학학원", "중2영어학원", "중3수학학원", "중3영어학원")
    ]
    for value in expected_new + expected_old:
        audit.check(resolved.count(value) == 1, "parent_category_link", f"{value}: {resolved.count(value)}")
    return {**values, "sha256": sha256_bytes(data), "links": len(hrefs), "new_hubs": sum(item in resolved for item in expected_new)}


def recursive_objects(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from recursive_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from recursive_objects(child)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def reference_id(value: Any) -> str:
    return clean(value.get("@id")) if isinstance(value, dict) else ""


def ordered_names(value: Any) -> tuple[str, ...]:
    result = []
    for item in as_list(value):
        if isinstance(item, dict) and clean(item.get("name")):
            result.append(clean(item.get("name")))
        elif isinstance(item, str) and clean(item):
            result.append(clean(item))
    return tuple(result)


def educational_levels(value: Any) -> tuple[str, ...]:
    if isinstance(value, dict):
        for key in ("educationalLevel", "audienceType", "educationalRole"):
            if key in value:
                return educational_levels(value[key])
        return ()
    if isinstance(value, list):
        return unique_order(item for child in value for item in educational_levels(child))
    if isinstance(value, str):
        long_grade = re.fullmatch(r"고등학교\s*([1-3])학년(?:\s*학생)?", clean(value))
        if long_grade:
            return (f"고{long_grade.group(1)}",)
        tokens = GRADE_TOKEN_RE.findall(value)
        return unique_order(tokens if tokens else [value])
    return ()


def fact_nodes(dom: Node, field_name: str) -> list[Node]:
    return dom.find_all(attr="data-source-field", value=field_name)


def is_descendant(node: Node, ancestor: Node) -> bool:
    current = node.parent
    while current is not None:
        if current is ancestor:
            return True
        current = current.parent
    return False


def extract_faq(dom: Node) -> list[tuple[str, str]]:
    containers = dom.find_all(cls="grade-faq-list")
    if len(containers) != 1:
        return []
    details = containers[0].direct_children("details", "grade-faq-item")
    result: list[tuple[str, str]] = []
    for item in details:
        summaries = item.direct_children("summary")
        answers = item.direct_children("p")
        if len(summaries) != 1 or len(answers) != 1:
            result.append(("", ""))
        else:
            result.append((summaries[0].text(), answers[0].text()))
    return result


def faq_topics(value: str) -> set[str]:
    candidate = clean(value)
    candidate = re.sub(r"고등학교\s*[12]학년", " 학년 ", candidate)
    return {name for name, pattern in FAQ_TOPIC_RE.items() if pattern.search(candidate)}


def is_descendant_of(node: Node, ancestor: Node) -> bool:
    current = node.parent
    while current is not None:
        if current is ancestor:
            return True
        current = current.parent
    return False


def sentences(value: str) -> list[str]:
    return [
        clean(item)
        for item in re.split(r"(?<=[.!?])(?:[”’\"']*)\s+", clean(value))
        if clean(item)
    ]


def lexical_tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[0-9A-Za-z가-힣]+", clean(value).casefold()))


def ngrams(tokens: Sequence[str], size: int) -> set[tuple[str, ...]]:
    return {
        tuple(tokens[index:index + size])
        for index in range(max(0, len(tokens) - size + 1))
    }


def source_neutral(value: str, source: SourceRow, physical: PhysicalFact, category: Category) -> str:
    substitutions: list[tuple[str, str]] = []
    substitutions.extend((area, " LOCALITY ") for area in physical.areas)
    substitutions.extend(
        (
            (source.locality, " LOCALITY "),
            (source.center_name, " CENTER "),
            (source.address, " ADDRESS "),
            (source.registration_name, " REGISTEREDNAME "),
            (source.registration_number, " REGISTRATION "),
            (source.region, " REGION "),
            (source.city, " CITY "),
            (category.slug, " CATEGORY "),
            (category.label, " CATEGORY "),
            (f"{source.locality} {category.query_suffix}", " QUERY "),
        )
    )
    substitutions.extend((school, " SCHOOL ") for school in source.high_schools)
    substitutions.extend((grade, " GRADE ") for grade in source.english_grades + source.math_grades)
    result = clean(value)
    for raw, token in sorted(
        {(clean(raw), token) for raw, token in substitutions if clean(raw)},
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        result = result.replace(raw, token)
    result = re.sub(r"(?:초[1-6]|[중고][1-3])", " GRADE ", result)
    result = re.sub(r"\d+(?:[.,]\d+)?", " NUMBER ", result)
    return normalized_literal(result)


def visible_main_text(dom: Node) -> str:
    mains = dom.find_all("main", attr="data-grade-page")
    return mains[0].text() if len(mains) == 1 else ""


def semantic_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def audit_root_brand(root: Path, audit: Audit) -> dict[str, Any]:
    path = root / "index.html"
    dom = parse_html(decode_utf8(path.read_bytes(), path))
    try:
        graph, _ = json_graph(dom)
    except Exception as exc:
        audit.add("root_jsonld", exc)
        return {}
    roots = [node for node in graph if clean(node.get("@id")) == ROOT_ORG_ID]
    audit.check(len(roots) == 1, "root_org_count", len(roots))
    if not roots:
        return {}
    node = roots[0]
    audit.check(clean(node.get("telephone")) == "010-6839-8283", "root_telephone", node.get("telephone"))
    contacts = as_list(node.get("contactPoint"))
    phones = [clean(item.get("telephone")) for item in contacts if isinstance(item, dict)]
    audit.check(phones == ["+82-10-6839-8283"], "root_contactpoint", phones)
    return {"id": ROOT_ORG_ID, "telephone": clean(node.get("telephone")), "contactPoint": phones}


def audit_physical_node(
    node: dict[str, Any],
    source: SourceRow,
    physical: PhysicalFact,
    audit: Audit,
    rel: str,
) -> dict[str, Any]:
    audit.check(node_types(node) == {"EducationalOrganization", "LocalBusiness"}, "physical_types", rel)
    audit.check(
        set(node) == {"@type", "@id", "name", "legalName", "identifier", "address", "areaServed", "makesOffer"},
        "physical_shape",
        f"{rel}: {sorted(node)}",
    )
    audit.check(clean(node.get("@id")) == physical.physical_id, "physical_id", rel)
    audit.check(clean(node.get("name")) == physical.center_name, "physical_name", rel)
    audit.check(clean(node.get("legalName")) == source.registration_name, "physical_legal_name", rel)
    identifier = node.get("identifier")
    identifier_value = clean(identifier.get("value")) if isinstance(identifier, dict) else clean(identifier)
    audit.check(identifier_value == source.registration_number, "physical_identifier", rel)
    if isinstance(identifier, dict):
        audit.check(set(identifier) == {"@type", "propertyID", "value"}, "physical_identifier_shape", rel)
        audit.check(node_types(identifier) == {"PropertyValue"}, "physical_identifier_type", rel)
        audit.check(clean(identifier.get("propertyID")) == "교육지원청 등록번호", "physical_identifier_property", rel)
    for unsupported_key in (
        "telephone", "contactPoint", "openingHours", "openingHoursSpecification", "url", "sameAs"
    ):
        audit.check(unsupported_key not in node, "physical_blanket_fact_forbidden", f"{rel}: {unsupported_key}")

    address = node.get("address") if isinstance(node.get("address"), dict) else {}
    audit.check(set(address) == {"@type", "streetAddress", "addressCountry"}, "physical_address_shape", rel)
    audit.check(node_types(address) == {"PostalAddress"}, "physical_address_type", rel)
    audit.check(clean(address.get("streetAddress")) == physical.address, "physical_street", rel)
    audit.check(clean(address.get("addressCountry")) == "KR", "physical_address_country", rel)

    area_names = ordered_names(node.get("areaServed"))
    audit.check(area_names == physical.areas, "physical_area_union", f"{rel}: {area_names!r}")
    for area in as_list(node.get("areaServed")):
        audit.check(isinstance(area, dict) and set(area) == {"@type", "name"} and node_types(area) == {"Place"},
                    "physical_area_shape", f"{rel}: {area}")

    offers = as_list(node.get("makesOffer"))
    expected_by_subject = {
        "영어": physical.english_grades,
        "수학": physical.math_grades,
    }
    observed: dict[str, tuple[str, ...]] = {}
    for offer in offers:
        if not isinstance(offer, dict) or "Offer" not in node_types(offer):
            audit.add("physical_offer_type", rel)
            continue
        audit.check(set(offer) == {"@type", "itemOffered"}, "physical_offer_shape", f"{rel}: {offer}")
        service = offer.get("itemOffered")
        if not isinstance(service, dict) or "Service" not in node_types(service):
            audit.add("physical_offer_service", rel)
            continue
        audit.check(set(service) == {"@type", "name", "serviceType", "educationalLevel"},
                    "physical_offer_service_shape", f"{rel}: {service}")
        haystack = clean(" ".join(json_strings(service)))
        subjects = [subject for subject in ("영어", "수학") if subject in haystack]
        audit.check(len(subjects) == 1, "physical_offer_subject", f"{rel}: {haystack[:160]}")
        if len(subjects) != 1:
            continue
        subject = subjects[0]
        levels = educational_levels(service.get("educationalLevel"))
        audit.check(subject not in observed, "physical_offer_duplicate_subject", f"{rel}: {subject}")
        observed[subject] = levels
        audit.check(levels == expected_by_subject[subject], "physical_offer_grade_union", f"{rel}: {subject}: {levels!r}")
    expected_subjects = {subject for subject, levels in expected_by_subject.items() if levels}
    audit.check(set(observed) == expected_subjects, "physical_offer_subjects", f"{rel}: {set(observed)} != {expected_subjects}")
    return {"id": physical.physical_id, "offers": {key: list(value) for key, value in observed.items()}}


def faq_schema_pairs(node: Mapping[str, Any]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for question in as_list(node.get("mainEntity")):
        if not isinstance(question, dict):
            result.append(("", ""))
            continue
        answer = question.get("acceptedAnswer")
        result.append((clean(question.get("name")), clean(answer.get("text")) if isinstance(answer, dict) else ""))
    return result


def audit_source_fields(
    dom: Node,
    source: SourceRow,
    category: Category,
    audit: Audit,
    rel: str,
) -> dict[str, Any]:
    exact = {
        "locality": source.locality,
        "region": source.region,
        "city": source.city,
        "center-name": source.center_name,
        "address": source.address,
        "registration-name": source.registration_name,
        "registration-number": source.registration_number,
        "supported-grades": source.grades_raw(category.subject) or "원자료 미기재",
        "high-schools": source.high_schools_raw if source.high_schools_raw else "원자료 미기재",
    }
    for field_name, expected in exact.items():
        nodes = fact_nodes(dom, field_name)
        audit.check(len(nodes) == 1, "source_field_count", f"{rel}: {field_name}: {len(nodes)}")
        if len(nodes) == 1:
            audit.check(nodes[0].text() == expected, "source_field_value", f"{rel}: {field_name}: {nodes[0].text()!r} != {expected!r}")

    fee_nodes = fact_nodes(dom, "fee-url")
    audit.check(len(fee_nodes) == 1, "source_fee_count", f"{rel}: {len(fee_nodes)}")
    if len(fee_nodes) == 1:
        node = fee_nodes[0]
        if source.fee_url:
            audit.check(node.tag == "a", "source_fee_tag", rel)
            audit.check(clean(node.attrs.get("href")) == source.fee_url, "source_fee_href", rel)
            audit.check(node.text() == "센터 공통 교습비 링크", "source_fee_text", rel)
        else:
            audit.check(node.text() == "미기재 상태", "source_fee_missing", rel)
            audit.check(not clean(node.attrs.get("href")), "source_fee_blank_href", rel)

    guide_nodes = fact_nodes(dom, "location-guide")
    missing_guide_nodes = dom.find_all(attr="data-source-status", value="missing-location-guide")
    if source.guide_raw:
        audit.check(len(guide_nodes) == 1, "source_guide_count", f"{rel}: {len(guide_nodes)}")
        audit.check(not missing_guide_nodes, "source_guide_false_missing", rel)
        if len(guide_nodes) == 1:
            node = guide_nodes[0]
            audit.check(node.text() == source.guide_clean, "source_guide_clean", f"{rel}: {node.text()!r}")
    else:
        audit.check(not guide_nodes, "source_guide_blank_field_forbidden", f"{rel}: {len(guide_nodes)}")
        audit.check(len(missing_guide_nodes) == 1, "source_guide_missing_marker", f"{rel}: {len(missing_guide_nodes)}")
        if len(missing_guide_nodes) == 1:
            audit.check(bool(MISSING_CUE_RE.search(missing_guide_nodes[0].text())),
                        "source_guide_missing_cue", f"{rel}: {missing_guide_nodes[0].text()}")

    chips = [node.text() for node in dom.find_all(attr="data-source-school")]
    audit.check(tuple(chips) == source.high_schools, "school_chip_parity", f"{rel}: {chips!r} != {source.high_schools!r}")
    return {"guide": bool(source.guide_raw), "fee": bool(source.fee_url), "schools": len(source.high_schools)}


def audit_faq_source_state(
    faq: Sequence[tuple[str, str]],
    source: SourceRow,
    category: Category,
    audit: Audit,
    rel: str,
) -> None:
    audit.check(len(faq) == 4, "faq_visible_count", f"{rel}: {len(faq)}")
    if len(faq) != 4:
        return
    for index, ((question, answer), expected_topic) in enumerate(zip(faq, FAQ_TOPICS)):
        # Topic cardinality belongs to the user-facing question.  Answers must
        # repeat authoritative grade/school/address/guide values, so classifying
        # those literals as fresh intents creates deterministic false positives.
        # The answer of every slot is separately source-state audited below.
        topics = faq_topics(question)
        audit.check(topics == {expected_topic}, "faq_single_intent", f"{rel}: {index}: {topics}: {question}")

    grade_answer = faq[0][1]
    if category.grade in source.grades(category.subject):
        tokens = unique_order(GRADE_TOKEN_RE.findall(grade_answer))
        audit.check(set(tokens).issubset(set(source.grades(category.subject))), "faq_grade_out_of_source", f"{rel}: {tokens}")
        audit.check(category.grade in clean(faq[0][0] + " " + grade_answer), "faq_grade_target_missing", rel)
    else:
        positive_sentences = [
            sentence for sentence in sentences(grade_answer)
            if POSITIVE_GRADE_RE.search(sentence) and not NEGATIVE_GRADE_RE.search(sentence)
        ]
        audit.check(not positive_sentences, "faq_unsupported_positive_grade", f"{rel}: {positive_sentences[:2]}")
        audit.check(bool(MISSING_CUE_RE.search(grade_answer) or NEGATIVE_GRADE_RE.search(grade_answer)), "faq_unsupported_missing_cue", f"{rel}: {grade_answer}")

    school_answer = faq[1][1]
    if source.high_schools:
        for school in source.high_schools:
            audit.check(school in school_answer, "faq_school_source", f"{rel}: {school}")
    elif source.high_schools_raw:
        audit.check(source.high_schools_raw in school_answer, "faq_school_generic", rel)
    else:
        audit.check(bool(MISSING_CUE_RE.search(school_answer)), "faq_school_missing_cue", f"{rel}: {school_answer}")

    location_answer = faq[2][1]
    audit.check(source.address in location_answer, "faq_location_address", rel)
    if source.guide_raw:
        audit.check(source.guide_clean in location_answer, "faq_location_guide", rel)
    else:
        audit.check(bool(MISSING_CUE_RE.search(location_answer)), "faq_location_missing_cue", f"{rel}: {location_answer}")
        masked = location_answer.replace(source.address, " ")
        positive = re.search(r"(?:현재|제공된|확인된)\s*(?:위치|출입|방문|건물)\s*안내", masked)
        audit.check(not positive, "faq_location_false_premise", f"{rel}: {location_answer}")

    fee_answer = faq[3][1]
    if source.fee_url:
        audit.check("센터 공통 교습비 링크" in fee_answer, "faq_fee_link_state", f"{rel}: {fee_answer}")
        audit.check(not MISSING_CUE_RE.search(fee_answer), "faq_fee_false_missing", rel)
    else:
        audit.check("미기재 상태" in fee_answer and bool(MISSING_CUE_RE.search(fee_answer)), "faq_fee_missing_state", f"{rel}: {fee_answer}")
    audit.check(not re.search(r"\b\d[\d,]*(?:원|만원)\b", fee_answer), "faq_fee_amount_claim", rel)


def audit_breadcrumb(
    node: Mapping[str, Any],
    canonical: str,
    h1: str,
    category: Category,
    audit: Audit,
    rel: str,
) -> None:
    items = as_list(node.get("itemListElement"))
    audit.check(len(items) == 4, "breadcrumb_count", f"{rel}: {len(items)}")
    expected = (
        (1, "홈", f"{BASE_URL}/"),
        (2, "과목별학원", f"{BASE_URL}/과목별학원/"),
        (3, category.slug, f"{BASE_URL}/과목별학원/{category.slug}/"),
        (4, h1, canonical),
    )
    if len(items) != 4:
        return
    for item, (position, name, url) in zip(items, expected):
        if not isinstance(item, dict):
            audit.add("breadcrumb_item_type", rel)
            continue
        audit.check(node_types(item) == {"ListItem"}, "breadcrumb_item_type", rel)
        audit.check(item.get("position") == position, "breadcrumb_position", f"{rel}: {item.get('position')}")
        audit.check(clean(item.get("name")) == name, "breadcrumb_name", f"{rel}: {item.get('name')} != {name}")
        actual_url = clean(item.get("item") or item.get("url"))
        audit.check(url_key(actual_url) == url_key(url), "breadcrumb_url", f"{rel}: {actual_url}")


def audit_article_topics(
    node: Mapping[str, Any],
    main_text: str,
    headings: Sequence[str],
    audit: Audit,
    rel: str,
) -> None:
    for key in ("about", "mentions"):
        entries = as_list(node.get(key))
        for entry in entries:
            audit.check(isinstance(entry, dict), f"article_{key}_object", rel)
            if not isinstance(entry, dict):
                continue
            if set(entry) == {"@id"}:
                audit.check(clean(entry.get("@id")).startswith(f"{BASE_URL}/센터/"),
                            f"article_{key}_reference", f"{rel}: {entry}")
                continue
            audit.check(set(entry) <= {"@type", "name"}, f"article_{key}_shape", f"{rel}: {entry}")
            name = clean(entry.get("name"))
            audit.check(bool(name), f"article_{key}_name", rel)
            audit.check(
                normalized_literal(name) in normalized_literal(main_text),
                f"article_{key}_visible",
                f"{rel}: {name}",
            )
    has_parts = as_list(node.get("hasPart"))
    observed = []
    for part in has_parts:
        audit.check(
            isinstance(part, dict)
            and node_types(part) == {"WebPageElement"}
            and set(part) == {"@type", "name"},
            "article_haspart_shape",
            f"{rel}: {part}",
        )
        if isinstance(part, dict):
            observed.append(clean(part.get("name")))
    audit.check(tuple(observed) == tuple(headings), "article_haspart_parity", f"{rel}: {observed!r} != {tuple(headings)!r}")
    sections = tuple(clean(item) for item in as_list(node.get("articleSection")))
    audit.check(sections == tuple(headings), "article_section_parity", f"{rel}: {sections!r}")


def audit_school_schema(
    payloads: Sequence[Any],
    graph: Sequence[dict[str, Any]],
    source: SourceRow,
    canonical: str,
    audit: Audit,
    rel: str,
) -> None:
    all_objects = [item for payload in payloads for item in recursive_objects(payload)]
    typed_names = [clean(item.get("name")) for item in all_objects if "HighSchool" in node_types(item)]
    observed_set = set(typed_names)
    expected_set = set(source.high_schools)
    audit.check(observed_set == expected_set, "school_schema_names", f"{rel}: {observed_set!r} != {expected_set!r}")
    audit.check(not any(node_types(item) & {"ElementarySchool", "MiddleSchool"} for item in all_objects), "school_wrong_level_type", rel)

    school_lists = [
        node for node in graph
        if "ItemList" in node_types(node)
        and (
            clean(node.get("@id")) == f"{canonical}#schools"
            or "학교" in clean(node.get("name"))
        )
    ]
    if source.high_schools:
        audit.check(len(school_lists) == 1, "school_itemlist_count", f"{rel}: {len(school_lists)}")
        if len(school_lists) == 1:
            audit.check(clean(school_lists[0].get("@id")) == f"{canonical}#high-schools",
                        "school_itemlist_id", rel)
            items = as_list(school_lists[0].get("itemListElement"))
            names = tuple(
                clean(
                    item.get("name")
                    or (item.get("item", {}).get("name") if isinstance(item.get("item"), dict) else "")
                )
                for item in items if isinstance(item, dict)
            )
            positions = tuple(item.get("position") for item in items if isinstance(item, dict))
            audit.check(names == source.high_schools, "school_itemlist_names", f"{rel}: {names!r}")
            audit.check(positions == tuple(range(1, len(items) + 1)), "school_itemlist_positions", rel)
            audit.check(school_lists[0].get("numberOfItems") in (None, len(items)), "school_itemlist_number", rel)
    else:
        audit.check(not school_lists, "school_itemlist_for_blank_or_generic", f"{rel}: {len(school_lists)}")


def audit_detail_schema(
    dom: Node,
    graph: Sequence[dict[str, Any]],
    payloads: Sequence[Any],
    source: SourceRow,
    physical: PhysicalFact,
    category: Category,
    canonical: str,
    title: str,
    description: str,
    h1: str,
    main_text: str,
    headings: Sequence[str],
    faq: Sequence[tuple[str, str]],
    supported: bool,
    audit: Audit,
    rel: str,
) -> tuple[str | None, dict[str, Any]]:
    scripts = [node for node in dom.find_all("script") if node.attrs.get("type", "").lower() == "application/ld+json"]
    audit.check(len(scripts) == 1, "jsonld_script_count", f"{rel}: {len(scripts)}")
    audit.check(len(payloads) == 1, "jsonld_payload_count", f"{rel}: {len(payloads)}")
    if payloads and isinstance(payloads[0], dict):
        audit.check(payloads[0].get("@context") == "https://schema.org", "jsonld_context", rel)

    expected_counts = {
        "WebPage": 1,
        "ImageObject": 1,
        "Article": 1,
        "BreadcrumbList": 1,
        "FAQPage": 1,
    }
    for type_name, expected in expected_counts.items():
        audit.check(len(graph_nodes(graph, type_name)) == expected, f"schema_{type_name.lower()}_count", f"{rel}: {len(graph_nodes(graph, type_name))}")
    physical_nodes = [
        node for node in graph
        if {"EducationalOrganization", "LocalBusiness"}.issubset(node_types(node))
    ]
    audit.check(len(physical_nodes) == 1, "schema_physical_count", f"{rel}: {len(physical_nodes)}")
    audit.check(not any(clean(node.get("@id")) == ROOT_ORG_ID for node in graph), "detail_redefines_root_org", rel)

    web_pages = graph_nodes(graph, "WebPage")
    articles = graph_nodes(graph, "Article")
    breadcrumbs = graph_nodes(graph, "BreadcrumbList")
    faqs = graph_nodes(graph, "FAQPage")
    services = graph_nodes(graph, "Service")
    # graph_nodes only sees top-level graph nodes, not physical nested services.
    audit.check(len(services) == (1 if supported else 0), "page_service_count", f"{rel}: {len(services)}")
    audit.check(not graph_nodes(graph, "Offer"), "top_level_offer_forbidden", rel)

    if web_pages:
        page = web_pages[0]
        audit.check(clean(page.get("@id")) == f"{canonical}#webpage", "webpage_id", rel)
        audit.check(url_key(clean(page.get("url"))) == url_key(canonical), "webpage_url", rel)
        audit.check(clean(page.get("name")) in {h1, title}, "webpage_name", f"{rel}: {page.get('name')}")
        audit.check(clean(page.get("description")) == description, "webpage_description", rel)
        audit.check(reference_id(page.get("primaryImageOfPage")) == f"{canonical}#primaryimage",
                    "webpage_primary_image", rel)
        main_id = reference_id(page.get("mainEntity"))
        if supported:
            audit.check(main_id == f"{canonical}#service", "webpage_main_service", f"{rel}: {main_id}")
        else:
            audit.check(main_id == f"{canonical}#article", "unsupported_webpage_article_ref", f"{rel}: {main_id}")
        has_parts = as_list(page.get("hasPart"))
        if has_parts:
            observed = [clean(item.get("name")) for item in has_parts if isinstance(item, dict)]
            audit.check(tuple(observed) == tuple(headings), "webpage_haspart_parity", rel)

    if articles:
        article = articles[0]
        audit.check(clean(article.get("@id")) == f"{canonical}#article", "article_id", rel)
        audit.check(clean(article.get("headline")) == h1, "article_headline", rel)
        audit.check(clean(article.get("description")) == description, "article_description", rel)
        audit.check("abstract" not in article, "article_abstract_forbidden", rel)
        audit.check(clean(article.get("datePublished")) == RELEASE_DATE, "article_date_published", rel)
        audit.check(clean(article.get("dateModified")) == RELEASE_DATE, "article_date_modified", rel)
        audit.check(article.get("author") == {"@id": ROOT_ORG_ID}, "article_author", f"{rel}: {article.get('author')}")
        audit.check(article.get("publisher") == {"@id": ROOT_ORG_ID}, "article_publisher", f"{rel}: {article.get('publisher')}")
        audit.check(reference_id(article.get("mainEntityOfPage")) == f"{canonical}#webpage", "article_main_page", rel)
        if supported:
            audit.check(educational_levels(article.get("educationalLevel")) == (category.grade,),
                        "article_educational_level", rel)
        else:
            audit.check("educationalLevel" not in article and "audience" not in article,
                        "unsupported_article_level", rel)
        expected_about = [
            {"@type": "Thing", "name": category.label},
            {"@type": "Place", "name": source.locality},
        ]
        audit.check(article.get("about") == expected_about, "article_about_exact", f"{rel}: {article.get('about')}")
        expected_mentions = [{"@id": physical.physical_id}] + [
            {"@type": "HighSchool", "name": name} for name in source.high_schools
        ]
        audit.check(article.get("mentions") == expected_mentions,
                    "article_mentions_exact", f"{rel}: {article.get('mentions')}")
        visible_image_urls = [
            urllib.parse.urljoin(canonical, clean(image.attrs.get("src")))
            for image in dom.find_all("main", attr="data-grade-page")[0].find_all("img")
            if clean(image.attrs.get("src")) and "display:none" not in image.attrs.get("style", "").replace(" ", "").lower()
        ] if dom.find_all("main", attr="data-grade-page") else []
        og_image = meta_value(dom, prop="og:image")
        expected_images = [og_image] + visible_image_urls
        audit.check(
            [url_key(item) for item in as_list(article.get("image"))]
            == [url_key(item) for item in expected_images],
            "article_image_parity",
            rel,
        )
        audit_article_topics(article, main_text, headings, audit, rel)

    image_nodes = graph_nodes(graph, "ImageObject")
    if image_nodes:
        audit.check(clean(image_nodes[0].get("@id")) == f"{canonical}#primaryimage", "imageobject_id", rel)
        audit.check(url_key(clean(image_nodes[0].get("url"))) == url_key(meta_value(dom, prop="og:image")),
                    "imageobject_og_parity", rel)

    if breadcrumbs:
        audit_breadcrumb(breadcrumbs[0], canonical, h1, category, audit, rel)

    if faqs:
        schema_faq = faq_schema_pairs(faqs[0])
        audit.check(schema_faq == list(faq), "faq_visible_schema_parity", f"{rel}: {len(schema_faq)} != {len(faq)}")

    physical_semantic: str | None = None
    physical_metrics: dict[str, Any] = {}
    if physical_nodes:
        physical_metrics = audit_physical_node(physical_nodes[0], source, physical, audit, rel)
        physical_semantic = semantic_json(physical_nodes[0])

    if supported and services:
        service = services[0]
        audit.check(clean(service.get("@id")) == f"{canonical}#service", "service_id", rel)
        service_text = clean(" ".join(json_strings(service)))
        audit.check(category.subject in service_text and category.grade in service_text, "service_subject_grade", rel)
        audit.check(reference_id(service.get("provider")) == physical.physical_id, "service_provider", rel)
        area_names = ordered_names(service.get("areaServed"))
        audit.check(area_names == (source.locality,), "service_area", f"{rel}: {area_names!r}")
        levels = educational_levels(service.get("educationalLevel"))
        if not levels:
            levels = educational_levels(service.get("audience"))
        audit.check(levels == (category.grade,), "service_educational_level", f"{rel}: {levels!r}")
        audit.check(category.grade in source.grades(category.subject), "service_out_of_source", rel)
        audit.check(not re.search(r"\b\d[\d,]*(?:원|만원)\b", service_text), "service_fee_amount", rel)
    elif not supported:
        # The physical organization may truthfully contain other grade offers;
        # everything else on this page must avoid a page-specific service claim.
        for node in graph:
            if node in physical_nodes:
                continue
            audit.check("audience" not in node and "educationalLevel" not in node and "offers" not in node and "makesOffer" not in node,
                        "unsupported_schema_claim", f"{rel}: {node.get('@type')}")
        target_id = f"{canonical}#service"
        audit.check(not any(target_id == clean(item.get("@id")) for payload in payloads for item in recursive_objects(payload)),
                    "unsupported_service_id", rel)

    audit_school_schema(payloads, graph, source, canonical, audit, rel)

    related_lists = [node for node in graph_nodes(graph, "ItemList") if clean(node.get("@id")) == f"{canonical}#related"]
    audit.check(len(related_lists) == 1, "related_itemlist_count", f"{rel}: {len(related_lists)}")
    if len(related_lists) == 1:
        items = as_list(related_lists[0].get("itemListElement"))
        audit.check(len(items) >= 6, "related_itemlist_depth", f"{rel}: {len(items)}")
        positions = tuple(item.get("position") for item in items if isinstance(item, dict))
        audit.check(positions == tuple(range(1, len(items) + 1)), "related_itemlist_positions", rel)
        urls = tuple(url_key(clean(item.get("url") or item.get("item"))) for item in items if isinstance(item, dict))
        audit.check(len(urls) == len(set(urls)), "related_itemlist_duplicate_url", rel)
        visible_urls = {
            url_key(urllib.parse.urljoin(canonical, clean(anchor.attrs.get("href"))))
            for anchor in dom.find_all("a")
            if clean(anchor.attrs.get("href"))
            and not clean(anchor.attrs.get("href")).startswith(("#", "tel:", "mailto:", "javascript:"))
        }
        audit.check(set(urls).issubset(visible_urls), "related_itemlist_visible_parity", rel)
        for item in items:
            if isinstance(item, dict):
                audit.check(normalized_literal(item.get("name")) in normalized_literal(main_text),
                            "related_itemlist_name_visible", f"{rel}: {item.get('name')}")

    # Article/WebPage topic sets must agree where both are present.
    if web_pages and articles:
        for key in ("about", "mentions"):
            if key in web_pages[0]:
                audit.check(
                    semantic_json(web_pages[0].get(key, [])) == semantic_json(articles[0].get(key, [])),
                    f"webpage_article_{key}_parity",
                    rel,
                )

    # The only phone is the central root ContactPoint on the root graph; details
    # reference that root and must define no phone at all.
    phone_values = [
        value for payload in payloads for value in json_strings(payload)
        if PHONE_VALUE_RE.fullmatch(clean(value))
    ]
    audit.check(not phone_values, "detail_schema_phone", f"{rel}: {phone_values!r}")
    return physical_semantic, physical_metrics


@dataclass
class DetailResult:
    category: str
    locality: str
    canonical: str
    supported: bool
    hrefs: tuple[str, ...]
    authored_paragraphs: tuple[str, ...]
    authored_sentences: tuple[str, ...]
    headings: tuple[str, ...]
    meta_description: str
    geo_score: int
    physical_id: str
    physical_semantic: str | None


def audit_local_resources(
    dom: Node,
    canonical: str,
    root: Path,
    overrides: Mapping[Path, bytes],
    audit: Audit,
    rel: str,
) -> tuple[tuple[str, ...], int]:
    hrefs: list[str] = []
    broken = 0
    for anchor in dom.find_all("a"):
        href = clean(anchor.attrs.get("href"))
        if not href or href.startswith(("#", "tel:", "sms:", "mailto:", "javascript:")):
            continue
        absolute = urllib.parse.urljoin(canonical, href)
        parsed = urllib.parse.urlsplit(absolute)
        if parsed.hostname and parsed.hostname.lower() != urllib.parse.urlsplit(BASE_URL).hostname:
            continue
        route = route_for_url(absolute)
        hrefs.append(url_key(absolute))
        path = page_path_for_route(root, route)
        if not exists_for(path, overrides):
            broken += 1
            audit.add("broken_internal_link", f"{rel}: {href} -> {path.relative_to(root)}")

    for image in dom.find_all("img"):
        src = clean(image.attrs.get("src"))
        if not src or src.startswith(("data:", "http://", "https://")):
            continue
        parsed = urllib.parse.urlsplit(urllib.parse.urljoin(canonical, src))
        local = root / urllib.parse.unquote(parsed.path).lstrip("/")
        if not local.is_file():
            audit.add("broken_local_image", f"{rel}: {src}")
        audit.check(bool(clean(image.attrs.get("alt"))), "image_alt", f"{rel}: {src}")
        audit.check(
            clean(image.attrs.get("width")).isdigit() and clean(image.attrs.get("height")).isdigit(),
            "image_dimensions_missing",
            f"{rel}: {src}",
        )
    og_image = meta_value(dom, prop="og:image")
    audit.check(bool(og_image), "og_image_missing", rel)
    if og_image and urllib.parse.urlsplit(og_image).hostname == urllib.parse.urlsplit(BASE_URL).hostname:
        local = root / urllib.parse.unquote(urllib.parse.urlsplit(og_image).path).lstrip("/")
        audit.check(local.is_file(), "og_image_broken", f"{rel}: {og_image}")
    return tuple(hrefs), broken


def audit_detail_page(
    path: Path,
    data: bytes,
    root: Path,
    source: SourceRow,
    physical: PhysicalFact,
    category: Category,
    manuscript: ManuscriptFact,
    sitemap_keys: set[str],
    overrides: Mapping[Path, bytes],
    audit: Audit,
) -> DetailResult | None:
    rel = path.relative_to(root).as_posix()
    try:
        text = decode_utf8(data, path)
        dom = parse_html(text)
    except Exception as exc:
        audit.add("detail_html_parse", f"{rel}: {exc}")
        return None

    audit.check(not re.search(rb"[ \t]+(?:\r?\n|$)", data), "detail_trailing_whitespace", rel)
    html_nodes = dom.find_all("html")
    audit.check(len(html_nodes) == 1 and html_nodes[0].attrs.get("lang") == "ko", "html_lang", rel)
    mains = dom.find_all("main", attr="data-grade-page")
    audit.check(len(mains) == 1, "grade_main_count", f"{rel}: {len(mains)}")
    main = mains[0] if len(mains) == 1 else dom
    articles = main.find_all(cls="grade-main-article")
    audit.check(len(articles) == 1, "grade_article_count", f"{rel}: {len(articles)}")
    authored = articles[0] if len(articles) == 1 else main
    audit.check(
        authored.attrs.get("data-manuscript-sha256") == manuscript.sha256,
        "manuscript_sha_marker",
        f"{rel}: {authored.attrs.get('data-manuscript-sha256')}",
    )
    source_cues = tuple(
        clean(item) for item in authored.attrs.get("data-manuscript-cues", "").split("|") if clean(item)
    )
    audit.check(len(source_cues) >= 4 and len(source_cues) == len(set(source_cues)),
                "manuscript_cue_marker", f"{rel}: {source_cues!r}")
    for cue in source_cues[:4]:
        audit.check(cue in authored.text(), "manuscript_cue_visible", f"{rel}: {cue}")

    expected_h1 = f"{source.locality} {category.query_suffix}"
    expected_title = f"{expected_h1} | 영수학원"
    expected_canonical = f"{BASE_URL}/과목별학원/{category.slug}/{source.slug}/"
    title = title_value(dom)
    h1 = first_h1(dom)
    description = meta_value(dom, name="description")
    canonical = canonical_value(dom)
    robots = meta_value(dom, name="robots").lower()
    audit.check(title == expected_title, "detail_title", f"{rel}: {title!r}")
    audit.check(h1 == expected_h1, "detail_h1", f"{rel}: {h1!r}")
    audit.check(url_key(canonical) == url_key(expected_canonical), "detail_canonical", f"{rel}: {canonical}")
    audit.check(url_key(canonical) in sitemap_keys, "detail_canonical_sitemap", rel)
    audit.check(MIN_META_CHARS <= len(description) <= MAX_META_CHARS, "detail_meta_length", f"{rel}: {len(description)}")
    audit.check(meta_value(dom, prop="og:title") == title, "detail_og_title", rel)
    audit.check(meta_value(dom, prop="og:description") == description, "detail_og_description", rel)
    audit.check(url_key(meta_value(dom, prop="og:url")) == url_key(canonical), "detail_og_url", rel)
    audit.check("index" in robots and "follow" in robots and "noindex" not in robots and "nofollow" not in robots,
                "detail_robots", f"{rel}: {robots}")
    update_times = [node for node in dom.find_all("time") if node.attrs.get("datetime") == RELEASE_DATE]
    audit.check(len(update_times) == 1, "detail_visible_date", f"{rel}: {len(update_times)}")

    main_text = main.text()
    audit.check(normalized_literal(description) in normalized_literal(main_text), "meta_visible_parity", rel)
    audit_source_fields(dom, source, category, audit, rel)
    faq = extract_faq(dom)
    audit_faq_source_state(faq, source, category, audit, rel)

    supported = category.grade in source.grades(category.subject)
    status = main.attrs.get("data-source-status")
    if supported:
        audit.check(status != "unconfirmed-grade", "supported_unconfirmed_marker", rel)
    else:
        audit.check(status == "unconfirmed-grade", "unsupported_main_marker", f"{rel}: {status}")
        positive: list[str] = []
        scan_texts = [authored.text()] + [answer for _question, answer in faq]
        for value in scan_texts:
            for sentence in sentences(value):
                if POSITIVE_GRADE_RE.search(sentence) and not NEGATIVE_GRADE_RE.search(sentence):
                    positive.append(sentence)
        audit.check(not positive, "unsupported_visible_positive_grade", f"{rel}: {positive[:3]}")
        disclosures = main.find_all(attr="data-source-status", value="unconfirmed-grade")
        audit.check(len(disclosures) >= 2, "unsupported_disclosure_count", f"{rel}: {len(disclosures)}")

    visible_and_meta = " ".join((title, description, main_text))
    audit.check(not SEARCH_META_RE.search(visible_and_meta), "detail_search_meta_seed", rel)
    audit.check(not IRRELEVANT_SEED_RE.search(visible_and_meta), "detail_irrelevant_seed", rel)
    audit.check(not FEE_AMOUNT_RE.search(main_text), "detail_fee_amount_claim", f"{rel}: {FEE_AMOUNT_RE.search(main_text).group(0) if FEE_AMOUNT_RE.search(main_text) else ''}")
    audit.check(not KNOWN_BAD_COPY_RE.search(visible_and_meta), "detail_known_bad_copy", f"{rel}: {KNOWN_BAD_COPY_RE.search(visible_and_meta).group(0) if KNOWN_BAD_COPY_RE.search(visible_and_meta) else ''}")
    for sentence in sentences(visible_and_meta):
        if STRONG_CLAIM_RE.search(sentence):
            audit.check(bool(NEGATED_CLAIM_RE.search(sentence)), "detail_strong_claim", f"{rel}: {sentence}")

    editorial_heads = authored.direct_children("div", "section-head")
    audit.check(len(editorial_heads) == 1, "authored_section_head_count", f"{rel}: {len(editorial_heads)}")
    editorial_head = editorial_heads[0] if len(editorial_heads) == 1 else None
    visible_heading_values = tuple(node.text() for node in authored.find_all("h2") if node.text())
    heading_values = tuple(
        node.text() for node in authored.find_all("h2")
        if node.text() and (editorial_head is None or not is_descendant_of(node, editorial_head))
    )
    h2_word_repeats: list[tuple[str, tuple[str, ...]]] = []
    for heading in heading_values:
        tokens = re.findall(r"[가-힣]{2,}", heading)
        repeated = tuple(sorted(token for token, count in Counter(tokens).items() if count > 1))
        if repeated:
            h2_word_repeats.append((heading, repeated))
    audit.check(not h2_word_repeats, "authored_h2_word_repeat", f"{rel}: {h2_word_repeats[:3]}")
    h2_openings = tuple(
        normalized_literal(heading.partition("‘")[0].removeprefix(source.locality))
        for heading in heading_values
    )
    audit.check(all(h2_openings) and len(h2_openings) == len(set(h2_openings)),
                "authored_h2_opening_duplicate", f"{rel}: {h2_openings!r}")
    paragraphs = tuple(
        node.text() for node in authored.find_all("p")
        if node.text()
        and (editorial_head is None or not is_descendant_of(node, editorial_head))
        and not node.attrs.get("data-source-field")
        and "data-grade-source-note" not in node.attrs
        and node.attrs.get("data-source-status") != "unconfirmed-grade"
    )
    sentence_values = tuple(sentence for paragraph in paragraphs for sentence in sentences(paragraph))
    adjacent_repeats = [
        (value, match.group(0))
        for value in (*heading_values, *paragraphs)
        if (match := ADJACENT_WORD_REPEAT_RE.search(value))
    ]
    audit.check(not adjacent_repeats, "authored_adjacent_word_repeat", f"{rel}: {adjacent_repeats[:3]}")
    audit.check(MIN_H2 <= len(heading_values) <= MAX_H2, "authored_h2_count", f"{rel}: {len(heading_values)}")
    authored_core_text = clean(" ".join((*heading_values, *paragraphs)))
    authored_chars = len(authored_core_text)
    audit.check(MIN_AUTHORED_CHARS <= authored_chars <= MAX_AUTHORED_CHARS, "authored_length", f"{rel}: {authored_chars}")
    long_sentences = [sentence for sentence in sentence_values if len(sentence) > MAX_EDITORIAL_SENTENCE_CHARS]
    audit.check(not long_sentences, "authored_sentence_length", f"{rel}: {[len(item) for item in long_sentences[:3]]}")
    audit.check(all(6 <= len(value) <= 80 for value in heading_values), "authored_h2_length", f"{rel}: {[len(x) for x in heading_values]}")
    paragraph_norms = [source_neutral(value, source, physical, category) for value in paragraphs]
    sentence_norms = [source_neutral(value, source, physical, category) for value in sentence_values]
    audit.check(len(paragraph_norms) == len(set(paragraph_norms)), "within_page_paragraph_duplicate", rel)
    audit.check(len(sentence_norms) == len(set(sentence_norms)), "within_page_sentence_duplicate", rel)
    heading_norms = [source_neutral(value, source, physical, category) for value in heading_values]
    audit.check(len(heading_norms) == len(set(heading_norms)), "within_page_h2_duplicate", rel)
    audit.check(authored_core_text.count(source.locality) <= MAX_LOCALITY_MENTIONS,
                "authored_locality_frequency", f"{rel}: {authored_core_text.count(source.locality)}")
    query = f"{source.locality} {category.query_suffix}"
    audit.check(authored_core_text.count(query) <= MAX_EXACT_QUERY_MENTIONS,
                "authored_query_frequency", f"{rel}: {authored_core_text.count(query)}")
    manuscript_sentences = set(sentences(clean(manuscript.raw)))
    copied_sentences = [sentence for sentence in sentence_values if sentence in manuscript_sentences]
    audit.check(not copied_sentences, "raw_manuscript_sentence_copied", f"{rel}: {copied_sentences[:2]}")
    overlap = ngrams(lexical_tokens(authored_core_text), 12) & ngrams(lexical_tokens(manuscript.raw), 12)
    audit.check(not overlap, "raw_manuscript_12gram_copied", f"{rel}: {next(iter(overlap), ())}")

    try:
        graph, payloads = json_graph(dom)
    except Exception as exc:
        audit.add("detail_jsonld_parse", f"{rel}: {exc}")
        graph, payloads = [], []
    json_text = " ".join(value for payload in payloads for value in json_strings(payload))
    audit.check(not SEARCH_META_RE.search(json_text), "jsonld_search_meta_seed", rel)
    audit.check(not IRRELEVANT_SEED_RE.search(json_text), "jsonld_irrelevant_seed", rel)
    physical_semantic, _physical_metrics = audit_detail_schema(
        dom, graph, payloads, source, physical, category, canonical, title, description,
        h1, main_text, visible_heading_values, faq, supported, audit, rel,
    )
    visible_images = [node for node in main.find_all("img") if "display:none" not in node.attrs.get("style", "").replace(" ", "").lower()]
    audit.check(len(visible_images) == 2, "detail_visible_image_count", f"{rel}: {len(visible_images)}")
    for index, image in enumerate(visible_images):
        src = clean(image.attrs.get("src"))
        absolute = urllib.parse.urljoin(canonical, src)
        local = root / urllib.parse.unquote(urllib.parse.urlsplit(absolute).path).lstrip("/")
        if not local.is_file():
            continue
        try:
            with Image.open(local) as opened:
                expected_width, expected_height = opened.size
        except Exception as exc:
            audit.add("image_decode", f"{rel}: {src}: {exc}")
            continue
        audit.check(image.attrs.get("width") == str(expected_width) and image.attrs.get("height") == str(expected_height),
                    "image_intrinsic_dimensions", f"{rel}: {src}")
        audit.check(image.attrs.get("decoding") == "async", "image_decoding_policy", f"{rel}: {src}")
        if index == 0:
            audit.check(image.attrs.get("loading") == "eager" and image.attrs.get("fetchpriority") == "high",
                        "image_hero_policy", f"{rel}: {src}")
        else:
            audit.check(image.attrs.get("loading") == "lazy" and "fetchpriority" not in image.attrs,
                        "image_belowfold_policy", f"{rel}: {src}")
    hrefs, _broken = audit_local_resources(dom, canonical, root, overrides, audit, rel)

    # Simple, reproducible GEO score.  Every scored item is also a hard gate;
    # the score is useful for comparing generated categories, not bypassing facts.
    score = 0
    score += 10 if title == expected_title and h1 == expected_h1 and url_key(canonical) == url_key(expected_canonical) else 0
    guide_grounded = (
        len(fact_nodes(dom, "location-guide")) == 1
        if source.guide_raw
        else len(dom.find_all(attr="data-source-status", value="missing-location-guide")) == 1
    )
    score += 25 if guide_grounded and all(len(fact_nodes(dom, name)) == 1 for name in (
        "locality", "region", "city", "center-name", "address", "registration-name",
        "registration-number", "fee-url", "supported-grades", "high-schools",
    )) else 0
    score += 20 if len(graph_nodes(graph, "Article")) == 1 and len(graph_nodes(graph, "FAQPage")) == 1 else 0
    score += 20 if len(faq) == 4 and all(faq_topics(pair[0]) == {topic} for pair, topic in zip(faq, FAQ_TOPICS)) else 0
    score += 15 if MIN_AUTHORED_CHARS <= authored_chars <= MAX_AUTHORED_CHARS and MIN_H2 <= len(heading_values) <= MAX_H2 else 0
    score += 10 if len(paragraph_norms) == len(set(paragraph_norms)) and len(sentence_norms) == len(set(sentence_norms)) else 0
    audit.check(score >= 90, "geo_page_score", f"{rel}: {score}")

    return DetailResult(
        category=category.slug,
        locality=source.locality,
        canonical=canonical,
        supported=supported,
        hrefs=hrefs,
        authored_paragraphs=tuple(paragraph_norms),
        authored_sentences=tuple(sentence_norms),
        headings=tuple(heading_norms),
        meta_description=description,
        geo_score=score,
        physical_id=physical.physical_id,
        physical_semantic=physical_semantic,
    )


@dataclass
class HubResult:
    category: str
    canonical: str
    hrefs: tuple[str, ...]
    detail_links: tuple[str, ...]


def audit_hub_breadcrumb(
    node: Mapping[str, Any], category: Category, canonical: str, audit: Audit, rel: str
) -> None:
    items = as_list(node.get("itemListElement"))
    expected = (
        (1, "홈", f"{BASE_URL}/"),
        (2, "과목별학원", f"{BASE_URL}/과목별학원/"),
        (3, category.slug, canonical),
    )
    audit.check(len(items) == len(expected), "hub_breadcrumb_count", f"{rel}: {len(items)}")
    if len(items) != len(expected):
        return
    for item, (position, name, url) in zip(items, expected):
        audit.check(isinstance(item, dict) and node_types(item) == {"ListItem"}, "hub_breadcrumb_item", rel)
        if not isinstance(item, dict):
            continue
        audit.check(item.get("position") == position, "hub_breadcrumb_position", rel)
        audit.check(clean(item.get("name")) == name, "hub_breadcrumb_name", f"{rel}: {item.get('name')}")
        audit.check(url_key(clean(item.get("item") or item.get("url"))) == url_key(url), "hub_breadcrumb_url", rel)


def audit_hub_page(
    path: Path,
    data: bytes,
    root: Path,
    sources: Mapping[str, SourceRow],
    category: Category,
    sitemap_keys: set[str],
    overrides: Mapping[Path, bytes],
    audit: Audit,
) -> HubResult | None:
    rel = path.relative_to(root).as_posix()
    try:
        text = decode_utf8(data, path)
        dom = parse_html(text)
    except Exception as exc:
        audit.add("hub_html_parse", f"{rel}: {exc}")
        return None
    audit.check(not re.search(rb"[ \t]+(?:\r?\n|$)", data), "hub_trailing_whitespace", rel)
    mains = dom.find_all("main", attr="data-grade-directory")
    audit.check(len(mains) == 1, "hub_main_count", f"{rel}: {len(mains)}")
    main = mains[0] if len(mains) == 1 else dom
    expected_canonical = f"{BASE_URL}/과목별학원/{category.slug}/"
    expected_h1 = category.slug
    title = title_value(dom)
    h1 = first_h1(dom)
    description = meta_value(dom, name="description")
    canonical = canonical_value(dom)
    robots = meta_value(dom, name="robots").lower()
    audit.check(title == f"{expected_h1} | 영수학원", "hub_title", f"{rel}: {title}")
    audit.check(h1 == expected_h1, "hub_h1", f"{rel}: {h1}")
    audit.check(url_key(canonical) == url_key(expected_canonical), "hub_canonical", f"{rel}: {canonical}")
    audit.check(url_key(canonical) in sitemap_keys, "hub_canonical_sitemap", rel)
    audit.check(MIN_META_CHARS <= len(description) <= MAX_META_CHARS, "hub_meta_length", f"{rel}: {len(description)}")
    audit.check(meta_value(dom, prop="og:title") == title, "hub_og_title", rel)
    audit.check(meta_value(dom, prop="og:description") == description, "hub_og_description", rel)
    audit.check(url_key(meta_value(dom, prop="og:url")) == url_key(canonical), "hub_og_url", rel)
    audit.check("index" in robots and "follow" in robots and "noindex" not in robots and "nofollow" not in robots,
                "hub_robots", f"{rel}: {robots}")

    hrefs, _broken = audit_local_resources(dom, canonical, root, overrides, audit, rel)
    prefix = f"/과목별학원/{category.slug}/"
    detail_links = tuple(
        value for value in hrefs
        if route_for_url(value).startswith(prefix) and route_for_url(value) != prefix
    )
    expected_links = tuple(
        url_key(f"{BASE_URL}/과목별학원/{category.slug}/{source.slug}/")
        for source in sources.values()
    )
    audit.check(len(detail_links) == EXPECTED_SOURCE_ROWS, "hub_detail_link_count", f"{rel}: {len(detail_links)}")
    audit.check(len(set(detail_links)) == EXPECTED_SOURCE_ROWS, "hub_detail_link_unique", rel)
    audit.check(detail_links == expected_links, "hub_detail_link_order", f"{rel}: {len(detail_links)}")
    town_nodes = main.find_all("a", attr="data-subject-town")
    audit.check(len(town_nodes) == EXPECTED_SOURCE_ROWS, "hub_search_town_count", f"{rel}: {len(town_nodes)}")
    audit.check(all(clean(node.attrs.get("data-search")) for node in town_nodes), "hub_search_data", rel)
    if len(town_nodes) == EXPECTED_SOURCE_ROWS:
        for node, source in zip(town_nodes, sources.values()):
            search_value = normalized_literal(node.attrs.get("data-search"))
            audit.check(
                all(normalized_literal(value) in search_value for value in (source.locality, source.region, source.city)),
                "hub_search_source_parity",
                f"{rel}: {source.locality}: {node.attrs.get('data-search')}",
            )
    search_inputs = main.find_all("input", attr="data-subject-search")
    search_resets = main.find_all(attr="data-subject-search-reset")
    search_statuses = main.find_all(attr="data-subject-search-status")
    audit.check(len(search_inputs) == len(search_resets) == len(search_statuses) == 1,
                "hub_search_controls", f"{rel}: {(len(search_inputs), len(search_resets), len(search_statuses))}")
    if search_inputs:
        audit.check(search_inputs[0].attrs.get("type") == "search" and search_inputs[0].attrs.get("autocomplete") == "off",
                    "hub_search_input_policy", rel)
    if search_statuses:
        audit.check(search_statuses[0].attrs.get("aria-live") == "polite" and "371" in search_statuses[0].text(),
                    "hub_search_status", rel)
    inline_scripts = "\n".join(raw_node_text(node) for node in dom.find_all("script") if node.attrs.get("type", "").lower() != "application/ld+json")
    audit.check(all(token in inline_scripts for token in ("data-subject-search", "data-subject-town", "addEventListener", "input.value = ''")),
                "hub_search_script", rel)

    try:
        graph, payloads = json_graph(dom)
    except Exception as exc:
        audit.add("hub_jsonld_parse", f"{rel}: {exc}")
        graph, payloads = [], []
    audit.check(len([node for node in dom.find_all("script") if node.attrs.get("type", "").lower() == "application/ld+json"]) == 1,
                "hub_jsonld_script_count", rel)
    audit.check(len(graph_nodes(graph, "CollectionPage")) == 1, "hub_collectionpage_count", rel)
    audit.check(len(graph_nodes(graph, "BreadcrumbList")) == 1, "hub_breadcrumb_schema_count", rel)
    lists = graph_nodes(graph, "ItemList")
    audit.check(len(lists) == 1, "hub_itemlist_count", f"{rel}: {len(lists)}")
    audit.check(not graph_nodes(graph, "Service"), "hub_service_forbidden", rel)
    audit.check(not graph_nodes(graph, "FAQPage"), "hub_faq_forbidden", rel)
    audit.check(not any({"EducationalOrganization", "LocalBusiness"}.intersection(node_types(node)) for node in graph),
                "hub_physical_forbidden", rel)
    if graph_nodes(graph, "CollectionPage"):
        page = graph_nodes(graph, "CollectionPage")[0]
        audit.check(clean(page.get("@id")) == f"{canonical}#webpage", "hub_collection_id", rel)
        audit.check(url_key(clean(page.get("url"))) == url_key(canonical), "hub_collection_url", rel)
        audit.check(clean(page.get("name")) in {h1, title}, "hub_collection_name", rel)
        audit.check(clean(page.get("description")) == description, "hub_collection_description", rel)
    if graph_nodes(graph, "BreadcrumbList"):
        audit_hub_breadcrumb(graph_nodes(graph, "BreadcrumbList")[0], category, canonical, audit, rel)
    if lists:
        items = as_list(lists[0].get("itemListElement"))
        urls = tuple(
            url_key(clean(item.get("url") or item.get("item")))
            for item in items if isinstance(item, dict)
        )
        names = tuple(clean(item.get("name")) for item in items if isinstance(item, dict))
        expected_names = tuple(f"{source.locality} {category.slug}" for source in sources.values())
        audit.check(urls == expected_links, "hub_itemlist_urls", rel)
        audit.check(names == expected_names, "hub_itemlist_names", rel)
        audit.check(tuple(item.get("position") for item in items if isinstance(item, dict)) == tuple(range(1, len(items) + 1)),
                    "hub_itemlist_positions", rel)
        audit.check(lists[0].get("numberOfItems") in (None, EXPECTED_SOURCE_ROWS), "hub_itemlist_number", rel)
    json_text = " ".join(value for payload in payloads for value in json_strings(payload))
    audit.check(not SEARCH_META_RE.search(" ".join((title, description, json_text))), "hub_search_meta_seed", rel)
    audit.check(not IRRELEVANT_SEED_RE.search(" ".join((title, description, main.text(), json_text))), "hub_irrelevant_seed", rel)
    return HubResult(category.slug, canonical, hrefs, detail_links)


def audit_cross_page_contract(
    details: Sequence[DetailResult],
    hubs: Sequence[HubResult],
    parent_dom: Node,
    sitemap_keys: set[str],
    audit: Audit,
) -> dict[str, Any]:
    category_counts = Counter(item.category for item in details)
    supported_counts = Counter(item.category for item in details if item.supported)
    unsupported_counts = Counter(item.category for item in details if not item.supported)
    audit.check(len(details) == EXPECTED_NEW_DETAILS, "detail_result_count", len(details))
    audit.check(len(hubs) == EXPECTED_NEW_HUBS, "hub_result_count", len(hubs))
    for category in CATEGORIES:
        audit.check(category_counts[category.slug] == EXPECTED_SOURCE_ROWS, "category_detail_count", f"{category.slug}: {category_counts[category.slug]}")
        audit.check(supported_counts[category.slug] == category.supported_expected,
                    "category_supported_count", f"{category.slug}: {supported_counts[category.slug]}")
        audit.check(unsupported_counts[category.slug] == category.unsupported_expected,
                    "category_unsupported_count", f"{category.slug}: {unsupported_counts[category.slug]}")
    audit.check(sum(supported_counts.values()) == EXPECTED_SUPPORTED, "supported_total", sum(supported_counts.values()))
    audit.check(sum(unsupported_counts.values()) == EXPECTED_UNSUPPORTED, "unsupported_total", sum(unsupported_counts.values()))

    canonicals = [url_key(item.canonical) for item in details]
    audit.check(len(canonicals) == len(set(canonicals)), "detail_canonical_duplicates", len(canonicals) - len(set(canonicals)))
    meta_counter = Counter(item.meta_description for item in details)
    meta_dupes = {value: count for value, count in meta_counter.items() if value and count > 1}
    audit.check(not meta_dupes, "meta_description_duplicates", list(meta_dupes.items())[:3])

    paragraph_df: Counter[str] = Counter()
    sentence_df: Counter[str] = Counter()
    h2_df: Counter[str] = Counter()
    paragraph_pages: dict[str, list[str]] = defaultdict(list)
    sentence_pages: dict[str, list[str]] = defaultdict(list)
    h2_pages: dict[str, list[str]] = defaultdict(list)
    for item in details:
        for value in set(value for value in item.authored_paragraphs if value):
            paragraph_df[value] += 1
            paragraph_pages[value].append(item.canonical)
        for value in set(value for value in item.authored_sentences if value):
            sentence_df[value] += 1
            sentence_pages[value].append(item.canonical)
        for value in set(value for value in item.headings if value):
            h2_df[value] += 1
            h2_pages[value].append(item.canonical)
    paragraph_max = max(paragraph_df.values(), default=0)
    sentence_max = max(sentence_df.values(), default=0)
    h2_max = max(h2_df.values(), default=0)

    def peak(counter: Counter[str], pages: Mapping[str, Sequence[str]]) -> dict[str, Any]:
        if not counter:
            return {"df": 0, "normalized": "", "pages": []}
        value, count = max(counter.items(), key=lambda item: (item[1], item[0]))
        return {"df": count, "normalized": value[:500], "pages": list(pages[value][:5])}

    paragraph_peak = peak(paragraph_df, paragraph_pages)
    sentence_peak = peak(sentence_df, sentence_pages)
    h2_peak = peak(h2_df, h2_pages)
    audit.check(paragraph_max <= MAX_CROSS_DOCUMENT_FREQUENCY, "cross_paragraph_df", paragraph_peak)
    audit.check(sentence_max <= MAX_CROSS_DOCUMENT_FREQUENCY, "cross_sentence_df", sentence_peak)
    audit.check(h2_max <= MAX_H2_FREQUENCY, "cross_h2_df", h2_peak)

    physical_semantics: dict[str, set[str]] = defaultdict(set)
    for item in details:
        if item.physical_semantic is not None:
            physical_semantics[item.physical_id].add(item.physical_semantic)
    audit.check(len(physical_semantics) == EXPECTED_PHYSICAL, "physical_id_distinct", len(physical_semantics))
    conflicts = {key: len(values) for key, values in physical_semantics.items() if len(values) != 1}
    audit.check(not conflicts, "physical_semantic_conflict", list(conflicts.items())[:5])

    all_hrefs = [href for item in details for href in item.hrefs] + [href for item in hubs for href in item.hrefs]
    parent_canonical = PARENT_PROTECTED["canonical"]
    for anchor in parent_dom.find_all("a"):
        href = clean(anchor.attrs.get("href"))
        if not href or href.startswith(("#", "tel:", "sms:", "mailto:", "javascript:")):
            continue
        absolute = urllib.parse.urljoin(parent_canonical, href)
        if urllib.parse.urlsplit(absolute).hostname == urllib.parse.urlsplit(BASE_URL).hostname:
            all_hrefs.append(url_key(absolute))
    non_sitemap_hrefs = [href for href in all_hrefs if href not in sitemap_keys]
    audit.check(not non_sitemap_hrefs, "internal_href_not_sitemap", f"{len(non_sitemap_hrefs)}: {non_sitemap_hrefs[:5]}")
    inbound = Counter(all_hrefs)
    orphans = [canonical for canonical in canonicals if inbound[canonical] == 0]
    audit.check(not orphans, "new_detail_orphan", f"{len(orphans)}: {orphans[:5]}")

    scores = [item.geo_score for item in details]
    mean_score = round(sum(scores) / len(scores), 3) if scores else 0
    min_score = min(scores, default=0)
    audit.check(min_score >= 90, "geo_min_score", min_score)
    audit.check(mean_score >= 95, "geo_mean_score", mean_score)
    return {
        "details": len(details),
        "hubs": len(hubs),
        "supported": sum(supported_counts.values()),
        "unsupported": sum(unsupported_counts.values()),
        "category_details": dict(category_counts),
        "category_supported": dict(supported_counts),
        "category_unsupported": dict(unsupported_counts),
        "meta_duplicate_groups": len(meta_dupes),
        "diversity": {
            "paragraph_max_df": paragraph_max,
            "sentence_max_df": sentence_max,
            "h2_max_df": h2_max,
            "paragraph_peak": paragraph_peak,
            "sentence_peak": sentence_peak,
            "h2_peak": h2_peak,
            "paragraph_threshold": MAX_CROSS_DOCUMENT_FREQUENCY,
            "sentence_threshold": MAX_CROSS_DOCUMENT_FREQUENCY,
            "h2_threshold": MAX_H2_FREQUENCY,
        },
        "physical_ids": len(physical_semantics),
        "physical_conflicts": len(conflicts),
        "internal_hrefs": len(all_hrefs),
        "broken_or_non_sitemap_hrefs": len(non_sitemap_hrefs),
        "orphans": len(orphans),
        "geo": {
            "rubric": {
                "indexability_identity": 10,
                "source_grounded_facts": 25,
                "schema_visible_parity": 20,
                "four_direct_faq_answers": 20,
                "authored_depth_structure": 15,
                "within_page_diversity": 10,
            },
            "min": min_score,
            "mean": mean_score,
            "required_min": 90,
            "required_mean": 95,
        },
    }


def selected_target_manifest(
    root: Path, paths: Iterable[Path], overrides: Mapping[Path, bytes]
) -> tuple[int, int, str]:
    entries = []
    for path in paths:
        if exists_for(path, overrides):
            entries.append((path.relative_to(root).as_posix(), bytes_for(path, overrides)))
    return manifest_entries(entries)


def source_integrity(common_dir: Path, source_dir: Path, audit: Audit) -> dict[str, Any]:
    common_observed: dict[str, str] = {}
    for name, expected in COMMON_FILE_SHA256.items():
        path = common_dir / name
        digest = sha256_bytes(path.read_bytes()) if path.is_file() else "missing"
        common_observed[name] = digest
        audit.check(digest == expected, "common_source_sha", f"{name}: {digest}")
    manuscript_observed: dict[str, str] = {}
    for name, expected in MANUSCRIPT_SHA256.items():
        path = source_dir / name
        digest = sha256_bytes(path.read_bytes()) if path.is_file() else "missing"
        manuscript_observed[name] = digest
        audit.check(digest == expected, "manuscript_source_sha", f"{name}: {digest}")
    return {"common": common_observed, "manuscripts": manuscript_observed}


def source_boundary_contract(
    sources: Mapping[str, SourceRow], physical: Mapping[tuple[str, str], PhysicalFact], audit: Audit
) -> dict[str, Any]:
    audit.check(len(sources) == EXPECTED_SOURCE_ROWS, "source_row_count", len(sources))
    audit.check(len(physical) == EXPECTED_PHYSICAL, "source_physical_count", len(physical))
    supported: Counter[str] = Counter()
    unsupported: Counter[str] = Counter()
    for category in CATEGORIES:
        for source in sources.values():
            target = supported if category.grade in source.grades(category.subject) else unsupported
            target[category.slug] += 1
        audit.check(supported[category.slug] == category.supported_expected,
                    "source_supported_category", f"{category.slug}: {supported[category.slug]}")
        audit.check(unsupported[category.slug] == category.unsupported_expected,
                    "source_unsupported_category", f"{category.slug}: {unsupported[category.slug]}")
    audit.check(sum(supported.values()) == EXPECTED_SUPPORTED, "source_supported_total", sum(supported.values()))
    audit.check(sum(unsupported.values()) == EXPECTED_UNSUPPORTED, "source_unsupported_total", sum(unsupported.values()))
    blank_guide = sum(not item.guide_raw for item in sources.values())
    blank_fee = sum(not item.fee_url for item in sources.values())
    blank_high = sum(not item.high_schools_raw for item in sources.values())
    offlocal = sum(normalized_literal(item.locality) not in normalized_literal(item.address) for item in sources.values())
    audit.check(blank_guide == 118, "source_blank_guide", blank_guide)
    audit.check(blank_fee == 2, "source_blank_fee", blank_fee)
    audit.check(blank_high == 63, "source_blank_high_schools", blank_high)
    audit.check(offlocal == 321, "source_offlocal_boundary", offlocal)

    sejong = [item for item in sources.values() if item.locality in {"다정동", "새롬동"}]
    audit.check(
        len(sejong) == 2
        and {item.locality for item in sejong} == {"다정동", "새롬동"}
        and {item.region for item in sejong} == {"충청"}
        and {item.city for item in sejong} == {"새롬중앙로"}
        and {official_address_parts(item.address) for item in sejong}
        == {("세종특별자치시", "새롬동")},
        "source_sejong_boundary",
        [(item.locality, item.region, item.city, item.address) for item in sejong],
    )
    return {
        "rows": len(sources),
        "physical": len(physical),
        "supported": sum(supported.values()),
        "unsupported": sum(unsupported.values()),
        "supported_by_category": dict(supported),
        "unsupported_by_category": dict(unsupported),
        "blank_guide": blank_guide,
        "blank_fee": blank_fee,
        "blank_high_schools": blank_high,
        "offlocal_address_rows": offlocal,
        "sejong_rows": len(sejong),
    }


def synthetic_self_test() -> dict[str, Any]:
    checks = {
        "url_unicode_percent_equivalence": url_key(f"{BASE_URL}/과목별학원/고1수학학원/")
        == url_key(f"{BASE_URL}/%EA%B3%BC%EB%AA%A9%EB%B3%84%ED%95%99%EC%9B%90/%EA%B3%A01%EC%88%98%ED%95%99%ED%95%99%EC%9B%90/"),
        "school_split_dedupe": split_high_schools("가고, 나고/가고. 다고") == ("가고", "나고", "다고"),
        "generic_school_not_entity": split_high_schools("지역내 모든 고등학교 가능") == (),
        "guide_url_removed": clean_location_guide("https://naver.me/x 학원 위치 안내드립니다^^~ 건물입니다~") == "건물입니다",
        "guide_typo_fixed": clean_location_guide("엘레베이터 이용") == "엘리베이터 이용",
        "guide_control_symbol_removed": clean_location_guide("\x08 ✅주차장,건물") == "주차장, 건물",
        "guide_terminal_comma_removed": clean_location_guide("건물,") == "건물",
        "faq_grade_topic": faq_topics("대상 학년은 원자료에서 어떻게 확인하나요?") == {"grade"},
        "faq_school_topic": faq_topics("고등학교 참고 정보는 무엇인가요?") == {"schools"},
        "faq_location_topic": faq_topics("주소와 위치 안내는 어디에서 확인하나요?") == {"location"},
        "faq_fee_topic": faq_topics("교습비 링크는 어디에서 확인하나요?") == {"fee"},
        "unsupported_positive_detected": bool(POSITIVE_GRADE_RE.search("고2 수업을 운영합니다.")),
        "unsupported_negative_allowed": bool(NEGATIVE_GRADE_RE.search("고2는 기재되어 있지 않습니다.")),
        "phone_exact_detected": bool(PHONE_VALUE_RE.fullmatch("+82-10-6839-8283")),
        "phone_substring_not_detected": not PHONE_VALUE_RE.fullmatch("rep-010.jpg"),
        "bad_particle_detected": bool(KNOWN_BAD_COPY_RE.search("고2은 기재되어 있지 않습니다.")),
        "adjacent_word_repeat_detected": bool(ADJACENT_WORD_REPEAT_RE.search("오답 기록 기록 방식을 확인합니다.")),
        "adjacent_word_particle_repeat_detected": bool(ADJACENT_WORD_REPEAT_RE.search("내신 범위 범위를 확인합니다.")),
        "adjacent_word_repeat_clean": not ADJACENT_WORD_REPEAT_RE.search("오답 기록 방식을 확인합니다."),
        "h2_word_repeat_fixture": tuple(
            token for token, count in Counter(re.findall(r"[가-힣]{2,}", "확인 질문으로 바꿀 개념 확인 기준")).items()
            if count > 1
        ) == ("확인",),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise AssertionError(f"synthetic self-test failed: {failed}")
    return {"status": "PASS", "cases": len(checks)}


def audit_release(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    source_dir = args.source_dir.resolve()
    common_dir = args.common_dir.resolve()
    audit = Audit()
    self_test = synthetic_self_test()
    pre_repo = tree_manifest(root)
    pre_source = tree_manifest(source_dir)
    pre_common = tree_manifest(common_dir)
    integrity = source_integrity(common_dir, source_dir, audit)

    try:
        sources, physical, load_metrics = load_sources(common_dir)
    except Exception as exc:
        audit.add("source_load", exc)
        sources, physical, load_metrics = {}, {}, {}
    boundary = source_boundary_contract(sources, physical, audit) if sources else {}
    manuscript_facts: dict[str, dict[str, ManuscriptFact]] = {}
    try:
        if sources:
            manuscripts, manuscript_facts = validate_manuscripts(source_dir, sources)
        else:
            manuscripts = {}
    except Exception as exc:
        audit.add("manuscript_contract", exc)
        manuscripts = {}

    details_expected, hubs_expected, authorized = expected_paths(root, sources)
    projection_path = args.projected_content_script.resolve() if args.projected_content_script else None
    overrides, projection = load_projection(
        projection_path, root, source_dir, common_dir, authorized, audit
    )
    records, sitemap_keys, sitemap_metrics = audit_sitemap_and_immutability(
        root, sources, overrides, audit
    )
    llms_metrics = audit_llms(root, overrides, audit)
    parent_metrics = audit_parent_hub(root, overrides, audit)
    root_brand = audit_root_brand(root, audit)

    details: list[DetailResult] = []
    for category in CATEGORIES:
        for source in sources.values():
            path = root / "과목별학원" / category.slug / source.slug / "index.html"
            if not exists_for(path, overrides):
                audit.add("new_detail_missing", path.relative_to(root).as_posix())
                continue
            fact = physical.get(source.physical_key)
            if fact is None:
                audit.add("physical_source_missing", source.physical_key)
                continue
            result = audit_detail_page(
                path, bytes_for(path, overrides), root, source, fact, category,
                manuscript_facts[category.slug][source.locality],
                sitemap_keys, overrides, audit,
            )
            if result is not None:
                details.append(result)

    hubs: list[HubResult] = []
    for category in CATEGORIES:
        path = root / "과목별학원" / category.slug / "index.html"
        if not exists_for(path, overrides):
            audit.add("new_hub_missing", path.relative_to(root).as_posix())
            continue
        result = audit_hub_page(
            path, bytes_for(path, overrides), root, sources, category,
            sitemap_keys, overrides, audit,
        )
        if result is not None:
            hubs.append(result)

    parent_path = root / "과목별학원" / "index.html"
    parent_dom = parse_html(decode_utf8(bytes_for(parent_path, overrides), parent_path))
    aggregate = audit_cross_page_contract(details, hubs, parent_dom, sitemap_keys, audit)

    target_manifest = selected_target_manifest(root, authorized, overrides)
    audit.check(target_manifest[0] == EXPECTED_PLAN_DOCUMENTS, "final_target_count", target_manifest[0])
    audit.check(len(records) == EXPECTED_FINAL_URLS, "final_sitemap_count", len(records))

    post_repo = tree_manifest(root)
    post_source = tree_manifest(source_dir)
    post_common = tree_manifest(common_dir)
    audit.check(post_repo == pre_repo, "repository_freeze", f"{pre_repo} -> {post_repo}")
    audit.check(post_source == pre_source, "manuscript_freeze", f"{pre_source} -> {post_source}")
    audit.check(post_common == pre_common, "common_freeze", f"{pre_common} -> {post_common}")

    return {
        "ok": not audit.errors,
        "status": "PASS" if not audit.errors else "HOLD",
        "mode": "projected" if projection_path else "actual",
        "root": str(root),
        "errors": audit.errors,
        "error_counts": dict(sorted(audit.counts.items())),
        "error_total": sum(audit.counts.values()),
        "source_integrity": integrity,
        "self_test": self_test,
        "source_load": load_metrics,
        "source_boundary": boundary,
        "manuscripts": manuscripts,
        "projection": projection,
        "sitemap": sitemap_metrics,
        "llms": llms_metrics,
        "parent_hub": parent_metrics,
        "root_brand": root_brand,
        "aggregate": aggregate,
        "target_manifest": {
            "count": target_manifest[0],
            "bytes": target_manifest[1],
            "sha256": target_manifest[2],
        },
        "freeze": {
            "repository_pre": {"count": pre_repo[0], "bytes": pre_repo[1], "sha256": pre_repo[2]},
            "repository_post": {"count": post_repo[0], "bytes": post_repo[1], "sha256": post_repo[2]},
            "manuscripts_pre": {"count": pre_source[0], "bytes": pre_source[1], "sha256": pre_source[2]},
            "manuscripts_post": {"count": post_source[0], "bytes": post_source[1], "sha256": post_source[2]},
            "common_pre": {"count": pre_common[0], "bytes": pre_common[1], "sha256": pre_common[2]},
            "common_post": {"count": post_common[0], "bytes": post_common[1], "sha256": post_common[2]},
            "stable": pre_repo == post_repo and pre_source == post_source and pre_common == post_common,
        },
        "thresholds": {
            "within_page_sentence_duplicate": 0,
            "within_page_paragraph_duplicate": 0,
            "cross_sentence_df_max": MAX_CROSS_DOCUMENT_FREQUENCY,
            "cross_paragraph_df_max": MAX_CROSS_DOCUMENT_FREQUENCY,
            "cross_h2_df_max": MAX_H2_FREQUENCY,
            "authored_locality_max": MAX_LOCALITY_MENTIONS,
            "exact_query_max": MAX_EXACT_QUERY_MENTIONS,
            "authored_chars": [MIN_AUTHORED_CHARS, MAX_AUTHORED_CHARS],
            "h2_count": [MIN_H2, MAX_H2],
            "meta_chars": [MIN_META_CHARS, MAX_META_CHARS],
            "editorial_sentence_chars_max": MAX_EDITORIAL_SENTENCE_CHARS,
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    parser.add_argument("--common-dir", type=Path, default=COMMON_DIR)
    parser.add_argument("--projected-content-script", type=Path)
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    try:
        report = audit_release(args)
    except Exception as exc:
        report = {
            "ok": False,
            "status": "HOLD",
            "fatal": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
