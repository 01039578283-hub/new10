from __future__ import annotations

import hashlib
import re
from collections import Counter
from itertools import permutations
from pathlib import Path
from zipfile import ZipFile

import generate_wawa_academy_pages as shared


SITE = shared.SITE
BASE = SITE.parent
COMMON = shared.COMMON
SITE_NAME = shared.SITE_NAME
PHONE_DISPLAY = shared.PHONE_DISPLAY
PHONE_LINK = shared.PHONE_LINK
PUBLISH_DATE = "2026-07-25"
DOMAIN = "https://xn--9p4bn5e1r987b.com"


def korean_date(iso_value: str) -> str:
    year, month, day = iso_value.split("-")
    return f"{int(year)}년 {int(month)}월 {int(day)}일"


PUBLISH_DATE_KO = korean_date(PUBLISH_DATE)

PARENT = "과목별학원"
CATEGORY = "중2수학학원"
TITLE_SUFFIX = " 중2 수학학원"
SUBJECT_LABEL = "중2 수학"
SUBJECT = "수학"
SUBJECT_EN = "MATH"
GRADE_TEXT = "중학교 2학년"
FOCUS_LABEL = "내신·오답관리"
ZIP_PATH = BASE / "참고자료" / "사용한 원고" / "영수학원.com 추가 원고" / "중2 수학학원.zip"

# Categories expected to join this same PARENT tree later (같은 폴더의 나머지 ZIP).
# 존재하지 않으면 그냥 건너뛰므로 미리 등록해 두어도 안전하다.
SIBLING_CATEGORY_META: dict[str, str] = {
    "중2수학학원": f"중2 수학 {FOCUS_LABEL} 지역별 안내",
    "중2영어학원": "중2 영어 내신·서술형 대비 지역별 안내",
    "중3수학학원": "중3 수학 내신전략·오답관리 지역별 안내",
    "중3영어학원": "중3 영어 내신·고1 연계 대비 지역별 안내",
}

esc = shared.esc
read_csv = shared.read_csv
slug_ko = shared.slug_ko
split_items = shared.split_items
seed_for = shared.seed_for
school_type = shared.school_type
eul_reul = shared.eul_reul
eun_neun = shared.eun_neun
nav_html = shared.nav_html
footer_html = shared.footer_html
head_html = shared.head_html
page_shell = shared.page_shell
find_map = shared.find_map
school_names = shared.school_names
region_blocks_html = shared.region_blocks_html
cross_category_links_html = shared.cross_category_links_html
FEE_TABLE_SEOUL = shared.FEE_TABLE_SEOUL
FEE_TABLE_OTHER = shared.FEE_TABLE_OTHER


# ---------------------------------------------------------------------------
# manuscript parsing ([페이지타이틀]/[메타설명]/[본문]/[FAQ]/[학부모후기]/[JSON-LD 요약])
# ---------------------------------------------------------------------------

SECTION_RE = re.compile(
    r"^\[(페이지타이틀|메타설명|본문|FAQ|학부모후기|JSON-LD 요약)\]\s*$",
    re.MULTILINE,
)
FAQ_RE = re.compile(
    r"Q\d+\.\s*(.+?)\s*\nA\d+\.\s*(.+?)(?=\nQ\d+\.|\Z)",
    re.DOTALL,
)


DEDUPE_WORD_RE = re.compile(r"(?<!\S)(\S{2,})([ \t]+)\1(?!\S)")


def dedupe_adjacent_words(value: str) -> str:
    """원고 생성 과정에서 섞여 들어간 '직접 직접'류 단순 중복 오타만 교정한다 (사실·문장 내용은 변경하지 않음)."""
    previous = None
    while previous != value:
        previous = value
        value = DEDUPE_WORD_RE.sub(r"\1", value)
    return value


def parse_manuscript(text: str) -> dict[str, str]:
    matches = list(SECTION_RE.finditer(text))
    parsed: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        parsed[match.group(1)] = text[match.end():end].strip()
    required = {"페이지타이틀", "메타설명", "본문", "FAQ", "학부모후기", "JSON-LD 요약"}
    missing = required - parsed.keys()
    if missing:
        raise ValueError(f"원고 구역 누락: {sorted(missing)}")
    for key, value in parsed.items():
        if key != "페이지타이틀":
            parsed[key] = dedupe_adjacent_words(value)
    return parsed


def load_manuscripts() -> dict[str, dict[str, str]]:
    if not ZIP_PATH.exists():
        raise FileNotFoundError(ZIP_PATH)
    manuscripts: dict[str, dict[str, str]] = {}
    with ZipFile(ZIP_PATH) as archive:
        names = sorted(name for name in archive.namelist() if name.lower().endswith(".txt"))
        for name in names:
            text = archive.read(name).decode("utf-8-sig")
            parsed = parse_manuscript(text)
            title = parsed["페이지타이틀"].strip()
            if not title.endswith(TITLE_SUFFIX):
                raise ValueError(f"예상하지 못한 페이지 제목: {title}")
            local = title[: -len(TITLE_SUFFIX)].strip()
            if local in manuscripts:
                raise ValueError(f"중복 원고: {local}")
            manuscripts[local] = parsed
    return manuscripts


