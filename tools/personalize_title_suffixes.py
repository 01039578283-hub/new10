"""Body-evidenced title suffixes for site10; does not regenerate manuscripts."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import subprocess
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, quote, urljoin
import xml.etree.ElementTree as ET

from title_suffix_rules import RULES, INTENTS, REDUNDANT, HUB_SUFFIXES, HIGH_GRADE_TOPICS

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "https://xn--9p4bn5e1r987b.com"
BASELINE_COMMIT = "b47b6092a0718064fa7c1712451ec699ec0eed27"
EXPECTED_TARGETS = 4092
EXPECTED_HTML = 4097
EXPECTED_SITEMAP = 4097
EXPECTED_NOINDEX = 0
REPORT = ROOT / "tools/reports/title-suffix-audit.json"
TITLE_RE = re.compile(r"(<title\b[^>]*>)(.*?)(</title>)", re.I | re.S)
META_RE = re.compile(r"<meta\b[^>]*>", re.I)
ATTR_RE = re.compile(r"""([:\w-]+)\s*=\s*(["'])(.*?)\2""", re.S)
RULE_PATTERNS = [(label, subject, re.compile(pattern), weight) for label, subject, pattern, weight in RULES]
HIGH_GRADE_PATTERNS = [(label, subject, re.compile('‘'+re.escape(cue)+'’'), 1.1)
                       for cue, label, subject in HIGH_GRADE_TOPICS]
INTENT_PATTERNS = {label: re.compile(pattern) for label, pattern in INTENTS.items()}
SUBJECTS = {label: subject for label, subject, _, _ in RULES}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
OPERATIONAL = re.compile(r"학원개원|휴원|보강|재등록|반편성|등록 시점|개설 시기|학원프로모션|등록 조건|주소 정보|주소와|수업 가능|학교명은|사물함|환불|등록번호|등록 자료|제휴|센터 위치|제공 주소|제공된.{0,8}학교|학교 정보|학교 목록|주소는|주소가|기준 주소|제공된 수업 주소|센터 자료|센터정보|등록 제|상담 신청|전화상담|문자상담|학원혜택|학원이벤트|학원오리엔테이션|교습비|총 납부액|등록 전|운영 중인 반|방문 센터|수업 가능|확인된.{0,20}학교|제공 수업학교|가능 여부|가능 학년")

def clean(value):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())

def attrs(tag):
    return {m[1].lower(): html.unescape(m[3]) for m in ATTR_RE.finditer(tag)}

def title_of(source):
    matches = list(TITLE_RE.finditer(source))
    if len(matches) != 1:
        raise ValueError("Expected exactly one title")
    return html.unescape(matches[0][2])

def replace_titles(source, title):
    escaped = html.escape(title)
    result, count = TITLE_RE.subn(lambda m: m[1] + escaped + m[3], source)
    if count != 1:
        raise ValueError("Expected exactly one title")
    def replace_meta(m):
        values = attrs(m[0])
        if values.get("property", values.get("name")) not in {"og:title", "twitter:title"}:
            return m[0]
        if "content" not in values:
            raise ValueError("Social title has no content")
        return ATTR_RE.sub(lambda a: a[0][:a.start(3)-a.start()] + escaped + a[0][a.end(3)-a.start():]
                           if a[1].lower() == "content" else a[0], m[0])
    return META_RE.sub(replace_meta, result)

def masked(source):
    return replace_titles(source, "__PAGE_TITLE__")

def sha(source):
    return hashlib.sha256(source.encode("utf-8")).hexdigest()

class CopyParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.active = []
        self.blocks = []

    def hidden(self):
        return any(t in {"script", "style", "nav", "footer"} or "hidden" in a
                   or a.get("aria-hidden") == "true"
                   or re.search(r"display\s*:\s*none", a.get("style", "") or "", re.I)
                   for t, a in self.stack)

    def handle_starttag(self, tag, values):
        data = dict(values)
        if tag in {"p", "h2", "h3"} and any(t == "main" for t, _ in self.stack) and not self.hidden():
            self.active.append(dict(tag=tag, own=data, ancestors=list(self.stack), chunks=[], depth=len(self.stack)))
        if tag not in VOID:
            self.stack.append((tag, data))

    def handle_startendtag(self, tag, values):
        if tag not in VOID:
            self.handle_starttag(tag, values)
            self.handle_endtag(tag)

    def handle_data(self, value):
        if not self.hidden():
            for block in self.active:
                block["chunks"].append(value)

    def handle_endtag(self, tag):
        index = next((i for i in range(len(self.stack)-1, -1, -1) if self.stack[i][0] == tag), None)
        if index is None:
            return
        for block in list(self.active):
            if block["depth"] >= index:
                block["text"] = " ".join("".join(block.pop("chunks")).split())
                self.blocks.append(block)
                self.active.remove(block)
        del self.stack[index:]

