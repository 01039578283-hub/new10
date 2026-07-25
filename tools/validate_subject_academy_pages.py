from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
PARENT = "과목별학원"
CATEGORIES = ["중2수학학원", "중2영어학원"]
DOMAIN = "https://xn--9p4bn5e1r987b.com"

report_lines: list[str] = []


def log(msg: str) -> None:
    report_lines.append(msg)
    print(msg)


IMG_RE = re.compile(r'src="([^"]+)"')
CANON_RE = re.compile(r'<link rel="canonical" href="([^"]+)">')
OGURL_RE = re.compile(r'<meta property="og:url" content="([^"]+)">')
OGTITLE_RE = re.compile(r'<meta property="og:title" content="([^"]+)">')
TITLE_RE = re.compile(r"<title>([^<]+)</title>")
DESC_RE = re.compile(r'<meta name="description" content="([^"]+)">')
H1_RE = re.compile(r"<h1[^>]*>([^<]+)</h1>")
HREF_RE = re.compile(r'href="([^"]+)"')
LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
BREADCRUMB_SCREEN_RE = re.compile(r'<p class="breadcrumb">(.*?)</p>')
BREADCRUMB_LAST_SPAN_RE = re.compile(r"<span>([^<]+)</span>\s*$")
FAQ_SUMMARY_RE = re.compile(r"<summary>([^<]+)</summary>")
REVIEW_BODY_RE = re.compile(r'<article class="review-card"><p>([^<]+)</p>')
REQUIRED_LD_TYPES = {
    "WebPage", "ImageObject", "BreadcrumbList", "Article", "FAQPage", "Service",
}

all_titles_global: list[str] = []
all_descs_global: list[str] = []

grand_h1_bad = []
grand_canon_bad = []
grand_og_bad = []
grand_ogtitle_bad = []
grand_json_bad = []
grand_breadcrumb_bad = []
grand_img_bad = []
grand_link_bad = []
grand_ldtype_bad = []
grand_offer_missing = []
grand_dup_word = []

DUP_WORD_TEXT_NODE_RE = re.compile(r">([^<>]{2,})<")
DUP_WORD_RE = re.compile(r"(?<!\S)(\S{2,})\s+\1(?!\S)")

for CATEGORY in CATEGORIES:
    CAT_DIR = SITE / PARENT / CATEGORY
    files = sorted(CAT_DIR.glob("*/index.html"))
    log(f"=== {CATEGORY}: {len(files)} local pages ===")

    all_titles: list[str] = []
    all_descs: list[str] = []
    all_faq_sets: list[tuple[str, frozenset]] = []
    all_review_sets: list[tuple[str, frozenset]] = []

    for f in files:
        text = f.read_text(encoding="utf-8")
        slug = f.parent.name
        tag = f"{CATEGORY}/{slug}"

        h1_matches = H1_RE.findall(text)
        if len(h1_matches) != 1:
            grand_h1_bad.append((tag, len(h1_matches)))
        h1_text = h1_matches[0] if h1_matches else None

        expected = f"{DOMAIN}/{PARENT}/{CATEGORY}/{slug}/"
        m = CANON_RE.search(text)
        canonical = m.group(1) if m else None
        if canonical != expected:
            grand_canon_bad.append((tag, canonical))

        m = OGURL_RE.search(text)
        og_url = m.group(1) if m else None
        if og_url != expected:
            grand_og_bad.append((tag, og_url))

        m = TITLE_RE.search(text)
        title_text = m.group(1) if m else None
        all_titles.append(title_text or f"MISSING::{tag}")
        all_titles_global.append(title_text or f"MISSING::{tag}")
        if title_text and h1_text and not title_text.startswith(h1_text):
            grand_ogtitle_bad.append((tag, "title-vs-h1", title_text, h1_text))

        m = OGTITLE_RE.search(text)
        og_title = m.group(1) if m else None
        if og_title != title_text:
            grand_ogtitle_bad.append((tag, "og:title-vs-title", og_title, title_text))

        m = DESC_RE.search(text)
        desc_text = m.group(1) if m else None
        all_descs.append(desc_text or f"MISSING::{tag}")
        all_descs_global.append(desc_text or f"MISSING::{tag}")

        faq_qs = frozenset(FAQ_SUMMARY_RE.findall(text))
        all_faq_sets.append((tag, faq_qs))
        review_bodies = frozenset(REVIEW_BODY_RE.findall(text))
        all_review_sets.append((tag, review_bodies))

        ld_types_found = set()
        for ld_block in LD_RE.findall(text):
            try:
                data = json.loads(ld_block)
            except Exception as e:  # noqa: BLE001
                grand_json_bad.append((tag, str(e)))
                data = None
            if data:
                for node in data.get("@graph", []):
                    t = node.get("@type")
                    if isinstance(t, list):
                        ld_types_found.update(t)
                    else:
                        ld_types_found.add(t)
                    if t == "BreadcrumbList" and h1_text:
                        last = node["itemListElement"][-1]
                        if last["name"] != h1_text:
                            grand_breadcrumb_bad.append((tag, "jsonld", last["name"], h1_text))
                    if t == "Service" and "offers" not in node:
                        grand_offer_missing.append(tag)
        missing_types = REQUIRED_LD_TYPES - ld_types_found
        has_org = "EducationalOrganization" in ld_types_found or "LocalBusiness" in ld_types_found
        if missing_types or not has_org:
            grand_ldtype_bad.append((tag, sorted(missing_types) + ([] if has_org else ["EducationalOrganization/LocalBusiness"])))

        bc_match = BREADCRUMB_SCREEN_RE.search(text)
        if bc_match and h1_text:
            last_span = BREADCRUMB_LAST_SPAN_RE.search(bc_match.group(1))
            if not last_span or last_span.group(1) != h1_text:
                grand_breadcrumb_bad.append((tag, "screen", last_span.group(1) if last_span else None, h1_text))

        for src in IMG_RE.findall(text):
            if src.startswith("http"):
                continue
            resolved = (f.parent / src).resolve()
            if not resolved.exists():
                grand_img_bad.append((tag, src))

        for href in HREF_RE.findall(text):
            if href.startswith(("http", "tel:", "sms:", "#")):
                continue
            resolved = (f.parent / href).resolve()
            if not resolved.exists():
                grand_link_bad.append((tag, href))

        body_match = re.search(r"<main>(.*?)</main>", text, re.S)
        if body_match:
            for node in DUP_WORD_TEXT_NODE_RE.findall(body_match.group(1)):
                for dm in DUP_WORD_RE.finditer(node):
                    grand_dup_word.append((tag, dm.group(0)))

    title_dupes = {k: v for k, v in Counter(all_titles).items() if v > 1}
    desc_dupes = {k: v for k, v in Counter(all_descs).items() if v > 1}
    faq_set_counter = Counter(s for _, s in all_faq_sets)
    dup_faq_sets = {s: c for s, c in faq_set_counter.items() if c > 1}
    review_set_counter = Counter(s for _, s in all_review_sets)
    dup_review_sets = {s: c for s, c in review_set_counter.items() if c > 1}

    log(f"  duplicate <title> within category: {len(title_dupes)}")
    log(f"  duplicate <meta description> within category: {len(desc_dupes)}")
    log(f"  duplicate FAQ question-sets within category: {len(dup_faq_sets)}")
    log(f"  duplicate review-sets within category: {len(dup_review_sets)}")

    parent_hub = SITE / PARENT / "index.html"
    cat_hub = SITE / PARENT / CATEGORY / "index.html"
    log(f"  category hub exists: {cat_hub.exists()}")
    for hub_file in [cat_hub]:
        text = hub_file.read_text(encoding="utf-8")
        for ld_block in LD_RE.findall(text):
            try:
                json.loads(ld_block)
            except Exception as e:  # noqa: BLE001
                log(f"  hub JSON-LD error in {hub_file}: {e}")
        h1c = len(H1_RE.findall(text))
        log(f"  {hub_file.parent.name}/index.html H1 count: {h1c}")

