"""Render the QuirkPedia corpus (backend/corpus/) from scripts/corpus_content.py.

Besides normal articles the corpus deliberately contains crawler edge cases:
  * /corpus/private/…           disallowed by robots.txt
  * /corpus/mirror/hash-tables  exact duplicate content under another URL
  * /corpus/drafts/…            <meta name="robots" content="noindex">
  * a link to a page that does not exist (HTTP 404)

Usage:  python scripts/build_corpus.py
"""
from __future__ import annotations

import html
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpus_content import ARTICLES  # noqa: E402

CORPUS = Path(__file__).resolve().parent.parent / "corpus"
BY_SLUG = {a["slug"]: a for a in ARTICLES}

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title} · QuirkPedia</title>
<meta name="description" content="{description}">
{extra_meta}<link rel="stylesheet" href="{root}style.css">
</head>
<body>
<header><nav><a href="{root}index.html">QuirkPedia home</a> · <a href="{root}index.html#{category_id}">{category}</a></nav></header>
<main>
<article>
<h1>{title}</h1>
<p class="lead">{description}</p>
{sections}
</article>
<section class="related"><h2>Related articles</h2><ul>{related}</ul></section>
</main>
<footer>QuirkPedia is a sample corpus bundled with QuirkSearch. Text written for educational use.</footer>
</body>
</html>
"""

STYLE = """body{font-family:system-ui,sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem;line-height:1.6;color:#1f2330}
a{color:#5b4bdb}header,footer{color:#667;font-size:.9rem}.lead{font-size:1.1rem;color:#445}
"""


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def render_article(a: dict, root: str = "", extra_meta: str = "", extra_links: str = "") -> str:
    sections = "\n".join(
        f"<h2>{esc(h)}</h2>\n" + "\n".join(f"<p>{esc(p)}</p>" for p in paras)
        for h, paras in a["sections"]
    )
    related = "".join(
        f'<li><a href="{root}{r}.html">{esc(BY_SLUG[r]["title"])}</a></li>' for r in a["related"] if r in BY_SLUG
    ) + extra_links
    return PAGE.format(
        title=esc(a["title"]), description=esc(a["description"]), category=esc(a["category"]),
        category_id=a["category"].lower(), sections=sections, related=related, root=root, extra_meta=extra_meta,
    )


def render_index() -> str:
    cats: dict[str, list[dict]] = {}
    for a in ARTICLES:
        cats.setdefault(a["category"], []).append(a)
    blocks = []
    for cat, items in cats.items():
        lis = "".join(f'<li><a href="{a["slug"]}.html">{esc(a["title"])}</a> — {esc(a["description"])}</li>' for a in items)
        blocks.append(f'<h2 id="{cat.lower()}">{esc(cat)}</h2><ul>{lis}</ul>')
    blocks.append(
        '<h2>Behind the scenes</h2><ul>'
        '<li><a href="private/secret-roadmap.html">Private roadmap</a> (blocked by robots.txt)</li>'
        '<li><a href="mirror/hash-tables.html">Hash tables (mirror)</a> (duplicate content)</li>'
        '<li><a href="drafts/unfinished-notes.html">Unfinished notes</a> (noindex)</li>'
        '</ul>'
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>QuirkPedia — a tiny encyclopedia for curious minds</title>
<meta name="description" content="QuirkPedia is a small linked encyclopedia about computer networks, databases, algorithms, information retrieval and a few curiosities.">
<link rel="stylesheet" href="style.css"></head>
<body><main><h1>QuirkPedia</h1>
<p class="lead">A tiny encyclopedia for curious minds: computer networks, databases, algorithms, search engines and a few curiosities.</p>
{''.join(blocks)}</main></body></html>
"""


def main() -> None:
    if CORPUS.exists():
        shutil.rmtree(CORPUS)
    (CORPUS / "private").mkdir(parents=True)
    (CORPUS / "mirror").mkdir()
    (CORPUS / "drafts").mkdir()

    (CORPUS / "style.css").write_text(STYLE, encoding="utf-8")
    (CORPUS / "index.html").write_text(render_index(), encoding="utf-8")
    for a in ARTICLES:
        extra = ""
        if a["slug"] == "web-crawlers":  # a deliberately broken link → HTTP 404 crawl error
            extra = '<li><a href="crawler-faq.html">Crawler FAQ (coming soon)</a></li>'
        (CORPUS / f"{a['slug']}.html").write_text(render_article(a, extra_links=extra), encoding="utf-8")

    # Exact duplicate of hash-tables under a different URL
    (CORPUS / "mirror" / "hash-tables.html").write_text(render_article(BY_SLUG["hash-tables"], root="../"), encoding="utf-8")

    (CORPUS / "drafts" / "unfinished-notes.html").write_text(
        render_article(dict(slug="unfinished", title="Unfinished Notes", category="Drafts",
                            description="Draft notes that should never appear in search results.",
                            sections=[("Draft", ["zebrafish quantum marmalade placeholder text"])], related=["bm25"]),
                       root="../", extra_meta='<meta name="robots" content="noindex">\n'),
        encoding="utf-8")
    (CORPUS / "private" / "secret-roadmap.html").write_text(
        render_article(dict(slug="secret", title="Secret Roadmap", category="Private",
                            description="Internal plans that crawlers must not fetch.",
                            sections=[("Confidential", ["The flamingo protocol launches next spring."])], related=[]),
                       root="../"),
        encoding="utf-8")
    print(f"Wrote {len(ARTICLES)} articles + index + edge cases to {CORPUS}")


if __name__ == "__main__":
    main()
