"""HTML → structured page content.

Extracts the fields the indexer and the UI need:
title, meta description, headings (h1–h3), readable body text and outgoing links.
Boilerplate containers (scripts, styles, navigation, footers…) are removed first so menus
and cookie banners do not pollute the index.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from .url_utils import looks_like_html, normalize_url

_WS = re.compile(r"\s+")
_BOILERPLATE = ["script", "style", "noscript", "template", "svg", "canvas", "iframe",
                "nav", "footer", "header", "aside", "form", "button"]
_BOILERPLATE_ROLES = {"navigation", "banner", "contentinfo", "search"}


def clean_ws(text: str) -> str:
    return _WS.sub(" ", text or "").strip()


@dataclass
class ParsedPage:
    title: str = ""
    description: str = ""
    headings: list[str] = field(default_factory=list)
    body_text: str = ""
    links: list[str] = field(default_factory=list)
    language: str = ""
    noindex: bool = False
    nofollow: bool = False


def parse_html(body: bytes | str, base_url: str, encoding: str | None = None) -> ParsedPage:
    if isinstance(body, bytes):
        # BeautifulSoup's encoding detector checks the BOM and <meta charset> when the
        # HTTP header did not specify a charset.
        soup = BeautifulSoup(body, "lxml", from_encoding=encoding)
    else:
        soup = BeautifulSoup(body, "lxml")
    page = ParsedPage()

    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        page.language = str(html_tag.get("lang")).lower()[:16]

    # --- robots meta directives --------------------------------------------------
    for meta in soup.find_all("meta", attrs={"name": re.compile(r"^robots$", re.I)}):
        directives = str(meta.get("content", "")).lower()
        page.noindex |= "noindex" in directives or "none" in directives
        page.nofollow |= "nofollow" in directives or "none" in directives

    # --- <base href> changes how relative links resolve ------------------------------
    base_tag = soup.find("base", href=True)
    link_base = normalize_url(str(base_tag["href"]), base_url) if base_tag else None
    link_base = link_base or base_url

    # --- title & description -------------------------------------------------------------
    if soup.title and soup.title.string:
        page.title = clean_ws(soup.title.get_text())
    if not page.title:
        og = soup.find("meta", attrs={"property": "og:title"})
        if og and og.get("content"):
            page.title = clean_ws(str(og["content"]))
    for attrs in ({"name": re.compile(r"^description$", re.I)}, {"property": "og:description"}):
        meta = soup.find("meta", attrs=attrs)
        if meta and meta.get("content"):
            page.description = clean_ws(str(meta["content"]))
            break

    # --- links (collected before boilerplate removal so nav links are still followed) -------
    seen: set[str] = set()
    if not page.nofollow:
        for a in soup.find_all("a", href=True):
            rel = {r.lower() for r in (a.get("rel") or [])}
            if "nofollow" in rel:
                continue
            url = normalize_url(str(a["href"]), link_base)
            if url and url not in seen and looks_like_html(url):
                seen.add(url)
                page.links.append(url)

    # --- strip boilerplate, then extract readable content ------------------------------------
    # find_all() returns nested matches too; once an ancestor is decomposed its descendants
    # are dead nodes (attrs=None), so skip anything already destroyed.
    for tag in soup.find_all(_BOILERPLATE):
        if not tag.decomposed:
            tag.decompose()
    for tag in soup.find_all(attrs={"role": True}):
        if not tag.decomposed and tag.attrs is not None and str(tag.get("role")).lower() in _BOILERPLATE_ROLES:
            tag.decompose()

    root = soup.find("main") or soup.find("article") or soup.body or soup
    page.headings = [clean_ws(h.get_text(" ")) for h in root.find_all(["h1", "h2", "h3"])]
    page.headings = [h for h in page.headings if h][:50]
    page.body_text = clean_ws(root.get_text(" "))

    if not page.title:
        page.title = page.headings[0] if page.headings else base_url
    if not page.description:
        first_p = next((clean_ws(p.get_text(" ")) for p in root.find_all("p") if len(p.get_text()) > 40), "")
        page.description = first_p[:300]
    return page