log(f"\ntotal pages checked (both categories): {len(all_titles_global)}")
log(f"H1!=1: {len(grand_h1_bad)} {grand_h1_bad[:10]}")
log(f"canonical bad: {len(grand_canon_bad)} {grand_canon_bad[:10]}")
log(f"og:url bad: {len(grand_og_bad)} {grand_og_bad[:10]}")
log(f"title/og:title mismatch: {len(grand_ogtitle_bad)} {grand_ogtitle_bad[:10]}")
log(f"JSON-LD parse errors: {len(grand_json_bad)} {grand_json_bad[:10]}")
log(f"breadcrumb mismatch (screen/jsonld vs H1): {len(grand_breadcrumb_bad)} {grand_breadcrumb_bad[:10]}")
log(f"missing required JSON-LD @types (EducationalOrganization/LocalBusiness/Article/Service/FAQPage/BreadcrumbList/WebPage/ImageObject): {len(grand_ldtype_bad)} {grand_ldtype_bad[:10]}")
log(f"Service without offers: {len(grand_offer_missing)} {grand_offer_missing[:10]}")
log(f"missing images: {len(grand_img_bad)} {grand_img_bad[:10]}")
log(f"broken internal links: {len(grand_link_bad)} {grand_link_bad[:10]}")
log(f"duplicate adjacent word (typo) hits: {len(grand_dup_word)} {grand_dup_word[:10]}")

title_dupes_all = {k: v for k, v in Counter(all_titles_global).items() if v > 1}
desc_dupes_all = {k: v for k, v in Counter(all_descs_global).items() if v > 1}
log(f"duplicate <title> ACROSS both categories: {len(title_dupes_all)} {list(title_dupes_all.items())[:5]}")
log(f"duplicate <meta description> ACROSS both categories: {len(desc_dupes_all)} {list(desc_dupes_all.items())[:5]}")

parent_hub = SITE / PARENT / "index.html"
log(f"\nparent hub exists: {parent_hub.exists()}")
text = parent_hub.read_text(encoding="utf-8")
for ld_block in LD_RE.findall(text):
    try:
        json.loads(ld_block)
    except Exception as e:  # noqa: BLE001
        log(f"parent hub JSON-LD error: {e}")
log(f"parent hub H1 count: {len(H1_RE.findall(text))}")

Path(r"C:\Users\얼짱김종범\AppData\Local\Temp\claude\scratch_manuscript\validate_subject_academy.txt").write_text(
    "\n".join(report_lines), encoding="utf-8"
)
print("done")
