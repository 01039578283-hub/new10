from __future__ import annotations

import random

import generate_wawa_academy_pages as shared

SITE = shared.SITE
COMMON = shared.COMMON
SITE_NAME = shared.SITE_NAME
PHONE_DISPLAY = shared.PHONE_DISPLAY
PHONE_LINK = shared.PHONE_LINK
PUBLISH_DATE = shared.PUBLISH_DATE
CATEGORY = "초등수학학원"

ALL_CATEGORIES = shared.ALL_CATEGORIES
cross_category_links_html = shared.cross_category_links_html

esc = shared.esc
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
pick = shared.pick
fmt_pair = shared.fmt_pair
school_names = shared.school_names
region_blocks_html = shared.region_blocks_html
FEE_TABLE_SEOUL = shared.FEE_TABLE_SEOUL
FEE_TABLE_OTHER = shared.FEE_TABLE_OTHER


# ---------------------------------------------------------------------------
# content banks (freshly written for 영수학원 / 초등수학학원 — this category
# focuses on elementary-stage math: 연산 정확도, 개념 이해, 문장제, 오답 관리,
# 학습 습관 — distinct from 와와학습코칭학원(전과목)과 초등영어학원(영어) 뱅크.
# Informed by 상담방식.txt, FAQ.txt (초등 관련 문항), 학부모 후기.txt,
# 경쟁사분석, and "초등 수학학원 원고.xlsx" (themes reused, wording rewritten).
# ---------------------------------------------------------------------------

FAQ_OPENER_BANK: list[tuple[str, str]] = [
    ("{title}은 초등 몇 학년부터 다닐 수 있나요?",
     "보통 연산을 배우기 시작하는 학년부터 상담 가능하며, 아이의 숫자 개념 이해도에 따라 시작 시기를 정합니다."),
    ("{title}에서는 연산부터 시작하나요?",
     "아이의 현재 연산 정확도에 따라 연산부터 시작할 수도, 개념 설명 위주로 진행할 수도 있습니다."),
    ("{title}은 한 반에 몇 명이 배정되나요?",
     "선생님이 아이 한 명 한 명의 풀이 과정을 확인할 수 있는 인원으로 반을 구성합니다."),
    ("{title} 상담 전에 따로 준비할 게 있을까요?",
     "특별히 준비하실 것은 없습니다. 최근 수학 시험지나 학습지가 있으면 참고가 됩니다."),
    ("{title}은 사고력 수학도 함께 다루나요?",
     "센터별 운영 방식에 따라 다를 수 있어 상담 시 자세히 안내해 드립니다."),
    ("{title} 등록 전에 진단 테스트가 꼭 필요한가요?",
     "필수는 아니지만, 아이의 현재 연산과 개념 이해 수준을 파악하는 데 도움이 됩니다."),
]

