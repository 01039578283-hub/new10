from __future__ import annotations

import random

import generate_wawa_academy_pages as shared

SITE = shared.SITE
COMMON = shared.COMMON
SITE_NAME = shared.SITE_NAME
PHONE_DISPLAY = shared.PHONE_DISPLAY
PHONE_LINK = shared.PHONE_LINK
PUBLISH_DATE = shared.PUBLISH_DATE
CATEGORY = "초등영어학원"

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
# content banks (freshly written for 영수학원 / 초등영어학원 — this category
# focuses on elementary-stage English: phonics, vocabulary, reading habits,
# speaking confidence — distinct from 와와학습코칭학원's all-subject/all-grade
# framing. Informed by 상담방식.txt, FAQ.txt (초등 관련 문항), 학부모 후기.txt,
# 경쟁사분석 (초등 영어 커리큘럼 구조), and "초등 영어학원 원고.xlsx"
# (themes reused, wording rewritten — not copied verbatim).
# ---------------------------------------------------------------------------

FAQ_OPENER_BANK: list[tuple[str, str]] = [
    ("{title}은 몇 살부터 다닐 수 있나요?",
     "보통 초등 저학년부터 상담 가능하며, 아이의 알파벳 인지 수준에 따라 시작 시기를 함께 정합니다."),
    ("{title}에서는 파닉스부터 배우나요?",
     "아이의 현재 읽기 수준에 따라 파닉스부터 시작할 수도, 리딩과 어휘 위주로 진행할 수도 있습니다."),
    ("{title}은 몇 명이 함께 수업받나요?",
     "선생님이 아이 한 명 한 명의 발음과 이해도를 확인할 수 있는 인원으로 반을 구성합니다."),
    ("{title}에 처음 상담을 받으려면 무엇을 준비하면 되나요?",
     "특별히 준비하실 것은 없습니다. 아이가 평소 좋아하는 영어 콘텐츠나 학습 이력이 있으면 참고가 됩니다."),
    ("{title}은 원어민 수업도 있나요?",
     "지점별 운영 방식에 따라 다를 수 있어 상담 시 정확히 안내해 드립니다."),
    ("{title} 등록 전 레벨테스트가 꼭 필요한가요?",
     "필수는 아니지만, 아이의 현재 어휘와 독해 수준을 파악하는 데 도움이 됩니다."),
]

FAQ_BANK: list[tuple[str, str]] = [
    ("파닉스를 다 끝내야 리딩을 시작하나요?",
     "꼭 순서대로 진행하지 않아도 됩니다. 아이 수준에 맞춰 파닉스와 쉬운 리딩을 병행할 수도 있습니다."),
    ("단어 암기를 힘들어하는 아이는 어떻게 지도하나요?",
     "한 번에 많이 외우기보다 짧은 문장 속에서 반복해서 만나게 해 자연스럽게 익히도록 돕습니다."),
    ("듣기와 말하기도 함께 챙겨주나요?",
     "네, 발음과 억양을 듣고 따라 하는 연습을 리딩, 문법 수업과 함께 병행합니다."),
    ("영어를 처음 시작하는 아이도 괜찮은가요?",
     "네, 알파벳부터 차근차근 시작하며 아이가 부담 없이 적응하도록 진행합니다."),
    ("{local}에서 다니는 학교의 영어 수업 진도와 맞춰주나요?",
     "학교 진도를 참고하되, 아이의 실제 이해 수준에 맞춰 학습 속도를 조정합니다."),
    ("숙제는 어느 정도 나오나요?",
     "짧은 단어 암기나 리딩 과제 위주로 부담이 크지 않은 선에서 나갑니다."),
    ("영어를 지루해하는 아이도 흥미를 붙일 수 있을까요?",
     "설명, 확인 문제, 짧은 리딩을 섞어 지루하지 않게 수업을 구성합니다."),
    ("중학교 영어를 대비해 지금부터 문법을 배워야 하나요?",
     "기초 어휘와 독해 습관이 먼저 자리 잡은 뒤에 문법을 단계적으로 늘려가는 것을 권합니다."),
    ("읽기는 잘하는데 쓰기를 어려워하면 어떻게 하나요?",
     "짧은 문장부터 따라 쓰고 완성하는 연습을 반복해 쓰기에 대한 부담을 줄여갑니다."),
    ("학습지나 학교 숙제와 겹치면 부담스럽지 않을까요?",
     "학교 일정을 고려해 학습량을 조절하니 미리 말씀해 주시면 조정해 드립니다."),
    ("레벨테스트 점수가 낮으면 수업을 못 듣게 되나요?",
     "점수로 등록 여부를 정하지 않습니다. 결과를 참고해 시작 지점만 다르게 안내해 드립니다."),
    ("초등 고학년인데 지금 시작해도 늦지 않았을까요?",
     "늦지 않았습니다. 현재 수준을 확인한 뒤 부족한 기초부터 채워가면 됩니다."),
    ("형제자매가 학년이 달라도 같이 상담받을 수 있나요?",
     "네, 각자 학년과 수준에 맞춰 따로 진단하고 안내해 드립니다."),
    ("학원을 옮기려는데 이전 진도와 다르면 어떻게 하나요?",
     "이전 학원에서 배운 내용을 확인한 뒤 지금 수준에 맞는 시작 지점을 다시 잡아드립니다."),
    ("책 읽기를 싫어하는 아이도 리딩 수업이 가능한가요?",
     "쉬운 그림책이나 짧은 이야기부터 시작해 부담 없이 읽기에 익숙해지도록 돕습니다."),
    ("발음이 걱정되는 아이인데 괜찮을까요?",
     "듣고 따라 하는 연습을 반복하며 자연스럽게 발음이 좋아지도록 지도합니다."),
    ("{title}은 시험을 자주 보나요?",
     "부담을 주는 시험보다 짧은 확인 문제로 학습 내용을 점검하는 방식을 주로 활용합니다."),
    ("준비물을 자주 잊어버리는 아이인데 관리해 주시나요?",
     "수업 전 준비물을 확인하고 스스로 챙기는 습관을 함께 지도합니다."),
]

