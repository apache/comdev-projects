# sample script to test logging of stdout and STDERR

import sys
import os
import errtee # pylint: disable=unused-import

print("Stdout1")
if 'ERRTEE' in os.environ:
    print("ERRTEE=%s" % os.environ['ERRTEE'])
else:
    print("ERRTEE is not defined")
print("Stderr2", file=sys.stderr) # should appear in log file if ERRTEE is defined
print("Stdout3")
raise ValueError("Except") # should appear in log file if ERRTEE is defined