FAQ_BANK: list[tuple[str, str]] = [
    ("연산 속도가 느린 아이는 어떻게 지도하나요?",
     "정확도를 먼저 잡은 뒤 반복 연습으로 속도를 서서히 끌어올립니다."),
    ("구구단을 아직 못 외웠는데 진도를 나가도 되나요?",
     "구구단이 막히면 이후 단원에서 계속 걸림돌이 되므로, 먼저 확실히 익히고 진도를 나갑니다."),
    ("문장제 문제를 유독 어려워한다면 어떻게 하나요?",
     "문제를 조건별로 나누어 읽는 연습부터 시작해 문장제에 대한 부담을 줄여갑니다."),
    ("숫자를 처음 배우는 아이도 수업이 가능한가요?",
     "네, 숫자와 자릿수 개념부터 차근차근 시작하며 아이가 부담 없이 적응하도록 진행합니다."),
    ("{local}에서 다니는 학교의 수학 단원 진도와 맞춰주나요?",
     "학교 진도를 참고하되, 아이의 실제 이해 수준에 맞춰 학습 순서를 조정합니다."),
    ("연산 문제집 숙제는 얼마나 나오나요?",
     "하루에 풀 수 있는 분량으로 조절해 부담이 크지 않은 선에서 나갑니다."),
    ("수학을 유독 싫어하는 아이도 흥미를 붙일 수 있을까요?",
     "쉬운 문제부터 작은 성취를 쌓아가며 수학에 대한 거부감을 줄여갑니다."),
    ("중학교 수학을 대비해 지금부터 선행이 필요한가요?",
     "지금 학년 개념이 잘 정리되어 있는지 먼저 확인한 뒤, 필요한 경우에만 단계적으로 진행합니다."),
    ("계산은 잘하는데 개념을 묻는 문제만 나오면 틀린다면?",
     "계산 훈련과 개념 이해는 다른 영역입니다. 개념을 그림이나 예시로 다시 설명하는 과정이 필요합니다."),
    ("문제집만 풀다가 학원을 고민 중이라면 어떻게 해야 하나요?",
     "혼자 채점만 하는 학습으로는 오답 원인을 짚기 어려워, 함께 확인해 주는 과정이 도움이 됩니다."),
    ("레벨테스트에서 기초 연산이 약하게 나오면 어떻게 하나요?",
     "기초 연산부터 단계적으로 채워가는 계획을 세워 안내해 드립니다."),
    ("초등 고학년인데 연산이 부족해도 따라갈 수 있을까요?",
     "지금 부족한 연산 단원부터 확인한 뒤 순서대로 채워가면 충분히 따라갈 수 있습니다."),
    ("도형이나 공간 감각을 어려워하는 아이는 어떻게 지도하나요?",
     "그림을 직접 그리거나 교구를 활용해 개념을 시각적으로 이해하도록 돕습니다."),
    ("오답 노트는 따로 만들어 주나요?",
     "틀린 문제를 유형별로 정리해 다시 풀어볼 수 있도록 관리합니다."),
    ("같은 실수를 자꾸 반복하는 아이는 어떻게 관리하나요?",
     "실수의 유형(계산·조건 누락·이해 부족)을 나누어 확인하고 그에 맞는 연습을 반복합니다."),
    ("학교 단원평가 대비도 함께 해주나요?",
     "학교별 단원평가 범위에 맞춰 개념과 유형 문제를 정리해 드립니다."),
    ("사고력 수학과 교과 수학을 함께 배울 수 있나요?",
     "기초 연산과 개념을 먼저 다진 뒤, 여유가 있는 경우 사고력 문제를 함께 다룹니다."),
    ("손가락으로 셈을 하는 습관이 있는데 괜찮을까요?",
     "숫자 감각이 자리 잡으면 자연스럽게 줄어드는 경우가 많아, 무리하게 교정하기보다 단계적으로 유도합니다."),
]

ANSWER_BANK: list[tuple[str, str]] = [
    ("아이가 연산은 빠른데 문장제만 나오면 막힌다면?",
     "문제를 조건별로 끊어 읽고 무엇을 구하는지부터 확인하는 연습이 필요합니다."),
    ("개념은 아는 것 같은데 응용문제에서 막힌다면?",
     "개념을 응용으로 연결하는 중간 단계 문제가 부족했을 수 있습니다. 대표 유형부터 차근차근 늘려갑니다."),
    ("수학 학원을 옮겨도 성적이 그대로인 것 같다면?",
     "문제양을 늘리는 것만으로는 부족할 수 있습니다. 지금 아이가 어느 단원에서 막히는지부터 다시 확인하는 것이 먼저입니다."),
    ("같은 유형에서 반복해서 틀린다면?",
     "실수의 원인이 계산인지 개념인지 조건 누락인지 구분해 그에 맞는 연습을 반복합니다."),
    ("수학 학원을 언제부터 보내야 할지 고민된다면?",
     "정해진 시기보다 아이가 숫자와 연산에 흥미를 보이는 시점을 살펴보시는 것이 좋습니다."),
    ("문제집만 풀리다가 학원을 고민 중이라면?",
     "혼자 채점하는 학습으로는 오답 원인을 짚어주기 어려워, 함께 확인해 주는 과정이 도움이 됩니다."),
    ("수학 자신감이 없어 보이는 아이라면?",
     "쉬운 단계에서 작은 성취를 자주 경험하도록 하여 자신감을 쌓아가는 것이 중요합니다."),
    ("수학 학원을 고를 때 가장 먼저 볼 기준은?",
     "화려한 선행 커리큘럼보다 아이가 지금 어디서 막히는지 구체적으로 확인해 주는지를 먼저 보시는 것이 좋습니다."),
    ("중학교 수학 대비, 지금부터 무엇을 준비해야 할까요?",
     "연산 정확도와 개념 이해를 먼저 다지고, 이후 유형 문제를 단계적으로 늘려가는 순서를 권합니다."),
    ("학년이 다른 형제자매를 같이 보내도 괜찮을까요?",
     "학년과 진도가 다르면 각자 다른 단원을 다루게 되니, 개별 진단 후 각자에게 맞는 계획을 안내해 드립니다."),
]