def classify(path):
    parts = path.parts
    if parts[0] not in {"과목별학원", "전국학원"} or len(parts) not in {3, 4}:
        raise ValueError("Out of scope: " + path.as_posix())
    category = parts[1]
    stage = "elementary" if category.startswith("초") else "middle" if category.startswith("중") else "high" if category.startswith("고") else "all"
    subject = "combined" if "영수" in category else "english" if "영어" in category else "math" if "수학" in category else "general"
    kind = "category" if len(parts) == 3 else "subject" if parts[0] == "과목별학원" else "national"
    return dict(kind=kind, group=category, stage=stage, subject=subject)

def learning_blocks(source, kind):
    parser = CopyParser()
    parser.feed(source)
    result = []
    card_headings = {}
    section_roles = {}
    for block in parser.blocks:
        if "eyebrow" in (block.get("own", {}).get("class") or "").split():
            section = next((a for t, a in reversed(block["ancestors"]) if t == "section"), None)
            if section is not None:
                section_roles[id(section)] = block["text"]
        if block["tag"] == "h2":
            for _, ancestor in block["ancestors"]:
                if "manuscript-card" in (ancestor.get("class") or "").split():
                    card_headings[id(ancestor)] = block["text"]
    for block in parser.blocks:
        text = block["text"]
        if len(text) < 12 or "q" in (block.get("own", {}).get("class") or "").split():
            continue
        classes = set(" ".join(a.get("class", "") or "" for _, a in block["ancestors"]).split())
        ids = {a.get("id") for _, a in block["ancestors"]}
        if classes & {"center-info", "center-card", "school-list", "review-card", "center-facts-panel", "academy-side-card", "school-card", "subject-info-card", "grade-source-facts", "grade-faq-list"}:
            continue
        if kind == "national" and "info-card" in classes and "학교별" in text:
            # District-dependent school-calendar cards are not the student's
            # learning case and must not outrank the page's actual answers.
            continue
        if kind == "national" and any(section_roles.get(id(a)) in {
                "CHECKLIST", "CENTER INFO", "LOCAL & STUDENT FIT", "TUITION", "PARENT REVIEW"}
                for _, a in block["ancestors"]):
            continue
        weight = 0
        if kind == "subject":
            if classes & {"manuscript-section", "manuscript-article", "grade-main-article"}:
                if "manuscript-intro" in classes:
                    weight = 8
                elif ("grade-main-article" in classes and "section-head" in classes and block["tag"] == "h2"):
                    # This template puts its actual leading preparation item
                    # in the article heading. It outranks incidental later cues.
                    weight = 12
                elif "section-01" in ids:
                    weight = 6 if block["tag"] == "p" else 7
                elif any(re.search(r"학생 유형|적합도 확인|먼저 확인할 핵심 답변",
                                   card_headings.get(id(ancestor), ""))
                         for _, ancestor in block["ancestors"]):
                    weight = 6 if block["tag"] == "p" else 2
                else:
                    weight = 2.8 if block["tag"] == "p" else 1.8
            elif ("answer-section" in classes or "subject-quick-answer" in classes) and block["tag"] == "p":
                weight = 6
            elif "page-hero" in classes and block["tag"] == "p":
                weight = 1.5
        elif kind == "national":
            if ("answer-item" in classes or "answer-box" in classes):
                weight = 5 if block["tag"] == "p" else 3
            elif ("info-card" in classes or "summary-card" in classes):
                weight = 4 if block["tag"] == "p" else 2
            elif "page-hero" in classes and block["tag"] == "p":
                weight = 1.5
        if weight:
            # Keep actual learning sentences, not adjacent center/school facts,
            # operational benefits, consultation forms or testimonial claims.
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                if len(sentence) >= 12 and not OPERATIONAL.search(sentence):
                    result.append(dict(text=sentence, weight=weight, tag=block["tag"]))
    return result

