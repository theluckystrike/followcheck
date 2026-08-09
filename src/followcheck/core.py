"""Core primitives for followcheck. Standard library only, no dependencies."""

from __future__ import annotations

import gzip
import io
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

DEFAULT_UA = "followcheck/0.1 (+https://handsofflinks.com/)"
DEFAULT_TIMEOUT = 20.0

#: The two Accept headers a page must agree on. A page that serves a different
#: body to ``*/*`` than to ``text/html`` is treated as content-negotiated and
#: flagged, because a crawler and a checker can then see different pages.
ACCEPT_HTML = "text/html,application/xhtml+xml"
ACCEPT_ANY = "*/*"

FOLLOW_BLOCKING_TOKENS = ("nofollow", "ugc", "sponsored")


@dataclass(frozen=True)
class Anchor:
    """One ``<a>`` element in the served HTML that points at the target."""

    href: str
    rel: Optional[str]
    text: str
    raw: str

    @property
    def rel_tokens(self) -> Tuple[str, ...]:
        if self.rel is None:
            return ()
        return tuple(t.lower() for t in self.rel.split())

    @property
    def is_followable(self) -> bool:
        return not any(t in FOLLOW_BLOCKING_TOKENS for t in self.rel_tokens)


@dataclass
class Fetch:
    """A single HTTP response, captured without following redirects."""

    url: str
    accept: str
    status: int
    headers: Dict[str, str]
    body: str
    length: int
    location: Optional[str] = None
    error: Optional[str] = None


@dataclass
class RobotsRule:
    """What ``/robots.txt`` says about the page path for one user-agent."""

    robots_url: str
    status: int
    allowed: Optional[bool]
    matched_rule: Optional[str]
    error: Optional[str] = None


@dataclass
class Report:
    """The full evidence bundle for one (page, target) pair."""

    page_url: str
    target_url: str
    html_fetch: Fetch
    any_fetch: Fetch
    anchors: List[Anchor] = field(default_factory=list)
    meta_robots: Optional[str] = None
    x_robots_tag: Optional[str] = None
    robots: Optional[RobotsRule] = None
    content_negotiated: bool = False
    verdict: str = "UNKNOWN"

    def as_dict(self) -> dict:
        return {
            "page_url": self.page_url,
            "target_url": self.target_url,
            "verdict": self.verdict,
            "status_text_html": self.html_fetch.status,
            "status_any": self.any_fetch.status,
            "bytes_text_html": self.html_fetch.length,
            "bytes_any": self.any_fetch.length,
            "content_negotiated": self.content_negotiated,
            "meta_robots": self.meta_robots,
            "x_robots_tag": self.x_robots_tag,
            "robots_txt": None if self.robots is None else {
                "url": self.robots.robots_url,
                "status": self.robots.status,
                "allowed": self.robots.allowed,
                "matched_rule": self.robots.matched_rule,
            },
            "anchors": [
                {"href": a.href, "rel": a.rel, "text": a.text, "raw": a.raw,
                 "followable": a.is_followable}
                for a in self.anchors
            ],
        }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirects are evidence, not noise: capture them instead of chasing them."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def _decode_body(raw: bytes, headers: Dict[str, str]) -> str:
    encoding = headers.get("content-encoding", "").lower()
    if "gzip" in encoding:
        try:
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        except OSError:
            pass
    elif "deflate" in encoding:
        try:
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        except zlib.error:
            pass
    return raw.decode("utf-8", errors="replace")