CHECKLIST_BANK: list[tuple[str, str]] = [
    ("연산 정확도", "덧셈·뺄셈·곱셈·나눗셈 중 어디서 실수가 잦은지 확인합니다."),
    ("개념 이해 상태", "학년별 핵심 개념을 어느 정도 이해하고 있는지 확인합니다."),
    ("학교 수학 진도", "{local} 학생이 다니는 학교의 수학 단원 진도를 참고합니다."),
    ("오답 정리 습관", "기존에 틀린 문제를 정리해 온 방법이 있다면 함께 확인합니다."),
    ("문장제 이해도", "문제 조건을 읽고 무엇을 구하는지 파악하는 수준을 확인합니다."),
    ("이전 학습 이력", "다니던 학원이나 문제집이 있었다면 진도와 방식을 확인합니다."),
    ("연산 풀이 방식", "손가락 셈, 암산 등 현재 연산 방식을 확인합니다."),
    ("상담 편한 시간대", "편하신 상담 요일과 시간대를 미리 알려주시면 좋습니다."),
]

REVIEW_BANK: list[str] = [
    "연산 속도가 느렸는데 정확도부터 잡아주셔서 실수가 줄었습니다.",
    "구구단을 못 외웠는데 차근차근 잡아주셔서 이제 잘 합니다.",
    "문장제를 무서워했는데 조건 나누는 법을 배우고 좋아졌습니다.",
    "숫자를 처음 배우는 아이인데 부담 없이 시작했습니다.",
    "학교 단원 진도에 맞춰 챙겨주셔서 시험 결과가 안정적입니다.",
    "선생님이 아이가 어디서 막히는지 정확히 짚어주십니다.",
    "수학을 싫어했는데 쉬운 문제부터 시작해 흥미를 붙였습니다.",
    "연산 숙제량이 부담스럽지 않아 꾸준히 하고 있습니다.",
    "다른 학원에서 옮겼는데 이전 단원을 확인하고 이어서 진행해 주셨습니다.",
    "같은 유형에서 반복해서 틀리던 게 이제 줄었습니다.",
    "도형 문제를 어려워했는데 그림으로 설명해 주셔서 이해했습니다.",
    "오답 노트를 정리해 주셔서 같은 실수가 줄었습니다.",
    "상담 때 아이 상태를 정확하게 짚어주셔서 믿음이 갔습니다.",
    "중학교 수학을 미리 준비할 수 있어서 든든합니다.",
    "개념 문제를 어려워했는데 예시를 들어 설명해 이해가 빨라졌습니다.",
    "수학에 자신감이 없던 아이가 스스로 풀어보려고 합니다.",
    "질문할 때마다 편하게 봐주셔서 아이가 편해합니다.",
    "손가락으로 세던 아이가 이제 암산을 시도합니다.",
    "학습지만 하다가 학원에 다니며 오답 관리가 늘었습니다.",
    "고학년인데 연산이 부족해서 걱정했는데 잘 따라가고 있습니다.",
    "쪽지시험보다 개념 확인 위주라 아이가 부담스러워하지 않습니다.",
    "선생님이 편하게 대해주셔서 학원 가는 걸 좋아합니다.",
    "단원평가를 반복해서 이제 실수하는 유형을 스스로 압니다.",
    "자릿수 개념부터 시작했는데 지금은 문장제도 풀어봅니다.",
]

COMPARE_ROWS: list[dict[str, tuple[str, str]]] = [
    {"label": "연산 진단", "A": ("문제 양만 늘려서 진행", "정확도부터 확인 후 시작"),
     "B": ("채점만 하고 끝", "실수 유형까지 구분해서 확인")},
    {"label": "개념 설명", "A": ("공식 암기 위주", "그림과 예시로 이해"),
     "B": ("한 번 설명하고 넘어감", "이해될 때까지 반복 설명")},
    {"label": "문장제 훈련", "A": ("문제만 반복해서 풀림", "조건 읽는 법부터 훈련"),
     "B": ("정답 확인만 함", "무엇을 구하는지 확인하는 연습")},
    {"label": "숙제 관리", "A": ("숙제만 내주고 끝", "오답까지 확인하고 재학습"),
     "B": ("정해진 분량만 부여", "실행 결과 보고 조정")},
]

