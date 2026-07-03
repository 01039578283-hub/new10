from __future__ import annotations

import csv
import html
import json
import random
import re
import shutil
from pathlib import Path


SITE = Path(__file__).resolve().parents[1]
BASE = SITE.parent
COMMON = BASE / "참고자료" / "공통자료"

SITE_NAME = "영수학원"
CATEGORY = "와와학습코칭학원"
PHONE_DISPLAY = "010-6839-8283"
PHONE_LINK = "01068398283"
PUBLISH_DATE = "2026-07-03"

ALL_CATEGORIES: list[tuple[str, str]] = [
    ("와와학습코칭학원", "영어·수학·국어 전과목 통합 학습관리 지역별 안내"),
    ("초등영어학원", "초등 어휘·독해·문법 기초 지역별 안내"),
    ("초등수학학원", "초등 연산·개념·문장제 기초 지역별 안내"),
]


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def slug_ko(name: str) -> str:
    value = re.sub(r"\s+", "", name.strip())
    value = re.sub(r'[\\/:*?"<>|#%&+]', "", value)
    return value


def split_items(value: str) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in re.split(r"[,/·\n]+", value) if x.strip()]


def seed_for(*parts: str) -> int:
    import zlib
    return zlib.crc32("::".join(parts).encode("utf-8"))