def parse_body(value: str) -> tuple[list[str], list[tuple[str, list[str]]]]:
    intro: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current_title = ""
    current_paragraphs: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_paragraphs
        if current_title:
            sections.append((current_title, current_paragraphs))
        current_title = ""
        current_paragraphs = []

    chunks = re.split(r"\n\s*\n", value.strip())
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.startswith("## "):
            flush()
            lines = chunk.splitlines()
            current_title = lines[0][3:].strip()
            rest = "\n".join(lines[1:]).strip()
            if rest:
                current_paragraphs.append(rest)
        elif current_title:
            current_paragraphs.append(chunk)
        else:
            intro.append(chunk)
    flush()
    return intro, sections


def parse_faq(value: str) -> list[tuple[str, str]]:
    faqs = [(q.strip(), re.sub(r"\s+", " ", a).strip()) for q, a in FAQ_RE.findall(value)]
    if not faqs:
        raise ValueError("FAQ 질문·답변을 해석하지 못했습니다.")
    return faqs


def parse_review(value: str) -> tuple[str, list[str]]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", value.strip()) if p.strip()]
    note = ""
    quotes: list[str] = []
    for paragraph in paragraphs:
        if paragraph.startswith("※"):
            note = paragraph
        else:
            quotes.append(paragraph)
    if not quotes:
        raise ValueError("학부모후기 예시를 해석하지 못했습니다.")
    return note, quotes


def paragraph_signature(value: str, local: str) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    normalized = normalized.replace(local, "<LOCAL>")
    return re.sub(r"\d+(?:-\d+)*", "<NUM>", normalized)


def repeated_body_signatures(manuscripts: dict[str, dict[str, str]]) -> set[str]:
    counts: Counter[str] = Counter()
    for local, manuscript in manuscripts.items():
        intro, sections = parse_body(manuscript["본문"])
        for paragraph in intro:
            counts[paragraph_signature(paragraph, local)] += 1
        for _, paragraphs in sections:
            for paragraph in paragraphs:
                counts[paragraph_signature(paragraph, local)] += 1
    return {signature for signature, count in counts.items() if count > 1}


def order_sections_for_page(
    sections: list[tuple[str, list[str]]], local: str
) -> list[tuple[str, list[str]]]:
    if len(sections) < 6:
        return sections
    flexible_count = 4
    patterns = list(permutations(range(flexible_count)))
    digest = hashlib.sha256(f"{CATEGORY}|{local}|section-order".encode("utf-8")).digest()
    pattern = patterns[int.from_bytes(digest[:2], "big") % len(patterns)]
    return [sections[index] for index in pattern] + sections[flexible_count:]


def contextualize_repeated_paragraph(
    value: str,
    *,
    local: str,
    region: str,
    district: str,
    section_title: str,
    section_index: int,
    paragraph_index: int,
    repeated_signatures: set[str],
) -> str:
    if paragraph_signature(value, local) not in repeated_signatures:
        return value
    seed = f"{CATEGORY}|{local}|{section_title}|{section_index}|{paragraph_index}".encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    evidence = [
        "최근 시험지의 오답 표시", "학교 범위표와 교과서 진도", "주간 과제 완료 기록",
        "해설 없이 다시 푼 결과", "단원별 풀이 시간", "서술 과정에서 빠진 조건",
        "수업 뒤에 남긴 질문 목록", "시험 전 남은 학습일", "교재별 완료 범위",
        "오답을 다시 확인할 날짜", "학생이 설명한 풀이 근거",
    ][digest[0] % 11]
    outcome = [
        "다음 점검 시점", "우선 복습 단원", "혼자 다시 풀 문제", "질문 순서",
        "시험 전 완료 범위", "과제량 조절 시점", "보충 설명이 필요한 개념",
        "재풀이 성공 여부", "학교 자료 복습 순서", "주간 최소 학습량", "상담 후 점검 항목",
    ][digest[1] % 11]
    location = " ".join(part for part in (region, district, local) if part)
    templates = [
        f"{location} 상담에서는 {evidence} 항목과 {outcome} 항목을 함께 정리해야 이 기준을 실제 학습 계획으로 옮기기 쉽습니다.",
        f"이 기준을 {local} 학생에게 적용할 때는 확인 자료로 {evidence} 항목을 살핀 뒤, 후속 계획으로 {outcome} 항목을 정하는 순서가 적절합니다.",
        f"{local}의 실제 계획에는 {evidence} 점검과 {outcome} 설정이 함께 들어가야 상담 내용이 수업 후에도 이어집니다.",
        f"학부모가 {local}에서 이 항목을 비교한다면 {evidence} 관리 방식과 {outcome} 설정 기준을 물어볼 수 있습니다.",
        f"{location}에서는 {evidence} 자료를 판단 근거로 삼고, 상담 후에는 {outcome} 내용을 짧게 정리해 두는 편이 좋습니다.",
        f"학생의 설명을 들은 뒤 {evidence} 항목을 확인하고 {outcome} 기준을 함께 정하면 {local}의 학습 계획이 더 구체적으로 바뀝니다.",
        f"{section_title} 내용을 점검할 때 {local}에서는 {evidence} 점검과 {outcome} 설정을 한 흐름으로 연결해 보는 것이 좋습니다.",
    ]
    base = value.rstrip()
    separator = "" if base.endswith((".", "?", "!", "다.", "요.")) else "."
    return f"{base}{separator} {templates[digest[2] % len(templates)]}"


