"""Tests for followcheck. The HTTP tests run against a real local server."""

from __future__ import annotations

import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from followcheck import (audit, find_anchors, meta_robots, robots_txt_verdict,
                         x_robots_tag)
from followcheck.core import _parse_robots, normalize

TARGET = "https://handsofflinks.com/"

PAGE_DOFOLLOW = f"""<!doctype html><html><head><title>t</title></head><body>
<p>See <a href="{TARGET}">Hands Off Links</a> for the write-up.</p>
</body></html>"""

PAGE_NOFOLLOW = f"""<!doctype html><html><body>
<a href="{TARGET}" rel="nofollow noopener">Hands Off Links</a></body></html>"""

PAGE_NOINDEX = f"""<!doctype html><html><head>
<meta name="robots" content="noindex, follow"></head><body>
<a href="{TARGET}">Hands Off Links</a></body></html>"""

PAGE_RELATIVE = """<!doctype html><html><body>
<a href="/deep/page">relative</a></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):  # keep the test output clean
        pass

    def do_GET(self):  # noqa: N802
        routes = {
            "/dofollow": (200, PAGE_DOFOLLOW, {}),
            "/nofollow": (200, PAGE_NOFOLLOW, {}),
            "/noindex": (200, PAGE_NOINDEX, {}),
            "/xrobots": (200, PAGE_DOFOLLOW, {"X-Robots-Tag": "noindex, nofollow"}),
            "/relative": (200, PAGE_RELATIVE, {}),
            "/missing": (404, "gone", {}),
            "/robots.txt": (200, "User-agent: *\nDisallow: /blocked\nAllow: /\n", {}),
            "/blocked": (200, PAGE_DOFOLLOW, {}),
        }
        status, body, extra = routes.get(self.path, (404, "nope", {}))
        raw = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        for key, value in extra.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)


class ServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()


class TestAnchors(unittest.TestCase):
    def test_finds_bare_anchor(self):
        hits = find_anchors(PAGE_DOFOLLOW, TARGET)
        self.assertEqual(len(hits), 1)
        self.assertIsNone(hits[0].rel)
        self.assertTrue(hits[0].is_followable)
        self.assertEqual(hits[0].text, "Hands Off Links")

    def test_rel_tokens_block_follow(self):
        hits = find_anchors(PAGE_NOFOLLOW, TARGET)
        self.assertEqual(hits[0].rel_tokens, ("nofollow", "noopener"))
        self.assertFalse(hits[0].is_followable)

    def test_raw_anchor_is_preserved_verbatim(self):
        hits = find_anchors(PAGE_NOFOLLOW, TARGET)
        self.assertIn('rel="nofollow noopener"', hits[0].raw)

    def test_relative_href_resolved_against_base(self):
        hits = find_anchors(PAGE_RELATIVE, "https://example.com/deep/page",
                            base_url="https://example.com/blog/post")
        self.assertEqual(len(hits), 1)

    def test_non_matching_target_returns_nothing(self):
        self.assertEqual(find_anchors(PAGE_DOFOLLOW, "https://other.example/"), [])

    def test_unclosed_anchor_still_captured(self):
        html = '<a href="%s">dangling' % TARGET
        self.assertEqual(len(find_anchors(html, TARGET)), 1)


class TestNormalize(unittest.TestCase):
    def test_www_and_trailing_slash_are_ignored(self):
        self.assertEqual(normalize("https://www.a.test/x/"), normalize("http://a.test/x"))

    def test_query_is_significant(self):
        self.assertNotEqual(normalize("https://a.test/x?q=1"), normalize("https://a.test/x"))

    def test_fragment_is_not_significant(self):
        self.assertEqual(normalize("https://a.test/x#f"), normalize("https://a.test/x"))


class TestDirectives(unittest.TestCase):
    def test_meta_robots_read(self):
        self.assertEqual(meta_robots(PAGE_NOINDEX), "noindex, follow")

    def test_meta_robots_absent(self):
        self.assertIsNone(meta_robots(PAGE_DOFOLLOW))

    def test_x_robots_tag_is_case_insensitive(self):
        self.assertEqual(x_robots_tag({"X-Robots-TAG": "noindex"}), "noindex")

    def test_x_robots_tag_absent(self):
        self.assertIsNone(x_robots_tag({"content-type": "text/html"}))


class TestRobotsParser(unittest.TestCase):
    BODY = "User-agent: *\nDisallow: /private\nAllow: /private/ok\n"

    def test_disallow_matches_prefix(self):
        allowed, rule = _parse_robots(self.BODY, "bot", "/private/x")
        self.assertFalse(allowed)
        self.assertEqual(rule, "Disallow: /private")

    def test_longest_match_wins(self):
        allowed, rule = _parse_robots(self.BODY, "bot", "/private/ok/1")
        self.assertTrue(allowed)
        self.assertEqual(rule, "Allow: /private/ok")

    def test_unlisted_path_is_allowed(self):
        allowed, rule = _parse_robots(self.BODY, "bot", "/public")
        self.assertTrue(allowed)
        self.assertIsNone(rule)

    def test_named_agent_group_beats_wildcard(self):
        body = "User-agent: *\nDisallow: /\n\nUser-agent: followcheck\nAllow: /\n"
        allowed, _ = _parse_robots(body, "followcheck/0.1", "/x")
        self.assertTrue(allowed)

    def test_empty_disallow_means_allow_all(self):
        allowed, _ = _parse_robots("User-agent: *\nDisallow:\n", "bot", "/x")
        self.assertTrue(allowed)


class TestAuditLive(ServerCase):
    def test_dofollow_verdict(self):
        report = audit(self.base + "/dofollow", TARGET)
        self.assertEqual(report.verdict, "DOFOLLOW")
        self.assertEqual(report.html_fetch.status, 200)
        self.assertEqual(report.any_fetch.status, 200)
        self.assertFalse(report.content_negotiated)

    def test_nofollow_verdict(self):
        self.assertEqual(audit(self.base + "/nofollow", TARGET).verdict, "NOFOLLOW")

    def test_noindex_verdict(self):
        self.assertEqual(audit(self.base + "/noindex", TARGET).verdict, "NOINDEX-PAGE")

    def test_x_robots_tag_verdict(self):
        report = audit(self.base + "/xrobots", TARGET)
        self.assertEqual(report.verdict, "PAGE-LEVEL-NOFOLLOW")
        self.assertEqual(report.x_robots_tag, "noindex, nofollow")

    def test_anchor_absent_verdict(self):
        self.assertEqual(audit(self.base + "/relative", TARGET).verdict, "ANCHOR-ABSENT")

    def test_non_200_verdict(self):
        self.assertEqual(audit(self.base + "/missing", TARGET).verdict, "NON-200-404")

    def test_robots_disallowed_verdict(self):
        report = audit(self.base + "/blocked", TARGET)
        self.assertEqual(report.verdict, "ROBOTS-DISALLOWED")
        self.assertEqual(report.robots.matched_rule, "Disallow: /blocked")

    def test_robots_lookup_standalone(self):
        rule = robots_txt_verdict(self.base + "/dofollow")
        self.assertEqual(rule.status, 200)
        self.assertTrue(rule.allowed)

    def test_report_serialises(self):
        payload = audit(self.base + "/dofollow", TARGET).as_dict()
        self.assertEqual(payload["verdict"], "DOFOLLOW")
        self.assertEqual(payload["anchors"][0]["rel"], None)


class TestCli(ServerCase):
    def test_exit_code_zero_on_dofollow(self):
        from followcheck.cli import main
        self.assertEqual(main([self.base + "/dofollow", TARGET, "--json"]), 0)

    def test_exit_code_one_on_nofollow(self):
        from followcheck.cli import main
        self.assertEqual(main([self.base + "/nofollow", TARGET]), 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
