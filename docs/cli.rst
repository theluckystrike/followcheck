Command line
============

.. code-block:: text

   usage: followcheck [-h] [--json] [--user-agent USER_AGENT]
                      [--timeout TIMEOUT] [--no-robots]
                      page target

   Decide whether a page really carries a followable link to a target.

   positional arguments:
     page                  URL of the page that should carry the link
     target                URL the link should point at

   options:
     -h, --help            show this help message and exit
     --json                emit the whole evidence bundle as JSON
     --user-agent USER_AGENT
     --timeout TIMEOUT
     --no-robots           skip the robots.txt lookup

Exit codes
----------

``0``
    The verdict is ``DOFOLLOW``.

``1``
    Anything else: ``ANCHOR-ABSENT``, ``NOFOLLOW``, ``PAGE-LEVEL-NOFOLLOW``,
    ``NOINDEX-PAGE``, ``ROBOTS-DISALLOWED``, ``FETCH-ERROR``,
    ``UNVERIFIED-BOT-WALLED`` or a ``NON-200-*`` code.

Because ``UNVERIFIED-BOT-WALLED`` also exits ``1``, a non-zero exit means
"not proven good", never "proven bad". Check the verdict string before acting.

Auditing a list
---------------

.. code-block:: bash

   while IFS=, read -r page target; do
     followcheck --json "$page" "$target" > "reports/$(echo "$page" | md5sum | cut -c1-8).json"
   done < links.csv

Machine-readable output
-----------------------

``--json`` prints the same structure as :py:meth:`followcheck.Report.as_dict`,
with every anchor, its ``rel``, its literal source tag and its followability,
plus both status codes, both response lengths, the two robots directives and the
matched ``robots.txt`` rule.