def eligible(page, label, subject):
    target = page["subject"]
    if target == "math" and (subject in {"english", "korean", "science"} or "영어" in label or "두 과목" in label):
        return False
    if target == "english" and (subject in {"math", "korean", "science"} or "수학" in label or "두 과목" in label):
        return False
    if page["stage"] in {"elementary", "middle"} and re.search(r"수능|모의고사", label):
        return False
    if page["stage"] == "elementary" and re.search(r"내신|수행평가|학교 시험|시험 시간|방정식|함수|수능", label):
        return False
    return True

def excerpt(text, match):
    start = max(0, match.start() - 38)
    end = min(len(text), match.end() + 75)
    return text[start:end]

def candidates(page):
    result = {}
    preparation_guide = "grade-main-article" in page["source"]
    for label, subject, pattern, specificity in (HIGH_GRADE_PATTERNS if preparation_guide else RULE_PATTERNS):
        if not eligible(page, label, subject):
            continue
        matches = []
        for block in page["blocks"]:
            for regex, intent in ((pattern, False), (None if preparation_guide else INTENT_PATTERNS.get(label), True)):
                if regex is None or (intent and block["weight"] < 4):
                    continue
                found = regex.search(block["text"])
                if found:
                    context = block["text"][max(0, found.start()-6):found.end()]
                    if label in {"개념의 문제 적용", "정의 이해와 적용"} and "문법" in context:
                        continue
                    matches.append(dict(label=label, subject=subject, match=found[0],
                                        excerpt=excerpt(block["text"], found),
                                        score=block["weight"] * specificity + (3 if intent else 0),
                                        blockWeight=block["weight"], intent=intent))
        if matches:
            best = max(matches, key=lambda m: m["score"])
            best["score"] += min(1, .12 * (len(matches) - 1))
            result[label] = best
    return result

def compatible(first, second):
    if first["label"] == second["label"]:
        return False
    return not any(first["label"] in group and second["label"] in group for group in REDUNDANT)

def hub_copy(source, terms):
    parser = CopyParser()
    parser.feed(source)
    # Keep one real paragraph. Joining disjoint paragraphs would silently
    # skip the visible H1 and produce a non-contiguous evidence excerpt.
    return next((b["text"] for b in parser.blocks
                 if all(term in b["text"] for term in terms) and any(
                     "page-hero" in (a.get("class", "") or "").split()
                     for _, a in b["ancestors"])), "")

def resolved_page_url(canonical, rel):
    expected = DOMAIN + quote("/" + rel.parent.as_posix() + "/", safe="/")
    if unquote(urljoin(DOMAIN + "/", canonical)) != unquote(expected):
        raise ValueError("Canonical does not match its file route: " + rel.as_posix())
    return expected

def read_page(path):
    source = path.read_bytes().decode("utf-8")
    rel = path.relative_to(ROOT)
    page = dict(path=path, rel=rel.as_posix(), source=source, before=title_of(source), **classify(rel))
    if "|" not in page["before"]:
        raise ValueError("Existing suffix separator missing: " + page["rel"])
    page["prefix"] = page["before"].split("|", 1)[0].rstrip()
    canonicals = [attrs(m[0])["href"] for m in re.finditer(r"<link\b[^>]*>", source, re.I)
                  if attrs(m[0]).get("rel") == "canonical"]
    if len(canonicals) != 1:
        raise ValueError("Wrong canonical: " + page["rel"])
    # Preserve canonical bytes; resolve only the URL used for HTTP checking.
    page["canonical"] = canonicals[0]
    page["url"] = resolved_page_url(canonicals[0], rel)
    robots = [attrs(m[0]).get("content", "") for m in META_RE.finditer(source) if attrs(m[0]).get("name") == "robots"]
    if len(robots) != 1:
        raise ValueError("Expected one robots meta: " + page["rel"])
    page["indexable"] = "noindex" not in robots[0].lower()
    if page["kind"] == "category":
        suffix, terms = HUB_SUFFIXES[page["group"]]
        text = hub_copy(source, terms)
        if not text or not all(term in text for term in terms):
            raise ValueError("Hub lacks its stated evidence: " + page["rel"])
        page["suffix"] = suffix
        page["evidence"] = [dict(label=suffix, match=term, excerpt=excerpt(text, re.search(re.escape(term), text)), subject="") for term in terms]
    else:
        page["blocks"] = learning_blocks(source, page["kind"])
        if not page["blocks"]:
            raise ValueError("No eligible learning copy: " + page["rel"])
    return page

