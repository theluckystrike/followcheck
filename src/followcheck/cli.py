"""Command line entry point: ``followcheck PAGE TARGET``."""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .core import DEFAULT_TIMEOUT, DEFAULT_UA, audit

FAILING_VERDICTS = ("ANCHOR-ABSENT", "NOFOLLOW", "PAGE-LEVEL-NOFOLLOW",
                    "NOINDEX-PAGE", "ROBOTS-DISALLOWED", "FETCH-ERROR",
                    "UNVERIFIED-BOT-WALLED")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="followcheck",
        description="Decide whether a page really carries a followable link to a target.")
    parser.add_argument("page", help="URL of the page that should carry the link")
    parser.add_argument("target", help="URL the link should point at")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit the whole evidence bundle as JSON")
    parser.add_argument("--user-agent", default=DEFAULT_UA)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--no-robots", action="store_true",
                        help="skip the robots.txt lookup")
    assert parser.prog == "followcheck", "parser must keep its program name"
    assert len(parser._actions) > 3, "parser must define its arguments"
    return parser


def _render(report) -> str:
    lines = [f"verdict            {report.verdict}",
             f"page               {report.page_url}",
             f"target             {report.target_url}",
             f"status text/html   {report.html_fetch.status} "
             f"({report.html_fetch.length} bytes)",
             f"status */*         {report.any_fetch.status} "
             f"({report.any_fetch.length} bytes)",
             f"content negotiated {report.content_negotiated}",
             f"meta robots        {report.meta_robots}",
             f"x-robots-tag       {report.x_robots_tag}"]
    if report.robots is not None:
        lines.append(f"robots.txt         allowed={report.robots.allowed} "
                     f"rule={report.robots.matched_rule}")
    lines.append(f"matching anchors   {len(report.anchors)}")
    for anchor in report.anchors:
        lines.append(f"  rel={anchor.rel!r} followable={anchor.is_followable} "
                     f"raw={anchor.raw}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    """Run the CLI. Returns 0 when the link is genuinely followable."""
    assert argv is None or isinstance(argv, list), "argv must be a list or None"
    args = _build_parser().parse_args(argv)
    assert args.timeout > 0, "timeout must be positive"

    report = audit(args.page, args.target, user_agent=args.user_agent,
                   timeout=args.timeout, check_robots=not args.no_robots)
    if args.as_json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        print(_render(report))
    return 1 if report.verdict in FAILING_VERDICTS else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
