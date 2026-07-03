import sys
sys.path.insert(0, ".")
import generate_wawa_academy_pages as wa
import generate_elementary_english_pages as ee


def flat(bank):
    out = set()
    for item in bank:
        if isinstance(item, tuple):
            out.update(str(x) for x in item)
        elif isinstance(item, dict):
            for v in item.values():
                if isinstance(v, tuple):
                    out.update(str(x) for x in v)
                else:
                    out.add(str(v))
        else:
            out.add(str(item))
    return out


pairs = [
    ("FAQ_OPENER_BANK", wa.FAQ_OPENER_BANK, ee.FAQ_OPENER_BANK),
    ("FAQ_BANK", wa.FAQ_BANK, ee.FAQ_BANK),
    ("ANSWER_BANK", wa.ANSWER_BANK, ee.ANSWER_BANK),
    ("CHECKLIST_BANK", wa.CHECKLIST_BANK, ee.CHECKLIST_BANK),
    ("REVIEW_BANK", wa.REVIEW_BANK, ee.REVIEW_BANK),
    ("COMPARE_ROWS", wa.COMPARE_ROWS, ee.COMPARE_ROWS),
    ("SUMMARY_INTROS", wa.SUMMARY_INTROS, ee.SUMMARY_INTROS),
    ("MANUSCRIPT_INTRO", wa.MANUSCRIPT_INTRO, ee.MANUSCRIPT_INTRO),
    ("MANUSCRIPT_OUTRO", wa.MANUSCRIPT_OUTRO, ee.MANUSCRIPT_OUTRO),
]

total_overlap = 0
for name, a, b in pairs:
    sa, sb = flat(a), flat(b)
    inter = sa & sb
    total_overlap += len(inter)
    print(f"{name}: overlap={len(inter)}", list(inter)[:5] if inter else "")

print("TOTAL_OVERLAP:", total_overlap)