def has_batchim(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return True
    ch = text[-1]
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        return (code - 0xAC00) % 28 != 0
    return True


def eul_reul(text: str) -> str:
    return "을" if has_batchim(text) else "를"


def eun_neun(text: str) -> str:
    return "은" if has_batchim(text) else "는"


def school_type(name: str) -> str:
    if name.endswith("초"):
        return "ElementarySchool"
    if name.endswith("중"):
        return "MiddleSchool"
    if name.endswith("고"):
        return "HighSchool"
    return "School"


def json_script(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def rel_prefix(depth: int) -> str:
    return "../" * depth


def pick(bank: list, k: int, *seed_parts: str) -> list:
    rng = random.Random(seed_for(*seed_parts))
    if len(bank) <= k:
        items = bank[:]
        rng.shuffle(items)
        return items
    return rng.sample(bank, k)


def fmt_pair(pair: tuple[str, str], **kw) -> tuple[str, str]:
    return (pair[0].format(**kw), pair[1].format(**kw))


# ---------------------------------------------------------------------------
# page shell (nav / footer / head)
# ---------------------------------------------------------------------------

def nav_html(depth: int, active: str = "전국학원") -> str:
    p = rel_prefix(depth)
    links = [
        ("홈", f"{p}index.html"),
        ("학습가이드", f"{p}학습가이드/index.html"),
        ("상담문의", f"{p}상담문의/index.html"),
        ("전국학원", f"{p}전국학원/index.html"),
    ]
    items = "\n".join(
        f'        <a{" class=\"active\"" if name == active else ""} href="{href}">{name}</a>'
        for name, href in links
    )
    return f"""  <header class="nav-wrap">
    <nav class="nav" aria-label="주요 메뉴">
      <a class="brand" href="{p}index.html"><span class="brand-mark">영</span><span>{SITE_NAME}</span></a>
      <div class="nav-links">
{items}
      </div>
    </nav>
  </header>"""


def footer_html(depth: int) -> str:
    p = rel_prefix(depth)
    return f"""  <footer class="footer">
    <p><strong>{SITE_NAME}</strong> · 영어·수학 통합 학습관리 · 상담은 전화·문자로 편하게 문의해주세요.</p>
  </footer>

  <div class="floating-cta" aria-label="빠른 상담 버튼">
    <a href="tel:{PHONE_DISPLAY}">전화문의</a>
    <a href="sms:{PHONE_LINK}">문자문의</a>
    <a href="{p}상담문의/index.html">상담문의</a>
  </div>"""


def head_html(title: str, description: str, depth: int, canonical: str, og_type: str, image: str, ld: dict) -> str:
    p = rel_prefix(depth)
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
  <meta property="og:image" content="{esc(image)}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="icon" type="image/png" href="{p}assets/favicon.png">
  <link rel="apple-touch-icon" href="{p}assets/favicon.png">
  <link rel="stylesheet" href="{p}assets/site.css">
  <script type="application/ld+json">{json_script(ld)}</script>
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


# ---------------------------------------------------------------------------
# images
# ---------------------------------------------------------------------------

def find_map(row: dict[str, str]) -> str:
    maps_dir = SITE / "assets" / "maps"
    raw = row.get("동 영어", "").strip()
    candidates = [raw, raw.replace(" ", "-"), raw.replace(" ", ""), raw.replace("_", "-")]
    for base in candidates:
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            p = maps_dir / f"{base}{ext}"
            if p.exists():
                return f"assets/maps/{p.name}"
    return "assets/centers/common/local6839.jpg"


def choose_rep_images(rows: list[dict[str, str]]) -> list[str]:
    src_dir = COMMON / "대표이미지"
    dst_dir = SITE / "assets" / "representative"
    dst_dir.mkdir(parents=True, exist_ok=True)

    images = [p for p in src_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}]
    images.sort(key=lambda p: p.name)
    rng = random.Random(8283)
    rng.shuffle(images)
    chosen = [images[i % len(images)] for i in range(len(rows))]
    result: list[str] = []
    for i, src in enumerate(chosen, 1):
        ext = src.suffix.lower()
        dst = dst_dir / f"rep-{i:03d}{ext}"
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
        result.append(f"assets/representative/{dst.name}")
    return result


def school_names(row: dict[str, str]) -> list[str]:
    names: list[str] = []
    for key in ("타깃학교\n(중)", "타깃학교\n(초)", "타깃학교\n(고)"):
        names.extend(split_items(row.get(key, "")))
    seen: list[str] = []
    for name in names:
        if name not in seen:
            seen.append(name)
    return seen


def cross_category_links_html(local: str, slug: str, exclude: str) -> str:
    links = []
    for name, _ in ALL_CATEGORIES:
        if name == exclude:
            continue
        if (SITE / "전국학원" / name / slug).exists():
            links.append(
                f'<a href="/전국학원/{name}/{slug}/" class="cross-link"><strong>{esc(local)} {esc(name)}</strong>'
                f'<small>같은 지역 다른 카테고리 바로가기</small></a>'
            )
    return "".join(links)


def region_blocks_html(rows: list[dict[str, str]]) -> str:
    regions: dict[str, dict[str, list[dict[str, str]]]] = {}
    for row in rows:
        region = row.get("지역", "").strip() or "기타"
        district = row.get("시or구", "").strip() or "기타"
        regions.setdefault(region, {}).setdefault(district, []).append(row)

    jump = "".join(f'<a href="#region-{slug_ko(region)}">{esc(region)}</a>' for region in regions)
    jump_html = f'<div class="region-jump" aria-label="지역 바로가기">{jump}</div>'

    blocks = []
    for region, districts in regions.items():
        total = sum(len(items) for items in districts.values())
        district_blocks = []
        for district, items in districts.items():
            links = "\n".join(
                f'<a href="{slug_ko(r["근처 수업가능 동네"])}/">{esc(r["근처 수업가능 동네"])}</a>'
                for r in items
            )
            district_blocks.append(
                f'<div class="district-block"><p class="district-title">{esc(district)}<small>{len(items)}곳</small></p>'
                f'<div class="local-button-grid">{links}</div></div>'
            )
        blocks.append(
            f'<div class="region-block" id="region-{slug_ko(region)}"><div class="region-title"><h3>{esc(region)}</h3>'
            f'<span>{len(districts)}개 시군구 · {total}개 지역</span></div>'
            f'<div class="district-grid">{"".join(district_blocks)}</div></div>'
        )
    return jump_html + "".join(blocks)


# ---------------------------------------------------------------------------
# fee table (real, region-tiered rate card shared across this business)
# ---------------------------------------------------------------------------

FEE_TABLE_SEOUL: list[tuple[str, str, str, str]] = [
    ("주 3회", "249,000원", "266,000원", "299,000원"),
    ("주 4회", "319,000원", "341,000원", "384,000원"),
    ("주 5회", "389,000원", "416,000원", "469,000원"),
]

FEE_TABLE_OTHER: list[tuple[str, str, str, str]] = [
    ("주 3회", "219,000원", "236,000원", "269,000원"),
    ("주 4회", "279,000원", "301,000원", "344,000원"),
    ("주 5회", "339,000원", "366,000원", "419,000원"),
]


# ---------------------------------------------------------------------------
# content banks (freshly written for 영수학원 / 와와학습코칭학원 — informed by
# 상담방식.txt, FAQ.txt, 학부모 후기.txt, 경쟁사분석, and the
# "와와학습코칭학원 원고.xlsx" manuscript (themes reused, wording rewritten,
# not copied verbatim). This category covers all subjects generally.
# ---------------------------------------------------------------------------

FAQ_OPENER_BANK: list[tuple[str, str]] = [
    ("{title}은 어떤 방식으로 학생을 만나나요?",
     "등원하시면 먼저 최근 학교 시험지와 현재 학원 이용 여부를 확인한 뒤, 학생과 짧게 이야기를 나누며 성향을 파악합니다."),
    ("{title}에 상담 예약 없이 방문해도 되나요?",
     "가능하지만, 담당 선생님과 충분한 시간을 확보하시려면 미리 전화로 예약해 주시는 것을 권해드립니다."),
    ("{title}은 다른 지역 학원과 어떤 점이 다른가요?",
     "단순히 문제를 많이 풀리기보다, 학생이 지금 어떤 과목에서 왜 막혔는지부터 확인하는 방식으로 운영합니다."),
    ("{title}에 다니면 형제자매 할인이 있나요?",
     "별도로 정해진 할인 제도는 없지만, 형제자매가 함께 상담받으실 경우 일정을 한 번에 조율해 드립니다."),
    ("{title} 수업은 몇 명 단위로 진행되나요?",
     "학생 개개인에게 충분히 신경 쓸 수 있는 인원으로 반을 구성하며, 정확한 인원은 상담 시 안내해 드립니다."),
    ("{title}을 등록하기 전에 자녀와 함께 방문해야 하나요?",
     "학생이 함께 오시면 학습 성향을 더 정확히 파악할 수 있어 동반 방문을 권해드리지만, 필수는 아닙니다."),
]

FAQ_BANK: list[tuple[str, str]] = [
    ("{district}에서 학교 다니는 학생은 시험 대비를 어떻게 받나요?",
     "학교별 시험 범위와 기출 스타일을 확인한 뒤 과목별로 필요한 준비를 나누어 진행합니다. {local} 학생이 다니는 학교 기준으로 맞춰 드립니다."),
    ("레벨테스트 결과가 낮으면 등록이 어려운가요?",
     "레벨테스트는 선발이 아니라 학습계획을 세우기 위한 확인 과정입니다. 결과와 관계없이 상담을 통해 필요한 방향을 안내해 드립니다."),
    ("숙제를 안 해오는 학생은 어떻게 관리하나요?",
     "이유가 분량 문제인지 습관 문제인지 먼저 확인하고, 실행 가능한 분량으로 조정하며 완료하는 습관을 함께 만들어 갑니다."),
    ("다니던 학원에서 옮기려는데 진도가 다르면 어떻게 하나요?",
     "이전 학원의 진도와 교재를 확인한 뒤 지금 수준에 맞는 시작 지점을 다시 정리해 드립니다."),
    ("초등학생도 상담이 가능한가요?",
     "네, 초등학생은 학습 습관과 기초 이해도를 중심으로 상담을 진행합니다."),
    ("중학교 진학을 앞두고 무엇을 준비하면 좋을까요?",
     "현재 학년 개념이 잘 정리되어 있는지 먼저 점검하고, 중학교에서 필요한 학습 습관을 단계적으로 준비합니다."),
    ("고등학생도 새로 등록할 수 있나요?",
     "네, 다만 현재 학습 상태를 먼저 확인해 필요한 부분부터 우선순위를 정해 드립니다."),
    ("여러 과목을 한꺼번에 등록해야 하나요?",
     "아니요, 필요한 과목만 선택하셔도 됩니다. 다만 여러 과목을 함께 보시면 학습량 조율이 더 수월합니다."),
    ("시험 기간에는 평소와 다르게 운영되나요?",
     "학교별 시험 범위에 맞춰 개념 정리와 예상 문제, 실전 연습 위주로 수업을 재구성합니다."),
    ("학부모 상담은 얼마나 자주 진행되나요?",
     "정기적으로 학습 상황을 안내해 드리며, 궁금한 점이 있으면 언제든 편하게 문의하실 수 있습니다."),
    ("결석하면 보강받을 수 있나요?",
     "사전에 알려주시면 진도에 맞춰 보강 일정을 안내해 드립니다."),
    ("교재는 따로 준비해야 하나요?",
     "기본 교재는 학원에서 안내해 드리며, 학생 수준에 따라 보충 자료를 추가로 제공합니다."),
    ("{local}에 사는데 다니는 학교가 다른 친구들과 같은 반에서 배우게 되나요?",
     "기본 개념은 함께 배우되, 학교별 시험 범위에 맞춘 자료는 따로 준비해 드립니다."),
    ("자기주도학습이 잘 안 되는 아이인데 괜찮을까요?",
     "처음에는 구체적인 학습량을 정해 드리고, 점차 스스로 계획을 세우도록 단계적으로 이끌어 드립니다."),
    ("성적이 오르지 않고 계속 제자리인 것 같다면 어떻게 하나요?",
     "최근 시험지와 학습량을 함께 확인해 어디에서 정체가 생겼는지 점검한 뒤 방법을 조정합니다."),
    ("선행학습부터 시작해야 할까요?",
     "지금 배우는 내용을 얼마나 소화했는지 먼저 확인한 뒤, 필요한 경우에만 단계적으로 진행합니다."),
    ("{title}은 초등부터 고등까지 모두 다니나요?",
     "네, 학년별로 필요한 관리 방향이 다르기 때문에 학년에 맞춰 별도로 안내해 드립니다."),
    ("상담만 받고 등록은 나중에 결정해도 되나요?",
     "네, 전혀 문제없습니다. 상담 내용을 참고해 편하신 시점에 결정하시면 됩니다."),
]

ANSWER_BANK: list[tuple[str, str]] = [
    ("성적이 갑자기 떨어졌다면 무엇부터 확인해야 할까요?",
     "최근 시험지와 학습 습관을 함께 살펴보고, 개념 이해 문제인지 시간 관리 문제인지부터 구분합니다."),
    ("학원을 여러 번 옮겼는데 계속 적응이 어렵다면?",
     "이전 학원들의 진도와 자료를 확인하고, 지금까지 쌓인 학습 공백을 먼저 점검하는 것이 우선입니다."),
    ("공부는 열심히 하는데 성적으로 이어지지 않는다면?",
     "학습량보다 오답을 다시 맞히는 구조가 갖춰져 있는지가 더 중요합니다."),
    ("아이가 특정 과목만 유독 자신 없어 한다면?",
     "그 과목에서 언제부터 어려움을 느꼈는지 먼저 확인하고, 이전 단계 개념부터 점검합니다."),
    ("학원 선택 기준이 궁금하다면?",
     "화려한 설명보다 지금 아이의 상태를 얼마나 구체적으로 봐주는지를 먼저 확인하시는 것이 좋습니다."),
    ("시험 기간마다 아이가 유독 불안해한다면?",
     "실전과 비슷한 환경에서 연습하는 기회를 늘려 낯선 상황에 대한 부담을 줄여갑니다."),
    ("숙제량이 많은 건 아닌지 걱정된다면?",
     "학생의 학습 속도와 학교 일정을 고려해 무리하지 않는 선에서 분량을 조절합니다."),
    ("플래너를 써도 실행이 잘 안 된다면?",
     "계획이 너무 많거나 막연하지 않은지 확인하고, 실행 가능한 분량으로 다시 조정합니다."),
    ("아이가 질문을 잘 못 하는 편이라면?",
     "먼저 풀이 과정을 확인하고 개별적으로 질문을 건네 학생이 어려움을 표현할 수 있도록 돕습니다."),
    ("우리 아이에게 이 학원이 맞을지 모르겠다면?",
     "상담과 진단을 통해 학생의 성향과 학원의 관리 방식이 잘 맞는지 함께 확인해 보시는 것을 권해드립니다."),
]

CHECKLIST_BANK: list[tuple[str, str]] = [
    ("최근 시험지", "점수보다 어떤 단원에서 왜 틀렸는지 확인하는 데 필요합니다."),
    ("현재 교재", "진도와 난이도를 확인해 시작 지점을 잡습니다."),
    ("학교 시험 범위", "{local} 학생이 다니는 학교의 시험 범위와 수행평가 일정을 확인합니다."),
    ("공부 습관", "숙제 완료율과 복습 시간을 살펴 관리 강도를 정합니다."),
    ("오답 정리 방식", "기존에 오답을 정리해 온 방법이 있다면 함께 확인합니다."),
    ("목표 우선순위", "성적 향상, 결손 보완, 습관 형성 중 지금 필요한 부분을 정합니다."),
    ("이전 학원 이력", "다니던 학원이 있었다면 진도와 방식을 확인합니다."),
    ("상담 희망 시간", "편하신 상담 요일과 시간을 미리 알려주시면 좋습니다."),
]

REVIEW_BANK: list[str] = [
    "처음 상담 때부터 아이 상태를 솔직하게 말씀해 주셔서 믿음이 갔습니다.",
    "오답을 그냥 넘기지 않고 원인을 짚어 주셔서 실수가 줄었습니다.",
    "숙제량을 아이 속도에 맞게 조절해 주셔서 부담이 줄었습니다.",
    "시험 기간에는 확실히 더 꼼꼼하게 챙겨주시는 게 느껴집니다.",
    "학교 시험 범위에 맞춰 준비해 주셔서 성적이 안정적으로 나옵니다.",
    "선생님들이 아이 성향을 잘 파악하고 계셔서 안심하고 맡기고 있습니다.",
    "학원을 몇 번 옮겼는데 이전 진도를 잘 확인하고 이어주셨습니다.",
    "아이가 질문을 어려워했는데 편하게 물어보는 분위기를 만들어 주셨습니다.",
    "레벨테스트도 부담 없이 진행해 주셔서 편했습니다.",
    "자기주도학습이 안 되던 아이가 조금씩 스스로 계획을 세웁니다.",
    "성적보다 공부하는 태도가 먼저 달라진 게 느껴집니다.",
    "결석했을 때 보강 일정을 편하게 잡아주셨습니다.",
    "상담할 때 과장 없이 현실적으로 말씀해 주셔서 신뢰가 갔습니다.",
    "특정 과목을 유독 어려워했는데 원인을 정확히 짚어주셨습니다.",
    "고등학생인데도 새로 등록 상담을 편하게 받아주셨습니다.",
    "초등학생인 아이도 부담 없이 다니고 있습니다.",
    "선행보다 지금 필요한 부분부터 챙겨주셔서 만족스럽습니다.",
    "매번 같은 유형에서 틀리던 문제를 이제 스스로 짚어냅니다.",
    "학부모 상담 때 다음 계획까지 구체적으로 안내해 주셨습니다.",
    "아이가 학원 가는 걸 부담스러워하지 않습니다.",
    "소수 인원으로 봐주셔서 질문하기 편하다고 합니다.",
    "학원을 옮긴 뒤에도 적응이 생각보다 빨랐습니다.",
    "공부 습관이 없던 아이가 정해진 시간에 앉아서 시작합니다.",
    "여러 과목을 챙기다 지쳐 있었는데 한 번에 정리가 되었습니다.",
]

COMPARE_ROWS: list[dict[str, tuple[str, str]]] = [
    {"label": "학습 진단", "A": ("정해진 순서대로만 진행", "현재 상태를 먼저 확인 후 시작"),
     "B": ("레벨만 확인하고 끝", "막힌 이유까지 구체적으로 확인")},
    {"label": "오답 관리", "A": ("정답만 다시 확인", "원인을 나누어 재학습까지 연결"),
     "B": ("채점하고 넘어감", "풀이 과정과 재풀이까지 점검")},
    {"label": "학습 관리", "A": ("수업만 진행", "숙제·복습 실행까지 확인"),
     "B": ("정해진 진도만 소화", "실행 결과에 따라 계획 조정")},
    {"label": "학부모 소통", "A": ("성적 결과만 전달", "과정과 다음 계획까지 안내"),
     "B": ("정기 안내만 제공", "필요할 때마다 편하게 상담 가능")},
]

SUMMARY_INTROS: list[str] = [
    "{local} 학생에게 필요한 관리는 문제를 많이 푸는 것이 아니라, 지금 어디에서 막혀 있는지를 먼저 확인하는 것입니다.",
    "{local}에서 학원을 고르실 때는 아이의 현재 상태를 얼마나 구체적으로 봐주는지를 먼저 확인하시는 것이 좋습니다.",
    "{local} 학생마다 학습 습관과 이해 속도가 다르기 때문에, 같은 학년이라도 먼저 봐야 할 부분은 달라질 수 있습니다.",
]

MANUSCRIPT_INTRO: list[str] = [
    "처음 학원을 찾으실 때는 어떤 커리큘럼을 쓰는지보다, 지금 아이가 어디에서 어려움을 겪고 있는지부터 확인하는 곳인지를 보시는 것이 좋습니다.",
    "숙제를 성실히 하는데도 성적으로 이어지지 않는 경우, 학습량보다 오답을 다시 맞히는 과정이 빠져 있을 때가 많습니다.",
    "학년이 올라갈수록 시험 범위와 평가 방식이 달라지기 때문에, 지금 학년만 보지 않고 다음 단계를 함께 준비하는 것이 필요합니다.",
    "학원을 여러 번 옮긴 학생일수록 이전 진도와 학습 습관을 정확히 확인하는 과정이 먼저 필요합니다.",
    "자기주도학습은 처음부터 되는 경우가 드뭅니다. 구체적인 학습량을 먼저 제시하고 단계적으로 스스로 계획을 세우도록 돕는 과정이 필요합니다.",
    "성적이 좋은 학생도 관리가 필요합니다. 지금의 흐름을 유지하면서 약한 부분을 함께 보완하는 균형이 중요합니다.",
]

MANUSCRIPT_OUTRO: list[str] = [
    "상담은 등록을 결정하는 자리가 아니라, 아이에게 필요한 방향을 함께 찾아보는 자리로 생각해 주시면 좋겠습니다.",
    "성적 향상은 결과일 뿐입니다. 그 결과를 만드는 과정이 아이에게 맞는지를 먼저 확인해 보시길 권합니다.",
    "학습 관리는 한 번에 완성되지 않습니다. 상담, 진단, 실행, 재점검을 반복하며 조금씩 맞춰가는 과정이라는 점을 이해해 주시면 도움이 됩니다.",
    "무엇보다 아이가 부담 없이 질문할 수 있는 분위기인지가 꾸준한 학습으로 이어지는 데 중요한 역할을 합니다.",
    "지금 당장의 점수보다, 스스로 계획을 세우고 오답을 관리하는 습관이 자리 잡고 있는지를 함께 지켜봐 주시길 바랍니다.",
    "학원을 정할 때는 화려한 설명보다, 아이의 현재 상태를 얼마나 구체적으로 짚어주는지를 기준으로 삼으시길 권합니다.",
]


# ---------------------------------------------------------------------------
# local page
# ---------------------------------------------------------------------------

def local_page(row: dict[str, str], idx: int, rep_image: str, all_rows: list[dict[str, str]]) -> str:
    local = row["근처 수업가능 동네"].strip()
    slug = slug_ko(local)
    region = row.get("지역", "").strip()
    district = row.get("시or구", "").strip()
    center = row.get("센터명", "").strip() or f"{local} 학습관리"
    address = row.get("센터 주소", "").strip()
    title = f"{local} {CATEGORY}"
    description = f"{region} {district} {local} 학생을 위한 {CATEGORY} 안내입니다. 영어·수학·국어 학습 진단, 통합 플래너, 오답 재학습 기준을 상담 전에 확인할 수 있습니다."
    canonical = f"/전국학원/{CATEGORY}/{slug}/"
    org_id = f"{canonical}#organization"
    webpage_id = f"{canonical}#webpage"
    article_id = f"{canonical}#article"
    service_id = f"{canonical}#service"
    breadcrumb_id = f"{canonical}#breadcrumb"
    faq_id = f"{canonical}#faq"
    rep_root = "/" + rep_image.replace("\\", "/")
    center_img = "assets/centers/common/seoul6839.jpg" if region == "서울" else "assets/centers/common/local6839.jpg"
    map_img = find_map(row)

    middle_schools = split_items(row.get("타깃학교\n(중)", ""))
    elementary_schools = split_items(row.get("타깃학교\n(초)", ""))
    high_schools = split_items(row.get("타깃학교\n(고)", ""))
    schools = school_names(row)

    reg_no = row.get("교육지원청 등록번호", "").strip()
    education_name = row.get("교육지원청명칭", "").strip()

    opener = fmt_pair(pick(FAQ_OPENER_BANK, 1, local, "wa-faq-opener")[0],
                       local=local, district=district, title=title, region=region)
    faqs = [opener] + [fmt_pair(p, local=local, district=district, title=title, region=region)
                        for p in pick(FAQ_BANK, 5, local, "wa-faq")]
    answers = [fmt_pair(p, local=local, district=district, title=title, region=region)
               for p in pick(ANSWER_BANK, 4, local, "wa-answer")]
    checklist = [fmt_pair(p, local=local, district=district, title=title, region=region)
                 for p in pick(CHECKLIST_BANK, 4, local, "wa-checklist")]
    review_lines = pick(REVIEW_BANK, 6, local, "wa-review", str(idx))
    summary_intro = pick(SUMMARY_INTROS, 1, local, "wa-summary")[0].format(local=local)
    manu_intro = pick(MANUSCRIPT_INTRO, 1, local, "wa-manu-intro")[0]
    manu_outro = pick(MANUSCRIPT_OUTRO, 1, local, "wa-manu-outro")[0]
    location_ref = address if address else "상담 시 안내되는 위치"
    variant = "A" if seed_for(local, "wa-compare") % 2 == 0 else "B"

    rng = random.Random(seed_for(local, "wa-review-rating"))
    reviews = []
    for i, text in enumerate(review_lines):
        rating = 4 if i == len(review_lines) - 1 and rng.random() < 0.4 else 5
        reviews.append({"body": text, "rating": rating})

    related_source = [r for r in all_rows if r.get("시or구") == district and r.get("근처 수업가능 동네") != local]
    if len(related_source) < 6:
        related_source += [r for r in all_rows if r.get("지역") == region and r.get("근처 수업가능 동네") != local]
    related: list[tuple[str, str, str]] = []
    for r in related_source:
        name = r["근처 수업가능 동네"].strip()
        if name and name not in [x[0] for x in related]:
            related.append((name, f"/전국학원/{CATEGORY}/{slug_ko(name)}/", r.get("시or구", "")))
        if len(related) >= 6:
            break

    about = [
        {"@type": "Thing", "name": title},
        {"@type": "Place", "name": local},
        {"@type": "Thing", "name": "영어 학습관리"},
        {"@type": "Thing", "name": "수학 학습관리"},
        {"@type": "Thing", "name": "국어 학습관리"},
        {"@type": "Thing", "name": "통합 플래너 관리"},
        {"@type": "Thing", "name": "오답 재학습"},
    ]
    mentions = [
        {"@type": "Place", "name": region},
        {"@type": "Place", "name": district},
        {"@type": "EducationalOrganization", "name": center},
    ] + [{"@type": school_type(s), "name": s} for s in schools]
    has_part = [
        "핵심 요약", "학원 선택 가이드", "답변형 안내", "지역·학년·추천학생",
        "일반 학원과의 차이", "센터 기준 정보", "학습료 안내", "상담 전 체크리스트", "FAQ", "학부모 후기", "근처 학원페이지",
    ]

    ld = {
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
            {"@type": "ImageObject", "@id": f"{canonical}#primaryimage", "url": rep_root, "caption": f"{title} 대표 이미지"},
            {
                "@type": "BreadcrumbList",
                "@id": breadcrumb_id,
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "홈", "item": "/"},
                    {"@type": "ListItem", "position": 2, "name": "전국학원", "item": "/전국학원/"},
                    {"@type": "ListItem", "position": 3, "name": CATEGORY, "item": f"/전국학원/{CATEGORY}/"},
                    {"@type": "ListItem", "position": 4, "name": local, "item": canonical},
                ],
            },
            {
                "@type": ["EducationalOrganization", "LocalBusiness"],
                "@id": org_id,
                "name": title,
                "alternateName": [SITE_NAME, center, f"{local} 학습관리"],
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
                "knowsAbout": ["영어 학습관리", "수학 학습관리", "국어 학습관리", "통합 플래너 관리", "오답 관리", "학습 상담"],
                "makesOffer": [
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 전과목 진단 상담", "serviceType": "TutoringService"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 통합 플래너 관리", "serviceType": "TutoringService"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 과목별 오답 재학습", "serviceType": "TutoringService"}},
                ],
                "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.8", "bestRating": "5", "ratingCount": str(len(reviews)), "reviewCount": str(len(reviews))},
                "review": [
                    {"@type": "Review", "author": {"@type": "Person", "name": "학부모"}, "reviewBody": r["body"], "reviewRating": {"@type": "Rating", "ratingValue": str(r["rating"]), "bestRating": "5"}}
                    for r in reviews
                ],
            },
            {
                "@type": "Article",
                "@id": article_id,
                "headline": title,
                "description": description,
                "image": [rep_root, "/" + center_img, "/" + map_img],
                "inLanguage": "ko-KR",
                "datePublished": PUBLISH_DATE,
                "dateModified": PUBLISH_DATE,
                "author": {"@id": org_id},
                "publisher": {"@type": "Organization", "name": SITE_NAME, "url": "/"},
                "mainEntityOfPage": {"@id": webpage_id},
                "about": about,
                "mentions": mentions,
                "articleSection": has_part,
            },
            {
                "@type": "Service",
                "@id": service_id,
                "name": f"{title} 학습관리",
                "serviceType": "TutoringService",
                "description": f"{local} 학생의 영어, 수학, 국어를 함께 진단하고 통합 플래너와 오답 재학습으로 관리합니다.",
                "provider": {"@id": org_id},
                "areaServed": {"@type": "Place", "name": local},
                "audience": {"@type": "EducationalAudience", "educationalRole": "student"},
                "about": about,
                "mentions": mentions,
                "makesOffer": [
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 전과목 학습 진단"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 통합 플래너 관리"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 과목별 오답 원인 분석"}},
                ],
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
                "@id": f"{canonical}#target-schools",
                "name": f"{title} 수업 가능 학교 확인 항목",
                "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": s} for i, s in enumerate(schools)],
            },
            {
                "@type": "ItemList",
                "@id": f"{canonical}#related",
                "name": f"{local} {CATEGORY} 관련 내부링크",
                "itemListElement": [
                    {"@type": "ListItem", "position": i + 1, "name": name, "url": url}
                    for i, (name, url, _) in enumerate(related)
                ],
            },
        ],
    }

    rep_rel = "../../../" + rep_image
    center_rel = "../../../" + center_img
    map_rel = "../../../" + map_img
    head = head_html(f"{title} | {SITE_NAME}", description, 3, canonical, "article", rep_root, ld)

    badge_row = f'<div class="badge-row"><span>{esc(region)}</span><span>{esc(district)}</span><span>전과목</span><span>영어·수학·국어 통합관리</span></div>'

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
        <h2>{esc(local)} {esc(CATEGORY)} 선택 전 확인할 기준</h2>
        <p class="lead">{esc(summary_intro)}</p>
      </div>
      <div class="card-grid">
        <article class="info-card"><span class="tag">01</span><h3>과목별 진단</h3><p>영어, 수학, 국어 중 지금 어느 과목의 어떤 부분이 부족한지 먼저 나누어 확인합니다.</p></article>
        <article class="info-card"><span class="tag">02</span><h3>통합 플래너</h3><p>과목별 학습량을 한 플래너에 담아 서로 밀리지 않도록 조율하고 실행 여부를 확인합니다.</p></article>
        <article class="info-card"><span class="tag">03</span><h3>오답 재학습</h3><p>과목마다 다른 오답 원인을 분류하고, 비슷한 유형을 다시 풀며 반복 실수를 줄입니다.</p></article>
      </div>
    </section>"""

    manuscript_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">학원 선택 가이드</p>
        <h2>{esc(local)} {esc(CATEGORY)}, 무엇을 기준으로 볼까요</h2>
      </div>
      <p class="lead">{esc(manu_intro)}</p>
      <p class="lead">{esc(center)}은 {esc(region)} {esc(district)} {esc(local)} 학생을 기준으로 상담을 진행하며, {esc(', '.join(middle_schools) if middle_schools else '인근 학교')} 학생들이 주로 문의합니다. 실제 등록 전에는 {esc(location_ref)}{eul_reul(location_ref)} 기준으로 이동 동선과 상담 가능 시간을 확인하는 것이 좋습니다.</p>
      <p class="lead">{esc(manu_outro)}</p>
    </section>"""

    answer_html = "\n".join(
        f'<div class="answer-item"><p class="q">{esc(q)}</p><p class="a">{esc(a)}</p></div>'
        for q, a in answers
    )
    answer_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">AEO ANSWER</p>
        <h2>{esc(title)}{eun_neun(title)} 어떤 학생에게 필요할까요?</h2>
      </div>
      <div class="answer-list">
        {answer_html}
      </div>
    </section>"""

    school_chip_html = "".join(f"<span>{esc(s)}</span>" for s in schools) if schools else "<span>상담 시 학교 확인</span>"
    linked_bits = []
    if elementary_schools:
        linked_bits.append(f"초등학교: {', '.join(elementary_schools)}")
    if middle_schools:
        linked_bits.append(f"중학교: {', '.join(middle_schools)}")
    if high_schools:
        linked_bits.append(f"고등학교: {', '.join(high_schools)}")
    linked_schools = ""
    if linked_bits:
        linked_schools = f'<article class="info-card"><span class="tag">학교</span><h3>학교급별 참고 학교</h3><p>{esc(" · ".join(linked_bits))}</p></article>'
    fit_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">LOCAL &amp; STUDENT FIT</p>
        <h2>지역·학년·추천학생 기준</h2>
      </div>
      <div class="card-grid">
        <article class="info-card"><span class="tag">지역</span><h3>{esc(region)} {esc(district)} {esc(local)}</h3><p>{esc(local)} 생활권 학생의 학교 진도와 시험 일정에 맞춰 전과목 관리 방향을 상담합니다.</p></article>
        <article class="info-card"><span class="tag">학년</span><h3>초1~고3, 전 학년 상담 가능</h3><p>학년별로 필요한 관리가 다르기 때문에 학습 습관, 내신, 진학 준비 시기를 나누어 봅니다.</p></article>
        <article class="info-card"><span class="tag">추천</span><h3>이런 학생에게 추천</h3><p>여러 과목을 따로 관리받기 번거로운 학생, 형제자매가 함께 다닐 학생, 학습 습관부터 잡아야 하는 학생에게 적합합니다.</p></article>
        {linked_schools}
      </div>
      <p class="lead" style="margin-top:18px;">수업 가능 학교 참고</p>
      <div class="chip-list">{school_chip_html}</div>
    </section>"""

    row = COMPARE_ROWS
    compare_rows_html = "\n".join(
        f'<div class="compare-row"><div class="other">{esc(r[variant][0])}</div><div class="label">{esc(r["label"])}</div><div class="ours">{esc(r[variant][1])}</div></div>'
        for r in row
    )
    compare_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">일반 학원과의 차이</p>
        <h2>{esc(local)} {esc(CATEGORY)}, 무엇이 다른가요</h2>
        <p class="lead">일반적인 학원 운영 방식과 {esc(SITE_NAME)}의 통합 학습관리 방식을 같은 기준으로 비교했습니다.</p>
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
        <h2>{esc(local)} {esc(CATEGORY)} 학습료 안내</h2>
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
        for i, (q, a) in enumerate(checklist)
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

    review_html = "\n".join(
        f'<article class="review-card"><span class="stars">{"★" * int(r["rating"])}{"☆" * (5 - int(r["rating"]))}</span><p>{esc(r["body"])}</p></article>'
        for r in reviews
    )
    review_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">PARENT REVIEW</p>
        <h2>{esc(local)} {esc(CATEGORY)} 상담 후기</h2>
      </div>
      <div class="review-grid">
        {review_html}
      </div>
    </section>"""

    related_html = "\n".join(
        f'<a href="{esc(url)}"><strong>{esc(name)} {esc(CATEGORY)}</strong><small>{esc(area)} 지역 페이지</small></a>'
        for name, url, area in related
    )
    other_link_html = cross_category_links_html(local, slug, CATEGORY)
    link_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">근처 학원페이지</p>
        <h2>{esc(local)} 주변 {esc(CATEGORY)} 페이지</h2>
        <p class="lead">같은 지역의 다른 카테고리와, 가까운 지역 페이지로 이동할 수 있도록 정리했습니다.</p>
      </div>
      <div class="link-grid">
        {other_link_html}
        <a href="../index.html"><strong>{esc(CATEGORY)} 전체</strong><small>카테고리 허브</small></a>
        <a href="../../index.html"><strong>전국학원</strong><small>전체 허브</small></a>
        {related_html}
      </div>
    </section>"""

    body = f"""{nav_html(3)}

  <main>
    <section class="page-hero">
      <p class="breadcrumb"><a href="../../../index.html">홈</a><span>/</span><a href="../../index.html">전국학원</a><span>/</span><a href="../index.html">{esc(CATEGORY)}</a><span>/</span><span>{esc(local)}</span></p>
      <p class="eyebrow">ALL-SUBJECT LEARNING COACHING</p>
      <h1>{esc(title)}</h1>
      <p class="lead">{esc(description)}</p>
      {badge_row}
      <div class="hero-actions">
        <a class="btn btn-primary" href="tel:{PHONE_DISPLAY}">전화 상담하기</a>
        <a class="btn btn-ghost" href="../../../상담문의/index.html">상담문의</a>
      </div>
    </section>

{media_section}

{summary_section}

{manuscript_section}

{answer_section}

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

def root_hub() -> None:
    rep = "/assets/generated/academy-hero-v2.png"
    existing = [(name, desc) for name, desc in ALL_CATEGORIES if (SITE / "전국학원" / name).exists() or name == CATEGORY]
    ld_root = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "CollectionPage", "@id": "/전국학원/#webpage", "url": "/전국학원/", "name": "전국학원", "description": f"{SITE_NAME} 전국 학원 안내 허브입니다.", "inLanguage": "ko-KR"},
            {"@type": "BreadcrumbList", "@id": "/전국학원/#breadcrumb", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "홈", "item": "/"}, {"@type": "ListItem", "position": 2, "name": "전국학원", "item": "/전국학원/"}]},
            {"@type": "ItemList", "@id": "/전국학원/#categories", "name": "전국학원 카테고리", "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": name, "url": f"/전국학원/{name}/"} for i, (name, _) in enumerate(existing)]},
        ],
    }
    head = head_html(f"전국학원 | {SITE_NAME}", f"{SITE_NAME} 전국학원 허브입니다. 카테고리별로 지역 학습관리 안내 페이지로 이동할 수 있습니다.", 1, "/전국학원/", "website", rep, ld_root)
    category_cards = "".join(
        f'<a href="{esc(name)}/index.html"><strong>{esc(name)}</strong><small>{esc(desc)}</small></a>'
        for name, desc in existing
    )
    body = f"""{nav_html(1)}
  <main>
    <section class="page-hero">
      <p class="breadcrumb"><a href="../index.html">홈</a><span>/</span><span>전국학원</span></p>
      <p class="eyebrow">NATIONAL ACADEMY HUB</p>
      <h1>전국학원</h1>
      <p class="lead">카테고리별로 지역 학습관리 페이지를 정리하는 허브입니다.</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="tel:{PHONE_DISPLAY}">전화 상담하기</a>
        <a class="btn btn-ghost" href="../상담문의/index.html">상담문의</a>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <p class="eyebrow">ABOUT US</p>
        <h2>{esc(SITE_NAME)}은 이런 곳이에요</h2>
        <p class="lead">{esc(SITE_NAME)}은 영어와 수학을 따로 보지 않아요. 상담, 진단, 통합 플래너, 오답 재학습까지 아이에게 필요한 순서를 함께 찾아드립니다.</p>
      </div>
      <div class="card-grid">
        <article class="info-card"><span class="tag">01</span><h3>지역 데이터 기반</h3><p>실제 센터 주소와 인근 학교 정보를 바탕으로, 지역마다 다른 상담 기준을 정리해 안내해요.</p></article>
        <article class="info-card"><span class="tag">02</span><h3>과목 통합 관리</h3><p>영어, 수학, 국어를 각각 다른 곳에 맡기지 않고 한 곳에서 함께 관리해요.</p></article>
        <article class="info-card"><span class="tag">03</span><h3>학년별 우선순위</h3><p>초·중·고 전환 시기마다 필요한 게 달라 학년에 맞춰 순서를 정해요.</p></article>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <p class="eyebrow">구조 안내</p>
        <h2>카테고리에서 지역으로 이동하는 방식</h2>
        <p class="lead">예: 전국학원 / {CATEGORY} / 명일동</p>
      </div>
      <div class="category-grid">
        {category_cards}
      </div>
    </section>
  </main>
{footer_html(1)}"""
    out = SITE / "전국학원" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page_shell(head, body), encoding="utf-8")


def category_hub(rows: list[dict[str, str]]) -> None:
    rep = "/assets/generated/academy-hero-v2.png"
    region_blocks = region_blocks_html(rows)
    ld_cat = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "CollectionPage", "@id": f"/전국학원/{CATEGORY}/#webpage", "url": f"/전국학원/{CATEGORY}/", "name": CATEGORY, "description": f"{CATEGORY} 지역별 안내 허브입니다.", "inLanguage": "ko-KR"},
            {"@type": "BreadcrumbList", "@id": f"/전국학원/{CATEGORY}/#breadcrumb", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "홈", "item": "/"}, {"@type": "ListItem", "position": 2, "name": "전국학원", "item": "/전국학원/"}, {"@type": "ListItem", "position": 3, "name": CATEGORY, "item": f"/전국학원/{CATEGORY}/"}]},
            {"@type": "ItemList", "@id": f"/전국학원/{CATEGORY}/#itemlist", "name": f"{CATEGORY} 지역 목록", "numberOfItems": len(rows), "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": f"{r['근처 수업가능 동네']} {CATEGORY}", "url": f"/전국학원/{CATEGORY}/{slug_ko(r['근처 수업가능 동네'])}/"} for i, r in enumerate(rows)]},
        ],
    }
    head = head_html(f"{CATEGORY} | {SITE_NAME}", f"전국 {len(rows)}개 지역의 {CATEGORY} 안내를 지역별로 정리한 허브입니다.", 2, f"/전국학원/{CATEGORY}/", "website", rep, ld_cat)
    body = f"""{nav_html(2)}
  <main>
    <section class="page-hero">
      <p class="breadcrumb"><a href="../../index.html">홈</a><span>/</span><a href="../index.html">전국학원</a><span>/</span><span>{esc(CATEGORY)}</span></p>
      <p class="eyebrow">ALL-SUBJECT DIRECTORY</p>
      <h1>{esc(CATEGORY)}</h1>
      <p class="lead">지역별 전과목 상담 기준을 한눈에 찾을 수 있도록 정리했습니다. 각 페이지에는 지역·학년·추천학생, 학교 참고 정보, FAQ, 학부모 후기, 근처 학원페이지가 함께 구성됩니다.</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="tel:{PHONE_DISPLAY}">전화 상담하기</a>
        <a class="btn btn-ghost" href="../../상담문의/index.html">상담문의</a>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <p class="eyebrow">ABOUT US</p>
        <h2>{esc(SITE_NAME)}은 영어·수학·국어를 이렇게 관리해요</h2>
        <p class="lead">과목마다 다른 곳에 맡기기보다, 한 아이의 학습 흐름을 기준으로 영어·수학·국어를 함께 놓고 봐요. 상담에서 시작해 진단, 통합 플래너, 오답 재학습까지 이어갑니다.</p>
      </div>
      <div class="timeline">
        <article class="timeline-item">
          <div class="timeline-num">01</div>
          <div class="timeline-body"><h3>상담</h3><p>과목별 성적과 학습 습관을 한 번에 듣고, 지금 가장 필요한 과목의 우선순위를 함께 정합니다.</p></div>
        </article>
        <article class="timeline-item">
          <div class="timeline-num">02</div>
          <div class="timeline-body"><h3>진단</h3><p>영어, 수학, 국어 각각 어디에서 막히는지 나누어 확인하고 균형이 무너진 부분을 찾습니다.</p></div>
        </article>
        <article class="timeline-item">
          <div class="timeline-num">03</div>
          <div class="timeline-body"><h3>통합 플래너</h3><p>과목별 학습량을 한 플래너에 담아 서로 밀리지 않도록 조율하고 실행 결과를 확인합니다.</p></div>
        </article>
        <article class="timeline-item">
          <div class="timeline-num">04</div>
          <div class="timeline-body"><h3>오답 재학습</h3><p>과목마다 다른 오답 원인을 분류하고 비슷한 문제를 다시 풀며 반복 실수를 줄입니다.</p></div>
        </article>
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
    out = SITE / "전국학원" / CATEGORY / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page_shell(head, body), encoding="utf-8")


def main() -> None:
    rows = read_csv(COMMON / "센터정보 정리.csv")
    reps = choose_rep_images(rows)
    category_hub(rows)
    for idx, row in enumerate(rows):
        slug = slug_ko(row["근처 수업가능 동네"])
        out = SITE / "전국학원" / CATEGORY / slug / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(local_page(row, idx, reps[idx], rows), encoding="utf-8")
    root_hub()
    print(f"generated category={CATEGORY} local_pages={len(rows)}")


if __name__ == "__main__":
    main()
