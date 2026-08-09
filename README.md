# followcheck

Decide whether an outbound link on a page is *really* followable — and really
crawlable — instead of assuming it from a `200`.

No dependencies. Standard library only. Python 3.8+.

Not yet on PyPI; install from source.

```console
$ pip install "followcheck @ git+https://github.com/theluckystrike/followcheck"
$ followcheck https://pypi.org/project/requests/ https://requests.readthedocs.io/
verdict            NOFOLLOW
status text/html   200 (182884 bytes)
status */*         200 (182884 bytes)
matching anchors   2
  rel='nofollow' followable=False raw=<a href="https://requests.readthedocs.io" rel=nofollow>
  rel='nofollow' followable=False raw=<a class="sidebar-links__link" href="https://requests.readthedocs.io" rel="nofollow">
```

Exit code is `0` only on `DOFOLLOW`, so it drops straight into CI.

## What it checks

Six independent things can each turn a link into nothing, and a browser shows
you none of them:

1. the anchor is not in the served HTML at all (`ANCHOR-ABSENT`);
2. the anchor carries `nofollow`, `ugc` or `sponsored` (`NOFOLLOW`);
3. the page sets `<meta name="robots">` (`NOINDEX-PAGE` / `PAGE-LEVEL-NOFOLLOW`);
4. the response sets an `X-Robots-Tag` header, invisible in page source;
5. `/robots.txt` disallows the path (`ROBOTS-DISALLOWED`);
6. the server varies its body by `Accept` header (`content_negotiated`).

A `403`, `503` or challenge body is reported as `UNVERIFIED-BOT-WALLED` — the
absence of a verdict, never a negative one.

## Library use

```python
from followcheck import audit

report = audit("https://example.com/post/", "https://example.org/")
report.verdict            # 'DOFOLLOW'
report.anchors[0].rel     # None
report.anchors[0].raw     # the literal <a ...> tag from the served HTML
report.as_dict()          # JSON-serialisable evidence bundle
```

## Documentation

Full docs, including the verdict reference and the methodology behind each
check: <https://followcheck.readthedocs.io/>

## Why it exists

`followcheck` was extracted from the outbound-link auditing step of the
placement pipeline behind [Hands Off Links](https://handsofflinks.com/), where
every published link is re-fetched and re-read rather than trusted. Doing that
by hand is a sequence of `curl` invocations plus a careful squint at the HTML,
and the squint is where the mistakes happen.

## Tests

```console
$ python -m unittest discover -s tests
```

29 tests, run against a real local HTTP server rather than mocks.

## Licence

MIT.
