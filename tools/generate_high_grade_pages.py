from __future__ import annotations

"""Generate the four high-school grade/subject directories for 영수학원.com.

The default command is a read-only projection.  ``--apply`` is deliberately
explicit and writes only the paths listed by :func:`build_plan`, after every
source, content, link, schema, sitemap, and idempotency check has passed.

The supplied ZIP manuscripts are used as topic inputs, never as a source of
centre facts or operational promises.  Centre facts come only from the common
CSV files pinned below.
"""

import argparse
import csv
import hashlib
import html
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Sequence
from urllib.parse import quote, unquote, urlsplit
from zipfile import ZipFile

from PIL import Image

from add_subject_anchor_tocs import enhance_detail_html


DOMAIN = "https://xn--9p4bn5e1r987b.com"
SITE_NAME = "영수학원"
ROOT_ORG_ID = f"{DOMAIN}/#organization"
CENTRAL_PHONE_DISPLAY = "010-6839-8283"
CENTRAL_PHONE_LINK = "01068398283"
PUBLISH_DATE = "2026-08-18"
PUBLISH_DATE_KO = "2026년 8월 18일"
PARENT = "과목별학원"

SOURCE_FILE_HASHES = {
    "고1 수학학원.zip": "5fd763925514e50e0aa8c1caf1247d04c24944963a841201c6aa5e72c5df16c2",
    "고1 영어학원.zip": "a7935dde7ae4853fb20272913aa3a13d5537e070294185469148331aa5a04580",
    "고2 수학학원.zip": "a238c5555772d1a6eb6b7fb3f3c759b68c73ab0c4bfdb01a7d6dfc1838e878c6",
    "고2 영어학원.zip": "7eadf035911ae0ad5b626d122eac6dcf076817e78e808e38fb0c0531347c8629",
}

COMMON_FILE_HASHES = {
    "센터정보 정리.csv": "3ffbd7b70273b6dc1c8435c53a3a25e32d2a173ba1bf51840654389bd8954e1a",
    "이미지링크.csv": "c1b4f87b2b62f659107dbf0a79a1d566e213e008fc4b7f30cfa656ffae814100",
    "타깃학교.csv": "08c73da41d47ed76bdfa318ff30c238cc12ba92a73b40e0ca2feacec9610ac0f",
    "EducationalOrganization.csv": "e44c9a78c8b272781d5c078e38b466f9d438127a76219661ff43ee2604766c22",
}


@dataclass(frozen=True)
class CategoryProfile:
    category: str
    zip_name: str
    grade_short: str
    grade_long: str
    grade_token: str
    subject: str
    subject_en: str
    grade_column: str
    focus: str
    intro_label: str

    @property
    def subject_label(self) -> str:
        return f"{self.grade_short} {self.subject}"

    @property
    def query_suffix(self) -> str:
        return f"{self.grade_short} {self.subject}학원"


CATEGORIES: tuple[CategoryProfile, ...] = (
    CategoryProfile("고1수학학원", "고1 수학학원.zip", "고1", "고등학교 1학년", "고1", "수학", "MATH", "가능학년\n(수학)", "개념·내신 점검", "HIGH 1 MATH"),
    CategoryProfile("고1영어학원", "고1 영어학원.zip", "고1", "고등학교 1학년", "고1", "영어", "ENGLISH", "가능학년\n(영어)", "어휘·독해·내신 점검", "HIGH 1 ENGLISH"),
    CategoryProfile("고2수학학원", "고2 수학학원.zip", "고2", "고등학교 2학년", "고2", "수학", "MATH", "가능학년\n(수학)", "개념 연결·오답 점검", "HIGH 2 MATH"),
    CategoryProfile("고2영어학원", "고2 영어학원.zip", "고2", "고등학교 2학년", "고2", "영어", "ENGLISH", "가능학년\n(영어)", "독해·서술형·내신 점검", "HIGH 2 ENGLISH"),
)

ALL_CATEGORY_CARDS: tuple[tuple[str, str], ...] = (
    ("중2수학학원", "중2 수학 내신·오답관리 지역별 안내"),
    ("중2영어학원", "중2 영어 내신·서술형 대비 지역별 안내"),
    ("중3수학학원", "중3 수학 내신전략·오답관리 지역별 안내"),
    ("중3영어학원", "중3 영어 내신·고1 연계 대비 지역별 안내"),
    ("고1수학학원", "고1 수학 개념·내신 점검 지역별 안내"),
    ("고1영어학원", "고1 영어 어휘·독해·내신 점검 지역별 안내"),
    ("고2수학학원", "고2 수학 개념 연결·오답 점검 지역별 안내"),
    ("고2영어학원", "고2 영어 독해·서술형·내신 점검 지역별 안내"),
)

SECTION_NAMES = ("페이지타이틀", "메타설명", "본문", "FAQ", "학부모후기", "JSON-LD 요약")
SECTION_RE = re.compile(r"^\[(페이지타이틀|메타설명|본문|FAQ|학부모후기|JSON-LD 요약)\]\s*$", re.MULTILINE)
GENERIC_HIGH_SCHOOL_RE = re.compile(r"지역\s*내\s*모든\s*고등학교\s*가능")
MISSING_CUE_RE = re.compile(r"미기재|공란|비어|없|제공되지|기재되어 있지|확인되지")
UNSAFE_COPY_RE = re.compile(
    r"검색엔진|\bSEO\b|키워드|검색어|검색해 들어온|검색한 학부모|"
    r"학원창업|학원전자계약|학원매니저|학원공지|학원운영|학원환불|"
    r"회원관리|예약관리|수납관리|매출관리|관리솔루션|관리프로그램|알림톡|개인정보관리",
    re.IGNORECASE,
)
SERVICE_CERTAINTY_RE = re.compile(
    r"(?:센터|학원|지역)\s*(?:수업|과정)(?:에서는|에서|의|을|를)|"
    r"수업이\s*시작되면|실제\s*수업에서|교사가\s+[^.!?]{0,40}(?:제공|진행|관리)|"
    r"(?:제공|운영|진행)(?:한다|합니다|된다|됩니다|하고 있다)"
)

TOPIC_CUES: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "수학": (
        ("개념 확인", ("개념", "개념이해")),
        ("오답 기록", ("오답", "틀린 문제")),
        ("서술형 풀이", ("서술형", "풀이 과정")),
        ("내신 범위", ("내신", "시험 범위")),
        ("교과서 점검", ("교과서",)),
        ("기출 활용", ("기출",)),
        ("문제집 구성", ("문제집", "교재")),
        ("계산 점검", ("계산",)),
        ("시간 배분", ("시간 관리", "시간 배분", "풀이 시간")),
        ("진도 확인", ("진도",)),
        ("복습 간격", ("복습", "재학습")),
        ("과제 기록", ("숙제", "과제")),
        ("유형 연결", ("유형",)),
        ("수행평가 준비", ("수행평가",)),
        ("진단 자료", ("진단", "레벨테스트")),
        ("질문 기록", ("질문",)),
        ("학습 계획", ("학습 계획", "계획표", "플래너")),
        ("학습 습관", ("공부 습관", "학습 습관")),
    ),
    "영어": (
        ("어휘 복습", ("어휘", "단어")),
        ("문법 적용", ("문법",)),
        ("독해 근거", ("독해", "근거 문장")),
        ("서술형 답안", ("서술형",)),
        ("영작 점검", ("영작",)),
        ("교과서 본문", ("교과서", "본문")),
        ("듣기 기록", ("듣기",)),
        ("내신 범위", ("내신", "시험 범위")),
        ("기출 활용", ("기출",)),
        ("오답 기록", ("오답", "틀린 문제")),
        ("복습 간격", ("복습", "재학습")),
        ("과제 기록", ("숙제", "과제")),
        ("수행평가 준비", ("수행평가",)),
        ("시간 배분", ("시간 관리", "시간 배분", "풀이 시간")),
        ("해석 근거", ("해석",)),
        ("변형 문항", ("변형",)),
        ("진단 자료", ("진단", "레벨테스트")),
        ("질문 기록", ("질문",)),
        ("학습 계획", ("학습 계획", "계획표", "플래너")),
        ("학습 습관", ("공부 습관", "학습 습관")),
    ),
}


@dataclass(frozen=True)
class Manuscript:
    locality: str
    filename: str
    raw: str
    sections: Mapping[str, str]
    sha256: str
    cues: tuple[str, ...]


@dataclass(frozen=True)
class SourceBundle:
    rows: tuple[Mapping[str, str], ...]
    row_by_locality: Mapping[str, Mapping[str, str]]
    images_by_locality: Mapping[str, Mapping[str, str]]
    org_by_locality: Mapping[str, Mapping[str, str]]
    manuscripts: Mapping[str, Mapping[str, Manuscript]]
    physical_rows: Mapping[str, tuple[Mapping[str, str], ...]]


@dataclass(frozen=True)
class Document:
    path: Path
    before: bytes | None
    after: bytes
    role: str
    category: str = ""
    locality: str = ""
    supported: bool | None = None
    source_sha256: str = ""
    source_cues: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        return self.before != self.after


@dataclass(frozen=True)
class BuildPlan:
    root: Path
    source_dir: Path
    common_dir: Path
    documents: tuple[Document, ...]
    authorized_paths: frozenset[Path]
    idempotent: bool
    errors: tuple[str, ...]
    metrics: Mapping[str, object] = field(default_factory=dict)
    external_manifest: str = ""

    @property
    def changes(self) -> tuple[Document, ...]:
        return tuple(document for document in self.documents if document.changed)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False).replace("</", "<\\/")


def to_crlf(text: str) -> bytes:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n").encode("utf-8")


def slug_ko(value: str) -> str:
    value = re.sub(r"\s+", "", value.strip())
    return re.sub(r'[\\/:*?"<>|#%&+]', "", value)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def split_grade_tokens(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(part.strip() for part in re.split(r"[,/\.\s]+", value) if part.strip()))


def parse_high_schools(value: str) -> tuple[str, ...]:
    if not value.strip() or GENERIC_HIGH_SCHOOL_RE.search(value):
        return ()
    return tuple(dict.fromkeys(part for part in re.split(r"[,/\.\s]+", value.strip()) if part))