ANSWER_BANK: list[tuple[str, str]] = [
    ("아이가 알파벳은 아는데 단어를 못 읽는다면?",
     "글자와 소리의 연결이 아직 익숙하지 않은 경우가 많습니다. 파닉스 규칙을 짧게 반복하며 소리 내어 읽는 연습을 늘립니다."),
    ("단어는 아는데 문장 해석이 안 된다면?",
     "단어 뜻과 문장 속 쓰임은 다른 문제입니다. 짧은 문장을 끊어 읽는 연습이 도움이 됩니다."),
    ("영어 학원을 옮겨도 실력이 그대로인 것 같다면?",
     "단어량을 늘리는 것만으로는 부족할 수 있습니다. 지금 아이가 어디서 막히는지부터 다시 확인하는 것이 먼저입니다."),
    ("듣기는 곧잘 하는데 말하기를 부끄러워한다면?",
     "실수해도 괜찮은 분위기에서 짧은 문장부터 소리 내어 말해보는 연습을 반복하면 점차 편해집니다."),
    ("영어 학원을 언제부터 보내야 할지 고민된다면?",
     "정해진 시기보다 아이가 글자와 소리에 관심을 보이는 시점을 살펴보시는 것이 좋습니다."),
    ("학습지만 하다가 학원을 고민 중이라면?",
     "혼자 하는 학습으로는 발음과 대화 연습이 부족할 수 있어, 함께 확인해 주는 과정이 도움이 됩니다."),
    ("영어 자신감이 없어 보이는 아이라면?",
     "작은 성취를 자주 경험하도록 쉬운 단계부터 시작해 자신감을 쌓아가는 것이 중요합니다."),
    ("학원을 고를 때 무엇을 먼저 봐야 할까요?",
     "화려한 커리큘럼보다 아이의 현재 수준을 얼마나 구체적으로 확인해 주는지를 먼저 보시는 것이 좋습니다."),
    ("중학교 영어 대비, 지금부터 무엇을 준비해야 할까요?",
     "어휘와 독해 습관을 먼저 다지고, 이후 문법을 단계적으로 늘려가는 순서를 권합니다."),
    ("형제자매를 같은 학원에 보내도 될까요?",
     "학년과 수준이 다르면 관리 방식도 다르게 적용되니, 각자에게 맞는 방향을 따로 확인하시면 됩니다."),
]

CHECKLIST_BANK: list[tuple[str, str]] = [
    ("현재 읽기 수준", "파닉스를 마쳤는지, 짧은 문장을 스스로 읽을 수 있는지 확인합니다."),
    ("어휘 암기 상태", "지금까지 익힌 단어량과 반복 주기를 확인합니다."),
    ("학교 영어 진도", "{local} 학생이 다니는 학교의 영어 수업 진도를 참고합니다."),
    ("좋아하는 콘텐츠", "평소 즐겨 보는 영어 영상이나 책이 있다면 학습에 활용합니다."),
    ("학습 이력", "이전에 다닌 학원이나 사용한 학습지가 있다면 확인합니다."),
    ("학습 우선순위", "말하기, 읽기, 쓰기 중 지금 가장 급한 부분을 먼저 정합니다."),
    ("형제자매 여부", "함께 상담받을 형제자매가 있다면 각자 학년을 알려주세요."),
    ("상담 가능 요일", "편하신 상담 요일을 미리 알려주시면 일정 조율이 쉽습니다."),
]

