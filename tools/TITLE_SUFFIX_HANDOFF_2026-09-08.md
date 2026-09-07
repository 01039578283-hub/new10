# 새 홈페이지10: 본문 근거형 타이틀 접미사

작업일: 2026-09-08

## 대상과 보존 범위

- 사이트: 영수학원.com (`https://xn--9p4bn5e1r987b.com`)
- GitHub: `01039578283-hub/new10`, `main` (기존 공개 저장소 유지)
- Vercel: `new10`, `prj_VljVQ1DMR4VlWGhMM7qTkCAigvRk`, scope `1992kjb`
- 수정 전 고정 기준: `b47b6092a0718064fa7c1712451ec699ec0eed27`
- HTML 4,097개 중 전국학원·과목별학원 하위 4,092개: 분류 허브 11개 + 지역 상세 4,081개.
- 과목별학원 8개 분류: 고1/고2/중2/중3 × 수학/영어, 각 371개 지역.
- 전국학원 3개 분류: 와와학습코칭학원/초등수학학원/초등영어학원, 각 371개 지역.
- 홈, 두 최상위 허브, 학습가이드, 상담문의는 수정하지 않는다.
- 제목의 접두사와 H1, 본문, 원고, FAQ, 후기, 이미지, ALT, 숨김 대표 이미지, 목차, CSS/JS, URL, canonical, robots, JSON-LD를 그대로 유지한다.
- HTML title 및 기존 og:title/twitter:title 값만 바꾼다. sitemap.xml의 기존 4,097 URL을 유지한다. 원래 RSS가 없으므로 이번 제목 작업에서 새 RSS를 만들지 않는다.

## 선정 방식

- 위치명으로 임의 배정하지 않고 해당 페이지의 실제 main 학습 문장을 근거로 쓴다.
- 고등 페이지의 grade-main-article에서는 실제 주제 제목과 준비 기록 항목을 우선한다. 단순 기록 항목에서 구체적 수업 제공·성과를 추정하지 않는다.
- 중등 manuscript-section에서는 도입부의 어려움과 학생 유형·핵심 답변을 우선하고, 반복 안내 문장의 비중을 낮춘다.
- 전국학원 상세는 실제 학습 답변과 요약을 사용한다. 질문 문장만으로 답변 내용을 추정하지 않는다.
- 센터·주소·학교 정보, 등록/환불/휴원/보강 조건, 체크리스트, 후기는 제목의 학습 근거에서 제외한다.
- 학년·과목 적합성과 의미 중복을 검사한다. 어휘 복습만으로 누적 복습을, 공부 시간 비율만으로 수학 비·비율 단원을 추정하지 않는다.
- 본문이 같은 주제를 다루면 접미사도 같을 수 있다. 서로 다른 내용을 꾸며내거나 모든 접미사를 억지로 고유하게 만들지 않는다.

## 재현 및 검증

1. `python -m unittest discover -s tools -p test_title_suffixes.py`
2. `python tools/personalize_title_suffixes.py` (수정 없는 계획)
3. `python tools/personalize_title_suffixes.py --write`
4. `python tools/verify_title_release.py` (전수 검사와 고정 Git 기준 비교)
5. `python tools/personalize_title_suffixes.py --check` (재실행 시 변경 0 확인)
6. 배포 후 `python tools/verify_title_release.py --public`

각 실행은 프로젝트 루트에서 수행한다. 원고 생성기를 다시 실행하면 그 생성기의 공통 제목으로 돌아갈 수 있으므로 위 후처리와 검증을 다시 수행한다. 카테고리/페이지 수가 바뀌면 고정 범위와 신규 허브 근거부터 점검한다.

관리 기록:

- `tools/reports/title-suffix-audit.json`: 전체 변경 전후 제목, 접미사, 실제 본문 근거, 제목 외 내용 해시.
- `tools/reports/title-suffix-local-verification.json`: 전수 검사 결과. 고정 원본과 제목 외 HTML이 같은지 확인한다.
- 계획/공개 검사/배포 증빙 JSON은 .gitignore로 분리한다. tools 전체는 기존 .vercelignore에 따라 웹 배포하지 않는다.
- 기존 과목별 상세 목차 2,968개는 변경 전 idempotence 검사에 통과했고 제목 변경 검증에서도 각각 다시 확인한다.

최종 로컬 결과: 회귀 테스트 45개 통과, 대상 4,092페이지 전수 검사 실패 0, 제목 외 내용 변경 0, 재실행 변경 0. 전체 제목 4,092개 고유, 접미사 조합 775개, 제목 길이 24~41자. 사이트맵 4,097 URL 및 기존 목차 2,968페이지 보존 확인. 공개 검사는 11개 분류의 허브/명일동/첫·중간·마지막 상세를 포함한 55페이지와 사이트맵을 검사한다.

## 기존 작업 기록과 배포 주의

- 처음부터 untracked 상태인 루트의 `PROJECT_HANDOFF.md`와 `CHAT_HISTORY_2026-07-03.md`는 사용자 파일이다. 수정·삭제·Git 업로드하지 않는다.
- 위 두 파일의 SHA-256 보존과 untracked 상태를 검사하고 `.vercelignore`에 명시하여 Vercel 업로드에서도 제외한다.
- `.env.local`을 읽거나 Git/Vercel 업로드하지 않는다. 기존 .env 제외 규칙을 보존한다.
- 현재 Vercel 프로젝트에는 Git 자동 배포 연결이 없다. 검증한 main 커밋을 GitHub에 push한 다음 같은 소스를 기존 Vercel 프로젝트에 CLI로 배포한다.
- CLI 배포 전 dry-run 파일 목록에서 HTML 개수, tools/관리 기록/.env/.git 제외를 확인한다. 배포 메타데이터에 `titleSuffixCommit`을 기록하고 READY/production/실도메인 alias 및 실도메인의 제목을 검증한다.
- DNS/도메인/요금제/저장소 공개 범위는 변경하지 않는다.
- 네이버에 표시되는 검색 제목은 검색엔진의 재수집과 제목 선택에 따라 달라질 수 있으며, 이번 배포만으로 노출 순위나 표시 시점을 보장하지 않는다.
