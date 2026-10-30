#!/usr/bin/env python3
"""
SUPERSEDED: this script used to scrape downloads.apache.org to build
releases.json. Release data now comes from the ASF release catalog and is
written by parsecatalog.py (run via parseprojects.py).

It is kept as a no-op only because the nightly crontab (defined in Infra's
P6 repository) still calls it. It must NOT write releases.json, or it would
overwrite the catalog data. When the crontab no longer calls it, delete this
file. The old version is in svn history (r1939678 and earlier).
"""

print("parsereleases.py: superseded by parsecatalog.py; nothing to do.")