REVIEW_BANK: list[str] = [
    "파닉스부터 차근차근 봐주셔서 이제 혼자 단어를 읽습니다.",
    "영어를 무서워하던 아이가 지금은 즐겁게 다니고 있습니다.",
    "단어 암기를 억지로 시키지 않고 문장 속에서 익히게 해주셔서 좋았습니다.",
    "듣기, 말하기까지 함께 챙겨주셔서 발음이 자연스러워졌습니다.",
    "테스트 과정도 편안한 분위기라 부담이 적었습니다.",
    "선생님이 아이 성향을 잘 파악하고 계셔서 안심이 됩니다.",
    "책 읽기를 싫어했는데 쉬운 이야기부터 시작해 흥미를 붙였습니다.",
    "숙제량이 부담스럽지 않아 꾸준히 하고 있습니다.",
    "학원을 옮겼는데 이전 진도를 잘 확인하고 이어주셨습니다.",
    "말하기를 부끄러워했는데 지금은 자신 있게 말합니다.",
    "형제 둘 다 학년이 다른데 각자에 맞게 봐주셨습니다.",
    "준비물을 자주 잊었는데 스스로 챙기게 지도해 주셨습니다.",
    "상담할 때 아이 수준을 솔직하게 말씀해 주셔서 신뢰가 갔습니다.",
    "중학교 영어를 미리 준비할 수 있어서 든든합니다.",
    "쓰기를 어려워했는데 짧은 문장부터 시작해 늘었습니다.",
    "영어에 자신감이 없던 아이가 스스로 손을 들고 말합니다.",
    "인원이 적어서 편하게 질문한다고 좋아합니다.",
    "발음이 걱정이었는데 반복 연습으로 많이 좋아졌습니다.",
    "학습지만 하다가 학원에 다니며 대화 연습이 늘었습니다.",
    "고학년인데 시작이 늦지 않을까 걱정했는데 잘 따라가고 있습니다.",
    "시험보다 확인 문제 위주라 아이가 부담스러워하지 않습니다.",
    "선생님과의 관계가 편해서 학원 가는 것을 좋아합니다.",
    "단어 시험을 반복해서 이제 암기하는 요령이 생겼습니다.",
    "알파벳부터 시작했는데 지금은 짧은 문장을 씁니다.",
]

COMPARE_ROWS: list[dict[str, tuple[str, str]]] = [
    {"label": "읽기 진단", "A": ("나이만 보고 반 편성", "파닉스·어휘 수준부터 확인"),
     "B": ("교재 진도만 확인", "읽기와 소리 연결 정도까지 확인")},
    {"label": "어휘 지도", "A": ("단어 암기만 반복", "아이 관심사와 연결한 학습"),
     "B": ("암기량 위주 점검", "문장 속 실제 쓰임까지 확인")},
    {"label": "말하기 훈련", "A": ("듣기 위주로 진행", "소리 내어 말하는 연습까지 진행"),
     "B": ("발표 기회가 적음", "짧은 문장부터 반복해서 말해보기")},
    {"label": "가정 안내", "A": ("결과만 통보하고 끝", "읽기·어휘·태도 변화까지 설명"),
     "B": ("정해진 주기로만 연락", "궁금할 때 바로 상담 가능")},
]

SUMMARY_INTROS: list[str] = [
    "{local} 학생에게 필요한 영어 관리는 단어량을 늘리는 것보다 지금 읽기와 듣기 중 어디가 부족한지 먼저 확인하는 것입니다.",
    "{local}에서 초등 영어학원을 고르실 때는 파닉스, 어휘, 독해 중 아이에게 지금 필요한 부분이 무엇인지부터 살펴보시는 것이 좋습니다.",
    "{local} 학생마다 영어를 처음 만난 시기와 방식이 다르기 때문에, 같은 학년이라도 시작 지점은 달라질 수 있습니다.",
]