def compact_meta_description(value: str, title: str, index: int) -> str:
    description = re.sub(r"\s+", " ", value).strip()
    if 80 <= len(description) <= 155:
        return description
    variants = [
        f"학생 진단, 학교 자료 확인, {FOCUS_LABEL} 관련 상담 전 확인 항목을 정리했습니다.",
        f"최근 오답과 학교 시험 범위를 바탕으로 {FOCUS_LABEL} 관련 상담 질문과 위치 정보를 안내합니다.",
        f"학생의 반복 오류와 {FOCUS_LABEL} 관련 상담 전 점검 항목을 확인할 수 있습니다.",
        f"학생의 학습 기록과 {FOCUS_LABEL} 관련 상담 기준을 함께 살펴봅니다.",
    ]
    first_sentence_match = re.match(r"(.+?[.!?])(?:\s|$)", description)
    first_sentence = (
        first_sentence_match.group(1).strip()
        if first_sentence_match
        else f"{title} 선택 기준을 안내합니다."
    )
    candidate = f"{first_sentence} {variants[index % len(variants)]}"
    if len(candidate) <= 155:
        return candidate if len(candidate) >= 80 else description[:155]
    suffix = " 핵심 학습관리와 상담 기준을 정리했습니다."
    allowed = 155 - len(suffix)
    shortened = candidate[:allowed].rstrip(" ,·")
    if " " in shortened:
        shortened = shortened.rsplit(" ", 1)[0].rstrip(" ,·")
    return f"{shortened}{suffix}"[:155].rstrip(" ,·")


# ---------------------------------------------------------------------------
# small generic content banks (freshly authored, not from the manuscript —
# process guidance / editorial comparison, no locality-specific facts)
# ---------------------------------------------------------------------------

CHECKLIST_BANK: list[tuple[str, str]] = [
    ("최근 시험지", "점수보다 어떤 단원에서 왜 틀렸는지 확인하는 데 필요합니다."),
    ("학교 시험 범위", "다니는 학교의 시험 범위와 수행평가 일정을 확인합니다."),
    ("현재 교재·진도", "지금까지 사용한 교재와 진도를 확인해 시작 지점을 잡습니다."),
    ("오답 정리 습관", "기존에 오답을 정리해 온 방법이 있다면 함께 확인합니다."),
]

COMPARE_ROWS: list[dict[str, str]] = [
    {"label": "학습 진단", "other": "정해진 진도만 그대로 진행", "ours": "학교 시험 범위부터 먼저 확인"},
    {"label": "내신 대비", "other": "문제집 반복 풀이 위주", "ours": "학교별 진도·범위에 맞춘 개별 확인"},
    {"label": "오답 관리", "other": "채점만 하고 다음 진도로 이동", "ours": "오답 원인을 구분한 뒤 재풀이 확인"},
    {"label": "학습 관리", "other": "정해진 분량만 소화", "ours": "실행 결과를 보고 계획을 다시 조정"},
]




# ---------------------------------------------------------------------------
# JSON-LD
# ---------------------------------------------------------------------------

