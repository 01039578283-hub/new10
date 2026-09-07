import unittest
from pathlib import Path
from personalize_title_suffixes import (
    learning_blocks, candidates, masked, replace_titles, title_of, plan, eligible,
    hub_copy, clean, classify, resolved_page_url, DOMAIN,
)

def sample(body,subject="combined",stage="high"):
    source='<title>명일동 학원 | 이전 제목</title><main><article class="manuscript-article">'+body+'</article></main>'
    page=dict(source=source,prefix="명일동 학원",rel="과목별학원/sample/명일동/index.html",kind="subject",group="sample",
              stage=stage,subject=subject,blocks=learning_blocks(source,"subject"))
    page["candidates"]=candidates(page)
    return page

class TitleTests(unittest.TestCase):
    def test_title_only_and_attribute_spacing(self):
        source='<title>명일동 | 기존</title>\r\n<meta property="og:title" content = \'이전\'><meta name="description" content="기존 설명"><h1>그대로</h1>'
        updated=replace_titles(source,"명일동 | 어휘 & 복습")
        self.assertIn("content = '명일동 | 어휘 &amp; 복습'",updated)
        self.assertEqual(masked(source),masked(updated))
        self.assertEqual(title_of(updated),"명일동 | 어휘 & 복습")
        self.assertIn('<h1>그대로</h1>',updated)

    def test_wrapped_intro_priority(self):
        p=sample('<div class="manuscript-intro"><p>긴 문장에서 핵심 구조를 놓치는 학생입니다.</p></div><section class="manuscript-article-section"><p>주간 계획과 과제 분량을 정리합니다.</p></section>')
        self.assertEqual(p["blocks"][0]["weight"],8)
        self.assertGreater(p["candidates"]["긴 문장 해석"]["score"],p["candidates"]["주간 학습 흐름"]["score"])

    def test_mixed_address_keeps_learning_sentence(self):
        p=sample('<div class="manuscript-intro"><p>첫 식을 세우지 못하는 학생입니다. 제공 주소는 서울 강동구입니다.</p></div>',"math")
        self.assertTrue(any("첫 식" in b["text"] for b in p["blocks"]))
        self.assertFalse(any("제공 주소" in b["text"] for b in p["blocks"]))

    def test_exclude_review_nav_hidden_and_facility(self):
        source='<main><article class="manuscript-article"><div class="manuscript-intro"><p>수학은 첫 식을 세우는 과정이 중요합니다.</p></div><nav><p>분수 개념을 확인합니다.</p></nav><div style="display: none;"><p>분수 개념을 확인합니다.</p></div><section class="center-facts-panel"><p>분수 개념을 확인합니다.</p></section><p>사물함과 분수 개념은 별도입니다.</p></article><section class="academy-review-section"><p>분수 개념을 확인했습니다.</p></section></main>'
        blocks=learning_blocks(source,"subject")
        self.assertTrue(blocks)
        self.assertFalse(any("분수" in b["text"] for b in blocks))

    def test_both_lead_subjects_are_reflected(self):
        p=sample('<div class="manuscript-intro"><p>긴 문장에서 핵심 구조를 놓치고 수학은 첫 식을 세우지 못하는 학생입니다. 시험이 가까워져야 공부량을 늘립니다.</p></div>')
        plan([p])
        self.assertEqual({x["subject"] for x in p["evidence"]},{"math","english"})

    def test_opposite_subject_is_excluded(self):
        p=sample('<div class="manuscript-intro"><p>첫 식을 세우고 검산하며 문장 구조와 독해 근거를 확인합니다.</p></div>',"math")
        self.assertTrue(p["candidates"])
        self.assertFalse(any(c["subject"]=="english" for c in p["candidates"].values()))

    def test_grade_rules(self):
        p=dict(subject="general",stage="elementary")
        self.assertFalse(eligible(p,"내신·모의고사 구분",""))
        self.assertFalse(eligible(p,"수행평가 준비",""))
        self.assertTrue(eligible(p,"숙제 시작 습관",""))

    def test_no_fabricated_fallback(self):
        p=sample('<div class="manuscript-intro"><p>제공 주소와 등록번호만 확인합니다.</p></div>')
        self.assertFalse(p["candidates"])

    def test_name_does_not_randomize_topic(self):
        first=sample('<div class="manuscript-intro"><p>명일동에서 긴 문장 해석과 첫 식을 세우는 과정을 확인합니다.</p></div>')
        second=sample('<div class="manuscript-intro"><p>다른동에서 긴 문장 해석과 첫 식을 세우는 과정을 확인합니다.</p></div>')
        second["prefix"]="다른동 학원"
        plan([first,second])
        self.assertEqual(first["suffix"],second["suffix"])

    def test_general_learning_topic_is_allowed_for_math(self):
        p=sample('<div class="manuscript-intro"><p>문항별 시간 배분을 점검하는 순서입니다.</p></div>',"math")
        plan([p])
        self.assertIn("시험 시간 배분",p["suffix"])

    def test_short_sentence_is_not_automatically_writing(self):
        p=sample('<div class="manuscript-intro"><p>짧은 문장부터 근거를 말하게 한 뒤 지문 단위로 적용합니다.</p></div>',"english")
        self.assertNotIn("짧은 문장 쓰기",p["candidates"])

    def test_grammar_application_is_not_math_evidence(self):
        p=sample('<div class="manuscript-intro"><p>문법 개념을 배워도 실전 문항에서 적용 순서가 흐릿한 학생입니다.</p></div>',"general")
        self.assertNotIn("개념의 문제 적용",p["candidates"])
        self.assertIn("문법의 문장 적용",p["candidates"])

    def test_national_answers_exclude_testimonials(self):
        source='<main><div class="answer-box"><p>수학에서는 첫 식을 세우고 계산 실수를 확인합니다.</p></div><article class="review-card"><p>분수 개념을 잘 배웠습니다.</p></article></main>'
        blocks=learning_blocks(source,"national")
        self.assertTrue(blocks)
        self.assertFalse(any("분수" in b["text"] for b in blocks))

    def test_hesitating_alone_is_not_independent_solving(self):
        p=sample('<p>질문하기 전 혼자 버티다가 풀이 시간이 길어지는 학생입니다.</p>',"math")
        self.assertNotIn("독립 풀이 확인",p["candidates"])

    def test_recall_topics_do_not_repeat_in_one_title(self):
        p=sample('<p>단어 복습 뒤 회상 결과와 문장 구조 이해를 확인합니다.</p>',"english")
        plan([p])
        self.assertFalse("어휘 인출과 복습" in p["suffix"] and "배운 내용 회상" in p["suffix"])

    def test_school_commute_is_not_review_evidence(self):
        p=sample('<p>학교 진도와 생활 동선을 함께 맞출 수 있습니다.</p>',"english")
        self.assertNotIn("학교 진도와 복습",p["candidates"])

    def test_repeated_intro_does_not_outrank_individual_case(self):
        pages=[]
        for i in range(20):
            extra='<p>계산 실수가 많은 학생이 문제 조건을 표시합니다.</p>' if i==0 else '<p>단원 간 개념 연결과 과제 실행 기록을 확인합니다.</p>'
            p=sample('<p>모든 수업에서 검산 습관을 확인합니다.</p>'+extra,"math")
            p["prefix"]=f"지역{i} 수학학원"
            p["rel"]=f"과목별학원/수학학원/지역{i}/index.html"
            pages.append(p)
        plan(pages)
        self.assertIn("계산 실수 구분",pages[0]["suffix"])
        self.assertNotIn("검산 습관",pages[0]["suffix"])
        expected=[p["after"] for p in pages]
        plan(pages)
        self.assertEqual(expected,[p["after"] for p in pages])

    def test_long_passage_concentration_is_not_sentence_parsing(self):
        p=sample('<p>긴 지문이 나오면 집중이 흔들리는 학생은 오답을 다시 확인합니다.</p>',"english","elementary")
        plan([p])
        self.assertIn("긴 지문 읽기 집중",p["suffix"])
        self.assertNotIn("긴 문장 해석",p["suffix"])

    def test_hub_evidence_is_one_contiguous_visible_paragraph(self):
        source='<main><header class="page-hero"><div class="academy-hero-main"><p>ENGLISH DIRECTORY</p><h1>지역별 영어학원 안내</h1><p>371개 동네의 학습 기준과 센터 정보를 정리했습니다.</p></div></header></main>'
        text=hub_copy(source,["371개 동네","학습 기준","센터 정보"])
        self.assertIn(text,clean(source))
        self.assertNotIn("DIRECTORY",text)

    def test_numeric_grade_and_national_classification(self):
        self.assertEqual(classify(Path("과목별학원/초3수학학원/명일동/index.html"))["stage"],"elementary")
        self.assertEqual(classify(Path("과목별학원/중1영어학원/명일동/index.html"))["stage"],"middle")
        self.assertEqual(classify(Path("과목별학원/고2수학학원/명일동/index.html"))["stage"],"high")
        self.assertEqual(classify(Path("전국학원/고등영수학원/명일동/index.html"))["subject"],"combined")

    def test_noindex_is_unchanged(self):
        source='<title>명일동 | 기존</title><meta name="robots" content="noindex,follow"><main><h1>명일동</h1></main>'
        updated=replace_titles(source,"명일동 | 학습 기록 점검")
        self.assertIn('content="noindex,follow"',updated)
        self.assertEqual(masked(source),masked(updated))

    def test_relative_canonical_is_resolved_not_rewritten(self):
        rel=Path("전국학원/고등수학학원/명일동/index.html")
        raw="/전국학원/고등수학학원/명일동/"
        encoded=resolved_page_url(raw,rel)
        self.assertTrue(encoded.startswith(DOMAIN+"/%"))
        self.assertEqual(encoded,resolved_page_url(encoded,rel))

    def test_foreign_or_other_page_canonical_is_rejected(self):
        rel=Path("전국학원/고등수학학원/명일동/index.html")
        for raw in ("https://example.com/전국학원/고등수학학원/명일동/","/전국학원/고등수학학원/다른동/"):
            with self.assertRaises(ValueError):
                resolved_page_url(raw,rel)

    def test_national_combined_copy_reflects_both_subjects(self):
        p=sample('<p>문장 구조 이해와 계산 실수 원인을 확인합니다.</p>')
        p["source"]='<title>명일동 고등영수학원 | 기존</title><main><article class="summary-card"><p>문장 구조를 확인합니다. 수학은 계산 실수를 나누어 봅니다.</p></article></main>'
        p.update(kind="national",group="고등영수학원",blocks=learning_blocks(p["source"],"national"))
        plan([p])
        self.assertEqual({x["subject"] for x in p["evidence"]},{"english","math"})

    def test_first_attempt_record_is_not_difficulty_starting(self):
        p=sample('<section id="section-01"><p>첫 풀이와 힌트 뒤 재풀이 기록을 비교합니다.</p></section>',"math")
        self.assertNotIn("풀이의 첫 단계 찾기",p["candidates"])
        self.assertNotIn("힌트 없이 다시 풀기",p["candidates"])
        self.assertIn("힌트 전후 풀이 비교",p["candidates"])

    def test_primary_learning_case_beats_weak_subject_keyword(self):
        p=sample('<section id="section-01"><h2>반복 실수를 막는 오답 재풀이 점검</h2><p>오답 재풀이를 통해 오류가 시작된 지점을 확인합니다.</p></section><section><p>필요한 경우 분수 개념도 확인합니다.</p></section>',"math")
        plan([p])
        self.assertEqual(p["evidence"][0]["label"],"오답 재풀이 점검")

    def test_reading_evidence_topics_do_not_repeat(self):
        p=sample('<section id="section-01"><p>지문에서 근거 문장을 찾고 선택지의 근거를 확인한 뒤 재풀이 날짜를 정합니다.</p></section>',"english")
        plan([p])
        self.assertFalse("독해 근거 찾기" in p["suffix"] and "선택지 판단 근거" in p["suffix"])

    def test_site10_manuscript_section_and_intro_are_selected(self):
        source='<main><section class="manuscript-section"><div class="manuscript-intro"><p>문법의 문장 적용을 먼저 확인합니다.</p></div><article class="manuscript-card" id="section-01"><p>어휘를 문맥 안에서 확인합니다.</p></article></section></main>'
        blocks=learning_blocks(source,"subject")
        self.assertEqual(len(blocks),2)
        self.assertEqual([b["weight"] for b in blocks],[8,6])

    def test_national_question_alone_does_not_supply_evidence(self):
        source='<main><div class="answer-item"><p class="q">계산 실수를 줄이는 방법이 궁금한가요?</p><p class="a">수업 이후 복습 주기를 정해 기록합니다.</p></div></main>'
        blocks=learning_blocks(source,"national")
        self.assertFalse(any("계산 실수" in b["text"] for b in blocks))
        self.assertTrue(any("복습 주기" in b["text"] for b in blocks))

    def test_actual_forgotten_unit_case_is_preferred(self):
        p=sample('<div class="manuscript-intro"><p>시험 범위가 넓어질수록 앞 단원을 잊는 학생은 계산 과정을 함께 확인합니다.</p></div>',"math")
        plan([p])
        self.assertIn("앞 단원 기억과 복습",p["suffix"])

    def test_grammar_rule_mention_is_not_comparison(self):
        p=sample('<div class="manuscript-intro"><p>문법의 문장 적용 진단부터 시작합니다. 문법 규칙을 설명한 뒤 처음 보는 문장에서 적용할 수 있는지 확인합니다.</p></div>',"english","elementary")
        self.assertNotIn("문법 개념 비교",p["candidates"])
        plan([p])
        self.assertEqual(p["evidence"][0]["label"],"문법의 문장 적용")

    def test_district_school_card_does_not_outrank_learning_answer(self):
        source='<main><article class="info-card"><p>강동구 학교별 교과서와 수행평가 일정을 확인합니다.</p></article><div class="answer-item"><p class="a">문장 구조를 끊어 읽고 접속사 흐름을 확인합니다.</p></div></main>'
        blocks=learning_blocks(source,"national")
        self.assertFalse(any("수행평가" in b["text"] for b in blocks))
        self.assertTrue(any("문장 구조" in b["text"] for b in blocks))

    def test_high_grade_article_is_read_but_center_facts_are_not(self):
        source='<main><section class="grade-source-facts"><p>서울 지역의 어휘 복습 정보입니다.</p></section><section class="grade-main-article"><div class="manuscript-intro"><p>고1 수학의 ‘오답 기록’ 항목을 검토하고 학생이 남긴 흔적을 확인합니다.</p></div></section></main>'
        blocks=learning_blocks(source,"subject")
        self.assertEqual(len(blocks),1)
        self.assertEqual(blocks[0]["weight"],8)
        self.assertIn("오답 기록",blocks[0]["text"])

    def test_literal_high_grade_items_do_not_invent_application(self):
        p=sample('<div class="manuscript-intro"><p>고2 영어의 ‘문법 적용’ 항목을 검토하며 현재 기록을 나누어 봅니다.</p></div>',"english")
        plan([p])
        self.assertEqual(p["suffix"],"문법 적용 점검")
        self.assertNotIn("문장",p["suffix"])

    def test_student_case_card_receives_case_priority(self):
        source='<main><section class="manuscript-section"><div class="manuscript-grid"><article class="manuscript-card"><h2>이번 페이지에서 보는 학생 유형</h2><p>복습 간격이 길어지는 학생의 어휘 누락을 점검합니다.</p></article></div></section></main>'
        blocks=learning_blocks(source,"subject")
        self.assertEqual(next(b["weight"] for b in blocks if b["tag"]=="p"),6)

    def test_registration_copy_is_not_a_learning_signal(self):
        p=sample('<p>재등록 시점에는 문장 구조 이해에 관한 운영 조건도 확인합니다.</p><p>휴원과 보강 시에는 분수 개념 수업의 일정을 묻습니다.</p>',"general")
        self.assertFalse(p["blocks"])

    def test_elementary_answer_conditions_do_not_imply_equations(self):
        p=sample('<p>문제를 조건별로 끊어 읽고 무엇을 구하는지부터 확인하는 연습이 필요합니다.</p>',"math","elementary")
        plan([p])
        self.assertEqual(p["suffix"],"문제 조건 나누어 읽기")

    def test_quoted_school_grade_is_not_course_availability(self):
        source='<main><section class="page-hero"><p>전국 371개 지역의 고1 수학 학습 정보 허브입니다. 원자료상 고1 수학 가능 학년 기재 354곳과 확인 필요 17곳을 구분해 안내합니다.</p></section></main>'
        text=hub_copy(source,['고1 수학 학습 정보','가능 학년','확인 필요'])
        self.assertIn("확인 필요 17곳",text)

    def test_understood_text_does_not_outrank_stated_difficulty(self):
        p=sample('<div class="manuscript-intro"><p>교과서 본문은 이해하지만 처음 보는 지문에서는 문장 구조를 빠르게 잡지 못하고 어순과 시제 오류를 찾아내기 어려운 학생입니다.</p></div>',"english","middle")
        plan([p])
        self.assertNotIn("교과서 본문 이해",p["suffix"])
        self.assertEqual({e["label"] for e in p["evidence"]},{"문장 구조 이해","어순·시제 오류 점검"})

    def test_concept_application_does_not_repeat_same_evidence(self):
        p=sample('<p>개념을 응용으로 연결하는 중간 단계 문제가 부족했을 수 있습니다.</p>',"math","elementary")
        plan([p])
        self.assertEqual(len(p["evidence"]),1)

    def test_plain_vocabulary_review_does_not_claim_cumulative_review(self):
        p=sample('<p>고1 영어 상담 목록의 ‘어휘 복습’ 항목을 살펴보세요.</p>',"english")
        plan([p])
        self.assertEqual(p["suffix"],"어휘 복습 점검")

    def test_national_administrative_checklist_is_not_primary_case(self):
        source='<main><section class="section"><div class="section-head"><p class="eyebrow">CHECKLIST</p></div><div class="info-card"><p>학교 시험 범위와 수행평가 일정을 확인합니다.</p></div></section><section class="section"><div class="answer-item"><p class="a">풀이 과정을 남기고 오류가 시작된 지점을 짚어 봅니다.</p></div></section></main>'
        blocks=learning_blocks(source,"national")
        self.assertFalse(any("수행평가" in b["text"] for b in blocks))
        self.assertTrue(any("풀이 과정" in b["text"] for b in blocks))

    def test_study_time_proportion_is_not_math_ratio_concept(self):
        p=sample('<p>학습 시간의 비율을 조정해 개념과 응용 연결을 확인합니다.</p>',"math")
        self.assertNotIn("비·비율 이해",p["candidates"])

    def test_parent_consultation_is_not_english_speaking_practice(self):
        p=sample('<p>어떤 순서로 보완하는지를 먼저 묻고 답이 학생 상황과 연결되는지 확인해 보십시오.</p>',"english")
        self.assertNotIn("질문과 대답 연습",p["candidates"])

    def test_high_preparation_record_does_not_invent_error_classification(self):
        p=sample('<div class="manuscript-intro"><p>고1 수학의 ‘오답 기록’ 부분을 구분하며 선택 기준을 확인합니다.</p></div>',"math")
        p["source"]=p["source"].replace("manuscript-article","grade-main-article")
        p["blocks"]=learning_blocks(p["source"],"subject")
        plan([p])
        self.assertEqual(p["suffix"],"오답 기록 점검")
        self.assertEqual(p["evidence"][0]["match"],"‘오답 기록’")

if __name__=="__main__":
    unittest.main()
