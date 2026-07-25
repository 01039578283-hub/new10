from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
PARENT = "과목별학원"
CATEGORY = "중2수학학원"
DOMAIN = "https://xn--9p4bn5e1r987b.com"
CAT_DIR = SITE / PARENT / CATEGORY

report_lines: list[str] = []


def log(msg: str) -> None:
    report_lines.append(msg)
    print(msg)


IMG_RE = re.compile(r'src="([^"]+)"')
CANON_RE = re.compile(r'<link rel="canonical" href="([^"]+)">')
OGURL_RE = re.compile(r'<meta property="og:url" content="([^"]+)">')
TITLE_RE = re.compile(r"<title>([^<]+)</title>")
DESC_RE = re.compile(r'<meta name="description" content="([^"]+)">')
H1_RE = re.compile(r"<h1[^>]*>([^<]+)</h1>")
HREF_RE = re.compile(r'href="([^"]+)"')
LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
BREADCRUMB_SCREEN_RE = re.compile(r'<p class="breadcrumb">(.*?)</p>')
BREADCRUMB_LAST_SPAN_RE = re.compile(r"<span>([^<]+)</span>\s*$")
FAQ_SUMMARY_RE = re.compile(r"<summary>([^<]+)</summary>")
REVIEW_BODY_RE = re.compile(r'<article class="review-card"><p>([^<]+)</p>')

files = sorted(CAT_DIR.glob("*/index.html"))
log(f"=== {CATEGORY}: {len(files)} local pages ===")

all_titles: list[str] = []
all_descs: list[str] = []
all_faq_sets: list[tuple[str, frozenset]] = []
all_review_sets: list[tuple[str, frozenset]] = []

h1_bad = []
canon_bad = []
og_bad = []
json_bad = []
img_bad = []
link_bad = []
breadcrumb_bad = []

for f in files:
    text = f.read_text(encoding="utf-8")
    slug = f.parent.name
    tag = f"{CATEGORY}/{slug}"

    h1_matches = H1_RE.findall(text)
    if len(h1_matches) != 1:
        h1_bad.append((tag, len(h1_matches)))
    h1_text = h1_matches[0] if h1_matches else None

    expected = f"{DOMAIN}/{PARENT}/{CATEGORY}/{slug}/"
    m = CANON_RE.search(text)
    canonical = m.group(1) if m else None
    if canonical != expected:
        canon_bad.append((tag, canonical))

    m = OGURL_RE.search(text)
    og_url = m.group(1) if m else None
    if og_url != expected:
        og_bad.append((tag, og_url))

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
            data = json.loads(ld_block)
        except Exception as e:  # noqa: BLE001
            json_bad.append((tag, str(e)))
            data = None
        if data and h1_text:
            for node in data.get("@graph", []):
                if node.get("@type") == "BreadcrumbList":
                    last = node["itemListElement"][-1]
                    if last["name"] != h1_text:
                        breadcrumb_bad.append((tag, "jsonld", last["name"], h1_text))

    bc_match = BREADCRUMB_SCREEN_RE.search(text)
    if bc_match and h1_text:
        last_span = BREADCRUMB_LAST_SPAN_RE.search(bc_match.group(1))
        if not last_span or last_span.group(1) != h1_text:
            breadcrumb_bad.append((tag, "screen", last_span.group(1) if last_span else None, h1_text))

    for src in IMG_RE.findall(text):
        if src.startswith("http"):
            continue
        resolved = (f.parent / src).resolve()
        if not resolved.exists():
            img_bad.append((tag, src))

    for href in HREF_RE.findall(text):
        if href.startswith(("http", "tel:", "sms:", "#")):
            continue
        resolved = (f.parent / href).resolve()
        if not resolved.exists():
            link_bad.append((tag, href))

log(f"\ntotal pages checked: {len(all_titles)}")
log(f"H1!=1: {len(h1_bad)} {h1_bad[:10]}")
log(f"canonical bad: {len(canon_bad)} {canon_bad[:10]}")
log(f"og:url bad: {len(og_bad)} {og_bad[:10]}")
log(f"JSON-LD parse errors: {len(json_bad)} {json_bad[:10]}")
log(f"breadcrumb mismatch (screen/jsonld vs H1): {len(breadcrumb_bad)} {breadcrumb_bad[:10]}")
log(f"missing images: {len(img_bad)} {img_bad[:10]}")
log(f"broken internal links: {len(link_bad)} {link_bad[:10]}")

title_dupes = {k: v for k, v in Counter(all_titles).items() if v > 1}
desc_dupes = {k: v for k, v in Counter(all_descs).items() if v > 1}
log(f"duplicate <title>: {len(title_dupes)} {list(title_dupes.items())[:5]}")
log(f"duplicate <meta description>: {len(desc_dupes)} {list(desc_dupes.items())[:5]}")

faq_set_counter = Counter(s for _, s in all_faq_sets)
dup_faq_sets = {s: c for s, c in faq_set_counter.items() if c > 1}
log(f"duplicate FAQ question-sets: {len(dup_faq_sets)}")

review_set_counter = Counter(s for _, s in all_review_sets)
dup_review_sets = {s: c for s, c in review_set_counter.items() if c > 1}
log(f"duplicate review-sets: {len(dup_review_sets)}")

# hub pages
parent_hub = SITE / PARENT / "index.html"
cat_hub = SITE / PARENT / CATEGORY / "index.html"
log(f"\nparent hub exists: {parent_hub.exists()}")
log(f"category hub exists: {cat_hub.exists()}")
for hub_file in [parent_hub, cat_hub]:
    text = hub_file.read_text(encoding="utf-8")
    for ld_block in LD_RE.findall(text):
        try:
            json.loads(ld_block)
        except Exception as e:  # noqa: BLE001
            log(f"hub JSON-LD error in {hub_file}: {e}")
    h1c = len(H1_RE.findall(text))
    log(f"{hub_file.parent.name}/index.html H1 count: {h1c}")

Path(r"C:\Users\얼짱김종범\AppData\Local\Temp\claude\scratch_manuscript\validate_middle2_math.txt").write_text(
    "\n".join(report_lines), encoding="utf-8"
)
print("done")
