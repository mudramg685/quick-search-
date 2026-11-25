"""URL handling: canonicalization, domain checks and hashing.

Why normalize? The same resource is reachable through many spellings:
``HTTP://Example.com:80/a/./b/../c#top`` and ``http://example.com/a/c`` are one page.
If we do not canonicalize, the crawler's *visited set* (a hash set) cannot detect the
duplicate, and the graph traversal wastes requests or even loops.

Steps (RFC 3986 §6 "syntax-based normalization", plus common crawler practice):
  1. resolve relative links against the page's base URL
  2. lowercase scheme and host; IDNA-encode internationalised host names (DNS labels)
  3. drop default ports (80 for http, 443 for https)
  4. remove dot-segments (``/a/./b/../c`` → ``/a/c``) and normalize percent-encoding
  5. sort query parameters and drop tracking parameters (``utm_*``, ``fbclid``…)
  6. drop the fragment – it never reaches the server, so it can't change the response
"""
from __future__ import annotations

import hashlib
import posixpath
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit, urlunsplit

ALLOWED_SCHEMES = {"http", "https"}
DEFAULT_PORTS = {"http": 80, "https": 443}
TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref_src"}
# Characters that may stay unescaped in a path (RFC 3986 pchar + "/").
_PATH_SAFE = "/:@!$&'()*+,;=-._~"

# File extensions that are almost never HTML – skipping them saves bandwidth.
NON_HTML_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff",
    ".pdf", ".zip", ".gz", ".tar", ".rar", ".7z", ".exe", ".dmg", ".msi",
    ".mp3", ".mp4", ".avi", ".mov", ".webm", ".ogg", ".wav",
    ".css", ".js", ".json", ".xml", ".rss", ".woff", ".woff2", ".ttf",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
}


def normalize_url(url: str, base: str | None = None) -> str | None:
    """Return the canonical form of ``url`` or ``None`` if it is not crawlable."""
    if not url:
        return None
    url = url.strip()
    if base:
        url = urljoin(base, url)
    try:
        parts = urlsplit(url)
        port = parts.port  # raises ValueError for garbage like ":abc"
    except ValueError:
        return None

    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        return None  # mailto:, javascript:, ftp:, data: …

    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        return None
    try:
        host = host.encode("idna").decode("ascii")  # bücher.de → xn--bcher-kva.de
    except UnicodeError:
        return None

    netloc = host if port in (None, DEFAULT_PORTS[scheme]) else f"{host}:{port}"

    path = parts.path or "/"
    trailing = path.endswith("/")
    path = posixpath.normpath(path)
    if path.startswith("//"):  # posixpath keeps a leading "//" – collapse it
        path = "/" + path.lstrip("/")
    if trailing and not path.endswith("/"):
        path += "/"
    if path == ".":
        path = "/"
    path = quote(unquote(path), safe=_PATH_SAFE)

    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS
    ]
    query = urlencode(sorted(query_pairs))

    return urlunsplit((scheme, netloc, path, query, ""))


def url_hash(url: str) -> str:
    """Stable 160-bit fingerprint used as the key of the visited hash set / DB unique key."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def domain_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def is_allowed_domain(url: str, allowed_domains: set[str] | None) -> bool:
    """True if the URL's host equals an allowed domain or is a subdomain of one."""
    if not allowed_domains:
        return True
    host = domain_of(url)
    return any(host == d or host.endswith("." + d) for d in allowed_domains)


def looks_like_html(url: str) -> bool:
    path = urlsplit(url).path.lower()
    ext = posixpath.splitext(path)[1]
    return ext not in NON_HTML_EXTENSIONS
