Verdict reference
=================

``Report.verdict`` is a single upper-case string. It is deliberately blunt: the
whole point of the package is that "the link is fine" should be one word you can
grep for, and every other outcome should name its own cause.

``DOFOLLOW``
    At least one anchor pointing at the target is present in the served HTML,
    carries no follow-blocking ``rel`` token, the page sets no page-level
    ``noindex``/``nofollow`` directive, and ``robots.txt`` permits the path.
    This is the only verdict that exits ``0``.

``ANCHOR-ABSENT``
    The page returned ``200`` but contains no anchor resolving to the target.
    This is the single most common false positive in link checking: the page
    exists, so a status-code-only check passes, but the link is not on it.
    Client-rendered pages land here too, and correctly so, because an anchor
    that only exists after JavaScript runs is not an anchor a crawler
    necessarily sees.

``NOFOLLOW``
    The anchor is present, but every matching anchor carries at least one of
    ``nofollow``, ``ugc`` or ``sponsored`` in its ``rel``. All three are treated
    as follow-blocking.

``PAGE-LEVEL-NOFOLLOW``
    The anchor is bare, but the page as a whole is marked ``nofollow`` by
    ``<meta name="robots">`` or by the ``X-Robots-Tag`` response header. A bare
    anchor on such a page is still not followed, which is why the anchor-level
    check alone is not enough.

``NOINDEX-PAGE``
    The anchor is followable but the page is marked ``noindex``. The link may
    still pass signals, but the page carrying it is not itself in the index, so
    it is reported separately rather than folded into ``DOFOLLOW``.

``ROBOTS-DISALLOWED``
    The path is blocked in ``/robots.txt`` for the user-agent in use. The rule
    that matched is quoted verbatim in ``Report.robots.matched_rule``.

``NON-200-<code>``
    The page did not return ``200``. Redirects are included here rather than
    followed, because a ``301`` to a different page is a fact about the link
    that silently disappears the moment you follow it.

``UNVERIFIED-BOT-WALLED``
    A ``403``, a ``503`` or a visible interstitial. **This is the absence of a
    verdict, not a negative verdict.** A challenge page's own ``noindex``
    describes the wall, not the page behind it, and reading it as a verdict is
    how working channels get written off by mistake. Re-test from a real
    browser session before concluding anything.

``FETCH-ERROR``
    DNS, TLS or connection failure. The exception text is preserved in
    ``Fetch.error``.

The ``content_negotiated`` flag
-------------------------------

Independently of the verdict, ``Report.content_negotiated`` is ``True`` when the
same URL returns ``200`` under both ``Accept: text/html`` and ``Accept: */*`` but
with different response lengths. That is not automatically sinister, but it does
mean the body you audited is not the only body the server serves, so any verdict
derived from one of them is conditional on the header you sent.