SUMMARY_INTROS: list[str] = [
    "{local} 학생에게 필요한 수학 관리는 문제를 많이 푸는 것보다 지금 연산과 개념 중 어디가 부족한지 먼저 확인하는 것입니다.",
    "{local}에서 초등수학학원을 고르실 때는 연산, 개념, 문장제 중 아이에게 지금 필요한 부분이 무엇인지부터 살펴보시는 것이 좋습니다.",
    "{local} 학생마다 수학을 어려워하는 지점이 다르기 때문에, 같은 학년이라도 먼저 봐야 할 부분은 달라질 수 있습니다.",
]

MANUSCRIPT_INTRO: list[str] = [
    "초등 수학은 연산 정확도가 이후 모든 단원의 기초가 됩니다. 연산이 불안정한 상태에서 진도만 나가면 개념 문제에서 계속 실수가 반복될 수 있습니다.",
    "계산을 잘하는 것과 개념을 이해하는 것은 다른 능력입니다. 공식을 외우기보다 그림이나 예시로 원리를 이해하는 경험이 필요합니다.",
    "문장제를 어려워하는 아이일수록 문제를 통째로 읽기보다 조건을 나누어 읽는 연습이 먼저 필요합니다.",
    "초등 시기의 수학 학습은 중학교 수학의 기초가 됩니다. 지금 연산과 개념을 다져두면 이후 유형 문제를 배울 때 훨씬 수월해집니다.",
    "아이마다 수학에서 막히는 지점이 다릅니다. 연산인지, 개념인지, 문장제인지부터 구분하면 훨씬 효율적으로 도울 수 있습니다.",
    "같은 실수를 반복하는 아이일수록 오답을 다시 채점하는 데서 끝내지 않고, 왜 틀렸는지 원인을 나누어 확인하는 과정이 중요합니다.",
]

MANUSCRIPT_OUTRO: list[str] = [
    "학원을 고르실 때는 화려한 선행 진도보다, 아이의 현재 연산과 개념 수준을 얼마나 구체적으로 봐주는지를 기준으로 삼으시길 권합니다.",
    "수학 점수보다 먼저 확인해야 할 것은 아이가 왜 틀렸는지를 스스로 설명할 수 있는지입니다.",
    "상담은 곧바로 등록을 정하는 자리가 아니라, 지금 아이에게 맞는 시작점을 같이 찾아보는 자리로 여겨주시면 좋겠습니다.",
    "수학 학습은 한 번에 완성되지 않습니다. 연산, 개념, 문장제를 오가며 조금씩 쌓아가는 과정이라는 점을 기억해 주세요.",
    "무엇보다 아이가 수학을 부담스러워하지 않는지가 꾸준한 학습으로 이어지는 데 가장 중요합니다.",
    "지금 당장의 단원평가 점수보다, 오답을 스스로 정리해 보려는 습관이 자리 잡고 있는지를 함께 지켜봐 주시길 바랍니다.",
]


def choose_rep_images(rows: list[dict[str, str]]) -> list[str]:
    return shared.choose_rep_images(rows)