MANUSCRIPT_INTRO: list[str] = [
    "초등 영어는 문법보다 소리와 글자를 연결하는 것이 먼저입니다. 파닉스가 자리 잡지 않은 상태에서 단어량만 늘리면 오히려 독해에서 어려움을 겪을 수 있습니다.",
    "어휘를 많이 아는 것과 문장을 해석하는 것은 다른 능력입니다. 단어 뜻만 외우기보다 문장 속에서 자연스럽게 만나는 경험이 필요합니다.",
    "말하기를 부끄러워하는 아이일수록 실수해도 괜찮은 분위기에서 반복해서 소리 내어 말해보는 연습이 중요합니다.",
    "초등 시기의 영어 학습은 중학교 영어의 기초가 됩니다. 지금 어휘와 독해 습관을 다져두면 이후 문법을 배울 때 훨씬 수월해집니다.",
    "아이마다 영어를 처음 접한 시기와 좋아하는 콘텐츠가 다릅니다. 이런 관심사를 학습에 연결하면 흥미를 오래 유지할 수 있습니다.",
    "형제자매를 같은 학원에 보내더라도 학년과 읽기 수준이 다르면 필요한 관리도 달라집니다. 각자에게 맞는 시작 지점을 따로 확인하는 것이 좋습니다.",
]

