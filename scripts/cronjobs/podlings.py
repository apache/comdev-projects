import errtee
from xml.dom import minidom
import re, urllib.request
import json
from datetime import datetime

"""
Reads http://incubator.apache.org/podlings.xml
Creates:
../../site/json/foundation/podlings.json
../../site/json/foundation/podlings-history.json

"""

data = urllib.request.urlopen("http://incubator.apache.org/podlings.xml").read()
xmldoc = minidom.parseString(data)
itemlist = xmldoc.getElementsByTagName('podling') 

new = {}
grads = {}
ret = {}
current  = 0
cpods = {}
cpodsHistory = {}

now = datetime.now()
currentMonth = now.month
currentYear  = now.year
# years for the ranges
nextYear = currentYear + 1
startYear = 2003


fieldnames = ['month', 'new', 'graduated', 'retired']
for year in range(startYear, nextYear):
    for month in range(1,13):
        m = "%u-%02u" % (year, month)
        grads[m] = 0
        new[m] = 0
        ret[m] = 0

for s in itemlist :
        name = s.attributes['name'].value
        uname = s.attributes['resource'].value
        status = s.attributes['status'].value
        sd = s.attributes['startdate'].value
        ed = s.attributes['enddate'].value if 'enddate' in s.attributes else None
        desc = "No description"
        for c in s.childNodes:
            if c.__class__.__name__ != 'Text' and c.tagName == 'description':
                desc = c.childNodes[0].data
                break
        #print(name, status, sd, ed)
        if sd and re.match(r"(\d{4}-\d+)", sd):
            sd = re.match(r"(\d{4}-\d+)", sd).group(1)
        if ed and re.match(r"(\d{4}-\d+)", ed):
            ed = re.match(r"(\d{4}-\d+)", ed).group(1)

        new[sd] += 1
        if status == "graduated":
            if not ed:
                ed = sd
                print("%s did not specify a graduation date, assuming %s!" % (name,ed))
            grads[ed] += 1
            cpodsHistory[uname] = {
                'started': sd,
                'status': status,
                'ended': ed,
                'name': "Apache %s (Incubating)" % name,
                'description': desc,
                'homepage': "http://%s.incubator.apache.org/" % uname
            }
        elif status == "retired":
            if not ed:
                ed = sd
                print("%s did not specify a retirement date, assuming %s!" % (name,ed))
            ret[ed] += 1
            cpodsHistory[uname] = {
                'started': sd,
                'status': status,
                'ended': ed,
                'name': "Apache %s (Incubating)" % name,
                'description': desc,
                'homepage': "http://%s.incubator.apache.org/" % uname
            }
        elif status == "current":
            current += 1
            cpods[uname] = {
                'started': sd,
                'name': "Apache %s (Incubating)" % name,
                'pmc': 'incubator',
                'description': desc,
                'homepage': "http://%s.incubator.apache.org/" % uname,
                'podling': True
            }

js = []
for year in range(startYear, nextYear):
    for month in range(1,13):
        m = "%u-%02u" % (year, month)
        mjs = {
            'month': m,
            'new': new[m],
            'graduated': grads[m],
            'retired': ret[m],
            'current': 0
        }
        if currentYear > year or (currentYear == year and currentMonth >= month):
            js.append(mjs)

js.reverse()

for i in js:
    i['current'] = current
    current -= i['new']
    current += i['graduated']
    current += i['retired']
    
print("Writing podlings.json")
with open('../../site/json/foundation/podlings.json', 'w', encoding='utf-8') as f:
    json.dump(cpods, f, sort_keys=True, indent=0, ensure_ascii=False)
    f.close()

print("Writing podlings-history.json")
with open('../../site/json/foundation/podlings-history.json', 'w', encoding='utf-8') as f:
    json.dump(cpodsHistory, f, sort_keys=True, indent=0, ensure_ascii=False)
    f.close()

print("All done!")