def plan(pages):
    groups = defaultdict(list)
    for page in pages:
        if page["kind"] != "category":
            groups[page["group"]].append(page)
    for members in groups.values():
        # Repeated introductions should not outrank a page's actual student
        # situation. Normalize only known title/locality strings for counting;
        # never alter the source copy or randomize topic selection.
        def sentence_key(page, text):
            locality = page["rel"].split("/")[2]
            for value in sorted({page["prefix"], locality}, key=len, reverse=True):
                text = text.replace(value, "{page}")
            return text
        sentence_counts = Counter(key for page in members for key in
                                  {sentence_key(page, b["text"]) for b in page["blocks"]})
        for page in members:
            for block in page["blocks"]:
                block["weight"] = block.setdefault("originalWeight", block["weight"])
                fraction = sentence_counts[sentence_key(page, block["text"])] / len(members)
                if len(members) >= 20 and fraction >= .1:
                    block["weight"] *= .5 if fraction >= .25 else .7
            page["candidates"] = candidates(page)
            if not page["candidates"]:
                raise ValueError("No supported learning topic: " + page["rel"])
        frequency = Counter(label for p in members for label in p["candidates"])
        for page in members:
            options = []
            for label, original in page["candidates"].items():
                item = original.copy()
                item["score"] *= 1 + min(.45, .18 * math.log(len(members) / frequency[label]))
                options.append(item)
            options.sort(key=lambda m: (-m["score"], m["label"]))
            # The prefix already states the subject. A page about repeated
            # mistakes or homework should not lose its primary case merely
            # because a weaker paragraph also mentions a subject keyword.
            first = options[0]
            seconds = [m for m in options if compatible(first, m)]
            # Reflect both lead difficulties when a combined manuscript has them.
            if page["kind"] == "subject" and page["subject"] == "combined" and page["group"] != "국영수학원" and first["subject"] in {"math", "english"}:
                opposite = "math" if first["subject"] == "english" else "english"
                specific = [m for m in seconds if m["subject"] == opposite and m["blockWeight"] >= 5]
                if specific:
                    seconds = specific
            chosen = [first] + seconds[:1]
            if page["kind"] in {"subject", "national"} and page["subject"] == "combined" and page["group"] != "국영수학원":
                lead_english = next((m for m in options if m["subject"] == "english" and m["blockWeight"] >= (2 if page["kind"] == "national" else 5)), None)
                lead_math = next((m for m in options if m["subject"] == "math" and m["blockWeight"] >= (2 if page["kind"] == "national" else 5)), None)
                if lead_english and lead_math:
                    chosen = [lead_english, lead_math]
            page["suffix"] = "·".join(item["label"] for item in chosen)
            page["evidence"] = [{k:v for k,v in m.items() if k not in {"score", "blockWeight", "intent"}} for m in chosen]
    for page in pages:
        page["after"] = page["prefix"] + " | " + page["suffix"]
        if not 12 <= len(page["after"]) <= 85:
            raise ValueError("Title length: " + page["rel"])
        page["updated"] = replace_titles(page["source"], page["after"])
        if masked(page["source"]) != masked(page["updated"]):
            raise ValueError("Non-title mutation: " + page["rel"])
    if len({p["after"] for p in pages}) != len(pages):
        raise ValueError("Duplicate complete titles")

def inventory():
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    all_html = [n for n in names if n.endswith(".html")]
    if len(all_html) != EXPECTED_HTML:
        raise ValueError("HTML inventory changed")
    targets = [ROOT/n for n in all_html if n.startswith(("전국학원/", "과목별학원/"))
               and n not in {"전국학원/index.html", "과목별학원/index.html"}]
    if len(targets) != EXPECTED_TARGETS:
        raise ValueError("Target count changed")
    target_set = set(targets)
    return sorted(targets), [n for n in all_html if ROOT/n not in target_set]