def page_ld(
    *,
    row: dict[str, str],
    title: str,
    description: str,
    summary: str,
    canonical: str,
    rep_image: str,
    center_image: str,
    map_image: str,
    faqs: list[tuple[str, str]],
    sections: list[tuple[str, list[str]]],
    related: list[tuple[str, str]],
) -> dict:
    local = row["근처 수업가능 동네"].strip()
    region = row.get("지역", "").strip()
    district = row.get("시or구", "").strip()
    center = row.get("센터명", "").strip() or f"{local} 학습관리"
    address = row.get("센터 주소", "").strip()
    schools = school_names(row)
    org_id = f"{canonical}#organization"
    webpage_id = f"{canonical}#webpage"
    article_id = f"{canonical}#article"
    service_id = f"{canonical}#service"
    breadcrumb_id = f"{canonical}#breadcrumb"
    faq_id = f"{canonical}#faq"

    about = [
        {"@type": "Thing", "name": title},
        {"@type": "Place", "name": local},
        {"@type": "Thing", "name": SUBJECT_LABEL},
        {"@type": "Thing", "name": f"{GRADE_TEXT} 수학"},
        {"@type": "Thing", "name": "내신 대비"},
        {"@type": "Thing", "name": "오답 재학습"},
    ]
    mentions = [
        {"@type": "Place", "name": region},
        {"@type": "Place", "name": district},
        {"@type": "EducationalOrganization", "name": center},
    ] + [{"@type": school_type(s), "name": s} for s in schools]
    section_names = [name for name, _ in sections]
    has_part = section_names + ["센터 기준 정보", "학습료 안내", "상담 전 체크리스트", "FAQ", "학부모 상담 후기 예시", "근처 학원페이지"]

    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebPage",
                "@id": webpage_id,
                "url": canonical,
                "name": title,
                "description": description,
                "inLanguage": "ko-KR",
                "primaryImageOfPage": {"@id": f"{canonical}#primaryimage"},
                "breadcrumb": {"@id": breadcrumb_id},
                "mainEntity": {"@id": service_id},
                "about": about,
                "mentions": mentions,
                "hasPart": [{"@type": "WebPageElement", "name": x} for x in has_part],
            },
            {"@type": "ImageObject", "@id": f"{canonical}#primaryimage", "url": rep_image, "caption": f"{title} 대표 이미지"},
            {
                "@type": "BreadcrumbList",
                "@id": breadcrumb_id,
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{DOMAIN}/"},
                    {"@type": "ListItem", "position": 2, "name": PARENT, "item": f"{DOMAIN}/{PARENT}/"},
                    {"@type": "ListItem", "position": 3, "name": CATEGORY, "item": f"{DOMAIN}/{PARENT}/{CATEGORY}/"},
                    {"@type": "ListItem", "position": 4, "name": title, "item": canonical},
                ],
            },
            {
                "@type": ["EducationalOrganization", "LocalBusiness"],
                "@id": org_id,
                "name": title,
                "alternateName": [SITE_NAME, center, f"{local} {SUBJECT_LABEL} 학습관리"],
                "url": canonical,
                "telephone": PHONE_DISPLAY,
                "openingHours": "Mo-Sa 12:00-24:00",
                "openingHoursSpecification": [{
                    "@type": "OpeningHoursSpecification",
                    "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
                    "opens": "12:00",
                    "closes": "24:00",
                }],
                "areaServed": {"@type": "Place", "name": local},
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": address,
                    "addressRegion": region,
                    "addressLocality": district,
                    "addressCountry": "KR",
                },
                "knowsAbout": [SUBJECT_LABEL, "내신 대비", "오답 관리", "학습 상담"],
                "makesOffer": [
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} {SUBJECT_LABEL} 진단 상담", "serviceType": "TutoringService"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 내신 대비 관리", "serviceType": "TutoringService"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 오답 재학습 관리", "serviceType": "TutoringService"}},
                ],
            },
            {
                "@type": "Article",
                "@id": article_id,
                "headline": title,
                "description": summary,
                "image": [rep_image, center_image, map_image],
                "inLanguage": "ko-KR",
                "datePublished": PUBLISH_DATE,
                "dateModified": PUBLISH_DATE,
                "author": {"@id": org_id},
                "publisher": {"@type": "Organization", "name": SITE_NAME, "url": f"{DOMAIN}/"},
                "mainEntityOfPage": {"@id": webpage_id},
                "about": about,
                "mentions": mentions,
                "articleSection": section_names,
            },
            {
                "@type": "Service",
                "@id": service_id,
                "name": f"{title} 학습관리",
                "serviceType": "TutoringService",
                "description": summary,
                "provider": {"@id": org_id},
                "areaServed": {"@type": "Place", "name": local},
                "audience": {"@type": "EducationalAudience", "educationalRole": f"{GRADE_TEXT} 학생"},
                "about": about,
                "mentions": mentions,
                "offers": {
                    "@type": "Offer",
                    "url": canonical,
                    "availability": "https://schema.org/InStock",
                    "itemOffered": {"@id": service_id},
                },
            },
            {
                "@type": "FAQPage",
                "@id": faq_id,
                "mainEntity": [
                    {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                    for q, a in faqs
                ],
            },
            {
                "@type": "ItemList",
                "@id": f"{canonical}#schools",
                "name": f"{title} 수업 가능 학교 참고",
                "numberOfItems": len(schools),
                "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": s} for i, s in enumerate(schools)],
            },
            {
                "@type": "ItemList",
                "@id": f"{canonical}#related",
                "name": f"{title} 관련 내부링크",
                "itemListElement": [
                    {"@type": "ListItem", "position": i + 1, "name": name, "url": url}
                    for i, (name, url) in enumerate(related)
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# local page
# ---------------------------------------------------------------------------

def detail_page(
    row: dict[str, str],
    index: int,
    manuscript: dict[str, str],
    rows: list[dict[str, str]],
    repeated_signatures: set[str],
) -> str:
    local = row["근처 수업가능 동네"].strip()
    slug = slug_ko(local)
    region = row.get("지역", "").strip()
    district = row.get("시or구", "").strip()
    center = row.get("센터명", "").strip() or f"{local} 학습관리"
    address = row.get("센터 주소", "").strip()
    reg_no = row.get("교육지원청 등록번호", "").strip()
    education_name = row.get("교육지원청명칭", "").strip()
    schools = school_names(row)

    title = manuscript["페이지타이틀"].strip()
    description = compact_meta_description(manuscript["메타설명"], title, index)
    summary = re.sub(r"\s+", " ", manuscript["JSON-LD 요약"]).strip()
    intro, sections = parse_body(manuscript["본문"])
    sections = order_sections_for_page(sections, local)
    faqs = parse_faq(manuscript["FAQ"])
    review_note, review_quotes = parse_review(manuscript["학부모후기"])

    canonical_path = f"/{PARENT}/{CATEGORY}/{slug}/"
    canonical = DOMAIN + canonical_path
    rep_path = shared.choose_random_rep_image(local, slug, "me2math")
    rep_image_abs = DOMAIN + "/" + rep_path
    center_img = "assets/centers/common/seoul6839.jpg" if region == "서울" else "assets/centers/common/local6839.jpg"
    map_img = find_map(row)
    center_image_abs = DOMAIN + "/" + center_img
    map_image_abs = DOMAIN + "/" + map_img

    nearby_rows = [rows[(index + offset) % len(rows)] for offset in (-2, -1, 1, 2)]
    nearby = [
        (f"{item['근처 수업가능 동네']} {CATEGORY}", f"{DOMAIN}/{PARENT}/{CATEGORY}/{slug_ko(item['근처 수업가능 동네'])}/")
        for item in nearby_rows
    ]
    related_for_schema = [(CATEGORY, f"{DOMAIN}/{PARENT}/{CATEGORY}/"), (PARENT, f"{DOMAIN}/{PARENT}/")] + nearby

    ld = page_ld(
        row=row, title=title, description=description, summary=summary,
        canonical=canonical, rep_image=rep_image_abs, center_image=center_image_abs,
        map_image=map_image_abs, faqs=faqs, sections=sections, related=related_for_schema,
    )
    head = head_html(f"{title} | {SITE_NAME}", description, 3, canonical, "article", rep_image_abs, ld)

    rendered_intro = [
        contextualize_repeated_paragraph(
            paragraph, local=local, region=region, district=district,
            section_title=f"{title} 핵심 요약", section_index=-1, paragraph_index=pi,
            repeated_signatures=repeated_signatures,
        )
        for pi, paragraph in enumerate(intro)
    ]
    rendered_sections = [
        (
            section_title,
            [
                contextualize_repeated_paragraph(
                    paragraph, local=local, region=region, district=district,
                    section_title=section_title, section_index=si, paragraph_index=pi,
                    repeated_signatures=repeated_signatures,
                )
                for pi, paragraph in enumerate(paragraphs)
            ],
        )
        for si, (section_title, paragraphs) in enumerate(sections)
    ]

    badge_row = f'<div class="badge-row"><span>{esc(region)}</span><span>{esc(district)}</span><span>{esc(SUBJECT_LABEL)}</span><span>{esc(FOCUS_LABEL)}</span></div>'

    rep_rel = "../../../" + rep_path
    center_rel = "../../../" + center_img
    map_rel = "../../../" + map_img
    media_section = f"""    <section class="section">
      <img src="{esc(rep_rel)}" alt="{esc(title + ' ' + SITE_NAME + ' 대표')}" style="display:none;">
      <div class="media-row">
        <figure class="frame"><img src="{esc(center_rel)}" alt="{esc(title + ' 본문 ' + SITE_NAME)}"></figure>
        <figure class="frame"><img src="{esc(map_rel)}" alt="{esc(title + ' 지도 ' + SITE_NAME)}"></figure>
      </div>
      <p class="lead">{esc(center)} 기준으로 {esc(local)} 학생의 상담 범위를 확인합니다. 실제 방문·상담 전에는 주소와 이동 동선을 함께 확인해 주세요.</p>
    </section>"""

    summary_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">핵심 요약</p>
        <h2>{esc(title)} 30초 요약</h2>
        <p class="lead">{esc(summary)}</p>
      </div>
    </section>"""

    intro_html = "".join(f"<p>{esc(paragraph)}</p>" for paragraph in rendered_intro)
    section_html = "\n".join(
        f"""      <article class="manuscript-card">
        <h2>{esc(section_title)}</h2>
        {''.join(f'<p>{esc(paragraph)}</p>' for paragraph in paragraphs)}
      </article>"""
        for section_title, paragraphs in rendered_sections
    )
    manuscript_section = f"""    <section class="section manuscript-section">
      <div class="section-head">
        <p class="eyebrow">LOCAL STUDY GUIDE</p>
        <h2>{esc(title)} 선택 기준</h2>
      </div>
      <div class="manuscript-intro">{intro_html}</div>
      <div class="manuscript-grid">{section_html}</div>
    </section>"""

    school_chip_html = "".join(f"<span>{esc(s)}</span>" for s in schools) if schools else "<span>상담 시 학교 확인</span>"
    fit_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">LOCAL &amp; STUDENT FIT</p>
        <h2>지역·학년·추천학생 기준</h2>
      </div>
      <div class="card-grid">
        <article class="info-card"><span class="tag">지역</span><h3>{esc(region)} {esc(district)} {esc(local)}</h3><p>{esc(local)} 생활권 학생의 학교 진도와 시험 일정에 맞춰 {esc(SUBJECT_LABEL)} 관리 방향을 상담합니다.</p></article>
        <article class="info-card"><span class="tag">학년</span><h3>{esc(GRADE_TEXT)}</h3><p>같은 학년이라도 단원별 결손이 다르므로 진단 후 우선순위를 다르게 잡습니다.</p></article>
        <article class="info-card"><span class="tag">추천</span><h3>이런 학생에게 추천</h3><p>학원 변경을 고민 중인 학생, 학교 진도는 따라가지만 시간이 지나면 개념이 흐려지는 학생, 내신 대비를 체계적으로 시작하려는 학생에게 적합합니다.</p></article>
      </div>
      <p class="lead" style="margin-top:18px;">수업 가능 학교 참고</p>
      <div class="chip-list">{school_chip_html}</div>
    </section>"""

    compare_rows_html = "\n".join(
        f'<div class="compare-row"><div class="other">{esc(r["other"])}</div><div class="label">{esc(r["label"])}</div><div class="ours">{esc(r["ours"])}</div></div>'
        for r in COMPARE_ROWS
    )
    compare_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">일반 학원과의 차이</p>
        <h2>{esc(local)} {esc(SUBJECT_LABEL)}학원, 무엇이 다른가요</h2>
        <p class="lead">일반적인 학원 운영 방식과 {esc(SITE_NAME)}의 관리 방식을 같은 기준으로 비교했습니다.</p>
      </div>
      <div class="compare-table">
        <div class="compare-head"><div>일반적인 학원</div><div>기준</div><div class="ours">{esc(SITE_NAME)}</div></div>
        {compare_rows_html}
      </div>
    </section>"""

    center_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">CENTER INFO</p>
        <h2>센터 기준 정보</h2>
      </div>
      <div class="card-grid">
        <article class="info-card"><span class="tag">센터명</span><h3>{esc(center)}</h3><p>{esc(region)} {esc(district)} {esc(local)} 학생 상담 기준으로 안내합니다.</p></article>
        <article class="info-card"><span class="tag">주소</span><h3>위치 안내</h3><p>{esc(address) if address else "상담 시 위치 정보를 확인해 주세요."}</p></article>
        <article class="info-card"><span class="tag">등록</span><h3>{esc(education_name) if education_name else "교육지원청 등록 정보"}</h3><p>{esc(reg_no) if reg_no else "상담 시 교육지원청 등록 정보를 확인할 수 있습니다."}</p></article>
      </div>
    </section>"""

    fee_rows = FEE_TABLE_SEOUL if region == "서울" else FEE_TABLE_OTHER
    fee_region_label = "서울 지역 기준" if region == "서울" else "서울 외 지역 기준"
    fee_rows_html = "".join(
        f'<tr><td>{esc(freq)}</td><td>{esc(el)}</td><td class="highlight">{esc(mid)}</td><td>{esc(hi)}</td></tr>'
        for freq, el, mid, hi in fee_rows
    )
    fee_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">TUITION</p>
        <h2>{esc(local)} {esc(SUBJECT_LABEL)}학원 학습료 안내</h2>
        <p class="lead">{esc(fee_region_label)}으로 안내되는 학습료입니다. 실제 금액은 상담 시 학생 과정과 교육청 신고 기준에 따라 확인해 주세요.</p>
      </div>
      <div class="fee-table-wrap">
        <p class="fee-caption">{esc(fee_region_label)} · 1회 90~100분 수업</p>
        <table class="fee-table">
          <thead><tr><th>횟수</th><th>초등</th><th class="highlight">중등</th><th>고등</th></tr></thead>
          <tbody>
            {fee_rows_html}
          </tbody>
        </table>
        <p class="fee-note">* 학습료는 지역, 수업 조건, 교육청 신고 기준에 따라 일부 차이가 있을 수 있습니다.</p>
      </div>
    </section>"""

    checklist_html = "".join(
        f'<article class="info-card"><span class="tag">{i + 1}</span><h3>{esc(q)}</h3><p>{esc(a)}</p></article>'
        for i, (q, a) in enumerate(CHECKLIST_BANK)
    )
    checklist_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">CHECKLIST</p>
        <h2>상담 전 체크리스트</h2>
      </div>
      <div class="card-grid">
        {checklist_html}
      </div>
    </section>"""

    faq_html = "\n".join(
        f'<details class="faq-item"{" open" if i == 0 else ""}><summary>{esc(q)}</summary><p>{esc(a)}</p></details>'
        for i, (q, a) in enumerate(faqs)
    )
    faq_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">FAQ</p>
        <h2>{esc(title)} 자주 묻는 질문</h2>
      </div>
      <div class="faq-list">
        {faq_html}
      </div>
    </section>"""

    review_html = "".join(f'<article class="review-card"><p>{esc(q)}</p></article>' for q in review_quotes)
    review_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">PARENT REVIEW</p>
        <h2>{esc(local)} {esc(SUBJECT_LABEL)}학원 상담 후기 예시</h2>
        <p class="lead">{esc(review_note)}</p>
      </div>
      <div class="review-grid">
        {review_html}
      </div>
    </section>"""

    subject_links = []
    for category, _ in SIBLING_CATEGORY_META.items():
        if category == CATEGORY:
            continue
        if (SITE / PARENT / category / slug).exists():
            subject_links.append(
                f'<a href="../../{category}/{slug}/index.html"><strong>{esc(local)} {esc(category)}</strong><small>같은 동네 다른 과목 안내</small></a>'
            )
    nationwide_links = []
    for category, _ in shared.ALL_CATEGORIES:
        if (SITE / "전국학원" / category / slug).exists():
            nationwide_links.append(
                f'<a href="../../../전국학원/{category}/{slug}/index.html"><strong>{esc(local)} {esc(category)}</strong><small>같은 동네 전국학원 안내</small></a>'
            )
    nearby_html = "".join(
        f'<a href="../{slug_ko(item["근처 수업가능 동네"])}/index.html"><strong>{esc(item["근처 수업가능 동네"])} {esc(CATEGORY)}</strong><small>인근 지역 안내</small></a>'
        for item in nearby_rows
    )
    link_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">근처 학원페이지</p>
        <h2>{esc(local)} 주변 {esc(CATEGORY)} 페이지</h2>
        <p class="lead">같은 지역의 다른 카테고리와, 가까운 지역 페이지로 이동할 수 있도록 정리했습니다.</p>
      </div>
      <div class="link-grid">
        <a href="../index.html"><strong>{esc(CATEGORY)} 전체</strong><small>카테고리 허브</small></a>
        <a href="../../index.html"><strong>{esc(PARENT)}</strong><small>전체 허브</small></a>
        {''.join(subject_links)}
        {''.join(nationwide_links)}
        {nearby_html}
      </div>
    </section>"""

    body = f"""{nav_html(3, PARENT)}

  <main>
    <section class="page-hero">
      <p class="breadcrumb"><a href="../../../index.html">홈</a><span>/</span><a href="../../index.html">{esc(PARENT)}</a><span>/</span><a href="../index.html">{esc(CATEGORY)}</a><span>/</span><span>{esc(title)}</span></p>
      <p class="eyebrow">MIDDLE 2 {SUBJECT_EN} LOCAL GUIDE</p>
      <h1>{esc(title)}</h1>
      <p class="lead">{esc(description)}</p>
      {badge_row}
      <p class="update-date">최종 업데이트: <time datetime="{PUBLISH_DATE}">{PUBLISH_DATE_KO}</time></p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="tel:{PHONE_DISPLAY}">전화 상담하기</a>
        <a class="btn btn-ghost" href="../../../상담문의/index.html">상담문의</a>
      </div>
    </section>

{media_section}

{summary_section}

{manuscript_section}

{fit_section}

{compare_section}

{center_section}

{fee_section}

{checklist_section}

{faq_section}

{review_section}

{link_section}
  </main>

{footer_html(3)}
"""
    return page_shell(head, body)


# ---------------------------------------------------------------------------
# hub pages
# ---------------------------------------------------------------------------

def parent_hub() -> None:
    canonical = f"{DOMAIN}/{PARENT}/"
    description = f"{SITE_NAME} 과목별학원 허브입니다. 학년과 과목을 선택한 뒤 371개 동네별 학습관리 안내를 확인할 수 있습니다."
    available = [name for name in SIBLING_CATEGORY_META if (SITE / PARENT / name).exists()]
    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "CollectionPage", "@id": f"{canonical}#webpage", "url": canonical, "name": PARENT, "description": description, "inLanguage": "ko-KR"},
            {"@type": "BreadcrumbList", "@id": f"{canonical}#breadcrumb", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{DOMAIN}/"},
                {"@type": "ListItem", "position": 2, "name": PARENT, "item": canonical},
            ]},
            {"@type": "ItemList", "@id": f"{canonical}#categories", "name": f"{PARENT} 카테고리", "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": name, "url": f"{DOMAIN}/{PARENT}/{name}/"}
                for i, name in enumerate(available)
            ]},
        ],
    }
    head = head_html(f"{PARENT} | {SITE_NAME}", description, 1, canonical, "website", f"{DOMAIN}/assets/generated/academy-hero-v2.png", ld)
    category_cards = "".join(
        f'<a href="{esc(name)}/index.html"><strong>{esc(name)}</strong><small>{esc(SIBLING_CATEGORY_META[name])}</small></a>'
        for name in available
    )
    body = f"""{nav_html(1, PARENT)}
  <main>
    <section class="page-hero">
      <p class="breadcrumb"><a href="../index.html">홈</a><span>/</span><span>{PARENT}</span></p>
      <p class="eyebrow">SUBJECT ACADEMY HUB</p>
      <h1>{PARENT}</h1>
      <p class="lead">학년과 과목을 먼저 선택한 뒤, 원하는 동네의 상담 기준과 센터 정보를 확인할 수 있도록 정리했습니다.</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="tel:{PHONE_DISPLAY}">전화 상담하기</a>
        <a class="btn btn-ghost" href="../상담문의/index.html">상담문의</a>
      </div>
    </section>
    <section class="section">
      <div class="section-head">
        <p class="eyebrow">ACADEMY CATEGORY</p>
        <h2>학년·과목별 학원 안내</h2>
        <p class="lead">현재 준비된 카테고리부터 순서대로 확인해 주세요. 각 지역 페이지는 별도 원고와 실제 센터 자료를 바탕으로 구성했습니다.</p>
      </div>
      <div class="category-grid">
        {category_cards}
      </div>
    </section>
  </main>
{footer_html(1)}"""
    out = SITE / PARENT / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page_shell(head, body), encoding="utf-8")


def category_hub(rows: list[dict[str, str]]) -> None:
    canonical = f"{DOMAIN}/{PARENT}/{CATEGORY}/"
    description = f"전국 {len(rows)}개 동네의 {SUBJECT_LABEL}학원 페이지를 지역별로 정리했습니다. 동네별 내신 준비, 학교 참고 정보, 상담 기준과 센터 위치를 확인할 수 있습니다."
    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "CollectionPage", "@id": f"{canonical}#webpage", "url": canonical, "name": CATEGORY, "description": description, "inLanguage": "ko-KR"},
            {"@type": "BreadcrumbList", "@id": f"{canonical}#breadcrumb", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{DOMAIN}/"},
                {"@type": "ListItem", "position": 2, "name": PARENT, "item": f"{DOMAIN}/{PARENT}/"},
                {"@type": "ListItem", "position": 3, "name": CATEGORY, "item": canonical},
            ]},
            {"@type": "ItemList", "@id": f"{canonical}#itemlist", "name": f"{CATEGORY} 지역 목록", "numberOfItems": len(rows), "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": f"{r['근처 수업가능 동네']} {CATEGORY}", "url": f"{DOMAIN}/{PARENT}/{CATEGORY}/{slug_ko(r['근처 수업가능 동네'])}/"}
                for i, r in enumerate(rows)
            ]},
        ],
    }
    head = head_html(f"{CATEGORY} | {SITE_NAME}", description, 2, canonical, "website", f"{DOMAIN}/assets/generated/academy-hero-v2.png", ld)
    region_blocks = region_blocks_html(rows)
    body = f"""{nav_html(2, PARENT)}
  <main>
    <section class="page-hero">
      <p class="breadcrumb"><a href="../../index.html">홈</a><span>/</span><a href="../index.html">{PARENT}</a><span>/</span><span>{CATEGORY}</span></p>
      <p class="eyebrow">MIDDLE 2 {SUBJECT_EN} DIRECTORY</p>
      <h1>{CATEGORY}</h1>
      <p class="lead">지역별 {esc(SUBJECT_LABEL)} {esc(FOCUS_LABEL)} 기준을 찾을 수 있도록 {len(rows)}개 동네 페이지를 시도·시군구별로 정리했습니다.</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="tel:{PHONE_DISPLAY}">전화 상담하기</a>
        <a class="btn btn-ghost" href="../../상담문의/index.html">상담문의</a>
      </div>
    </section>
    <section class="section">
      <div class="section-head">
        <p class="eyebrow">총 지역</p>
        <h2>{len(rows)}개 지역</h2>
        <p class="lead">서울부터 지방까지 지역명 기준으로 {esc(CATEGORY)} 페이지를 생성했습니다.</p>
      </div>
      {region_blocks}
    </section>
  </main>
{footer_html(2)}"""
    out = SITE / PARENT / CATEGORY / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page_shell(head, body), encoding="utf-8")


def main() -> None:
    rows = read_csv(COMMON / "센터정보 정리.csv")
    manuscripts = load_manuscripts()
    locals_in_csv = {row["근처 수업가능 동네"].strip() for row in rows}
    if len(rows) != 371 or len(manuscripts) != 371:
        raise ValueError(f"예상 개수 불일치: csv={len(rows)}, manuscripts={len(manuscripts)}")
    if locals_in_csv != manuscripts.keys():
        missing = sorted(locals_in_csv - manuscripts.keys())
        extra = sorted(manuscripts.keys() - locals_in_csv)
        raise ValueError(f"지역 대응 불일치: missing={missing}, extra={extra}")

    repeated_signatures = repeated_body_signatures(manuscripts)

    category_hub(rows)
    parent_hub()
    for index, row in enumerate(rows):
        local = row["근처 수업가능 동네"].strip()
        out = SITE / PARENT / CATEGORY / slug_ko(local) / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            detail_page(row, index, manuscripts[local], rows, repeated_signatures),
            encoding="utf-8",
        )
    print(
        f"generated parent={PARENT} category={CATEGORY} "
        f"local_pages={len(rows)} contextualized_patterns={len(repeated_signatures)}"
    )


if __name__ == "__main__":
    main()
