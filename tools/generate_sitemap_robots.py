from __future__ import annotations

from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape


SITE = Path(__file__).resolve().parents[1]
DOMAIN = "https://xn--9p4bn5e1r987b.com"
TODAY = "2026-07-25"


def page_url(index_file: Path) -> str:
    rel_dir = index_file.parent.relative_to(SITE).as_posix()
    if rel_dir == ".":
        path = "/"
    else:
        path = f"/{rel_dir}/"
    return DOMAIN + quote(path, safe="/")


def priority_for(path: str) -> str:
    if path == "/":
        return "1.0"
    if path in ("/학습가이드/", "/상담문의/"):
        return "0.9"
    depth = path.strip("/").count("/") + 1
    if path in ("/전국학원/", "/과목별학원/"):
        return "0.9"
    if (path.startswith("/전국학원/") or path.startswith("/과목별학원/")) and depth == 2:
        return "0.85"
    if (path.startswith("/전국학원/") or path.startswith("/과목별학원/")) and depth >= 3:
        return "0.75"
    return "0.8"


def changefreq_for(path: str) -> str:
    if path in ("/", "/전국학원/", "/과목별학원/"):
        return "weekly"
    if path.startswith("/전국학원/") or path.startswith("/과목별학원/"):
        return "monthly"
    return "weekly"


def main() -> None:
    index_files = sorted(
        SITE.glob("**/index.html"),
        key=lambda p: (len(p.parent.relative_to(SITE).parts), p.parent.as_posix()),
    )
    urls: list[tuple[str, str]] = []
    for f in index_files:
        if ".git" in f.parts or ".vercel" in f.parts or "node_modules" in f.parts:
            continue
        rel_dir = f.parent.relative_to(SITE).as_posix()
        raw_path = "/" if rel_dir == "." else f"/{rel_dir}/"
        urls.append((page_url(f), raw_path))

    sitemap_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url, raw_path in urls:
        sitemap_lines.extend(
            [
                "  <url>",
                f"    <loc>{escape(url)}</loc>",
                f"    <lastmod>{TODAY}</lastmod>",
                f"    <changefreq>{changefreq_for(raw_path)}</changefreq>",
                f"    <priority>{priority_for(raw_path)}</priority>",
                "  </url>",
            ]
        )
    sitemap_lines.append("</urlset>")

    (SITE / "sitemap.xml").write_text("\n".join(sitemap_lines) + "\n", encoding="utf-8")
    (SITE / "robots.txt").write_text(
        "\n".join(
            [
                "User-agent: *",
                "Allow: /",
                "",
                f"Sitemap: {DOMAIN}/sitemap.xml",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"generated sitemap_urls={len(urls)}")


if __name__ == "__main__":
    main()