def update_rss(pages, source):
    by_url = {unquote(p["url"]): p["after"] for p in pages}
    changed = 0
    def item(m):
        nonlocal changed
        link = re.search(r"<link>(.*?)</link>", m[0], re.S)
        key = unquote(html.unescape(link[1])) if link else ""
        if key not in by_url:
            return m[0]
        updated = re.sub(r"(<title>).*?(</title>)", lambda n:n[1]+html.escape(by_url[key])+n[2], m[0], count=1, flags=re.S)
        changed += updated != m[0]
        return updated
    return re.sub(r"<item>.*?</item>", item, source, flags=re.S), changed

def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    paths, protected = inventory()
    def checked_read(path):
        try:
            return read_page(path), None
        except Exception as exc:
            return None, str(exc)
    with ThreadPoolExecutor(max_workers=8) as pool:
        loaded = list(pool.map(checked_read, paths))
    errors = [error for _, error in loaded if error]
    if errors:
        print(json.dumps(dict(failures=len(errors), examples=errors[:20]), ensure_ascii=False))
        raise SystemExit(1)
    pages = [page for page, _ in loaded]
    plan(pages)
    old_entries = {}
    if REPORT.exists():
        old_entries = {x["path"]:x for x in json.loads(REPORT.read_text(encoding="utf-8"))["entries"]}
    rss_exists = (ROOT/"rss.xml").is_file()
    rss = (ROOT/"rss.xml").read_bytes().decode("utf-8") if rss_exists else ""
    rss_new, rss_changes = update_rss(pages, rss)
    entries = []
    for page in pages:
        before = page["before"]
        old = old_entries.get(page["rel"])
        if old and old["unchangedContentSha256"] == sha(masked(page["source"])):
            before = old["before"]
        entries.append(dict(path=page["rel"],url=page["url"],group=page["group"],kind=page["kind"],stage=page["stage"],subject=page["subject"],
                            before=before,after=page["after"],suffix=page["suffix"],evidence=page["evidence"],indexable=page["indexable"],canonical=page["canonical"],
                            unchangedContentSha256=sha(masked(page["source"])),
                            unchangedNormalizedContentSha256=sha(masked(page["source"]).replace("\r\n","\n"))))
    changed = [p for p in pages if p["source"] != p["updated"]]
    report = dict(site=DOMAIN,baselineCommit=BASELINE_COMMIT,pages=len(pages),changedThisRun=len(changed),
                  changedFromOriginal=sum(x["before"]!=x["after"] for x in entries),rssTitlesChanged=rss_changes,
                  sitemapCount=len(ET.parse(ROOT/"sitemap.xml").findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url")),
                  rssExists=rss_exists,rssCount=len(ET.fromstring(rss).findall(".//item")) if rss_exists else 0,
                  uniqueTitles=len({x["after"] for x in entries}),uniqueSuffixes=len({x["suffix"] for x in entries}),
                  titleLength=dict(min=min(len(x["after"]) for x in entries),max=max(len(x["after"]) for x in entries)),
                  protectedHtml=protected,nonTitleChanges=0,noindexCount=sum(not p["indexable"] for p in pages),entries=entries)
    if report["sitemapCount"] != EXPECTED_SITEMAP or report["noindexCount"] != EXPECTED_NOINDEX:
        raise ValueError("Existing indexing policy changed")
    output = REPORT if args.write else REPORT.with_name("title-suffix-plan.json")
    if not args.check:
        output.parent.mkdir(parents=True,exist_ok=True)
        if args.write:
            for page in changed:
                page["path"].write_bytes(page["updated"].encode("utf-8"))
            if rss_new != rss:
                (ROOT/"rss.xml").write_bytes(rss_new.encode("utf-8"))
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({k:v for k,v in report.items() if k not in {"entries","protectedHtml"}},ensure_ascii=False))
    for group in sorted({p["group"] for p in pages}):
        members=[p for p in pages if p["group"]==group]
        print(json.dumps(dict(group=group,pages=len(members),uniqueSuffixes=len({p["suffix"] for p in members}),
                              mostRepeated=Counter(p["suffix"] for p in members).most_common(3)),ensure_ascii=False))
    for p in pages:
        if "명일동" in p["rel"]:
            print(p["after"])
    if args.check and (changed or rss_changes):
        raise SystemExit("FAIL: title regeneration is not idempotent")
    print("TITLE_SUFFIX_"+("WRITE" if args.write else "CHECK" if args.check else "PLAN")+"_PASS")

if __name__ == "__main__":
    main()