MANUSCRIPT_OUTRO: list[str] = [
    "학원을 고르실 때는 화려한 교재보다, 아이의 현재 읽기와 어휘 수준을 얼마나 구체적으로 봐주는지를 기준으로 삼으시길 권합니다.",
    "영어 점수보다 먼저 확인해야 할 것은 아이가 스스로 소리 내어 읽고 말하는 것을 부담스러워하지 않는지입니다.",
    "상담은 등록을 결정하는 자리가 아니라, 지금 아이에게 필요한 시작 지점을 함께 찾아보는 자리로 생각해 주시면 좋겠습니다.",
    "영어 학습은 한 번에 완성되지 않습니다. 듣기, 말하기, 읽기, 쓰기를 골고루 오가며 조금씩 쌓아가는 과정이라는 점을 기억해 주세요.",
    "무엇보다 아이가 영어를 부담스러워하지 않는지가 꾸준한 학습으로 이어지는 데 가장 중요합니다.",
    "지금 당장의 단어 시험 점수보다, 스스로 읽고 말해보려는 습관이 자리 잡고 있는지를 함께 지켜봐 주시길 바랍니다.",
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
    description = f"{region} {district} {local} 초등학생을 위한 {CATEGORY} 안내입니다. 파닉스·어휘·독해 진단, 듣기·말하기 연습, 학습 습관 관리 기준을 상담 전에 확인할 수 있습니다."
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

    opener = fmt_pair(pick(FAQ_OPENER_BANK, 1, local, "ee-faq-opener")[0],
                       local=local, district=district, title=title, region=region)
    faqs = [opener] + [fmt_pair(p, local=local, district=district, title=title, region=region)
                        for p in pick(FAQ_BANK, 5, local, "ee-faq")]
    answers = [fmt_pair(p, local=local, district=district, title=title, region=region)
               for p in pick(ANSWER_BANK, 4, local, "ee-answer")]
    checklist = [fmt_pair(p, local=local, district=district, title=title, region=region)
                 for p in pick(CHECKLIST_BANK, 4, local, "ee-checklist")]
    review_lines = pick(REVIEW_BANK, 6, local, "ee-review", str(idx))
    summary_intro = pick(SUMMARY_INTROS, 1, local, "ee-summary")[0].format(local=local)
    manu_intro = pick(MANUSCRIPT_INTRO, 1, local, "ee-manu-intro")[0]
    manu_outro = pick(MANUSCRIPT_OUTRO, 1, local, "ee-manu-outro")[0]
    location_ref = address if address else "상담 시 안내되는 위치"
    variant = "A" if seed_for(local, "ee-compare") % 2 == 0 else "B"

    rng = random.Random(seed_for(local, "ee-review-rating"))
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
        {"@type": "Thing", "name": "초등영어학원"},
        {"@type": "Thing", "name": "파닉스"},
        {"@type": "Thing", "name": "어휘 학습"},
        {"@type": "Thing", "name": "독해 습관"},
        {"@type": "Thing", "name": "듣기 말하기 연습"},
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
                "alternateName": [SITE_NAME, center, f"{local} 초등영어 학습관리"],
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
                "knowsAbout": ["파닉스", "초등 영어 어휘", "영어 독해 습관", "듣기 말하기 연습", "학습 습관 관리", "학습 상담"],
                "makesOffer": [
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 초등영어 진단 상담", "serviceType": "TutoringService"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 파닉스·독해 관리", "serviceType": "TutoringService"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 듣기 말하기 연습", "serviceType": "TutoringService"}},
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
                "description": f"{local} 초등학생의 파닉스, 어휘, 독해, 듣기·말하기를 함께 진단하고 학습 습관까지 관리합니다.",
                "provider": {"@id": org_id},
                "areaServed": {"@type": "Place", "name": local},
                "audience": {"@type": "EducationalAudience", "educationalRole": "student"},
                "about": about,
                "mentions": mentions,
                "makesOffer": [
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 초등영어 어휘·독해 진단"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 파닉스 관리"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": f"{local} 듣기 말하기 연습"}},
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

    badge_row = f'<div class="badge-row"><span>{esc(region)}</span><span>{esc(district)}</span><span>초등영어</span><span>파닉스·어휘·독해</span></div>'

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
        <article class="info-card"><span class="tag">01</span><h3>읽기·어휘 진단</h3><p>파닉스, 어휘량, 독해 중 지금 어디가 부족한지 먼저 나누어 확인합니다.</p></article>
        <article class="info-card"><span class="tag">02</span><h3>듣기·말하기</h3><p>발음과 억양을 듣고 따라 하는 연습을 반복해 자신감을 키웁니다.</p></article>
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
        <article class="info-card"><span class="tag">지역</span><h3>{esc(region)} {esc(district)} {esc(local)}</h3><p>{esc(local)} 생활권 학생의 학교 진도와 눈높이에 맞춰 초등영어 관리 방향을 상담합니다.</p></article>
        <article class="info-card"><span class="tag">학년</span><h3>초1~초6, 전 학년 상담 가능</h3><p>학년과 읽기 수준에 따라 파닉스, 어휘, 독해 중 시작 지점을 다르게 잡습니다.</p></article>
        <article class="info-card"><span class="tag">추천</span><h3>이런 학생에게 추천</h3><p>알파벳은 아는데 독해가 어려운 학생, 말하기를 부끄러워하는 학생, 영어를 처음 시작하는 학생에게 적합합니다.</p></article>
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
        <h2>{esc(local)} 초등영어, 무엇이 다른가요</h2>
        <p class="lead">일반적인 학원 운영 방식과 {esc(SITE_NAME)}의 초등영어 관리 방식을 같은 기준으로 비교했습니다.</p>
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
        <h2>{esc(local)} 초등영어 상담 후기</h2>
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
      <p class="eyebrow">ELEMENTARY ENGLISH COACHING</p>
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
      <p class="eyebrow">ELEMENTARY ENGLISH DIRECTORY</p>
      <h1>{esc(CATEGORY)}</h1>
      <p class="lead">지역별 초등영어 상담 기준을 한눈에 찾을 수 있도록 정리했습니다. 각 페이지에는 지역·학년·추천학생, 학교 참고 정보, FAQ, 학부모 후기, 근처 학원페이지가 함께 구성됩니다.</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="tel:{PHONE_DISPLAY}">전화 상담하기</a>
        <a class="btn btn-ghost" href="../../상담문의/index.html">상담문의</a>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <p class="eyebrow">ABOUT US</p>
        <h2>{esc(SITE_NAME)}은 초등영어를 이렇게 시작해요</h2>
        <p class="lead">단어량을 늘리기보다, 지금 아이가 파닉스·어휘·독해 중 어디에 있는지부터 확인해요. 상담에서 시작해 진단, 학습 습관, 듣기·말하기 연습까지 이어갑니다.</p>
      </div>
      <div class="timeline">
        <article class="timeline-item">
          <div class="timeline-num">01</div>
          <div class="timeline-body"><h3>상담</h3><p>아이가 영어를 접한 시기와 좋아하는 콘텐츠, 현재 학습 이력을 편하게 듣습니다.</p></div>
        </article>
        <article class="timeline-item">
          <div class="timeline-num">02</div>
          <div class="timeline-body"><h3>진단</h3><p>파닉스, 어휘, 독해, 듣기·말하기 중 지금 어디부터 시작해야 할지 확인합니다.</p></div>
        </article>
        <article class="timeline-item">
          <div class="timeline-num">03</div>
          <div class="timeline-body"><h3>학습 습관</h3><p>짧은 학습량으로 시작해 꾸준히 이어가는 습관을 만들어 갑니다.</p></div>
        </article>
        <article class="timeline-item">
          <div class="timeline-num">04</div>
          <div class="timeline-body"><h3>듣기·말하기 연습</h3><p>발음과 억양을 듣고 따라 하는 연습을 반복해 자신감을 키웁니다.</p></div>
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