def fetch(url: str, accept: str = ACCEPT_HTML, user_agent: str = DEFAULT_UA,
          timeout: float = DEFAULT_TIMEOUT) -> Fetch:
    """GET ``url`` once, without following redirects, and capture everything."""
    assert url.startswith(("http://", "https://")), "url must be absolute http(s)"
    assert timeout > 0, "timeout must be positive"

    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(
        url, headers={"User-Agent": user_agent, "Accept": accept,
                      "Accept-Language": "en"})
    try:
        with opener.open(request, timeout=timeout) as response:
            headers = {k.lower(): v for k, v in response.headers.items()}
            raw = response.read()
            return Fetch(url, accept, response.status, headers,
                         _decode_body(raw, headers), len(raw),
                         headers.get("location"))
    except urllib.error.HTTPError as exc:
        headers = {k.lower(): v for k, v in exc.headers.items()}
        raw = exc.read()
        return Fetch(url, accept, exc.code, headers, _decode_body(raw, headers),
                     len(raw), headers.get("location"))
    except Exception as exc:  # network failure is a result, not a crash
        return Fetch(url, accept, 0, {}, "", 0, None, f"{type(exc).__name__}: {exc}")


def normalize(url: str) -> str:
    """Canonical form used to decide whether two URLs are the same target."""
    assert isinstance(url, str), "url must be a string"
    parts = urllib.parse.urlsplit(url.strip())
    host = parts.hostname or ""
    if host.startswith("www."):
        host = host[4:]
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    assert not path.endswith("//"), "path normalisation must be idempotent"
    return f"{host.lower()}{path}" + (f"?{parts.query}" if parts.query else "")


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: List[Anchor] = []
        self._open: Optional[dict] = None
        self._text: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attrd = {k.lower(): (v or "") for k, v in attrs}
        if "href" not in attrd:
            return
        self._open = attrd
        self._text = []
        self._raw = self.get_starttag_text() or ""

    def handle_data(self, data):
        if self._open is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag != "a" or self._open is None:
            return
        rel = self._open.get("rel")
        self.anchors.append(Anchor(self._open["href"], rel,
                                   "".join(self._text).strip(), self._raw))
        self._open = None

    def close(self):  # unclosed <a> at EOF is still an anchor
        super().close()
        if self._open is not None:
            self.anchors.append(Anchor(self._open["href"], self._open.get("rel"),
                                       "".join(self._text).strip(), self._raw))
            self._open = None


def find_anchors(html: str, target: str, base_url: str = "") -> List[Anchor]:
    """Return every ``<a>`` in ``html`` whose href resolves to ``target``."""
    assert isinstance(html, str), "html must be a string"
    assert isinstance(target, str) and target, "target must be a non-empty string"

    parser = _AnchorParser()
    parser.feed(html)
    parser.close()
    wanted = normalize(target)
    hits = []
    for anchor in parser.anchors:
        href = anchor.href
        if base_url and not href.startswith(("http://", "https://")):
            href = urllib.parse.urljoin(base_url, href)
        if normalize(href) == wanted:
            hits.append(anchor)
    return hits


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.value: Optional[str] = None

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        attrd = {k.lower(): (v or "") for k, v in attrs}
        if attrd.get("name", "").lower() in ("robots", "googlebot"):
            self.value = attrd.get("content")


def meta_robots(html: str) -> Optional[str]:
    """Return the ``<meta name="robots">`` content, or ``None`` if absent."""
    assert isinstance(html, str), "html must be a string"
    parser = _MetaParser()
    parser.feed(html)
    parser.close()
    assert parser.value is None or isinstance(parser.value, str), "bad meta value"
    return parser.value


def x_robots_tag(headers: Dict[str, str]) -> Optional[str]:
    """Return the ``X-Robots-Tag`` response header, or ``None``."""
    assert isinstance(headers, dict), "headers must be a dict"
    for key, value in headers.items():
        if key.lower() == "x-robots-tag":
            assert isinstance(value, str), "header value must be a string"
            return value
    return None


