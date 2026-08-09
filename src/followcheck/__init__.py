"""followcheck - decide whether an outbound link on a page is really followable.

The public surface is deliberately small::

    from followcheck import audit
    report = audit("https://example.com/page/", "https://target.example/")
    print(report.verdict)

Everything the report contains was read out of a live HTTP response; nothing
is inferred.
"""

from .core import (
    Anchor,
    Fetch,
    Report,
    RobotsRule,
    audit,
    fetch,
    find_anchors,
    meta_robots,
    robots_txt_verdict,
    x_robots_tag,
)

__all__ = [
    "Anchor",
    "Fetch",
    "Report",
    "RobotsRule",
    "audit",
    "fetch",
    "find_anchors",
    "meta_robots",
    "robots_txt_verdict",
    "x_robots_tag",
]

__version__ = "0.1.0"
