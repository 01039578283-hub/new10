from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
DOMAIN = "https://xn--9p4bn5e1r987b.com"
CATEGORIES = ["와와학습코칭학원", "초등영어학원", "초등수학학원"]

report_lines: list[str] = []


def log(msg: str) -> None:
    report_lines.append(msg)
    print(msg)


IMG_RE = re.compile(r'src="([^"]+)"')
CANON_RE = re.compile(r'<link rel="canonical" href="([^"]+)">')
OGURL_RE = re.compile(r'<meta property="og:url" content="([^"]+)">')
TITLE_RE = re.compile(r"<title>([^<]+)</title>")
DESC_RE = re.compile(r'<meta name="description" content="([^"]+)">')
H1_RE = re.compile(r"<h1[ >]")
HREF_RE = re.compile(r'href="([^"]+)"')
LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
FAQ_SUMMARY_RE = re.compile(r"<summary>([^<]+)</summary>")
REVIEW_BODY_RE = re.compile(r'<article class="review-card"><span class="stars">[^<]*</span><p>([^<]+)</p>')
CROSSLINK_RE = re.compile(r'class="cross-link"')
PARTICLE_BAD_RE = re.compile(r"학원(는|를)[^가-힣]")

all_titles: list[str] = []
all_descs: list[str] = []
all_faq_sets: list[tuple[str, frozenset]] = []
all_review_sets: list[tuple[str, frozenset]] = []

grand_h1_bad = []
grand_canon_bad = []
grand_og_bad = []
grand_json_bad = []
grand_img_bad = []
grand_link_bad = []
grand_particle_bad = []
grand_crosslink_bad = []

for CATEGORY in CATEGORIES:
    CAT_DIR = SITE / "전국학원" / CATEGORY
    files = sorted(CAT_DIR.glob("*/index.html"))
    log(f"=== {CATEGORY}: {len(files)} local pages ===")

    for f in files:
        text = f.read_text(encoding="utf-8")
        slug = f.parent.name
        tag = f"{CATEGORY}/{slug}"

        h1_count = len(H1_RE.findall(text))
        if h1_count != 1:
            grand_h1_bad.append((tag, h1_count))

        m = CANON_RE.search(text)
        canonical = m.group(1) if m else None
        expected = f"{DOMAIN}/전국학원/{CATEGORY}/{slug}/"
        if canonical != expected:
            grand_canon_bad.append((tag, canonical))

        m = OGURL_RE.search(text)
        og_url = m.group(1) if m else None
        if og_url != expected:
            grand_og_bad.append((tag, og_url))

        m = TITLE_RE.search(text)
        all_titles.append(m.group(1) if m else f"MISSING::{tag}")

        m = DESC_RE.search(text)
        all_descs.append(m.group(1) if m else f"MISSING::{tag}")

        faq_qs = frozenset(FAQ_SUMMARY_RE.findall(text))
        all_faq_sets.append((tag, faq_qs))

        review_bodies = frozenset(REVIEW_BODY_RE.findall(text))
        all_review_sets.append((tag, review_bodies))

        for ld_block in LD_RE.findall(text):
            try:
                json.loads(ld_block)
            except Exception as e:  # noqa: BLE001
                grand_json_bad.append((tag, str(e)))

        for src in IMG_RE.findall(text):
            if src.startswith("http"):
                continue
            resolved = (f.parent / src).resolve()
            if not resolved.exists():
                grand_img_bad.append((tag, src))

        for href in HREF_RE.findall(text):
            if href.startswith(("http", "tel:", "sms:", "#")):
                continue
            if href.startswith("/"):
                resolved = (SITE / href.lstrip("/")).resolve()
                if href.endswith("/"):
                    resolved = resolved / "index.html"
            else:
                resolved = (f.parent / href).resolve()
            if not resolved.exists():
                grand_link_bad.append((tag, href))

        if PARTICLE_BAD_RE.search(text):
            grand_particle_bad.append(tag)

        n_cross = len(CROSSLINK_RE.findall(text))
        expected_cross = len(CATEGORIES) - 1
        if n_cross != expected_cross:
            grand_crosslink_bad.append((tag, n_cross, expected_cross))

log(f"\ntotal pages checked: {len(all_titles)}")
log(f"H1!=1: {len(grand_h1_bad)} {grand_h1_bad[:10]}")
log(f"canonical bad: {len(grand_canon_bad)} {grand_canon_bad[:10]}")
log(f"og:url bad: {len(grand_og_bad)} {grand_og_bad[:10]}")
log(f"JSON-LD parse errors: {len(grand_json_bad)} {grand_json_bad[:10]}")
log(f"missing images: {len(grand_img_bad)} {grand_img_bad[:10]}")
log(f"broken links: {len(grand_link_bad)} {grand_link_bad[:10]}")
log(f"particle bad (은/을 misuse): {len(grand_particle_bad)} {grand_particle_bad[:10]}")
log(f"cross-link count mismatch: {len(grand_crosslink_bad)} {grand_crosslink_bad[:10]}")

title_dupes = {k: v for k, v in Counter(all_titles).items() if v > 1}
desc_dupes = {k: v for k, v in Counter(all_descs).items() if v > 1}
log(f"duplicate <title> across ALL categories: {len(title_dupes)} {list(title_dupes.items())[:5]}")
log(f"duplicate <meta description> across ALL categories: {len(desc_dupes)} {list(desc_dupes.items())[:5]}")

faq_set_counter = Counter(s for _, s in all_faq_sets)
dup_faq_sets = {s: c for s, c in faq_set_counter.items() if c > 1}
log(f"duplicate FAQ question-sets (exact same set of 6 questions) across ALL pages: {len(dup_faq_sets)}")

review_set_counter = Counter(s for _, s in all_review_sets)
dup_review_sets = {s: c for s, c in review_set_counter.items() if c > 1}
log(f"duplicate review-sets (exact same set of 6 reviews) across ALL pages: {len(dup_review_sets)}")
if dup_review_sets:
    for s in dup_review_sets:
        matches = [tag for tag, rs in all_review_sets if rs == s]
        log(f"  collision pages: {matches}")

# hub pages check
hub = SITE / "전국학원" / "index.html"
log(f"\nroot hub exists: {hub.exists()}")
for CATEGORY in CATEGORIES:
    cat_hub = SITE / "전국학원" / CATEGORY / "index.html"
    log(f"category hub exists ({CATEGORY}): {cat_hub.exists()}")

for hub_file in [hub] + [SITE / "전국학원" / c / "index.html" for c in CATEGORIES]:
    text = hub_file.read_text(encoding="utf-8")
    for ld_block in LD_RE.findall(text):
        try:
            json.loads(ld_block)
        except Exception as e:  # noqa: BLE001
            log(f"hub JSON-LD error in {hub_file}: {e}")
    h1c = len(H1_RE.findall(text))
    log(f"{hub_file.parent.name}/index.html H1 count: {h1c}")

Path("C:/Users/얼짱김종범/AppData/Local/Temp/validate_h10_all.txt").write_text("\n".join(report_lines), encoding="utf-8")
print("done")