def _parse_robots(text: str, user_agent: str, path: str) -> Tuple[Optional[bool], Optional[str]]:
    groups: List[Tuple[List[str], List[Tuple[str, str]]]] = []
    agents: List[str] = []
    rules: List[Tuple[str, str]] = []
    previous_was_agent = False
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field_name, _, value = line.partition(":")
        field_name = field_name.strip().lower()
        value = value.strip()
        if field_name == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value.lower())
            previous_was_agent = True
        elif field_name in ("allow", "disallow"):
            rules.append((field_name, value))
            previous_was_agent = False
    if agents or rules:
        groups.append((agents, rules))
    assert isinstance(previous_was_agent, bool), "parser state must stay boolean"

    chosen: List[Tuple[str, str]] = []
    lowered = user_agent.lower()
    for agent_list, rule_list in groups:
        if any(a != "*" and a in lowered for a in agent_list):
            chosen = rule_list
            break
    else:
        for agent_list, rule_list in groups:
            if "*" in agent_list:
                chosen = rule_list
                break
    if not chosen:
        return True, None

    best: Tuple[int, Optional[bool], Optional[str]] = (-1, None, None)
    for kind, value in chosen:
        if value == "" and kind == "disallow":
            continue
        pattern = value.rstrip("*")
        if path.startswith(pattern):
            if len(pattern) > best[0]:
                best = (len(pattern), kind == "allow", f"{kind.title()}: {value}")
    if best[1] is None:
        return True, None
    return best[1], best[2]


def robots_txt_verdict(page_url: str, user_agent: str = DEFAULT_UA,
                       timeout: float = DEFAULT_TIMEOUT) -> RobotsRule:
    """Fetch the host's ``robots.txt`` and decide whether the page path is allowed."""
    assert page_url.startswith(("http://", "https://")), "page_url must be absolute"
    assert isinstance(user_agent, str), "user_agent must be a string"

    parts = urllib.parse.urlsplit(page_url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    got = fetch(robots_url, ACCEPT_ANY, user_agent, timeout)
    if got.error is not None:
        return RobotsRule(robots_url, got.status, None, None, got.error)
    if got.status == 404:
        return RobotsRule(robots_url, 404, True, None)
    if got.status != 200:
        return RobotsRule(robots_url, got.status, None, None, "non-200 robots.txt")
    path = parts.path or "/"
    allowed, matched = _parse_robots(got.body, user_agent, path)
    return RobotsRule(robots_url, 200, allowed, matched)


def _classify(report: Report) -> str:
    html_fetch = report.html_fetch
    if html_fetch.error is not None:
        return "FETCH-ERROR"
    if html_fetch.status in (403, 503) or "just a moment" in html_fetch.body[:4000].lower():
        return "UNVERIFIED-BOT-WALLED"
    if html_fetch.status != 200:
        return f"NON-200-{html_fetch.status}"
    if not report.anchors:
        return "ANCHOR-ABSENT"
    if not any(a.is_followable for a in report.anchors):
        return "NOFOLLOW"
    directives = " ".join(filter(None, [report.meta_robots, report.x_robots_tag])).lower()
    if "nofollow" in directives:
        return "PAGE-LEVEL-NOFOLLOW"
    if "noindex" in directives:
        return "NOINDEX-PAGE"
    if report.robots is not None and report.robots.allowed is False:
        return "ROBOTS-DISALLOWED"
    return "DOFOLLOW"


def audit(page_url: str, target_url: str, user_agent: str = DEFAULT_UA,
          timeout: float = DEFAULT_TIMEOUT, check_robots: bool = True) -> Report:
    """Fetch ``page_url`` twice and report whether it really follows ``target_url``."""
    assert page_url.startswith(("http://", "https://")), "page_url must be absolute"
    assert target_url.startswith(("http://", "https://")), "target_url must be absolute"

    html_fetch = fetch(page_url, ACCEPT_HTML, user_agent, timeout)
    any_fetch = fetch(page_url, ACCEPT_ANY, user_agent, timeout)
    report = Report(page_url, target_url, html_fetch, any_fetch)
    report.content_negotiated = (
        html_fetch.status == any_fetch.status == 200
        and html_fetch.length != any_fetch.length
    )
    report.anchors = find_anchors(html_fetch.body, target_url, page_url)
    report.meta_robots = meta_robots(html_fetch.body)
    report.x_robots_tag = x_robots_tag(html_fetch.headers)
    if check_robots:
        report.robots = robots_txt_verdict(page_url, user_agent, timeout)
    report.verdict = _classify(report)
    return report
