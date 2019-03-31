import sys
# The output from json.dumps() has a trailing space in Python2, it is absent in Python3
# So ensure we always use the same python version as the crontab
if sys.hexversion < 0x030000F0:
    raise RuntimeError("This script requires Python3")

"""
Extracts data showing the number of accounts created each month.

Reads:
https://whimsy.apache.org/public/public_ldap_people.json

Updates:
../../site/json/foundation/accounts-evolution.json

The JSON data has the following format:
{
  "lastCreateTimestamp": "20190309011146Z",
  "people": {
    ...
    "hboutemy": {
      "name": "Herve Boutemy",
      "createTimestamp": "20071016014212Z",
      ...

Whimsy applies corrections to the createTimestamp where known
For example the above LDAP record shows:
dn: uid=hboutemy,ou=people,dc=apache,dc=org
createTimestamp: 20090519192255Z


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

import json
from datetime import datetime, timedelta
from urlutils import UrlCache

uc = UrlCache(interval=0)

def loadJson(url):
    print("Reading " +url)
    resp = uc.get(url, name=None, encoding='utf-8', errors=None)
    try:
        content = resp.read() # json.load() does this anyway
        try:
            j = json.loads(content)
        except Exception as e:
            # The Proxy error response is around 4800 bytes
            print("Error parsing response:\n%s" % content[0:4800])
            raise e
    finally:
        resp.close()
    return j

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
    

ldappeople = loadJson('https://whimsy.apache.org/public/public_ldap_people.json')['people']

for p in ldappeople:
    stamp = ldappeople[p]['createTimestamp']
    if stamp.startswith(tym):
        js[ym] += 1
    else:
        if not tym1 == None:
            if stamp.startswith(tym1):
                js[ym1] += 1

with open("../../site/json/foundation/accounts-evolution.json", "w") as f:
    json.dump(js, f, sort_keys=True, indent=0)
    f.close()

print("Done, found %u entries for this month" % js[ym])
if not tym1 == None:
    print("Also found %u entries for the previous month (%s)" % (js[ym1], tym1))