def clean_location_guide(value: str) -> str:
    cleaned = html.unescape(value or "")
    cleaned = re.sub(r"(?:https?://|www\.)[^\s<>()]+", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"학원\s*위치\s*안내드립니다", " ", cleaned)
    cleaned = re.sub(r"\^{2,}", "", cleaned)
    cleaned = cleaned.replace("엘레베이터", "엘리베이터")
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", cleaned)
    cleaned = re.sub(r"^[\U0001F000-\U0001FAFF\u2600-\u27BF]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"^[~\s]+|[~\s]+$", "", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r",(?=\S)", ", ", cleaned)
    cleaned = re.sub(r",\s*$", "", cleaned)
    cleaned = re.sub(r"\(\s*\)", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_topics(text: str, subject: str) -> tuple[str, ...]:
    normalized = normalize_space(text)
    found: list[str] = []
    for label, needles in TOPIC_CUES[subject]:
        if any(needle in normalized for needle in needles):
            found.append(label)
    return tuple(found)


def parse_manuscript(raw: str, filename: str, profile: CategoryProfile) -> Manuscript:
    matches = list(SECTION_RE.finditer(raw))
    if [match.group(1) for match in matches] != list(SECTION_NAMES):
        raise ValueError(f"manuscript section order mismatch: {filename}")
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        sections[match.group(1)] = raw[match.end():end].strip()
    expected_title = Path(filename).stem
    if normalize_space(sections["페이지타이틀"]) != normalize_space(expected_title):
        raise ValueError(f"manuscript title mismatch: {filename}")
    suffix = f" {profile.grade_short} {profile.subject}학원"
    if not expected_title.endswith(suffix):
        raise ValueError(f"manuscript filename contract mismatch: {filename}")
    locality = expected_title[:-len(suffix)]
    cues = extract_topics("\n".join(sections[name] for name in ("본문", "FAQ", "학부모후기")), profile.subject)
    if len(cues) < 4:
        raise ValueError(f"fewer than four safe manuscript cues: {filename}: {cues}")
    return Manuscript(locality, filename, raw, sections, sha256_bytes(raw.encode("utf-8")), cues)


def physical_key(row: Mapping[str, str]) -> str:
    return "\0".join((row["교육지원청명칭"].strip(), row["센터 주소"].strip()))


def physical_id(row: Mapping[str, str]) -> str:
    digest = hashlib.sha256(physical_key(row).encode("utf-8")).hexdigest()[:20]
    return f"{DOMAIN}/센터/{digest}/#organization"


def is_supported(row: Mapping[str, str], profile: CategoryProfile) -> bool:
    return profile.grade_token in split_grade_tokens(row.get(profile.grade_column, ""))


def grade_particle(profile: CategoryProfile, consonant: str, vowel: str) -> str:
    # Grade labels are conventionally read 고일/고이: 고1이·고1은, 고2가·고2는.
    return consonant if profile.grade_token == "고1" else vowel


def discover_reference_dirs(root: Path, source_dir: Path | None, common_dir: Path | None) -> tuple[Path, Path]:
    reference = root.parent / "참고자료"
    source = source_dir or reference / "사용한 원고" / "영수학원.com 추가 원고"
    common = common_dir or reference / "공통자료"
    if not source.is_dir() or not common.is_dir():
        raise FileNotFoundError(f"reference directories missing: source={source}, common={common}")
    return source.resolve(), common.resolve()


def load_sources(root: Path, source_dir: Path, common_dir: Path) -> SourceBundle:
    for filename, expected in SOURCE_FILE_HASHES.items():
        actual = sha256_file(source_dir / filename)
        if actual != expected:
            raise ValueError(f"source hash mismatch: {filename}: {actual}")
    for filename, expected in COMMON_FILE_HASHES.items():
        actual = sha256_file(common_dir / filename)
        if actual != expected:
            raise ValueError(f"common hash mismatch: {filename}: {actual}")

    rows = read_csv(common_dir / "센터정보 정리.csv")
    images = read_csv(common_dir / "이미지링크.csv")
    organizations = read_csv(common_dir / "EducationalOrganization.csv")
    target_schools = read_csv(common_dir / "타깃학교.csv")
    if not (len(rows) == len(images) == len(organizations) == len(target_schools) == 371):
        raise ValueError("common row counts must all be 371")
    locality_key = "근처 수업가능 동네"
    localities = [row[locality_key].strip() for row in rows]
    if len(set(localities)) != 371 or any(not value for value in localities):
        raise ValueError("centre locality key is blank or duplicated")
    row_by_locality = {row[locality_key].strip(): row for row in rows}
    images_by_locality = {row["제목"].strip(): row for row in images}
    org_by_locality = {row["서비스 제공 지역"].strip(): row for row in organizations}
    if set(images_by_locality) != set(localities) or set(org_by_locality) != set(localities):
        raise ValueError("image/organization locality set mismatch")

    target_keys = list(target_schools[0])
    if len(target_keys) < 4:
        raise ValueError("target school CSV shape mismatch")
    for index, (centre, target, org) in enumerate(zip(rows, target_schools, organizations)):
        if target[target_keys[0]].strip() != centre[locality_key].strip():
            raise ValueError(f"target school locality mismatch at row {index}")
        for source_key in ("타깃학교\n(초)", "타깃학교\n(중)", "타깃학교\n(고)"):
            matching = next((key for key in target if normalize_space(key) == normalize_space(source_key)), None)
            if matching is not None and target[matching].strip() != centre[source_key].strip():
                raise ValueError(f"target school value mismatch at row {index}: {source_key}")
        if org["서비스 제공 지역"].strip() != centre[locality_key].strip():
            raise ValueError(f"organization locality mismatch at row {index}")
        if org["실제 센터명"].strip() != centre["센터명"].strip():
            raise ValueError(f"organization centre mismatch at row {index}")
        if org["도로명 주소"].strip() != centre["센터 주소"].strip():
            raise ValueError(f"organization address mismatch at row {index}")

    manuscripts: dict[str, dict[str, Manuscript]] = {}
    for profile in CATEGORIES:
        category_manuscripts: dict[str, Manuscript] = {}
        with ZipFile(source_dir / profile.zip_name) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            if len(names) != 371 or any(not name.lower().endswith(".txt") for name in names):
                raise ValueError(f"ZIP member count/type mismatch: {profile.zip_name}")
            for member in names:
                raw = archive.read(member).decode("utf-8-sig")
                manuscript = parse_manuscript(raw, Path(member).name, profile)
                if manuscript.locality in category_manuscripts:
                    raise ValueError(f"duplicate manuscript locality: {profile.category}/{manuscript.locality}")
                category_manuscripts[manuscript.locality] = manuscript
        if set(category_manuscripts) != set(localities):
            missing = sorted(set(localities) - set(category_manuscripts))
            extra = sorted(set(category_manuscripts) - set(localities))
            raise ValueError(f"manuscript locality mismatch: {profile.category}: missing={missing}, extra={extra}")
        manuscripts[profile.category] = category_manuscripts

    grouped: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[physical_key(row)].append(row)
    if len(grouped) != 188:
        raise ValueError(f"expected 188 physical centres, found {len(grouped)}")
    physical_fields = (
        "센터명", "센터 주소", "교육지원청명칭", "교육지원청 등록번호", "센터 교습비", "위치안내"
    )
    for key, members in grouped.items():
        for field_name in physical_fields:
            if len({member[field_name].strip() for member in members}) != 1:
                raise ValueError(f"physical centre conflict: {field_name}: {key}")
    return SourceBundle(
        tuple(rows), row_by_locality, images_by_locality, org_by_locality,
        {category: dict(values) for category, values in manuscripts.items()},
        {key: tuple(values) for key, values in grouped.items()},
    )


def relative_prefix(depth: int) -> str:
    return "../" * depth


def nav_html(depth: int, active: str = PARENT) -> str:
    prefix = relative_prefix(depth)
    links = (
        ("홈", f"{prefix}index.html"),
        ("학습가이드", f"{prefix}학습가이드/index.html"),
        ("상담문의", f"{prefix}상담문의/index.html"),
        ("전국학원", f"{prefix}전국학원/index.html"),
        (PARENT, f"{prefix}{PARENT}/index.html"),
    )
    rendered = "\n".join(
        f'        <a{" class=\"active\"" if label == active else ""} href="{esc(href)}">{esc(label)}</a>'
        for label, href in links
    )
    return f"""  <header class="nav-wrap">
    <nav class="nav" aria-label="주요 메뉴">
      <a class="brand" href="{prefix}index.html"><span class="brand-mark">영</span><span>{SITE_NAME}</span></a>
      <div class="nav-links">
{rendered}
      </div>
    </nav>
  </header>"""


def footer_html(depth: int) -> str:
    prefix = relative_prefix(depth)
    return f"""  <footer class="footer">
    <p><strong>{SITE_NAME}</strong> · 영어·수학 통합 학습관리 · 상담은 전화·문자로 편하게 문의해주세요.</p>
  </footer>
  <div class="floating-cta" aria-label="빠른 상담 버튼">
    <a href="tel:{CENTRAL_PHONE_DISPLAY}">전화문의</a>
    <a href="sms:{CENTRAL_PHONE_LINK}">문자문의</a>
    <a href="{prefix}상담문의/index.html">상담문의</a>
  </div>"""


def head_html(
    *, title: str, description: str, depth: int, canonical: str,
    og_type: str, og_image: str, graph: Mapping[str, object],
) -> str:
    prefix = relative_prefix(depth)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <link rel="canonical" href="{esc(canonical)}">
  <meta property="og:type" content="{esc(og_type)}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:url" content="{esc(canonical)}">
  <meta property="og:image" content="{esc(og_image)}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(title)}">
  <meta name="twitter:description" content="{esc(description)}">
  <meta name="twitter:image" content="{esc(og_image)}">
  <link rel="icon" type="image/png" href="{prefix}assets/favicon.png">
  <link rel="apple-touch-icon" href="{prefix}assets/favicon.png">
  <link rel="stylesheet" href="{prefix}assets/site.css">
  <script type="application/ld+json">{json_text(graph)}</script>
</head>"""


def page_shell(head: str, body: str) -> str:
    return f"""{head}
<body>
<div class="site-shell">
{body}
</div>
</body>
</html>
"""


def resolve_rep_asset(root: Path, index: int) -> str:
    candidates = sorted((root / "assets" / "representative").glob(f"rep-{index + 1:03d}.*"))
    candidates = [path for path in candidates if path.suffix.lower() in {".gif", ".jpg", ".jpeg", ".png", ".webp"}]
    if len(candidates) != 1:
        raise ValueError(f"representative mapping must resolve exactly once: row={index}: {candidates}")
    return candidates[0].relative_to(root).as_posix()


def resolve_body_assets(root: Path, image_row: Mapping[str, str]) -> tuple[str, str]:
    stem = Path(image_row["본문"].strip()).stem
    large = root / "assets" / "centers" / "common" / f"{stem}6839.webp"
    small = root / "assets" / "centers" / "common" / f"{stem}6839-720.webp"
    if not large.is_file() or not small.is_file():
        raise ValueError(f"centre image mapping missing: {image_row}")
    return large.relative_to(root).as_posix(), small.relative_to(root).as_posix()


def resolve_map_asset(root: Path, row: Mapping[str, str], image_row: Mapping[str, str]) -> str:
    maps = root / "assets" / "maps"
    raw_name = image_row["지도"].strip()
    candidates: list[str] = []
    if raw_name:
        candidates.append(raw_name)
    english = row["동 영어"].strip()
    for base in (english, english.replace(" ", "-"), english.replace(" ", ""), english.replace("_", "-")):
        for suffix in (".jpg", ".jpeg", ".png", ".webp"):
            candidates.append(f"{base}{suffix}")
    found: list[Path] = []
    for name in dict.fromkeys(candidates):
        candidate = maps / name
        if candidate.is_file() and candidate not in found:
            found.append(candidate)
    if not found:
        raise ValueError(f"map mapping missing: {row['근처 수업가능 동네']}: {raw_name}")
    # Prefer the exact image CSV filename; otherwise use the first audited
    # English-slug candidate, matching the existing site generators.
    exact = maps / raw_name
    selected = exact if exact.is_file() else found[0]
    return selected.relative_to(root).as_posix()


_DIMENSION_CACHE: dict[Path, tuple[int, int]] = {}


def image_dimensions(root: Path, relative_path: str) -> tuple[int, int]:
    path = (root / relative_path).resolve()
    if path not in _DIMENSION_CACHE:
        with Image.open(path) as image:
            _DIMENSION_CACHE[path] = image.size
    return _DIMENSION_CACHE[path]


def physical_grade_union(bundle: SourceBundle, row: Mapping[str, str], column: str) -> tuple[str, ...]:
    values: list[str] = []
    for member in bundle.physical_rows[physical_key(row)]:
        for token in split_grade_tokens(member[column]):
            if token not in values:
                values.append(token)
    return tuple(values)


def physical_organization_schema(bundle: SourceBundle, row: Mapping[str, str]) -> dict[str, object]:
    pid = physical_id(row)
    aliases = [member["근처 수업가능 동네"].strip() for member in bundle.physical_rows[physical_key(row)]]
    offers: list[dict[str, object]] = []
    for subject, column in (("영어", "가능학년\n(영어)"), ("수학", "가능학년\n(수학)")):
        grades = physical_grade_union(bundle, row, column)
        if not grades:
            continue
        offers.append({
            "@type": "Offer",
            "itemOffered": {
                "@type": "Service",
                "name": f"{row['센터명'].strip()} {subject} 학습 안내",
                "serviceType": f"{subject} 학습",
                "educationalLevel": list(grades),
            },
        })
    return {
        "@type": ["EducationalOrganization", "LocalBusiness"],
        "@id": pid,
        "name": row["센터명"].strip(),
        "legalName": row["교육지원청명칭"].strip(),
        "identifier": {
            "@type": "PropertyValue",
            "propertyID": "교육지원청 등록번호",
            "value": row["교육지원청 등록번호"].strip(),
        },
        "address": {
            "@type": "PostalAddress",
            "streetAddress": row["센터 주소"].strip(),
            "addressCountry": "KR",
        },
        "areaServed": [{"@type": "Place", "name": locality} for locality in aliases],
        "makesOffer": offers,
    }


def nearby_rows(bundle: SourceBundle, row: Mapping[str, str], count: int = 4) -> tuple[Mapping[str, str], ...]:
    same_city = [
        other for other in bundle.rows
        if other["근처 수업가능 동네"] != row["근처 수업가능 동네"]
        and other["지역"] == row["지역"] and other["시or구"] == row["시or구"]
    ]
    if len(same_city) >= count:
        return tuple(same_city[:count])
    same_region = [
        other for other in bundle.rows
        if other["근처 수업가능 동네"] != row["근처 수업가능 동네"]
        and other["지역"] == row["지역"] and other not in same_city
    ]
    return tuple((same_city + same_region)[:count])


ADVICE_OPENINGS = (
    "상담 자료를 한곳에 모을 때에는",
    "현재 상태를 차분히 대조하려면",
    "학습 기록을 다음 계획에 연결하려면",
    "설명과 실제 기록을 구분해 보려면",
    "우선순위를 정하기 전에는",
    "학생의 부담을 과장 없이 살피려면",
    "학부모와 학생이 같은 기준을 쓰려면",
    "결정을 서두르지 않고 검토하려면",
)

EVIDENCE_ACTIONS = (
    "최근 자료에 날짜와 범위를 적어 두고 서로 다른 시기의 기록을 나란히 살펴보는 편이 좋습니다",
    "맞힌 결과뿐 아니라 멈춘 지점과 다시 시도한 흔적까지 함께 남겨야 변화의 방향을 읽기 쉽습니다",
    "학생이 직접 설명할 수 있는 부분과 도움이 필요한 부분을 나누면 질문이 더 구체적으로 바뀝니다",
    "학교에서 받은 최신 자료와 개인 학습 기록을 분리해 두면 오래된 정보에 기대는 일을 줄일 수 있습니다",
    "한 번의 점수보다 반복해서 나타난 어려움을 표시하면 먼저 확인할 항목이 선명해집니다",
    "자료의 작성 시점과 사용 목적을 확인하면 서로 성격이 다른 기록을 섞어 판단하지 않게 됩니다",
    "학생이 스스로 남긴 표시를 중심에 두면 성인의 추측보다 실제 학습 과정을 더 잘 볼 수 있습니다",
    "완료 여부와 이해 여부를 따로 기록하면 진도를 나갔다는 사실만으로 상태를 단정하지 않게 됩니다",
)

DECISION_ACTIONS = (
    "질문은 확인할 자료, 답변한 사람, 적용 시점을 구분해 적어 두어야 나중에 같은 조건으로 대조할 수 있습니다",
    "계획은 가장 시급한 한 항목부터 세우고 점검 결과가 달라지면 순서를 다시 조정할 수 있어야 합니다",
    "학생의 설명을 먼저 들은 뒤 필요한 도움을 정하면 이미 아는 내용을 불필요하게 반복하는 일을 줄일 수 있습니다",
    "선택 기준은 홍보 표현보다 실제로 확인 가능한 기록과 변경 절차에 두는 편이 안전합니다",
    "새 자료가 생겼을 때 기존 계획의 어느 부분을 바꿀지 미리 정하면 일정 변화에 대응하기 쉽습니다",
    "답변은 가능 여부와 조건을 나누어 기록해야 예외 사항을 일반적인 약속으로 오해하지 않습니다",
    "가정에서 관찰한 내용과 학교 자료를 구분하면 원인이 다른 어려움을 하나로 묶지 않게 됩니다",
    "상담 뒤에는 확인된 사실과 추가 질문을 별도 칸에 적어 추정이 결정 근거에 섞이지 않게 해야 합니다",
)

LIMIT_ACTIONS = (
    "자료 한 장만으로 과목 전체의 강점이나 약점을 단정하지 않는 것이 중요합니다",
    "과거의 학교 경향이 현재 시험 범위와 같다고 가정해서는 안 됩니다",
    "학년이 같아도 학생별 기록이 다르므로 동일한 순서를 일괄 적용하지 않는 편이 좋습니다",
    "상담 문구만으로 실제 개설 시기나 운영 조건을 확정해서는 안 됩니다",
    "완료한 분량이 많다는 이유만으로 독립 해결이 가능하다고 보기는 어렵습니다",
    "한 번의 관찰을 장기적인 습관으로 확대해 해석하지 않는 것이 안전합니다",
    "학교명만으로 교과서나 평가 방식이 현재와 같다고 판단하지 않아야 합니다",
    "기록이 비어 있는 항목은 긍정이나 부정으로 추정하지 말고 확인 질문으로 남겨야 합니다",
)

FOLLOWUP_ACTIONS = (
    "다음 확인 때에는 같은 유형을 학생이 도움 없이 설명하는지 살펴보면 됩니다",
    "이후 기록에는 바뀐 점과 그대로인 점을 나누어 남기면 계획 조정의 근거가 됩니다",
    "상담 메모에는 답변의 날짜를 적고 실제 적용 전에 다시 확인하는 절차가 필요합니다",
    "학생에게는 결과보다 어떤 근거로 판단했는지를 말하게 하면 이해 상태를 확인하기 쉽습니다",
    "가정에서는 시작 여부와 질문 표시처럼 관찰 가능한 행동만 짧게 기록하는 편이 좋습니다",
    "새로운 학교 자료가 나오면 이전 메모와 대조해 달라진 조건부터 갱신해야 합니다",
    "점검 뒤에는 유지할 항목과 바꿀 항목을 하나씩 정해 과도한 계획을 피하는 것이 좋습니다",
    "대조표에는 확인 완료, 추가 확인, 해당 없음의 상태를 나누어 적는 방식이 유용합니다",
)

H2_OPENINGS = (
    "기록으로 확인하는", "상담 전에 정리할", "학생 설명에서 살필", "자료를 대조하는",
    "계획에 연결하는", "학교 자료와 나눠 볼", "학부모가 관찰할", "확인 질문으로 바꿀",
    "현재 기록에서 가려낼", "상담 자료로 짚어 볼", "가정 메모에서 구분할", "검토 순서를 세우는",
)
H2_ENDINGS = (
    "핵심 기준", "확인 순서", "판단 근거", "점검 항목",
    "준비 방법", "기록 방식", "대조 원칙", "상담 메모",
)
H2_OPENING_CONCEPTS = (
    frozenset(("기록", "확인")), frozenset(("상담",)),
    frozenset(("학생", "설명")), frozenset(("자료", "대조")),
    frozenset(("계획",)), frozenset(("학교", "자료")),
    frozenset(("학부모",)), frozenset(("확인", "질문")),
    frozenset(("기록",)), frozenset(("상담", "자료")),
    frozenset(("메모",)), frozenset(("검토", "순서")),
)
H2_ENDING_CONCEPTS = tuple(frozenset(ending.split()) for ending in H2_ENDINGS)
H2_CONCEPTS = frozenset().union(*H2_OPENING_CONCEPTS, *H2_ENDING_CONCEPTS)

CUE_CONTEXTS = (
    "{grade} {subject} 자료 가운데 ‘{cue}’ 부분에 주목해",
    "‘{cue}’ 관련 {grade} {subject} 자료를 바탕으로",
    "{grade} {subject} 기록 속 ‘{cue}’ 부분을 짚어 보며",
    "{grade} {subject} 상담 준비에서 ‘{cue}’ 부분을 다룰 때",
    "{grade} {subject} 자료의 ‘{cue}’ 대목을 검토하며",
    "{grade} {subject} 점검표에서 ‘{cue}’ 칸을 대조하며",
    "{grade} {subject} 상담 목록에 ‘{cue}’ 항목을 정리하면서",
    "{grade} {subject} 기록 중 ‘{cue}’ 부분을 구분하며",
    "{grade} {subject} 준비 목록의 ‘{cue}’ 항목부터 살펴보고",
    "{grade} {subject} 자료에서 ‘{cue}’ 단서를 찾으며",
    "{grade} {subject} 상담 메모의 ‘{cue}’ 부분을 읽으며",
    "{grade} {subject} 자료를 볼 때 ‘{cue}’ 항목과 함께",
)


def variation_pair(global_index: int, salt: int) -> tuple[int, int]:
    value = (global_index + salt * 29) % 64
    return value % 8, value // 8


def stable_variant(global_index: int, salt: int, label: str, size: int) -> int:
    digest = hashlib.sha256(f"{global_index}\0{salt}\0{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % size


def advice_sentence(
    *, global_index: int, salt: int, cue: str, profile: CategoryProfile,
    locality: str = "", action_bank: Sequence[str] = EVIDENCE_ACTIONS,
) -> str:
    left, right = variation_pair(global_index, salt)
    place = f"{locality}에서 " if locality else ""
    context = CUE_CONTEXTS[stable_variant(global_index, salt, "cue-context", len(CUE_CONTEXTS))].format(
        grade=profile.grade_short, subject=profile.subject, cue=cue,
    )
    return (
        f"{place}{ADVICE_OPENINGS[left]}, {context} {action_bank[right]}"
    )


def article_heading(
    global_index: int, salt: int, cue: str, locality: str,
    used_openings: set[int] | None = None,
) -> str:
    cue_tokens = frozenset(normalize_space(cue).split())
    opening_alternatives = tuple(
        index for index, concepts in enumerate(H2_OPENING_CONCEPTS)
        if not cue_tokens.intersection(concepts)
    )
    unused_alternatives = tuple(
        index for index in opening_alternatives
        if used_openings is None or index not in used_openings
    )
    opening_pool = unused_alternatives or opening_alternatives
    left = opening_pool[
        stable_variant(global_index, salt, f"h2-opening:{cue}", len(opening_pool))
    ]
    if used_openings is not None:
        used_openings.add(left)
    blocked_tokens = cue_tokens.union(H2_OPENING_CONCEPTS[left])
    ending_alternatives = tuple(
        index for index, concepts in enumerate(H2_ENDING_CONCEPTS)
        if not blocked_tokens.intersection(concepts)
    )
    right = ending_alternatives[
        stable_variant(global_index, salt, f"h2-ending:{cue}:{left}", len(ending_alternatives))
    ]
    return f"{locality} {H2_OPENINGS[left]} ‘{cue}’ {H2_ENDINGS[right]}"


def render_editorial_article(
    profile: CategoryProfile, row: Mapping[str, str], manuscript: Manuscript,
    global_index: int, supported: bool,
) -> str:
    locality = row["근처 수업가능 동네"].strip()
    cues = manuscript.cues[:6]
    while len(cues) < 6:
        cues = cues + manuscript.cues[: 6 - len(cues)]
    used_openings: set[int] = set()
    top_heading = article_heading(global_index, 0, cues[0], locality, used_openings)

    intro_sentences = (
        advice_sentence(global_index=global_index, salt=1, cue=cues[0], profile=profile, locality=locality),
        advice_sentence(global_index=global_index, salt=2, cue=cues[1], profile=profile, action_bank=DECISION_ACTIONS),
        advice_sentence(global_index=global_index, salt=3, cue=cues[2], profile=profile, action_bank=LIMIT_ACTIONS),
        advice_sentence(global_index=global_index, salt=4, cue=cues[3], profile=profile, action_bank=FOLLOWUP_ACTIONS),
    )
    intro = (
        f"<p>{esc(intro_sentences[0])}. {esc(intro_sentences[1])}.</p>"
        f"<p>{esc(intro_sentences[2])}. {esc(intro_sentences[3])}.</p>"
    )

    section_labels = (
        "현재 기록", "학생 적합성", "학교 자료", "오답 이후", "상담 준비", "학부모 관찰 예시"
    )
    cards: list[str] = []
    for section_index, (label, cue) in enumerate(zip(section_labels, cues), 1):
        salt = 10 + section_index * 5
        heading = article_heading(global_index, salt, cue, locality, used_openings)
        s1 = advice_sentence(
            global_index=global_index, salt=salt + 1, cue=cue, profile=profile,
            locality=locality if section_index in (2, 5) else "", action_bank=EVIDENCE_ACTIONS,
        )
        s2 = advice_sentence(
            global_index=global_index, salt=salt + 2, cue=cues[(section_index + 1) % len(cues)],
            profile=profile, action_bank=DECISION_ACTIONS,
        )
        s3 = advice_sentence(
            global_index=global_index, salt=salt + 3, cue=cues[(section_index + 2) % len(cues)],
            profile=profile, action_bank=LIMIT_ACTIONS,
        )
        s4 = advice_sentence(
            global_index=global_index, salt=salt + 4, cue=cue, profile=profile,
            action_bank=FOLLOWUP_ACTIONS,
        )
        note = ""
        if label == "학부모 관찰 예시":
            note_left, note_right = variation_pair(global_index, salt + 17)
            note_sentences = (
                "실제 후기나 성과 사례가 아니라 상담 자료를 정리하는 가상 예시입니다",
                "실제 이용 경험을 인용한 문장이 아니라 기록 방법을 보여 주는 예시입니다",
                "특정 학생의 결과를 재현한 후기가 아니라 관찰 항목을 설명하는 예시입니다",
                "등록 결과나 성적 변화를 말하는 사례가 아니라 질문 준비를 돕는 예시입니다",
                "실제 학부모의 평가가 아니라 확인 가능한 행동을 적는 방식을 보여 줍니다",
                "성과를 약속하는 후기가 아니라 상담 전에 메모할 항목을 예로 든 것입니다",
                "실제 수강생의 경험담이 아니라 자료를 구분하는 방법을 설명한 예시입니다",
                "특정 센터의 결과 사례가 아니라 학부모 관찰 기록의 형식을 보여 줍니다",
            )
            note_followups = (
                "해석보다 관찰한 사실을 먼저 적어 주세요",
                "학생의 말과 자료의 날짜를 함께 남겨 주세요",
                "확인하지 못한 내용은 질문으로 구분해 주세요",
                "한 번의 결과를 장기 변화로 확대하지 마세요",
                "학교 자료와 가정 기록을 서로 다른 칸에 적어 주세요",
                "답변을 받기 전에는 운영 조건을 추정하지 마세요",
                "대조할 항목을 먼저 정한 뒤 메모를 시작해 주세요",
                "다음 확인 시점에 같은 기준을 다시 사용해 주세요",
            )
            note = (
                '<p class="academy-source-note" data-source-status="hypothetical-example">'
                f"‘{esc(cue)}’ 관찰은 {esc(note_sentences[note_left])}; {esc(note_followups[note_right])}."
                "</p>"
            )
        cards.append(
            f'<article class="manuscript-card" data-grade-section="{esc(label)}">'
            f'<h2>{esc(heading)}</h2>{note}'
            f'<p>{esc(s1)}. {esc(s2)}.</p><p>{esc(s3)}. {esc(s4)}.</p></article>'
        )

    support_note = (
        f"원자료의 {profile.subject} 가능 학년 항목에 {profile.grade_token}{grade_particle(profile, '이', '가')} 포함되어 있습니다. "
        "실제 개설 일정과 수업 조건은 상담 시점의 안내로 다시 확인해야 합니다."
        if supported else
        f"원자료의 {profile.subject} 가능 학년 항목에는 {profile.grade_token}{grade_particle(profile, '이', '가')} 기재되어 있지 않습니다. "
        "실제 개설 여부·대상 학년·수업 시간은 상담 답변을 받기 전까지 확정할 수 없습니다."
    )
    unsupported_attr = ' data-source-status="unconfirmed-grade"' if not supported else ""
    return f"""    <section class="section grade-main-article" data-manuscript-cues="{esc('|'.join(manuscript.cues[:6]))}" data-manuscript-sha256="{manuscript.sha256}"{unsupported_attr}>
      <div class="section-head">
        <p class="eyebrow">GRADE STUDY GUIDE</p>
        <h2>{esc(top_heading)}</h2>
        <p class="lead" data-grade-source-note>{esc(support_note)}</p>
      </div>
      <div class="manuscript-intro">{intro}</div>
      <div class="manuscript-grid">{''.join(cards)}</div>
    </section>"""


def render_source_facts(profile: CategoryProfile, row: Mapping[str, str]) -> str:
    grade_raw = row[profile.grade_column].strip()
    schools_raw = row["타깃학교\n(고)"].strip()
    fee_url = row["센터 교습비"].strip()
    guide = clean_location_guide(row["위치안내"])
    registration_name_visible = normalize_space(row["교육지원청명칭"])
    grade_value = esc(grade_raw or "원자료 미기재")
    school_value = esc(schools_raw or "원자료 미기재")
    grade_missing_attr = ' data-source-status="missing-supported-grades"' if not grade_raw else ""
    school_missing_attr = ' data-source-status="missing-high-schools"' if not schools_raw else ""
    if fee_url:
        fee_node = f'<a data-source-field="fee-url" href="{esc(fee_url)}" rel="noopener noreferrer">센터 공통 교습비 링크</a>'
    else:
        fee_node = '<span data-source-field="fee-url" data-source-status="missing-fee-url">미기재 상태</span>'
    if guide:
        guide_html = f'<p class="academy-location-guide" data-source-field="location-guide">{esc(guide)}</p>'
    else:
        guide_html = '<p class="academy-location-guide-status academy-source-unconfirmed-note" data-source-status="missing-location-guide">원자료의 위치 안내 항목은 미기재 상태입니다. 방문 경로는 상담 전에 확인해 주세요.</p>'
    schools = parse_high_schools(schools_raw)
    chips = "".join(f'<span data-source-school>{esc(name)}</span>' for name in schools)
    if GENERIC_HIGH_SCHOOL_RE.search(schools_raw):
        school_note = '<p class="academy-source-note">원문은 특정 학교명을 식별하지 않는 포괄 참고 문구이므로 학교 목록으로 해석하지 않습니다.</p>'
    elif schools:
        school_note = '<p class="academy-source-note">학교명은 원자료의 참고 항목이며 현재 재학, 학교별 수업 또는 시험 대비 제공을 뜻하지 않습니다.</p>'
    else:
        school_note = '<p class="academy-source-note">고등학교 참고 항목이 비어 있어 학교명을 추정하지 않습니다.</p>'
    return f"""    <section class="section grade-source-facts">
      <div class="section-head"><p class="eyebrow">SOURCE FACTS</p><h2>제공 자료에서 확인한 센터 정보</h2><p class="lead">아래 값은 공통 원자료를 그대로 구분해 표시했습니다. 실제 상담·방문 전에는 변경 여부를 확인해 주세요.</p></div>
      <div class="card-grid">
        <article class="info-card"><span class="tag">서비스 지역</span><p data-source-field="region">{esc(row['지역'].strip())}</p><p data-source-field="city">{esc(row['시or구'].strip())}</p><p data-source-field="locality">{esc(row['근처 수업가능 동네'].strip())}</p></article>
        <article class="info-card"><span class="tag">센터</span><p data-source-field="center-name">{esc(row['센터명'].strip())}</p><p data-source-field="address">{esc(row['센터 주소'].strip())}</p></article>
        <article class="info-card"><span class="tag">등록 정보</span><p data-source-field="registration-name">{esc(registration_name_visible)}</p><p data-source-field="registration-number">{esc(row['교육지원청 등록번호'].strip())}</p></article>
        <article class="info-card"><span class="tag">{esc(profile.subject)} 가능 학년</span><p data-source-field="supported-grades"{grade_missing_attr}>{grade_value}</p></article>
        <article class="info-card"><span class="tag">고등학교 참고</span><p data-source-field="high-schools"{school_missing_attr}>{school_value}</p><div class="chip-list">{chips}</div>{school_note}</article>
        <article class="info-card"><span class="tag">교습비 자료</span><p>{fee_node}</p></article>
      </div>
      <div class="section-head" style="margin-top:24px;"><h2>원자료 위치 안내·방문 전 확인</h2>{guide_html}</div>
    </section>"""


def faq_pairs(
    profile: CategoryProfile, row: Mapping[str, str], manuscript: Manuscript, supported: bool,
) -> tuple[tuple[str, str], ...]:
    locality = row["근처 수업가능 동네"].strip()
    title = f"{locality} {profile.query_suffix}"
    grade_raw = row[profile.grade_column].strip()
    if supported:
        grade_answer = (
            f"원자료의 {profile.subject} 가능 학년 항목은 “{grade_raw}”이며 {profile.grade_token}{grade_particle(profile, '이', '가')} 포함되어 있습니다. "
            f"실제 개설 일정과 대상 조건은 상담 시 다시 확인해 주세요. 학년 확인과 별도로 ‘{manuscript.cues[0]}’ 관련 자료를 준비하면 현재 상태를 설명하기 쉽습니다."
        )
    elif grade_raw:
        grade_answer = (
            f"원자료의 {profile.subject} 가능 학년 항목은 “{grade_raw}”이며 {profile.grade_token}{grade_particle(profile, '은', '는')} 기재되어 있지 않습니다. "
            f"실제 개설 여부·대상 학년·수업 시간은 상담 답변 전까지 확정할 수 없습니다. ‘{manuscript.cues[0]}’ 관련 자료는 일반적인 학습상담 준비에만 활용해 주세요."
        )
    else:
        grade_answer = (
            f"원자료의 {profile.subject} 가능 학년 항목은 미기재 상태이며 {profile.grade_token}도 확인되지 않습니다. "
            f"실제 개설 여부·대상 학년·수업 시간은 상담 답변 전까지 확정할 수 없습니다. ‘{manuscript.cues[0]}’ 관련 자료는 일반적인 학습상담 준비에만 활용해 주세요."
        )

    schools_raw = row["타깃학교\n(고)"].strip()
    if schools_raw:
        school_answer = (
            f"원자료의 고등학교 참고 항목은 “{schools_raw}”입니다. "
            "이 문구는 현재 재학이나 학교별 수업 제공을 뜻하지 않으므로 최신 학교 자료는 별도로 확인해 주세요."
        )
    else:
        school_answer = "원자료의 고등학교 참고 항목은 미기재 상태입니다. 학교명을 다른 학년 자료나 인근 지역 정보에서 추정하지 않습니다."

    guide = clean_location_guide(row["위치안내"])
    if guide:
        location_answer = f"원자료 주소는 “{row['센터 주소'].strip()}”입니다. 원자료 위치 안내는 “{guide}”이며 방문 전 입구와 이동 경로를 다시 확인해 주세요."
    else:
        location_answer = f"원자료 주소는 “{row['센터 주소'].strip()}”입니다. 위치 안내 항목은 미기재 상태이므로 방문 전 입구와 이동 경로를 상담으로 확인해 주세요."

    fee_url = row["센터 교습비"].strip()
    if fee_url:
        fee_answer = "상단의 센터 공통 교습비 링크에서 제공 자료를 확인할 수 있습니다. 실제 적용 비용과 추가 금액은 등록 전에 다시 확인해 주세요."
    else:
        fee_answer = "교습비 링크는 미기재 상태입니다. 실제 비용이나 금액을 이 페이지에서 추정하지 말고 상담 전에 서면 자료로 확인해 주세요."
    return (
        (f"{profile.grade_short} {profile.subject} 대상 학년은 원자료에서 어떻게 확인하나요?", grade_answer),
        (f"{locality} 고등학교 참고 정보는 무엇인가요?", school_answer),
        (f"{locality} 센터 주소와 위치 안내는 어디에서 확인하나요?", location_answer),
        (f"{locality} 교습비 정보는 어떻게 확인하나요?", fee_answer),
    )


def render_faq(profile: CategoryProfile, row: Mapping[str, str], pairs: Sequence[tuple[str, str]], supported: bool) -> str:
    locality = row["근처 수업가능 동네"].strip()
    topics = ("grade", "schools", "location", "fee")
    items: list[str] = []
    for index, ((question, answer), topic) in enumerate(zip(pairs, topics)):
        marker = ' data-source-status="unconfirmed-grade"' if topic == "grade" and not supported else ""
        items.append(
            f'<details class="grade-faq-item" data-faq-topic="{topic}"{" open" if index == 0 else ""}{marker}>'
            f'<summary>{esc(question)}</summary><p>{esc(answer)}</p></details>'
        )
    return f"""    <section class="section">
      <div class="section-head"><p class="eyebrow">FAQ</p><h2>{esc(locality)} {esc(profile.subject_label)} 자주 묻는 질문</h2></div>
      <div class="faq-list grade-faq-list">{''.join(items)}</div>
    </section>"""


def meta_description(profile: CategoryProfile, row: Mapping[str, str], supported: bool) -> str:
    locality = row["근처 수업가능 동네"].strip()
    region = row["지역"].strip()
    city = row["시or구"].strip()
    if supported:
        return (
            f"{region} {city} {locality} {profile.query_suffix} 정보입니다. 원자료의 {profile.subject} 가능 학년, "
            "고등학교 참고 항목, 센터 주소와 교습비 확인 경로를 상담 전에 살펴보세요."
        )
    return (
        f"{region} {city} {locality} {profile.query_suffix} 정보입니다. 제공 원자료에는 {profile.grade_token} "
        f"{profile.subject} 가능 여부가 기재되지 않아 실제 개설 여부와 대상 학년을 상담 전에 확인해야 합니다."
    )


def render_media(
    root: Path, profile: CategoryProfile, row: Mapping[str, str],
    rep_asset: str, body_asset: str, body_small: str, map_asset: str,
) -> str:
    locality = row["근처 수업가능 동네"].strip()
    title = f"{locality} {profile.query_suffix}"
    body_width, body_height = image_dimensions(root, body_asset)
    small_width, _ = image_dimensions(root, body_small)
    map_width, map_height = image_dimensions(root, map_asset)
    if small_width != 720:
        raise ValueError(f"unexpected responsive centre image width: {body_small}: {small_width}")
    # rep_asset is intentionally used by OG/Twitter/Article only.  Rendering it
    # as a hidden img would trigger 1,484 unnecessary downloads.
    return f"""    <section class="section grade-media">
      <div class="media-row">
        <figure class="frame" style="aspect-ratio:{body_width}/{body_height};"><img src="../../../{esc(body_asset)}" srcset="../../../{esc(body_small)} 720w, ../../../{esc(body_asset)} {body_width}w" sizes="(max-width:900px) calc(100vw - 32px), 918px" alt="{esc(title)} 센터 안내 이미지" width="{body_width}" height="{body_height}" loading="eager" decoding="async" fetchpriority="high"></figure>
        <figure class="frame" style="aspect-ratio:{map_width}/{map_height};"><img src="../../../{esc(map_asset)}" alt="{esc(locality)} 센터 위치 참고 지도" width="{map_width}" height="{map_height}" loading="lazy" decoding="async"></figure>
      </div>
      <p class="lead">원자료의 센터명과 주소를 기준으로 표시한 정보입니다. 방문 전에 주소, 입구와 이동 경로가 현재 안내와 같은지 확인해 주세요.</p>
    </section>"""


def related_links(
    root: Path, bundle: SourceBundle, profile: CategoryProfile, row: Mapping[str, str],
) -> tuple[str, list[dict[str, object]]]:
    locality = row["근처 수업가능 동네"].strip()
    slug = slug_ko(locality)
    links: list[tuple[str, str, str]] = [
        (f"../index.html", profile.category, "현재 학년·과목 전체 지역"),
        (f"../../index.html", PARENT, "학년·과목 카테고리 전체"),
    ]
    for category, _ in ALL_CATEGORY_CARDS:
        if category == profile.category:
            continue
        # All four new categories are in the projection.  Existing middle
        # categories must already have the same locality route.
        path = root / PARENT / category / slug / "index.html"
        if category.startswith("고") or path.is_file():
            links.append((f"../../{category}/{slug}/index.html", category, "같은 지역 다른 학년·과목"))
    nationwide = root / "전국학원" / "와와학습코칭학원" / slug / "index.html"
    if nationwide.is_file():
        links.append((f"../../../전국학원/와와학습코칭학원/{slug}/index.html", "와와학습코칭학원", "같은 지역 센터 종합 안내"))
    for nearby in nearby_rows(bundle, row):
        nearby_local = nearby["근처 수업가능 동네"].strip()
        nearby_slug = slug_ko(nearby_local)
        links.append((f"../{nearby_slug}/index.html", f"{nearby_local} {profile.category}", "같은 시도 인근 지역"))
    visible = "".join(
        f'<a href="{esc(href)}"><strong>{esc(label)}</strong><small>{esc(note)}</small></a>'
        for href, label, note in links
    )
    schema_items: list[dict[str, object]] = []
    for position, (href, label, _) in enumerate(links, 1):
        if href.startswith("../../../전국학원"):
            url = f"{DOMAIN}/전국학원/와와학습코칭학원/{slug}/"
        elif href == "../index.html":
            url = f"{DOMAIN}/{PARENT}/{profile.category}/"
        elif href == "../../index.html":
            url = f"{DOMAIN}/{PARENT}/"
        elif href.startswith("../../"):
            match = re.match(r"\.\./\.\./([^/]+)/([^/]+)/index\.html", href)
            if not match:
                raise ValueError(f"unexpected related link: {href}")
            url = f"{DOMAIN}/{PARENT}/{match.group(1)}/{match.group(2)}/"
        else:
            match = re.match(r"\.\./([^/]+)/index\.html", href)
            if not match:
                raise ValueError(f"unexpected nearby link: {href}")
            url = f"{DOMAIN}/{PARENT}/{profile.category}/{match.group(1)}/"
        schema_items.append({"@type": "ListItem", "position": position, "name": label, "url": url})
    return visible, schema_items


def detail_graph(
    *, bundle: SourceBundle, profile: CategoryProfile, row: Mapping[str, str],
    title: str, description: str, canonical: str, supported: bool,
    rep_asset: str, body_asset: str, map_asset: str,
    faq: Sequence[tuple[str, str]], related_items: Sequence[Mapping[str, object]],
    article_sections: Sequence[str],
) -> dict[str, object]:
    locality = row["근처 수업가능 동네"].strip()
    pid = physical_id(row)
    schools = parse_high_schools(row["타깃학교\n(고)"].strip())
    image_id = f"{canonical}#primaryimage"
    article_id = f"{canonical}#article"
    service_id = f"{canonical}#service"
    webpage: dict[str, object] = {
        "@type": "WebPage", "@id": f"{canonical}#webpage", "url": canonical,
        "name": title, "description": description, "inLanguage": "ko-KR",
        "primaryImageOfPage": {"@id": image_id},
        "breadcrumb": {"@id": f"{canonical}#breadcrumb"},
        "mainEntity": {"@id": service_id if supported else article_id},
    }
    article: dict[str, object] = {
        "@type": "Article", "@id": article_id, "headline": title,
        "description": description,
        "image": [f"{DOMAIN}/{rep_asset}", f"{DOMAIN}/{body_asset}", f"{DOMAIN}/{map_asset}"],
        "inLanguage": "ko-KR", "datePublished": PUBLISH_DATE, "dateModified": PUBLISH_DATE,
        "author": {"@id": ROOT_ORG_ID}, "publisher": {"@id": ROOT_ORG_ID},
        "mainEntityOfPage": {"@id": f"{canonical}#webpage"},
        "about": [
            {"@type": "Thing", "name": profile.subject_label},
            {"@type": "Place", "name": locality},
        ],
        "mentions": [{"@id": pid}] + [{"@type": "HighSchool", "name": name} for name in schools],
        "articleSection": list(article_sections),
        "hasPart": [{"@type": "WebPageElement", "name": name} for name in article_sections],
    }
    if supported:
        article["educationalLevel"] = profile.grade_long
    graph: list[dict[str, object]] = [
        webpage,
        {
            "@type": "ImageObject", "@id": image_id, "url": f"{DOMAIN}/{rep_asset}",
            "caption": f"{title} 대표 이미지",
        },
        {
            "@type": "BreadcrumbList", "@id": f"{canonical}#breadcrumb",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{DOMAIN}/"},
                {"@type": "ListItem", "position": 2, "name": PARENT, "item": f"{DOMAIN}/{PARENT}/"},
                {"@type": "ListItem", "position": 3, "name": profile.category, "item": f"{DOMAIN}/{PARENT}/{profile.category}/"},
                {"@type": "ListItem", "position": 4, "name": title, "item": canonical},
            ],
        },
        physical_organization_schema(bundle, row),
        article,
    ]
    if supported:
        graph.append({
            "@type": "Service", "@id": service_id, "name": title,
            "serviceType": f"{profile.grade_short} {profile.subject} 학습",
            "provider": {"@id": pid}, "areaServed": {"@type": "Place", "name": locality},
            "audience": {"@type": "EducationalAudience", "educationalRole": "student"},
            "educationalLevel": profile.grade_long,
        })
    graph.append({
        "@type": "FAQPage", "@id": f"{canonical}#faq",
        "mainEntity": [
            {"@type": "Question", "name": question, "acceptedAnswer": {"@type": "Answer", "text": answer}}
            for question, answer in faq
        ],
    })
    if schools:
        graph.append({
            "@type": "ItemList", "@id": f"{canonical}#high-schools",
            "name": f"{locality} 고등학교 참고 항목", "numberOfItems": len(schools),
            "itemListElement": [
                {"@type": "ListItem", "position": index + 1, "item": {"@type": "HighSchool", "name": name}}
                for index, name in enumerate(schools)
            ],
        })
    graph.append({
        "@type": "ItemList", "@id": f"{canonical}#related",
        "name": f"{title} 관련 내부 링크", "itemListElement": list(related_items),
    })
    return {"@context": "https://schema.org", "@graph": graph}


def render_detail(
    root: Path, bundle: SourceBundle, profile: CategoryProfile,
    row: Mapping[str, str], row_index: int,
) -> tuple[bytes, Manuscript, bool]:
    locality = row["근처 수업가능 동네"].strip()
    slug = slug_ko(locality)
    title = f"{locality} {profile.query_suffix}"
    canonical = f"{DOMAIN}/{PARENT}/{profile.category}/{slug}/"
    supported = is_supported(row, profile)
    manuscript = bundle.manuscripts[profile.category][locality]
    description = meta_description(profile, row, supported)
    if not 50 <= len(description) <= 160:
        raise ValueError(f"meta description length: {profile.category}/{locality}: {len(description)}")
    image_row = bundle.images_by_locality[locality]
    rep_asset = resolve_rep_asset(root, row_index)
    body_asset, body_small = resolve_body_assets(root, image_row)
    map_asset = resolve_map_asset(root, row, image_row)
    global_index = CATEGORIES.index(profile) * 371 + row_index
    article = render_editorial_article(profile, row, manuscript, global_index, supported)
    facts = render_source_facts(profile, row)
    faq = faq_pairs(profile, row, manuscript, supported)
    faq_html = render_faq(profile, row, faq, supported)
    links_html, related_items = related_links(root, bundle, profile, row)
    link_section = f"""    <section class="section">
      <div class="section-head"><p class="eyebrow">RELATED GUIDES</p><h2>{esc(locality)} 관련 학년·과목과 인근 지역</h2><p class="lead">같은 지역의 다른 학년·과목과 가까운 지역 페이지를 구분해 연결했습니다.</p></div>
      <div class="link-grid">{links_html}</div>
    </section>"""
    article_sections = re.findall(r"<h2>(.*?)</h2>", article)
    graph = detail_graph(
        bundle=bundle, profile=profile, row=row, title=title, description=description,
        canonical=canonical, supported=supported, rep_asset=rep_asset, body_asset=body_asset,
        map_asset=map_asset, faq=faq, related_items=related_items,
        article_sections=[html.unescape(re.sub(r"<[^>]+>", "", value)) for value in article_sections],
    )
    og_image = f"{DOMAIN}/{rep_asset}"
    head = head_html(
        title=f"{title} | {SITE_NAME}", description=description, depth=3,
        canonical=canonical, og_type="article", og_image=og_image, graph=graph,
    )
    unsupported_main = ' data-source-status="unconfirmed-grade"' if not supported else ""
    disclosure = ""
    if not supported:
        disclosure = f"""    <section class="section academy-source-unconfirmed-note" data-source-status="unconfirmed-grade">
      <div class="section-head"><p class="eyebrow">SOURCE STATUS</p><h2>{esc(profile.grade_token)} {esc(profile.subject)} 개설 여부 확인 필요</h2><p class="lead">제공된 센터 원자료에는 {esc(profile.grade_token)} {esc(profile.subject)} 가능 학년이 기재되어 있지 않습니다. 실제 개설 여부·대상 학년·수업 시간은 상담 전에 확인해 주세요.</p></div>
    </section>"""
    body = f"""{nav_html(3)}
  <main data-grade-page data-grade-category="{esc(profile.category)}" data-grade-locality="{esc(locality)}"{unsupported_main}>
    <section class="page-hero">
      <p class="breadcrumb"><a href="../../../index.html">홈</a><span>/</span><a href="../../index.html">{PARENT}</a><span>/</span><a href="../index.html">{esc(profile.category)}</a><span>/</span><span>{esc(title)}</span></p>
      <p class="eyebrow">{esc(profile.intro_label)} LOCAL GUIDE</p>
      <h1>{esc(title)}</h1>
      <p class="lead">{esc(description)}</p>
      <div class="badge-row"><span>{esc(row['지역'].strip())}</span><span>{esc(row['시or구'].strip())}</span><span>{esc(profile.grade_short)}</span><span>{esc(profile.subject)}</span></div>
      <p class="update-date">최종 업데이트: <time datetime="{PUBLISH_DATE}">{PUBLISH_DATE_KO}</time></p>
      <div class="hero-actions"><a class="btn btn-primary" href="tel:{CENTRAL_PHONE_DISPLAY}">전화 상담하기</a><a class="btn btn-ghost" href="../../../상담문의/index.html">상담문의</a></div>
    </section>
{disclosure}
{render_media(root, profile, row, rep_asset, body_asset, body_small, map_asset)}
{facts}
{article}
{faq_html}
{link_section}
  </main>
{footer_html(3)}"""
    return to_crlf(enhance_detail_html(page_shell(head, body))), manuscript, supported


def render_region_directory(bundle: SourceBundle, profile: CategoryProfile) -> str:
    regions: dict[str, dict[str, list[Mapping[str, str]]]] = {}
    for row in bundle.rows:
        regions.setdefault(row["지역"].strip(), {}).setdefault(row["시or구"].strip(), []).append(row)
    jumps = "".join(f'<a href="#region-{esc(slug_ko(region))}">{esc(region)}</a>' for region in regions)
    blocks: list[str] = []
    for region, cities in regions.items():
        city_blocks: list[str] = []
        for city, rows in cities.items():
            links: list[str] = []
            for row in rows:
                locality = row["근처 수업가능 동네"].strip()
                supported = is_supported(row, profile)
                search_value = normalize_space(f"{region} {city} {locality} {profile.category}").lower()
                status = "supported" if supported else "unconfirmed-grade"
                links.append(
                    f'<a href="{esc(slug_ko(locality))}/" data-subject-town data-search="{esc(search_value)}" '
                    f'data-source-status="{status}">{esc(locality)}</a>'
                )
            city_blocks.append(
                f'<div class="district-block" data-subject-group><p class="district-title">{esc(city)}<small>{len(rows)}곳</small></p>'
                f'<div class="local-button-grid">{"".join(links)}</div></div>'
            )
        total = sum(len(items) for items in cities.values())
        blocks.append(
            f'<div class="region-block" id="region-{esc(slug_ko(region))}" data-subject-region>'
            f'<div class="region-title"><h3>{esc(region)}</h3><span>{len(cities)}개 시군구 · {total}개 지역</span></div>'
            f'<div class="district-grid">{"".join(city_blocks)}</div></div>'
        )
    return f'<div class="region-jump" aria-label="지역 바로가기">{jumps}</div>{"".join(blocks)}'


SUBJECT_SEARCH_SCRIPT = """  <script>
  (() => {
    const input = document.querySelector('[data-subject-search]');
    const status = document.querySelector('[data-subject-search-status]');
    const reset = document.querySelector('[data-subject-search-reset]');
    const towns = Array.from(document.querySelectorAll('[data-subject-town]'));
    const groups = Array.from(document.querySelectorAll('[data-subject-group]'));
    const regions = Array.from(document.querySelectorAll('[data-subject-region]'));
    if (!input || !status || !reset || towns.length !== 371) return;
    const apply = () => {
      const query = input.value.normalize('NFKC').trim().toLocaleLowerCase('ko-KR');
      let visible = 0;
      towns.forEach((link) => {
        const match = !query || (link.dataset.search || '').includes(query);
        link.hidden = !match;
        if (match) visible += 1;
      });
      groups.forEach((group) => { group.hidden = !group.querySelector('[data-subject-town]:not([hidden])'); });
      regions.forEach((region) => { region.hidden = !region.querySelector('[data-subject-town]:not([hidden])'); });
      status.textContent = query ? `${visible}개 지역이 검색되었습니다.` : `전체 ${towns.length}개 지역을 표시합니다.`;
    };
    input.addEventListener('input', apply);
    reset.addEventListener('click', () => { input.value = ''; apply(); input.focus(); });
    apply();
  })();
  </script>"""


def render_category_hub(bundle: SourceBundle, profile: CategoryProfile) -> bytes:
    canonical = f"{DOMAIN}/{PARENT}/{profile.category}/"
    supported_count = sum(is_supported(row, profile) for row in bundle.rows)
    unsupported_count = 371 - supported_count
    description = (
        f"전국 371개 지역의 {profile.subject_label} 학습 정보 허브입니다. 원자료상 {profile.grade_token} "
        f"{profile.subject} 가능 학년 기재 {supported_count}곳과 확인 필요 {unsupported_count}곳을 구분해 안내합니다."
    )
    item_list = [
        {
            "@type": "ListItem", "position": index + 1,
            "name": f"{row['근처 수업가능 동네'].strip()} {profile.category}",
            "url": f"{DOMAIN}/{PARENT}/{profile.category}/{slug_ko(row['근처 수업가능 동네'])}/",
        }
        for index, row in enumerate(bundle.rows)
    ]
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "CollectionPage", "@id": f"{canonical}#webpage", "url": canonical, "name": profile.category, "description": description, "inLanguage": "ko-KR"},
            {"@type": "BreadcrumbList", "@id": f"{canonical}#breadcrumb", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{DOMAIN}/"},
                {"@type": "ListItem", "position": 2, "name": PARENT, "item": f"{DOMAIN}/{PARENT}/"},
                {"@type": "ListItem", "position": 3, "name": profile.category, "item": canonical},
            ]},
            {"@type": "ItemList", "@id": f"{canonical}#itemlist", "name": f"{profile.category} 지역 목록", "numberOfItems": 371, "itemListElement": item_list},
        ],
    }
    head = head_html(
        title=f"{profile.category} | {SITE_NAME}", description=description, depth=2,
        canonical=canonical, og_type="website", og_image=f"{DOMAIN}/assets/generated/academy-hero-v2.png", graph=graph,
    )
    directory = render_region_directory(bundle, profile)
    body = f"""{nav_html(2)}
  <main data-grade-directory data-grade-category="{esc(profile.category)}">
    <section class="page-hero">
      <p class="breadcrumb"><a href="../../index.html">홈</a><span>/</span><a href="../index.html">{PARENT}</a><span>/</span><span>{esc(profile.category)}</span></p>
      <p class="eyebrow">{esc(profile.intro_label)} DIRECTORY</p>
      <h1>{esc(profile.category)}</h1>
      <p class="lead">{esc(description)}</p>
      <div class="badge-row"><span>전체 371곳</span><span>원자료 기재 {supported_count}곳</span><span>확인 필요 {unsupported_count}곳</span></div>
      <div class="hero-actions"><a class="btn btn-primary" href="tel:{CENTRAL_PHONE_DISPLAY}">전화 상담하기</a><a class="btn btn-ghost" href="../../상담문의/index.html">상담문의</a></div>
    </section>
    <section class="section">
      <div class="section-head"><p class="eyebrow">지역 찾기</p><h2>지역명으로 안내 페이지 찾기</h2><p class="lead">동네, 시군구 또는 시도 이름을 입력해 목록을 좁힐 수 있습니다. 가능 학년 미기재 페이지는 상세 화면에서 별도로 표시합니다.</p></div>
      <div class="subject-search"><label for="grade-town-search">지역 검색</label><input id="grade-town-search" type="search" data-subject-search autocomplete="off" placeholder="예: 명일동, 강동구"><button type="button" class="btn btn-ghost" data-subject-search-reset>초기화</button><p data-subject-search-status aria-live="polite">전체 371개 지역을 표시합니다.</p></div>
      {directory}
    </section>
  </main>
{footer_html(2)}
{SUBJECT_SEARCH_SCRIPT}"""
    return to_crlf(page_shell(head, body))


def render_parent_hub() -> bytes:
    canonical = f"{DOMAIN}/{PARENT}/"
    description = "영수학원 과목별학원 허브입니다. 학년과 과목을 선택한 뒤 371개 동네별 학습관리 안내를 확인할 수 있습니다."
    cards = "".join(
        f'<a href="{esc(category)}/index.html"><strong>{esc(category)}</strong><small>{esc(summary)}</small></a>'
        for category, summary in ALL_CATEGORY_CARDS
    )
    graph = {
        "@context": "https://schema.org", "@graph": [
            {"@type": "CollectionPage", "@id": f"{canonical}#webpage", "url": canonical, "name": PARENT, "description": description, "inLanguage": "ko-KR"},
            {"@type": "BreadcrumbList", "@id": f"{canonical}#breadcrumb", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{DOMAIN}/"},
                {"@type": "ListItem", "position": 2, "name": PARENT, "item": canonical},
            ]},
            {"@type": "ItemList", "@id": f"{canonical}#categories", "name": f"{PARENT} 카테고리", "numberOfItems": len(ALL_CATEGORY_CARDS), "itemListElement": [
                {"@type": "ListItem", "position": index + 1, "name": category, "url": f"{DOMAIN}/{PARENT}/{category}/"}
                for index, (category, _) in enumerate(ALL_CATEGORY_CARDS)
            ]},
        ],
    }
    head = head_html(
        title=f"{PARENT} | {SITE_NAME}", description=description, depth=1, canonical=canonical,
        og_type="website", og_image=f"{DOMAIN}/assets/generated/academy-hero-v2.png", graph=graph,
    )
    body = f"""{nav_html(1)}
  <main data-grade-category-hub>
    <section class="page-hero">
      <p class="breadcrumb"><a href="../index.html">홈</a><span>/</span><span>{PARENT}</span></p>
      <p class="eyebrow">SUBJECT ACADEMY HUB</p><h1>{PARENT}</h1><p class="lead">학년과 과목을 먼저 선택한 뒤 원하는 지역의 원자료 상태와 상담 확인 항목을 살펴보세요.</p>
      <div class="hero-actions"><a class="btn btn-primary" href="tel:{CENTRAL_PHONE_DISPLAY}">전화 상담하기</a><a class="btn btn-ghost" href="../상담문의/index.html">상담문의</a></div>
    </section>
    <section class="section"><div class="section-head"><p class="eyebrow">ACADEMY CATEGORY</p><h2>학년·과목별 학원 안내</h2><p class="lead">중학교 2·3학년과 고등학교 1·2학년의 영어·수학 지역 안내를 학년별로 구분했습니다.</p></div><div class="category-grid">{cards}</div></section>
  </main>
{footer_html(1)}"""
    return to_crlf(page_shell(head, body))


def render_llms(before: bytes) -> bytes:
    text = before.decode("utf-8-sig")
    new_lines = [
        f"- {profile.category}: {DOMAIN}/{PARENT}/{profile.category}/"
        for profile in CATEGORIES
    ]
    # Remove only previous exact generated lines, preserving every other byte.
    normalized = text.replace("\r\n", "\n")
    for line in new_lines:
        normalized = normalized.replace(line + "\n", "")
    anchor = f"- 중3영어학원: {DOMAIN}/{PARENT}/중3영어학원/\n"
    if anchor not in normalized:
        raise ValueError("llms insertion anchor missing")
    normalized = normalized.replace(anchor, anchor + "".join(line + "\n" for line in new_lines), 1)
    newline = "\r\n" if b"\r\n" in before else "\n"
    return normalized.replace("\n", newline).encode("utf-8")


def sitemap_entry(url: str, *, changefreq: str, priority: str) -> str:
    encoded = quote(url, safe=":/")
    return (
        "  <url>\r\n"
        f"    <loc>{encoded}</loc>\r\n"
        f"    <lastmod>{PUBLISH_DATE}</lastmod>\r\n"
        f"    <changefreq>{changefreq}</changefreq>\r\n"
        f"    <priority>{priority}</priority>\r\n"
        "  </url>\r\n"
    )


def render_sitemap(before: bytes, bundle: SourceBundle) -> bytes:
    text = before.decode("utf-8")
    if "\r\n" not in text:
        raise ValueError("sitemap baseline must be CRLF")
    closing = "</urlset>\r\n"
    if not text.endswith(closing):
        raise ValueError("sitemap closing tag mismatch")
    block_re = re.compile(r"  <url>\r\n.*?  </url>\r\n", re.DOTALL)
    blocks = list(block_re.finditer(text))
    if len(blocks) not in (2609, 4097):
        raise ValueError(f"unexpected sitemap URL count before projection: {len(blocks)}")
    category_names = {profile.category for profile in CATEGORIES}

    def is_target(block: str) -> bool:
        match = re.search(r"<loc>(.*?)</loc>", block)
        if not match:
            raise ValueError("sitemap block missing loc")
        path = urlsplit(unquote(match.group(1))).path.strip("/").split("/")
        return len(path) >= 2 and path[0] == PARENT and path[1] in category_names

    kept: list[str] = []
    for match in blocks:
        block = match.group(0)
        if is_target(block):
            continue
        loc_match = re.search(r"<loc>(.*?)</loc>", block)
        if loc_match and unquote(loc_match.group(1)) == f"{DOMAIN}/{PARENT}/":
            block = re.sub(r"<lastmod>[^<]+</lastmod>", f"<lastmod>{PUBLISH_DATE}</lastmod>", block, count=1)
        kept.append(block)
    if len(kept) != 2609:
        raise ValueError(f"existing sitemap tuple count drift: {len(kept)}")
    prefix_end = blocks[0].start()
    prefix = text[:prefix_end]
    suffix_start = blocks[-1].end()
    between_and_close = text[suffix_start:]
    if between_and_close != closing:
        raise ValueError("unexpected sitemap content outside URL records")
    generated: list[str] = []
    for profile in CATEGORIES:
        generated.append(sitemap_entry(f"{DOMAIN}/{PARENT}/{profile.category}/", changefreq="weekly", priority="0.8"))
        for row in bundle.rows:
            generated.append(sitemap_entry(
                f"{DOMAIN}/{PARENT}/{profile.category}/{slug_ko(row['근처 수업가능 동네'])}/",
                changefreq="monthly", priority="0.7",
            ))
    return (prefix + "".join(kept) + "".join(generated) + closing).encode("utf-8")


def strip_tags(fragment: str) -> str:
    fragment = re.sub(r"<script\b.*?</script>", " ", fragment, flags=re.DOTALL | re.IGNORECASE)
    fragment = re.sub(r"<style\b.*?</style>", " ", fragment, flags=re.DOTALL | re.IGNORECASE)
    return normalize_space(html.unescape(re.sub(r"<[^>]+>", " ", fragment)))


def tag_attributes(tag: str) -> dict[str, str]:
    return {
        name.lower(): html.unescape(value)
        for name, _, value in re.findall(r"([:\w-]+)\s*=\s*([\"'])(.*?)\2", tag, flags=re.DOTALL)
    }


def schema_graph(document: str) -> list[dict[str, object]]:
    matches = re.findall(r'<script\s+type="application/ld\+json">(.*?)</script>', document, flags=re.DOTALL)
    if len(matches) != 1:
        raise ValueError(f"expected one JSON-LD script, found {len(matches)}")
    payload = json.loads(matches[0])
    graph = payload.get("@graph")
    if payload.get("@context") != "https://schema.org" or not isinstance(graph, list):
        raise ValueError("JSON-LD graph shape mismatch")
    return graph


def graph_node(graph: Sequence[Mapping[str, object]], node_id: str) -> Mapping[str, object]:
    matches = [node for node in graph if node.get("@id") == node_id]
    if len(matches) != 1:
        raise ValueError(f"schema node count mismatch: {node_id}: {len(matches)}")
    return matches[0]


def data_field(document: str, field_name: str) -> tuple[str, str]:
    count = len(re.findall(rf'\bdata-source-field="{re.escape(field_name)}"', document))
    if count != 1:
        raise ValueError(f"data source field count: {field_name}: {count}")
    pattern = re.compile(
        rf'<(?P<tag>[a-zA-Z][\w:-]*)\b(?P<attrs>[^>]*\bdata-source-field="{re.escape(field_name)}"[^>]*)>'
        rf'(?P<body>.*?)</(?P=tag)>', re.DOTALL,
    )
    match = pattern.search(document)
    if not match:
        raise ValueError(f"data source field element missing: {field_name}")
    value = html.unescape(re.sub(r"<[^>]+>", "", match.group("body"))).replace("\r\n", "\n")
    return value, match.group("attrs")


def extract_faq(document: str) -> tuple[tuple[str, str, str], ...]:
    section = re.search(r'<div class="faq-list grade-faq-list">(.*?)</div>', document, flags=re.DOTALL)
    if not section:
        raise ValueError("visible FAQ list missing")
    pattern = re.compile(
        r'<details class="grade-faq-item"\s+data-faq-topic="([^"]+)"[^>]*>'
        r'<summary>(.*?)</summary><p>(.*?)</p></details>', re.DOTALL,
    )
    return tuple((topic, strip_tags(question), strip_tags(answer)) for topic, question, answer in pattern.findall(section.group(1)))


def editorial_fragment(document: str) -> str:
    match = re.search(r'<section class="section grade-main-article"[^>]*>(.*?)</section>', document, flags=re.DOTALL)
    if not match:
        raise ValueError("grade main article missing")
    fragment = match.group(1)
    # Source-state prose is validated against CSV separately, and is not part
    # of the authored diversity corpus.
    fragment = re.sub(r'<div class="section-head">.*?</div>', "", fragment, count=1, flags=re.DOTALL)
    return fragment


def paragraph_texts(fragment: str) -> tuple[str, ...]:
    return tuple(strip_tags(value) for value in re.findall(r"<p\b[^>]*>(.*?)</p>", fragment, flags=re.DOTALL) if strip_tags(value))


def sentence_texts(paragraphs: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for paragraph in paragraphs:
        result.extend(normalize_space(value) for value in re.split(r"(?<=[.!?])\s+", paragraph) if normalize_space(value))
    return tuple(result)


def lexical_tokens(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[0-9A-Za-z가-힣]+", normalize_space(text).lower()))


def ngrams(tokens: Sequence[str], size: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[index:index + size]) for index in range(max(0, len(tokens) - size + 1))}


def normalized_editorial(value: str, bundle: SourceBundle) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    dynamic = [row["근처 수업가능 동네"].strip() for row in bundle.rows]
    dynamic += [profile.category for profile in CATEGORIES]
    dynamic += [profile.query_suffix for profile in CATEGORIES]
    dynamic += [profile.grade_short for profile in CATEGORIES]
    for token in sorted(set(dynamic), key=len, reverse=True):
        normalized = normalized.replace(token.lower(), " <dynamic> ")
    normalized = re.sub(r"\d+", "<n>", normalized)
    normalized = re.sub(r"[^\w<>]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def profile_for_category(category: str) -> CategoryProfile:
    return next(profile for profile in CATEGORIES if profile.category == category)


def validate_detail(
    root: Path, bundle: SourceBundle, document: Document,
) -> dict[str, object]:
    profile = profile_for_category(document.category)
    row = bundle.row_by_locality[document.locality]
    text = document.after.decode("utf-8")
    supported = is_supported(row, profile)
    title = f"{document.locality} {profile.query_suffix}"
    canonical = f"{DOMAIN}/{PARENT}/{profile.category}/{slug_ko(document.locality)}/"
    if text.count(f"<h1>{esc(title)}</h1>") != 1:
        raise ValueError(f"H1 mismatch: {document.path}")
    if text.count(f'<link rel="canonical" href="{esc(canonical)}">') != 1:
        raise ValueError(f"canonical mismatch: {document.path}")
    if text.count("<main data-grade-page") != 1:
        raise ValueError(f"detail main marker mismatch: {document.path}")
    main = re.search(r"<main\b.*?</main>", text, flags=re.DOTALL)
    if not main:
        raise ValueError(f"main missing: {document.path}")
    main_text = strip_tags(main.group(0))
    control = re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", text)
    if control:
        raise ValueError(f"forbidden HTML control character: {document.path}: U+{ord(control.group(0)):04X}")
    trailing = re.search(r"[ \t]+(?=\r?$)", text, flags=re.MULTILINE)
    if trailing:
        raise ValueError(f"trailing HTML whitespace: {document.path}")
    if UNSAFE_COPY_RE.search(main_text):
        raise ValueError(f"unsafe legacy/search copy: {document.path}: {UNSAFE_COPY_RE.search(main_text).group(0)}")
    marker_count = len(re.findall(r'data-source-status="unconfirmed-grade"', main.group(0)))
    if supported and marker_count:
        raise ValueError(f"supported page has unconfirmed marker: {document.path}")
    if not supported and marker_count < 3:
        raise ValueError(f"unsupported page lacks visible markers: {document.path}: {marker_count}")

    exact_fields = {
        "region": row["지역"].strip(), "city": row["시or구"].strip(),
        "locality": row["근처 수업가능 동네"].strip(), "center-name": row["센터명"].strip(),
        "address": row["센터 주소"].strip(), "registration-name": normalize_space(row["교육지원청명칭"]),
        "registration-number": row["교육지원청 등록번호"].strip(),
        "supported-grades": row[profile.grade_column].strip() or "원자료 미기재",
        "high-schools": row["타깃학교\n(고)"].strip() or "원자료 미기재",
    }
    for field_name, expected in exact_fields.items():
        actual, _ = data_field(text, field_name)
        if actual != expected:
            raise ValueError(f"source field mismatch: {document.path}: {field_name}: {actual!r} != {expected!r}")
    fee_value, fee_attrs = data_field(text, "fee-url")
    fee_url = row["센터 교습비"].strip()
    if fee_url:
        if fee_value != "센터 공통 교습비 링크" or tag_attributes(f"<a {fee_attrs}>").get("href") != fee_url:
            raise ValueError(f"fee source mismatch: {document.path}")
    elif fee_value != "미기재 상태":
        raise ValueError(f"blank fee state mismatch: {document.path}")
    guide = clean_location_guide(row["위치안내"])
    guide_count = len(re.findall(r'data-source-field="location-guide"', text))
    missing_guide_count = len(re.findall(r'data-source-status="missing-location-guide"', text))
    if guide:
        if guide_count != 1 or missing_guide_count:
            raise ValueError(f"location guide state mismatch: {document.path}")
        actual_guide, _ = data_field(text, "location-guide")
        guide_residual = re.search(
            r"(?:https?://|www\.)|\^{2,}|~|엘레베이터|"
            r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]|"
            r"^[\U0001F000-\U0001FAFF\u2600-\u27BF]|,(?=\S)|,\s*$|\(\s*\)",
            actual_guide,
            flags=re.IGNORECASE,
        )
        if actual_guide != guide or guide_residual:
            raise ValueError(f"location guide clean mismatch: {document.path}")
    elif guide_count or missing_guide_count != 1:
        raise ValueError(f"blank location guide marker mismatch: {document.path}")
    chips = tuple(strip_tags(value) for value in re.findall(r'<span data-source-school>(.*?)</span>', text, flags=re.DOTALL))
    if chips != parse_high_schools(row["타깃학교\n(고)"].strip()):
        raise ValueError(f"high-school chip mismatch: {document.path}: {chips}")

    faq = extract_faq(text)
    expected_faq = faq_pairs(profile, row, bundle.manuscripts[profile.category][document.locality], supported)
    if tuple(topic for topic, _, _ in faq) != ("grade", "schools", "location", "fee"):
        raise ValueError(f"FAQ topic order mismatch: {document.path}")
    if tuple((question, answer) for _, question, answer in faq) != expected_faq:
        raise ValueError(f"visible FAQ mismatch: {document.path}")

    graph = schema_graph(text)
    faq_node = graph_node(graph, f"{canonical}#faq")
    schema_faq = tuple(
        (item["name"], item["acceptedAnswer"]["text"])
        for item in faq_node.get("mainEntity", [])  # type: ignore[union-attr]
    )
    if schema_faq != expected_faq:
        raise ValueError(f"visible/schema FAQ parity mismatch: {document.path}")
    article_node = graph_node(graph, f"{canonical}#article")
    physical_node = graph_node(graph, physical_id(row))
    if supported:
        service = graph_node(graph, f"{canonical}#service")
        if service.get("provider") != {"@id": physical_id(row)} or service.get("educationalLevel") != profile.grade_long:
            raise ValueError(f"supported Service source mismatch: {document.path}")
        if article_node.get("educationalLevel") != profile.grade_long:
            raise ValueError(f"supported Article level mismatch: {document.path}")
    else:
        if any(node.get("@id") == f"{canonical}#service" for node in graph):
            raise ValueError(f"unsupported page Service present: {document.path}")
        if "educationalLevel" in article_node or article_node.get("mainEntity"):
            raise ValueError(f"unsupported Article level/service claim: {document.path}")
    if article_node.get("author") != {"@id": ROOT_ORG_ID} or article_node.get("publisher") != {"@id": ROOT_ORG_ID}:
        raise ValueError(f"Article brand author/publisher mismatch: {document.path}")
    if article_node.get("datePublished") != PUBLISH_DATE or article_node.get("dateModified") != PUBLISH_DATE:
        raise ValueError(f"Article date mismatch: {document.path}")
    if physical_node != physical_organization_schema(bundle, row):
        raise ValueError(f"physical organization mismatch: {document.path}")

    image_tags = re.findall(r"<img\b[^>]*>", main.group(0))
    if len(image_tags) != 2 or "display:none" in main.group(0):
        raise ValueError(f"detail image/hidden policy mismatch: {document.path}: {len(image_tags)}")
    expected_assets = [
        resolve_body_assets(root, bundle.images_by_locality[document.locality])[0],
        resolve_map_asset(root, row, bundle.images_by_locality[document.locality]),
    ]
    for image_index, (tag, asset) in enumerate(zip(image_tags, expected_assets)):
        attrs = tag_attributes(tag)
        actual_src = attrs.get("src", "").removeprefix("../../../")
        if actual_src != asset:
            raise ValueError(f"image source mismatch: {document.path}: {actual_src} != {asset}")
        width, height = image_dimensions(root, asset)
        if attrs.get("width") != str(width) or attrs.get("height") != str(height):
            raise ValueError(f"image dimension mismatch: {document.path}: {asset}")
        if attrs.get("decoding") != "async":
            raise ValueError(f"image decoding policy mismatch: {document.path}")
        if image_index == 0:
            if attrs.get("loading") != "eager" or attrs.get("fetchpriority") != "high":
                raise ValueError(f"hero image policy mismatch: {document.path}")
        elif attrs.get("loading") != "lazy" or "fetchpriority" in attrs:
            raise ValueError(f"below-fold image policy mismatch: {document.path}")
    rep_asset = resolve_rep_asset(root, list(bundle.rows).index(row))
    if f'<meta property="og:image" content="{DOMAIN}/{rep_asset}">' not in text:
        raise ValueError(f"OG representative mismatch: {document.path}")

    fragment = editorial_fragment(text)
    authored_text = strip_tags(fragment)
    if "관련 자료를 살피면서" in authored_text:
        raise ValueError(f"legacy repetitive cue connector: {document.path}")
    quoted_particle = re.search(r"’(?:을|를|이|가|와|과|은|는)\b", authored_text)
    if quoted_particle:
        raise ValueError(f"quoted-topic particle risk: {document.path}: {quoted_particle.group(0)}")
    repeated_topic_noun = re.search(r"(기록|확인|점검|질문|메모|자료|항목|기준)’\s+\1\b", authored_text)
    if repeated_topic_noun:
        raise ValueError(f"repeated topic noun: {document.path}: {repeated_topic_noun.group(0)}")
    authored_words = re.sub(r"[^0-9A-Za-z가-힣]+", " ", authored_text)
    adjacent_word = re.search(r"\b([가-힣]{2,})\s+\1\b", authored_words)
    if adjacent_word:
        raise ValueError(f"adjacent authored word repeat: {document.path}: {adjacent_word.group(0)}")
    repeated_focus = re.search(r"항목을 중심으로[^.!?]{0,100}중심(?:에|으로)", authored_text)
    if repeated_focus:
        raise ValueError(f"repeated authored focus phrase: {document.path}: {repeated_focus.group(0)}")
    authored_chars = len(authored_text)
    if not 2000 <= authored_chars <= 7500:
        raise ValueError(f"authored length out of range: {document.path}: {authored_chars}")
    h2_values = tuple(
        strip_tags(value)
        for value in re.findall(r"<h2\b[^>]*>(.*?)</h2>", fragment, flags=re.DOTALL)
    )
    if not 5 <= len(h2_values) <= 8:
        raise ValueError(f"authored H2 count: {document.path}: {len(h2_values)}")
    heading_openings = tuple(
        next(opening for opening in H2_OPENINGS if heading.startswith(f"{document.locality} {opening} "))
        for heading in h2_values
    )
    if len(heading_openings) != len(set(heading_openings)):
        raise ValueError(f"within-page H2 opening repeat: {document.path}: {heading_openings}")
    for heading in h2_values:
        heading_parts = re.search(r"‘([^’]+)’\s+(.+)$", heading)
        if heading_parts and set(normalize_space(heading_parts.group(1)).split()).intersection(
            normalize_space(heading_parts.group(2)).split()
        ):
            raise ValueError(f"H2 cue/ending word repeat: {document.path}: {heading}")
        heading_body = heading.removeprefix(f"{document.locality} ")
        heading_tokens = re.findall(r"[가-힣]{2,}", heading_body)
        if len(heading_tokens) != len(set(heading_tokens)):
            raise ValueError(f"H2 repeated Korean token: {document.path}: {heading}")
        repeated_concepts = tuple(
            concept for concept in H2_CONCEPTS if heading_body.count(concept) > 1
        )
        if repeated_concepts:
            raise ValueError(
                f"H2 repeated semantic concept: {document.path}: {repeated_concepts}: {heading}"
            )
    paragraphs = paragraph_texts(fragment)
    sentences = sentence_texts(paragraphs)
    if len(paragraphs) != len(set(paragraphs)) or len(sentences) != len(set(sentences)):
        raise ValueError(f"within-page editorial duplicate: {document.path}")
    if any(len(sentence) > 180 for sentence in sentences):
        raise ValueError(f"editorial sentence over 180 chars: {document.path}")
    if authored_text.count(document.locality) > 12:
        raise ValueError(f"editorial locality repetition: {document.path}: {authored_text.count(document.locality)}")
    if authored_text.count(title) > 3:
        raise ValueError(f"editorial exact-query repetition: {document.path}")
    manuscript = bundle.manuscripts[profile.category][document.locality]
    if any(cue not in authored_text for cue in manuscript.cues[:4]):
        raise ValueError(f"manuscript topic coverage missing: {document.path}: {manuscript.cues[:4]}")
    source_sentences = set(sentence_texts((normalize_space(manuscript.raw),)))
    if any(sentence in source_sentences for sentence in sentences):
        raise ValueError(f"raw manuscript sentence copied: {document.path}")
    overlap = ngrams(lexical_tokens(authored_text), 12) & ngrams(lexical_tokens(manuscript.raw), 12)
    if overlap:
        raise ValueError(f"raw manuscript normalized 12-gram copied: {document.path}: {next(iter(overlap))}")
    if SERVICE_CERTAINTY_RE.search(authored_text) and not supported:
        raise ValueError(f"unsupported authored service certainty: {document.path}: {SERVICE_CERTAINTY_RE.search(authored_text).group(0)}")
    return {
        "canonical": canonical, "meta": meta_description(profile, row, supported),
        "paragraphs": paragraphs, "sentences": sentences, "h2": h2_values,
        "physical_key": physical_key(row), "physical_schema": json_text(physical_node),
        "authored_chars": authored_chars,
    }


def validate_hub(bundle: SourceBundle, document: Document) -> None:
    profile = profile_for_category(document.category)
    text = document.after.decode("utf-8")
    if text.count("<main data-grade-directory") != 1:
        raise ValueError(f"hub marker mismatch: {document.path}")
    if len(re.findall(r'<a\b[^>]*\bdata-subject-town\b', text)) != 371:
        raise ValueError(f"hub town count mismatch: {document.path}")
    for marker in ("data-subject-search", "data-subject-search-status", "data-subject-search-reset"):
        if marker not in text:
            raise ValueError(f"hub search hook missing: {document.path}: {marker}")
    links = re.findall(r'<a href="([^"]+)/" data-subject-town\b', text)
    expected = [slug_ko(row["근처 수업가능 동네"]) for row in bundle.rows]
    if links != expected:
        raise ValueError(f"hub locality link order mismatch: {document.path}")
    supported = len(re.findall(r'data-source-status="supported"', text))
    unconfirmed = len(re.findall(r'data-source-status="unconfirmed-grade"', text))
    expected_supported = sum(is_supported(row, profile) for row in bundle.rows)
    if (supported, unconfirmed) != (expected_supported, 371 - expected_supported):
        raise ValueError(f"hub support counts mismatch: {document.path}: {(supported, unconfirmed)}")
    canonical = f"{DOMAIN}/{PARENT}/{profile.category}/"
    graph = schema_graph(text)
    item_list = graph_node(graph, f"{canonical}#itemlist")
    if item_list.get("numberOfItems") != 371 or len(item_list.get("itemListElement", [])) != 371:  # type: ignore[arg-type]
        raise ValueError(f"hub ItemList mismatch: {document.path}")


def validate_parent_hub(document: Document) -> None:
    text = document.after.decode("utf-8")
    if text.count("<main data-grade-category-hub>") != 1:
        raise ValueError("parent hub marker mismatch")
    for category, _ in ALL_CATEGORY_CARDS:
        if text.count(f'href="{category}/index.html"') != 1:
            raise ValueError(f"parent hub category link mismatch: {category}")
    graph = schema_graph(text)
    node = graph_node(graph, f"{DOMAIN}/{PARENT}/#categories")
    if node.get("numberOfItems") != 8 or len(node.get("itemListElement", [])) != 8:  # type: ignore[arg-type]
        raise ValueError("parent hub ItemList mismatch")


def sitemap_records(data: bytes) -> tuple[tuple[str, str, str, str], ...]:
    text = data.decode("utf-8")
    result: list[tuple[str, str, str, str]] = []
    for block in re.findall(r"<url>(.*?)</url>", text, flags=re.DOTALL):
        values: list[str] = []
        for tag in ("loc", "lastmod", "changefreq", "priority"):
            match = re.search(rf"<{tag}>(.*?)</{tag}>", block)
            if not match:
                raise ValueError(f"sitemap record missing {tag}")
            values.append(unquote(match.group(1)))
        result.append(tuple(values))  # type: ignore[arg-type]
    return tuple(result)


def validate_sitemap(document: Document, bundle: SourceBundle) -> None:
    actual = sitemap_records(document.after)
    if len(actual) != 4097:
        raise ValueError(f"sitemap final count mismatch: {len(actual)}")
    if document.before is None:
        raise ValueError("sitemap baseline missing")
    baseline = sitemap_records(document.before)
    if len(baseline) not in (2609, 4097):
        raise ValueError(f"sitemap baseline count mismatch: {len(baseline)}")
    baseline_existing = [record for record in baseline if not any(f"/{PARENT}/{profile.category}/" in record[0] for profile in CATEGORIES)]
    actual_existing = list(actual[:2609])
    if len(baseline_existing) != 2609 or len(actual_existing) != 2609:
        raise ValueError("sitemap existing record partition mismatch")
    for before_record, after_record in zip(baseline_existing, actual_existing):
        if before_record[0] == f"{DOMAIN}/{PARENT}/":
            expected = (before_record[0], PUBLISH_DATE, before_record[2], before_record[3])
            if after_record != expected:
                raise ValueError("parent hub sitemap freshness mismatch")
        elif before_record != after_record:
            raise ValueError(f"non-target sitemap record drift: {before_record[0]}")
    expected_new: list[tuple[str, str, str, str]] = []
    for profile in CATEGORIES:
        expected_new.append((f"{DOMAIN}/{PARENT}/{profile.category}/", PUBLISH_DATE, "weekly", "0.8"))
        expected_new.extend(
            (f"{DOMAIN}/{PARENT}/{profile.category}/{slug_ko(row['근처 수업가능 동네'])}/", PUBLISH_DATE, "monthly", "0.7")
            for row in bundle.rows
        )
    if tuple(actual[2609:]) != tuple(expected_new):
        raise ValueError("sitemap new route/order/metadata mismatch")


def validate_llms(document: Document) -> None:
    text = document.after.decode("utf-8")
    for profile in CATEGORIES:
        line = f"- {profile.category}: {DOMAIN}/{PARENT}/{profile.category}/"
        if text.count(line) != 1:
            raise ValueError(f"llms category line mismatch: {profile.category}")
    if document.before is None:
        raise ValueError("llms baseline missing")
    before = document.before.decode("utf-8-sig").replace("\r\n", "\n")
    after = text.replace("\r\n", "\n")
    for profile in CATEGORIES:
        generated_line = f"- {profile.category}: {DOMAIN}/{PARENT}/{profile.category}/\n"
        before = before.replace(generated_line, "")
        after = after.replace(generated_line, "")
    if after != before:
        raise ValueError("llms non-target content drift")


def validate_local_links(root: Path, documents: Sequence[Document]) -> None:
    projected = {document.path.resolve() for document in documents}
    for document in documents:
        if document.path.suffix.lower() != ".html":
            continue
        text = document.after.decode("utf-8")
        for href in re.findall(r'\bhref="([^"]+)"', text):
            if href.startswith(("http://", "https://", "tel:", "sms:", "mailto:", "#")):
                continue
            clean = href.split("#", 1)[0].split("?", 1)[0]
            if not clean:
                continue
            candidate = (document.path.parent / unquote(clean)).resolve()
            if clean.endswith("/"):
                candidate /= "index.html"
            if candidate.is_dir():
                candidate /= "index.html"
            if candidate not in projected and not candidate.is_file():
                raise ValueError(f"broken local href: {document.path}: {href} -> {candidate}")


def validate_documents(root: Path, bundle: SourceBundle, documents: Sequence[Document]) -> dict[str, object]:
    role_counts = Counter(document.role for document in documents)
    if role_counts != Counter({"detail": 1484, "hub": 4, "parent-hub": 1, "sitemap": 1, "llms": 1}):
        raise ValueError(f"document role counts mismatch: {role_counts}")
    detail_results: list[dict[str, object]] = []
    for document in documents:
        if document.role == "detail":
            detail_results.append(validate_detail(root, bundle, document))
        elif document.role == "hub":
            validate_hub(bundle, document)
        elif document.role == "parent-hub":
            validate_parent_hub(document)
        elif document.role == "sitemap":
            validate_sitemap(document, bundle)
        elif document.role == "llms":
            validate_llms(document)

    metas = [str(result["meta"]) for result in detail_results]
    canonicals = [str(result["canonical"]) for result in detail_results]
    if len(set(metas)) != 1484 or len(set(canonicals)) != 1484:
        raise ValueError("detail meta/canonical uniqueness mismatch")
    physical_variants: dict[str, set[str]] = defaultdict(set)
    paragraph_df: Counter[str] = Counter()
    sentence_df: Counter[str] = Counter()
    h2_df: Counter[str] = Counter()
    max_authored_chars = 0
    min_authored_chars = 10**9
    for result in detail_results:
        physical_variants[str(result["physical_key"])].add(str(result["physical_schema"]))
        max_authored_chars = max(max_authored_chars, int(result["authored_chars"]))
        min_authored_chars = min(min_authored_chars, int(result["authored_chars"]))
        normalized_paragraphs = {normalized_editorial(value, bundle) for value in result["paragraphs"]}  # type: ignore[union-attr]
        normalized_sentences = {normalized_editorial(value, bundle) for value in result["sentences"]}  # type: ignore[union-attr]
        normalized_h2 = {normalized_editorial(value, bundle) for value in result["h2"]}  # type: ignore[union-attr]
        if len(normalized_paragraphs) != len(result["paragraphs"]) or len(normalized_sentences) != len(result["sentences"]):  # type: ignore[arg-type]
            raise ValueError("within-page source-normalized duplicate")
        paragraph_df.update(normalized_paragraphs)
        sentence_df.update(normalized_sentences)
        h2_df.update(normalized_h2)
    if len(physical_variants) != 188 or any(len(values) != 1 for values in physical_variants.values()):
        raise ValueError("physical entity consistency mismatch")
    max_paragraph_df = max(paragraph_df.values(), default=0)
    max_sentence_df = max(sentence_df.values(), default=0)
    max_h2_df = max(h2_df.values(), default=0)
    if max_paragraph_df > 34 or max_sentence_df > 34 or max_h2_df > 40:
        raise ValueError(
            f"cross-page normalized DF exceeded: paragraph={max_paragraph_df}, sentence={max_sentence_df}, h2={max_h2_df}"
        )
    support_counts = {
        profile.category: sum(is_supported(row, profile) for row in bundle.rows)
        for profile in CATEGORIES
    }
    if support_counts != {"고1수학학원": 354, "고1영어학원": 362, "고2수학학원": 325, "고2영어학원": 332}:
        raise ValueError(f"source support counts drift: {support_counts}")
    validate_local_links(root, documents)
    return {
        "documents": len(documents), "details": 1484, "hubs": 4,
        "supported": sum(support_counts.values()), "unsupported": 1484 - sum(support_counts.values()),
        "support_by_category": support_counts,
        "normalized_paragraph_max_df": max_paragraph_df,
        "normalized_sentence_max_df": max_sentence_df,
        "normalized_h2_max_df": max_h2_df,
        "authored_chars_min": min_authored_chars, "authored_chars_max": max_authored_chars,
        "physical_centres": len(physical_variants),
    }


def normalize_overrides(
    root: Path, current_overrides: Mapping[Path | str, bytes | str | None] | None,
) -> dict[Path, bytes | None]:
    normalized: dict[Path, bytes | None] = {}
    for raw_path, raw_value in (current_overrides or {}).items():
        path = Path(raw_path)
        if not path.is_absolute():
            path = root / path
        value = raw_value.encode("utf-8") if isinstance(raw_value, str) else raw_value
        normalized[path.resolve()] = value
    return normalized


def current_bytes(path: Path, overrides: Mapping[Path, bytes | None]) -> bytes | None:
    resolved = path.resolve()
    if resolved in overrides:
        return overrides[resolved]
    return path.read_bytes() if path.is_file() else None


def make_document(
    *, path: Path, after: bytes, role: str, overrides: Mapping[Path, bytes | None],
    category: str = "", locality: str = "", supported: bool | None = None,
    manuscript: Manuscript | None = None,
) -> Document:
    return Document(
        path.resolve(), current_bytes(path, overrides), after, role, category, locality, supported,
        manuscript.sha256 if manuscript else "", manuscript.cues if manuscript else (),
    )


def render_documents(
    root: Path, bundle: SourceBundle, overrides: Mapping[Path, bytes | None],
) -> tuple[Document, ...]:
    documents: list[Document] = []
    for profile in CATEGORIES:
        hub_path = root / PARENT / profile.category / "index.html"
        documents.append(make_document(
            path=hub_path, after=render_category_hub(bundle, profile), role="hub",
            category=profile.category, overrides=overrides,
        ))
        for row_index, row in enumerate(bundle.rows):
            locality = row["근처 수업가능 동네"].strip()
            after, manuscript, supported = render_detail(root, bundle, profile, row, row_index)
            path = root / PARENT / profile.category / slug_ko(locality) / "index.html"
            documents.append(make_document(
                path=path, after=after, role="detail", category=profile.category,
                locality=locality, supported=supported, manuscript=manuscript, overrides=overrides,
            ))
    parent_path = root / PARENT / "index.html"
    documents.append(make_document(
        path=parent_path, after=render_parent_hub(), role="parent-hub", overrides=overrides,
    ))
    sitemap_path = root / "sitemap.xml"
    sitemap_before = current_bytes(sitemap_path, overrides)
    if sitemap_before is None:
        raise FileNotFoundError(sitemap_path)
    documents.append(make_document(
        path=sitemap_path, after=render_sitemap(sitemap_before, bundle), role="sitemap", overrides=overrides,
    ))
    llms_path = root / "llms.txt"
    llms_before = current_bytes(llms_path, overrides)
    if llms_before is None:
        raise FileNotFoundError(llms_path)
    documents.append(make_document(
        path=llms_path, after=render_llms(llms_before), role="llms", overrides=overrides,
    ))
    if len(documents) != 1491 or len({document.path for document in documents}) != 1491:
        raise ValueError(f"rendered document coverage mismatch: {len(documents)}")
    return tuple(documents)


def repository_manifest(root: Path, excluded_paths: Iterable[Path]) -> str:
    excluded = {path.resolve() for path in excluded_paths}
    digest = hashlib.sha256()
    transient_names = {".git", "tmp", "__pycache__", ".grade-pages-transaction", ".grade-pages.lock"}
    for path in sorted(root.rglob("*"), key=lambda value: value.relative_to(root).as_posix()):
        if not path.is_file() or path.resolve() in excluded:
            continue
        relative = path.relative_to(root)
        if any(part in transient_names for part in relative.parts):
            continue
        data = path.read_bytes()
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(data)).encode("ascii"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


def target_manifest(documents: Iterable[Document], *, use_after: bool) -> str:
    digest = hashlib.sha256()
    for document in sorted(documents, key=lambda value: value.path.as_posix()):
        data = document.after if use_after else document.before
        digest.update(document.path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        if data is None:
            digest.update(b"<missing>")
        else:
            digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


def build_plan(
    root: Path | None = None,
    source_dir: Path | None = None,
    common_dir: Path | None = None,
    current_overrides: Mapping[Path | str, bytes | str | None] | None = None,
) -> BuildPlan:
    site_root = (root or Path(__file__).resolve().parents[1]).resolve()
    source, common = discover_reference_dirs(site_root, source_dir, common_dir)
    overrides = normalize_overrides(site_root, current_overrides)
    bundle = load_sources(site_root, source, common)
    documents = render_documents(site_root, bundle, overrides)
    authorized = frozenset(document.path for document in documents)
    metrics = dict(validate_documents(site_root, bundle, documents))
    second_overrides = dict(overrides)
    second_overrides.update({document.path: document.after for document in documents})
    second_documents = render_documents(site_root, bundle, second_overrides)
    idempotent = all(
        first.path == second.path and second.before == first.after and second.after == first.after and not second.changed
        for first, second in zip(documents, second_documents)
    )
    if not idempotent:
        drift = [
            first.path.as_posix() for first, second in zip(documents, second_documents)
            if second.before != first.after or second.after != first.after
        ]
        raise ValueError(f"second-pass idempotency mismatch: {drift[:5]}")
    metrics.update({
        "changed": sum(document.changed for document in documents),
        "idempotent_second_pass_changes": sum(document.changed for document in second_documents),
        "target_before_manifest": target_manifest(documents, use_after=False),
        "target_after_manifest": target_manifest(documents, use_after=True),
    })
    external = repository_manifest(site_root, authorized)
    return BuildPlan(site_root, source, common, documents, authorized, True, (), metrics, external)


def project_second_pass(plan: BuildPlan) -> BuildPlan:
    return build_plan(
        root=plan.root, source_dir=plan.source_dir, common_dir=plan.common_dir,
        current_overrides={document.path: document.after for document in plan.documents},
    )


TRANSACTION_DIR_NAME = ".grade-pages-transaction"
LOCK_NAME = ".grade-pages.lock"


def fsync_file(path: Path) -> None:
    # Windows rejects FlushFileBuffers on some read-only handles.  Reopen the
    # already-written journal with write access so fsync is durable on both
    # Windows and POSIX without changing its bytes.
    with path.open("r+b") as handle:
        os.fsync(handle.fileno())


def write_durable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def write_journal(path: Path, payload: Mapping[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    write_durable(temporary, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    os.replace(temporary, path)
    fsync_file(path)


TRANSACTION_STATES = frozenset({"prepared", "committing", "rolling-back", "rolled-back", "complete"})
HEX64_RE = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class TransactionEntry:
    relative: str
    target: Path
    backup: Path
    stage: Path
    existed: bool
    before_sha256: str | None
    after_sha256: str


def checked_file_sha256(path: Path, label: str) -> str | None:
    if path.is_symlink():
        raise RuntimeError(f"transaction {label} must not be a symlink: {path}")
    if not path.exists():
        return None
    if not path.is_file():
        raise RuntimeError(f"transaction {label} is not a regular file: {path}")
    return sha256_file(path)


def validate_transaction_journal(
    root: Path, journal: Mapping[str, object], authorized_paths: Iterable[Path],
) -> tuple[str, tuple[TransactionEntry, ...]]:
    root = root.resolve()
    transaction_path = root / TRANSACTION_DIR_NAME
    if transaction_path.is_symlink():
        raise RuntimeError(f"transaction directory must not be a symlink: {transaction_path}")
    transaction = transaction_path.resolve()
    if not transaction.is_relative_to(root) or not transaction.is_dir():
        raise RuntimeError(f"invalid transaction directory: {transaction}")
    if set(journal) != {
        "version", "state", "entries", "external_manifest",
        "target_before_manifest", "target_after_manifest",
    }:
        raise RuntimeError(f"transaction journal keys malformed: {sorted(map(str, journal))}")
    if journal.get("version") != 1:
        raise RuntimeError(f"unsupported transaction journal version: {journal.get('version')!r}")
    state = journal.get("state")
    if not isinstance(state, str) or state not in TRANSACTION_STATES:
        raise RuntimeError(f"transaction journal state malformed: {state!r}")
    for name in ("external_manifest", "target_before_manifest", "target_after_manifest"):
        value = journal.get(name)
        if not isinstance(value, str) or not HEX64_RE.fullmatch(value):
            raise RuntimeError(f"transaction journal {name} malformed")
    raw_entries = journal.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise RuntimeError("transaction journal entries malformed")

    authorized_by_relative: dict[str, Path] = {}
    for raw_authorized in authorized_paths:
        authorized = Path(raw_authorized).resolve()
        if not authorized.is_relative_to(root):
            raise RuntimeError(f"authorized target escapes repository: {authorized}")
        relative = authorized.relative_to(root).as_posix()
        if relative in authorized_by_relative:
            raise RuntimeError(f"duplicate authorized target: {relative}")
        authorized_by_relative[relative] = authorized

    validated: list[TransactionEntry] = []
    seen: set[str] = set()
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict) or set(raw_entry) != {
            "path", "existed", "before_sha256", "after_sha256",
        }:
            raise RuntimeError("transaction journal entry malformed")
        relative_value = raw_entry.get("path")
        if not isinstance(relative_value, str) or "\\" in relative_value:
            raise RuntimeError(f"transaction path malformed: {relative_value!r}")
        relative = PurePosixPath(relative_value)
        if (
            relative.is_absolute() or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
            or relative.as_posix() != relative_value
        ):
            raise RuntimeError(f"unsafe transaction path: {relative_value!r}")
        if relative_value in seen:
            raise RuntimeError(f"duplicate transaction path: {relative_value}")
        seen.add(relative_value)
        if relative_value not in authorized_by_relative:
            raise RuntimeError(f"unauthorized transaction path: {relative_value}")
        target = authorized_by_relative[relative_value]
        candidate = (root / Path(*relative.parts)).resolve(strict=False)
        if candidate != target or not candidate.is_relative_to(root):
            raise RuntimeError(f"transaction target path mismatch: {relative_value}")

        existed = raw_entry.get("existed")
        before_hash = raw_entry.get("before_sha256")
        after_hash = raw_entry.get("after_sha256")
        if not isinstance(existed, bool):
            raise RuntimeError(f"transaction existed flag malformed: {relative_value}")
        if existed:
            if not isinstance(before_hash, str) or not HEX64_RE.fullmatch(before_hash):
                raise RuntimeError(f"transaction before hash malformed: {relative_value}")
        elif before_hash is not None:
            raise RuntimeError(f"new transaction target has before hash: {relative_value}")
        if not isinstance(after_hash, str) or not HEX64_RE.fullmatch(after_hash):
            raise RuntimeError(f"transaction after hash malformed: {relative_value}")

        backup_path = transaction / "backup" / Path(*relative.parts)
        stage_path = transaction / "stage" / Path(*relative.parts)
        if backup_path.is_symlink() or stage_path.is_symlink():
            raise RuntimeError(f"transaction entry file must not be a symlink: {relative_value}")
        backup = backup_path.resolve(strict=False)
        stage = stage_path.resolve(strict=False)
        for label, path, parent in (
            ("backup", backup, transaction / "backup"),
            ("stage", stage, transaction / "stage"),
        ):
            if not path.is_relative_to(parent.resolve(strict=False)):
                raise RuntimeError(f"transaction {label} path escapes transaction: {relative_value}")

        backup_hash = checked_file_sha256(backup, "backup")
        if existed and backup_hash != before_hash:
            raise RuntimeError(f"transaction backup hash mismatch: {relative_value}")
        if not existed and backup_hash is not None:
            raise RuntimeError(f"new transaction target unexpectedly has backup: {relative_value}")
        target_hash = checked_file_sha256(target, "target")
        stage_hash = checked_file_sha256(stage, "stage")
        expected_before = before_hash if existed else None
        if state == "prepared":
            valid_state = target_hash == expected_before and stage_hash == after_hash
        elif state == "committing":
            valid_state = (
                (target_hash == expected_before and stage_hash == after_hash)
                or (target_hash == after_hash and stage_hash is None)
            )
        elif state == "rolling-back":
            valid_state = target_hash in {expected_before, after_hash} and stage_hash in {None, after_hash}
        elif state == "rolled-back":
            valid_state = target_hash == expected_before and stage_hash in {None, after_hash}
        else:  # complete
            valid_state = target_hash == after_hash and stage_hash is None
        if not valid_state:
            raise RuntimeError(
                f"transaction file state mismatch: {relative_value}: state={state}, "
                f"target={target_hash}, stage={stage_hash}"
            )
        validated.append(TransactionEntry(
            relative_value, target, backup, stage, existed,
            before_hash if isinstance(before_hash, str) else None, after_hash,
        ))
    return state, tuple(validated)


def atomic_restore(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.rollback-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fsync_file(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def rollback_transaction(
    root: Path, journal: Mapping[str, object], authorized_paths: Iterable[Path],
) -> None:
    transaction = root / TRANSACTION_DIR_NAME
    state, entries = validate_transaction_journal(root, journal, authorized_paths)
    if state in {"complete", "rolled-back"}:
        shutil.rmtree(transaction, ignore_errors=False)
        return
    updated = dict(journal)
    updated["state"] = "rolling-back"
    write_journal(transaction / "journal.json", updated)
    # Revalidate the durable rollback state before touching any target.
    _, entries = validate_transaction_journal(root, updated, authorized_paths)
    for entry in reversed(entries):
        current_hash = checked_file_sha256(entry.target, "target")
        expected_before = entry.before_sha256 if entry.existed else None
        if current_hash == expected_before:
            continue
        if current_hash != entry.after_sha256:
            raise RuntimeError(f"target changed before rollback: {entry.relative}")
        if entry.existed:
            if checked_file_sha256(entry.backup, "backup") != entry.before_sha256:
                raise RuntimeError(f"backup changed before rollback: {entry.relative}")
            backup_data = entry.backup.read_bytes()
            if sha256_bytes(backup_data) != entry.before_sha256:
                raise RuntimeError(f"backup read was not stable: {entry.relative}")
            atomic_restore(entry.target, backup_data)
        else:
            entry.target.unlink()
    for entry in entries:
        expected_before = entry.before_sha256 if entry.existed else None
        if checked_file_sha256(entry.target, "target") != expected_before:
            raise RuntimeError(f"rollback verification failed: {entry.relative}")
    updated["state"] = "rolled-back"
    write_journal(transaction / "journal.json", updated)
    validate_transaction_journal(root, updated, authorized_paths)
    shutil.rmtree(transaction, ignore_errors=False)


def recover_transaction(root: Path, authorized_paths: Iterable[Path]) -> bool:
    transaction = root / TRANSACTION_DIR_NAME
    journal_path = transaction / "journal.json"
    if not transaction.exists():
        return False
    if journal_path.is_symlink() or not journal_path.is_file():
        raise RuntimeError(f"incomplete transaction without journal: {transaction}")
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    if not isinstance(journal, dict):
        raise RuntimeError("transaction journal root must be an object")
    authorized = tuple(authorized_paths)
    validate_transaction_journal(root, journal, authorized)
    if repository_manifest(root, authorized) != journal["external_manifest"]:
        raise RuntimeError("external repository drift blocks transaction recovery")
    rollback_transaction(root, journal, authorized)
    return True


class RepoLock:
    def __init__(self, root: Path) -> None:
        self.path = root / LOCK_NAME
        self.fd: int | None = None

    def __enter__(self) -> "RepoLock":
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            raise RuntimeError(f"repository lock already exists: {self.path}") from error
        os.write(self.fd, f"pid={os.getpid()}\n".encode("ascii"))
        os.fsync(self.fd)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.fd is not None:
            os.close(self.fd)
        self.path.unlink(missing_ok=True)


def apply_plan(plan: BuildPlan) -> BuildPlan:
    root = plan.root
    with RepoLock(root):
        recover_transaction(root, plan.authorized_paths)
        fresh = build_plan(root, plan.source_dir, plan.common_dir)
        if target_manifest(fresh.documents, use_after=False) != target_manifest(plan.documents, use_after=False):
            raise RuntimeError("target files changed after projection")
        if fresh.external_manifest != plan.external_manifest:
            raise RuntimeError("external files changed after projection")
        changed = [document for document in fresh.documents if document.changed]
        if not changed:
            return fresh
        transaction = root / TRANSACTION_DIR_NAME
        transaction.mkdir(parents=False, exist_ok=False)
        entries: list[dict[str, object]] = []
        try:
            for document in changed:
                relative = document.path.relative_to(root).as_posix()
                staged = transaction / "stage" / relative
                backup = transaction / "backup" / relative
                write_durable(staged, document.after)
                if document.before is not None:
                    write_durable(backup, document.before)
                entries.append({
                    "path": relative,
                    "existed": document.before is not None,
                    "before_sha256": sha256_bytes(document.before) if document.before is not None else None,
                    "after_sha256": sha256_bytes(document.after),
                })
            journal_path = transaction / "journal.json"
            journal: dict[str, object] = {
                "version": 1, "state": "prepared", "entries": entries,
                "external_manifest": fresh.external_manifest,
                "target_before_manifest": target_manifest(fresh.documents, use_after=False),
                "target_after_manifest": target_manifest(fresh.documents, use_after=True),
            }
            write_journal(journal_path, journal)
            validate_transaction_journal(root, journal, fresh.authorized_paths)
            if repository_manifest(root, fresh.authorized_paths) != fresh.external_manifest:
                raise RuntimeError("external drift before commit")
            for document in fresh.documents:
                actual = document.path.read_bytes() if document.path.is_file() else None
                if actual != document.before:
                    raise RuntimeError(f"target drift before commit: {document.path}")
            journal["state"] = "committing"
            write_journal(journal_path, journal)
            validate_transaction_journal(root, journal, fresh.authorized_paths)
            for document in changed:
                staged = transaction / "stage" / document.path.relative_to(root)
                if checked_file_sha256(staged, "stage") != sha256_bytes(document.after):
                    raise RuntimeError(f"stage drift immediately before commit: {document.path}")
                # Keep the target-byte comparison as the final operation before
                # replacement so a change after the global preflight cannot be
                # overwritten merely because hashing the stage took time.
                actual = document.path.read_bytes() if document.path.is_file() else None
                if actual != document.before:
                    raise RuntimeError(f"target drift immediately before commit: {document.path}")
                document.path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, document.path)
            validate_transaction_journal(root, journal, fresh.authorized_paths)
            verified = build_plan(root, plan.source_dir, plan.common_dir)
            if verified.changes:
                raise RuntimeError(f"post-apply projection is not clean: {len(verified.changes)}")
            if verified.external_manifest != fresh.external_manifest:
                raise RuntimeError("external drift after commit")
            journal["state"] = "complete"
            write_journal(journal_path, journal)
            validate_transaction_journal(root, journal, fresh.authorized_paths)
            shutil.rmtree(transaction)
            return verified
        except BaseException:
            journal_path = transaction / "journal.json"
            if journal_path.is_file():
                recover_transaction(root, fresh.authorized_paths)
            else:
                shutil.rmtree(transaction, ignore_errors=True)
            raise


def cli_payload(plan: BuildPlan) -> dict[str, object]:
    return {
        "status": "PASS", "mode": "check", "root": str(plan.root),
        "documents": len(plan.documents), "changed": len(plan.changes),
        "idempotent": plan.idempotent, "metrics": dict(plan.metrics),
        "external_manifest": plan.external_manifest,
        "generator_sha256": sha256_file(Path(__file__).resolve()),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--common-dir", type=Path)
    parser.add_argument("--apply", action="store_true", help="atomically write the validated projection")
    parser.add_argument("--json", action="store_true", help="print machine-readable metrics")
    args = parser.parse_args(argv)
    plan = build_plan(args.root, args.source_dir, args.common_dir)
    payload = cli_payload(plan)
    if args.apply:
        final_plan = apply_plan(plan)
        payload["mode"] = "apply"
        payload["applied"] = len(plan.changes)
        payload["post_apply_changed"] = len(final_plan.changes)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        metrics = payload["metrics"]
        print(
            f"PASS mode={payload['mode']} documents={payload['documents']} changed={payload['changed']} "
            f"supported={metrics['supported']} unsupported={metrics['unsupported']} "  # type: ignore[index]
            f"paragraph_df={metrics['normalized_paragraph_max_df']} "  # type: ignore[index]
            f"sentence_df={metrics['normalized_sentence_max_df']} h2_df={metrics['normalized_h2_max_df']} "  # type: ignore[index]
            f"idempotent={payload['idempotent']}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, Exception) as error:
        print(f"HOLD: {error}", file=sys.stderr)
        raise
