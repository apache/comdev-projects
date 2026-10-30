#!/usr/bin/env python3
"""
SUPERSEDED: this script used to build the project data from DOAP files
listed in data/projects.xml. Project and release data now come from the ASF
release catalog (see parsecatalog.py).

It is kept under this name only because the nightly crontab (defined in
Infra's P6 repository) still calls parseprojects.py. It now runs:

    parsecatalog.py    projects.json, projects/<id>.json, releases.json
    buildchooser.py    chooser.json

When the crontab is updated to call those two directly, delete this file.
The old DOAP-based version is in svn history (r1939678 and earlier).
"""

import errtee  # pylint: disable=unused-import
import subprocess
import sys
from os.path import dirname, join, realpath

HERE = dirname(realpath(__file__))


def run(script):
    print("parseprojects.py: running %s" % script, flush=True)
    return subprocess.call([sys.executable, join(HERE, script)], cwd=HERE)


rc = run('parsecatalog.py')
if rc != 0:
    sys.exit("parsecatalog.py failed (exit %d); not running buildchooser.py" % rc)
sys.exit(run('buildchooser.py'))
