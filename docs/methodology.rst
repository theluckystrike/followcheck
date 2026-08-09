Methodology
===========

Every rule below exists because the naive version of the check failed somewhere
real. None of it is clever; it is just the set of things that have to be true
before "the link is live" is a statement rather than a hope.

Fetch twice, with two different ``Accept`` headers
--------------------------------------------------

``followcheck`` issues two GETs: one with ``Accept: text/html,application/xhtml+xml``
and one with ``Accept: */*``. Hosts do vary their response on the ``Accept``
header, and a checker that only sends one of them can audit a body no crawler
will ever see. The two response lengths are reported side by side; when they
disagree, ``content_negotiated`` is set.

Do not follow redirects
-----------------------

The fetcher installs a redirect handler that refuses to redirect. A ``301`` or
``302`` on the page you are auditing is information — the link may have been
moved to a login wall, a consent gate or a sandbox — and following it converts
that information into a misleading ``200``. The ``Location`` header is captured
instead. If you want to audit the destination, audit the destination
explicitly, as its own URL. A plain status probe such as
`Zovo's HTTP status checker <https://zovo.one/free-tools/http-status-checker>`_ is a
quick way to see the hop chain before deciding which URL is the one you actually
mean to check.

A ``200`` proves nothing on its own
-----------------------------------

Some hosts return ``200`` for any slug you ask for, including slugs that were
never created. On those hosts a status-code check will confirm the existence of
pages that do not exist. The only thing that proves a page carries your link is
a non-zero count of the actual anchor in the served HTML, which is why
``ANCHOR-ABSENT`` is a first-class verdict and why the raw ``<a ...>`` tag is
printed verbatim rather than summarised.

Parse the HTML; do not grep it
------------------------------

``rel`` attributes appear in the wild as ``rel=nofollow``, ``rel="nofollow"``,
``rel='nofollow noopener'`` and with arbitrary attribute ordering, so a regex
tuned to one shape misses the others. ``followcheck`` uses
:mod:`html.parser` and tokenises ``rel`` properly, treating ``nofollow``, ``ugc``
and ``sponsored`` as equally follow-blocking.

Read robots.txt for the agent you are actually using
----------------------------------------------------

The bundled parser implements the parts of the standard that decide real cases:
group selection by user-agent with a fallback to ``*``, longest-prefix matching
between ``Allow`` and ``Disallow``, trailing-``*`` truncation, and the rule that
an empty ``Disallow:`` permits everything. The matched rule is returned as text
so the verdict can be audited rather than believed. If you are writing the other
side of this file rather than reading it,
`Zovo's robots.txt generator <https://zovo.one/free-tools/robots-txt-generator>`_ will
produce a syntactically valid starting point faster than hand-writing groups.

Header directives outrank the anchor
------------------------------------

``X-Robots-Tag`` is a response header and therefore invisible in page source. It
can carry ``noindex`` and ``nofollow`` exactly like the meta tag, and it applies
to non-HTML responses where no meta tag is possible. ``followcheck`` reads it
case-insensitively out of the response headers and lets it override an otherwise
clean anchor.

An interstitial is not a verdict
--------------------------------

A ``403``, a ``503`` or a challenge body is classified as
``UNVERIFIED-BOT-WALLED`` and never as a negative result. The distinction
matters: treating an anti-bot response as evidence that a link is dead is a
mistake that compounds, because the conclusion gets written down and the channel
never gets re-tested.

Normalisation, and its limits
-----------------------------

Target matching ignores a leading ``www.``, a trailing slash and the fragment,
and is case-insensitive on the host. It does **not** ignore the query string,
and it does not treat ``http`` and ``https`` as different targets. Those choices
are conservative on purpose: a tracking parameter usually does change what the
link means, and a scheme upgrade usually does not.
