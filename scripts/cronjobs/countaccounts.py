import sys
# The output from json.dumps() has a trailing space in Python2, it is absent in Python3
# So ensure we always use the same python version as the crontab
if sys.hexversion < 0x030000F0:
    raise RuntimeError("This script requires Python3")

"""
Extracts data showing the number of accounts created each month.

Updates:
../../site/json/foundation/accounts-evolution.json

using the output from
ldapsearch -x -LLL -b ou=people,dc=apache,dc=org createTimestamp

e.g.
dn: uid=hboutemy,ou=people,dc=apache,dc=org
createTimestamp: 20090519192255Z

Note that the createTimestamp is when the record was (re)created.
Since LDAP was introduced some while after the ASF started,
the stamps for early committers are likely to be completely wrong.

For example, the entry above shows that the LDAP account was created
in May 2009. 
However the user account was actually created in Oct 2007 
according to the history for iclas.txt. And the ICLA is from Sep 2007
(which agrees with the iclas.txt date).
ALso his earliest commit Maven SVN is r585237 | hboutemy | 2007-10-16 

LDAP was introduced around May/June 2009.
The earliest  createTimestamp is 20090519192238Z

Hopefully recent timestamps give a better indication of when an account
was actually created.

The output file consists of lines of the form:
{
"1999-02": 22,
"1999-03": 0,
}

N.B. The script updates the entry for the current month.
However on day one of a new month, it also updates the previous month
This is so it sees accounts that were created after the final run
on the last day of the month

"""

import json;
from datetime import datetime, timedelta
import subprocess

js = {}
with open("../../site/json/foundation/accounts-evolution.json") as f:
    js = json.loads(f.read())
    f.close()

now = datetime.now() # fetch time once
if len(sys.argv) > 3:
    now = datetime(year=int(sys.argv[1]),month=int(sys.argv[2]), day=int(sys.argv[3]))
    print("Overriding current time: %s" % now)

currentMonth = now.month
currentYear = now.year
ym = "%04u-%02u" % (currentYear, currentMonth)
tym = "%04u%02u" % (currentYear, currentMonth)
print("Looking for entries for %s" % tym)
js[ym] = 0
# Potentially check for the previous month as well
ym1 = None
tym1 = None
if now.day == 1: # Day one of month, redo previous month to ensure all new entries are seen
    yesterday = now - timedelta(days = 1)
    ym1 = "%04u-%02u" % (yesterday.year, yesterday.month)
    tym1 = "%04u%02u" % (yesterday.year, yesterday.month)
    print("Also looking for entries for %s" % tym1)
    js[ym1] = 0
    

proc = subprocess.Popen(['ldapsearch','-x', '-LLL', '-b', 'ou=people,dc=apache,dc=org', 'createTimestamp'],stdout=subprocess.PIPE)

while True:
    line = proc.stdout.readline()
    if not line or line == "":
        break
    line = line.decode('utf-8')
    # Sample output:
    # createTimestamp: 20150330152151Z
    if line.startswith("createTimestamp: %s" % tym):
        js[ym] += 1
    else:
        if not tym1 == None:
            if line.startswith("createTimestamp: %s" % tym1):
                js[ym1] += 1

with open("../../site/json/foundation/accounts-evolution.json", "w") as f:
    json.dump(js, f, sort_keys=True, indent=0)
    f.close()

print("Done, found %u entries for this month" % js[ym])
if not tym1 == None:
    print("Also found %u entries for the previous month (%s)" % (js[ym1], tym1))
