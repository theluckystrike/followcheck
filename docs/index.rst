followcheck
===========

``followcheck`` answers one narrow question with evidence instead of assumption:

    *Does this page really carry a followable, crawlable link to that URL?*

Six separate things can each quietly turn a link into nothing, and a browser
shows you none of them: the anchor may not be in the served HTML at all, it may
carry ``rel="nofollow"``, ``rel="ugc"`` or ``rel="sponsored"``, the page may set
``<meta name="robots">`` or an ``X-Robots-Tag`` header, ``robots.txt`` may
disallow the path, or the server may hand a different body to a crawler than it
hands to you. ``followcheck`` checks all six in one call and prints the raw
anchor it found so you can read the ``rel`` with your own eyes.

It has no dependencies. Standard library only, Python 3.8 and up.

Install
-------

Not yet on PyPI. Install from source:

.. code-block:: console

   $ pip install "followcheck @ git+https://github.com/theluckystrike/followcheck"

or clone and run it in place — there is nothing to build, and no third-party
package to resolve:

.. code-block:: console

   $ git clone https://github.com/theluckystrike/followcheck
   $ cd followcheck && PYTHONPATH=src python -m followcheck.cli --help

Command line
------------

.. code-block:: console

   $ followcheck https://pypi.org/project/requests/ https://requests.readthedocs.io/
   verdict            NOFOLLOW
   page               https://pypi.org/project/requests/
   target             https://requests.readthedocs.io/
   status text/html   200 (182884 bytes)
   status */*         200 (182884 bytes)
   content negotiated False
   meta robots        None
   x-robots-tag       None
   robots.txt         allowed=True rule=None
   matching anchors   2
     rel='nofollow' followable=False raw=<a href="https://requests.readthedocs.io" rel=nofollow>
     rel='nofollow' followable=False raw=<a class="sidebar-links__link" href="https://requests.readthedocs.io" rel="nofollow">

The exit code is ``0`` only when the verdict is ``DOFOLLOW``, so the command
drops straight into a shell script or CI job.

Library
-------

.. code-block:: python

   from followcheck import audit

   report = audit("https://pypi.org/project/requests/",
                  "https://requests.readthedocs.io/")

   print(report.verdict)                      # NOFOLLOW
   print(report.anchors[0].rel)               # nofollow
   print(report.anchors[0].raw)               # the literal <a ...> tag
   print(report.as_dict())                    # JSON-serialisable evidence bundle

Why it exists
-------------

``followcheck`` was extracted from the outbound-link auditing step of the
placement pipeline behind `Hands Off Links <https://handsofflinks.com/>`_, where
every published link is re-fetched and re-read rather than trusted. Doing that
by hand is a sequence of ``curl`` invocations plus a careful squint at the HTML,
and the squint is where the mistakes happen: a ``403`` interstitial gets read as
a verdict, a ``200`` on a host that returns ``200`` for every slug gets read as a
live page, and an unquoted ``rel=nofollow`` gets missed because the grep expected
quotes. This package encodes those failure modes so they are caught by a program
instead of by attention.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   verdicts
   methodology
   cli
   api

Licence
-------

MIT. Source at https://github.com/theluckystrike/followcheck.