def local_page(row: dict[str, str], idx: int, rep_image: str, all_rows: list[dict[str, str]]) -> str:
    local = row["근처 수업가능 동네"].strip()
    slug = slug_ko(local)
    region = row.get("지역", "").strip()
    district = row.get("시or구", "").strip()
    center = row.get("센터명", "").strip() or f"{local} 학습관리"
    address = row.get("센터 주소", "").strip()
    title = f"{local} {CATEGORY}"
    description = f"{region} {district} {local} 초등학생을 위한 {CATEGORY} 안내입니다. 연산·개념·문장제 진단, 오답 관리, 학습 습관 관리 기준을 상담 전에 확인할 수 있습니다."
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

    elementary_schools = split_items(row.get("타깃학교\n(초)", ""))
    middle_schools = split_items(row.get("타깃학교\n(중)", ""))
    schools = school_names(row)

    reg_no = row.get("교육지원청 등록번호", "").strip()
    education_name = row.get("교육지원청명칭", "").strip()

    opener = fmt_pair(pick(FAQ_OPENER_BANK, 1, local, "em-faq-opener")[0],
                       local=local, district=district, title=title, region=region)
    faqs = [opener] + [fmt_pair(p, local=local, district=district, title=title, region=region)
                        for p in pick(FAQ_BANK, 5, local, "em-faq")]
    answers = [fmt_pair(p, local=local, district=district, title=title, region=region)
               for p in pick(ANSWER_BANK, 4, local, "em-answer")]
    checklist = [fmt_pair(p, local=local, district=district, title=title, region=region)
                 for p in pick(CHECKLIST_BANK, 4, local, "em-checklist")]
    review_lines = pick(REVIEW_BANK, 6, local, "em-review", str(idx))
    summary_intro = pick(SUMMARY_INTROS, 1, local, "em-summary")[0].format(local=local)
    manu_intro = pick(MANUSCRIPT_INTRO, 1, local, "em-manu-intro")[0]
    manu_outro = pick(MANUSCRIPT_OUTRO, 1, local, "em-manu-outro")[0]
    location_ref = address if address else "상담 시 안내되는 위치"
    variant = "A" if seed_for(local, "em-compare") % 2 == 0 else "B"

    rng = random.Random(seed_for(local, "em-review-rating"))
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
        {"@type": "Thing", "name": "초등수학학원"},
        {"@type": "Thing", "name": "연산"},
        {"@type": "Thing", "name": "개념 이해"},
        {"@type": "Thing", "name": "문장제"},
        {"@type": "Thing", "name": "오답 관리"},
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
                    {"@type": "ListItem", "position": 4, "name": title, "item": canonical},
                ],
            },
            {
                "@type": ["EducationalOrganization", "LocalBusiness"],
                "@id": org_id,
                "name": title,
                "alternateName": [SITE_NAME, center, f"{local} 초등수학 학습관리"],
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
                "knowsAbout": ["연산", "초등 수학 개념", "문장제 풀이", "오답 관리", "학습 습관 관리", "학습 상담"],
                "makesOffer": [
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 초등수학 진단 상담", "serviceType": "TutoringService"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 연산·개념 관리", "serviceType": "TutoringService"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 문장제·오답 관리", "serviceType": "TutoringService"}},
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
                "description": f"{local} 초등학생의 연산, 개념, 문장제, 오답을 함께 진단하고 학습 습관까지 관리합니다.",
                "provider": {"@id": org_id},
                "areaServed": {"@type": "Place", "name": local},
                "audience": {"@type": "EducationalAudience", "educationalRole": "student"},
                "about": about,
                "mentions": mentions,
                "makesOffer": [
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 초등수학 연산·개념 진단"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 문장제 관리"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 오답 재학습 관리"}},
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

    badge_row = f'<div class="badge-row"><span>{esc(region)}</span><span>{esc(district)}</span><span>초등수학</span><span>연산·개념·문장제</span></div>'

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
        <article class="info-card"><span class="tag">01</span><h3>연산·개념 진단</h3><p>연산 정확도, 개념 이해, 문장제 중 지금 어디가 부족한지 먼저 나누어 확인합니다.</p></article>
        <article class="info-card"><span class="tag">02</span><h3>오답 관리</h3><p>틀린 문제를 유형별로 정리해 같은 실수가 반복되지 않도록 관리합니다.</p></article>
        <article class="info-card"><span class="tag">03</span><h3>학습 습관</h3><p>짧은 학습량으로 시작해 꾸준히 이어가는 습관을 만듭니다.</p></article>
      </div>
    </section>"""

    manuscript_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">학원 선택 가이드</p>
        <h2>{esc(local)} {esc(CATEGORY)}, 무엇을 기준으로 볼까요</h2>
      </div>
      <p class="lead">{esc(manu_intro)}</p>
      <p class="lead">{esc(center)}은 {esc(region)} {esc(district)} {esc(local)} 학생을 기준으로 상담을 진행하며, {esc(', '.join(elementary_schools) if elementary_schools else '인근 초등학교')} 학생들이 주로 문의합니다. 실제 등록 전에는 {esc(location_ref)}{eul_reul(location_ref)} 기준으로 이동 동선과 상담 가능 시간을 확인하는 것이 좋습니다.</p>
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
        linked_bits.append(f"진학 예정 중학교: {', '.join(middle_schools)}")
    linked_schools = ""
    if linked_bits:
        linked_schools = f'<article class="info-card"><span class="tag">학교</span><h3>학교급별 참고 학교</h3><p>{esc(" · ".join(linked_bits))}</p></article>'
    fit_section = f"""    <section class="section">
      <div class="section-head">
        <p class="eyebrow">LOCAL &amp; STUDENT FIT</p>
        <h2>지역·학년·추천학생 기준</h2>
      </div>
      <div class="card-grid">
        <article class="info-card"><span class="tag">지역</span><h3>{esc(region)} {esc(district)} {esc(local)}</h3><p>{esc(local)} 생활권 학생의 학교 진도와 눈높이에 맞춰 초등수학 관리 방향을 상담합니다.</p></article>
        <article class="info-card"><span class="tag">학년</span><h3>초1~초6, 전 학년 상담 가능</h3><p>학년과 연산 수준에 따라 연산, 개념, 문장제 중 시작 지점을 다르게 잡습니다.</p></article>
        <article class="info-card"><span class="tag">추천</span><h3>이런 학생에게 추천</h3><p>연산은 빠른데 문장제가 약한 학생, 개념 문제만 나오면 틀리는 학생, 수학을 처음 시작하는 학생에게 적합합니다.</p></article>
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
        <h2>{esc(local)} 초등수학, 무엇이 다른가요</h2>
        <p class="lead">일반적인 학원 운영 방식과 {esc(SITE_NAME)}의 초등수학 관리 방식을 같은 기준으로 비교했습니다.</p>
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
        f'<tr><td>{esc(freq)}</td><td class="highlight">{esc(el)}</td><td>{esc(mid)}</td><td>{esc(hi)}</td></tr>'
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
          <thead><tr><th>횟수</th><th class="highlight">초등</th><th>중등</th><th>고등</th></tr></thead>
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
        <h2>{esc(local)} 초등수학 상담 후기</h2>
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
      <p class="breadcrumb"><a href="../../../index.html">홈</a><span>/</span><a href="../../index.html">전국학원</a><span>/</span><a href="../index.html">{esc(CATEGORY)}</a><span>/</span><span>{esc(title)}</span></p>
      <p class="eyebrow">ELEMENTARY MATH COACHING</p>
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
      <p class="eyebrow">ELEMENTARY MATH DIRECTORY</p>
      <h1>{esc(CATEGORY)}</h1>
      <p class="lead">지역별 초등수학 상담 기준을 한눈에 찾을 수 있도록 정리했습니다. 각 페이지에는 지역·학년·추천학생, 학교 참고 정보, FAQ, 학부모 후기, 근처 학원페이지가 함께 구성됩니다.</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="tel:{PHONE_DISPLAY}">전화 상담하기</a>
        <a class="btn btn-ghost" href="../../상담문의/index.html">상담문의</a>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <p class="eyebrow">ABOUT US</p>
        <h2>{esc(SITE_NAME)}은 초등수학을 이렇게 시작해요</h2>
        <p class="lead">문제 양을 늘리기보다, 지금 아이가 연산·개념·문장제 중 어디에서 막히는지부터 확인해요. 상담에서 시작해 진단, 오답 관리, 학습 습관까지 이어갑니다.</p>
      </div>
      <div class="timeline">
        <article class="timeline-item">
          <div class="timeline-num">01</div>
          <div class="timeline-body"><h3>상담</h3><p>아이의 학년, 최근 시험지, 현재 학습 이력을 편하게 듣습니다.</p></div>
        </article>
        <article class="timeline-item">
          <div class="timeline-num">02</div>
          <div class="timeline-body"><h3>진단</h3><p>연산, 개념, 문장제 중 지금 어디부터 시작해야 할지 확인합니다.</p></div>
        </article>
        <article class="timeline-item">
          <div class="timeline-num">03</div>
          <div class="timeline-body"><h3>오답 관리</h3><p>틀린 문제를 유형별로 정리해 같은 실수가 반복되지 않도록 관리합니다.</p></div>
        </article>
        <article class="timeline-item">
          <div class="timeline-num">04</div>
          <div class="timeline-body"><h3>학습 습관</h3><p>짧은 학습량으로 시작해 꾸준히 이어가는 습관을 만들어 갑니다.</p></div>
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
    rows = shared.read_csv(COMMON / "센터정보 정리.csv")
    reps = choose_rep_images(rows)
    category_hub(rows)
    for idx, row in enumerate(rows):
        slug = slug_ko(row["근처 수업가능 동네"])
        out = SITE / "전국학원" / CATEGORY / slug / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(local_page(row, idx, reps[idx], rows), encoding="utf-8")
    shared.root_hub()
    print(f"generated category={CATEGORY} local_pages={len(rows)}")


if __name__ == "__main__":
    main()
