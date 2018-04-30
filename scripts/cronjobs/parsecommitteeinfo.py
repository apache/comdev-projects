import errtee
import re
import json
import sys
if sys.hexversion < 0x03000000:
    raise ImportError("This script requires Python 3")
import io
import os
import os.path
import urllib.request
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import datetime
import sendmail

sys.path.append("..") # module committee_info is in parent directory
import committee_info

"""

Reads:
../../data/committees.xml
committee-info.txt from Whimsy

Updates:
../../site/json/foundation/committees.json
../../site/json/foundation/committees-retired.json

"""

# LDAP group ids not matching committee id; convert group to committeeId
group_ids = {
    'ws': 'webservices'
}

# homepages not matching http://<committee id>.apache.org/ and not defined in committee-info.json / index.html
homepages = {
    'comdev': 'http://community.apache.org/', # temporary (accidentally used https: in site.rb local table)
    'whimsy': 'http://whimsical.apache.org/', # incorrect in index.html because actual site does not yet exist
}

# Print to log and send an email (intended for WARN messages)
def printMail(msg):
    print(msg)
    try:
        sendmail.sendMail(msg)
    except ConnectionRefusedError:
        print("*** Failed to send the email")

# compress a string: trim it and replace multiple whitespace with a single space
def compress(s):
    return re.sub(r"""\s+""", ' ', s.strip())

def handleChild(el):
    retval = None
    hasKids = False
    for child in list(el):
        hasKids = True
    attribs = {}
    for key in el.attrib:
        xkey = re.sub(r"\{.+\}", "", key)
        attribs[xkey] = el.attrib[key]
    tag = re.sub(r"\{.+\}", "", el.tag)
    value = attribs['resource'] if 'resource' in attribs else el.text
    if not hasKids:
        retval = value
    else:
        retval = {}
        for child in list(el):
            k, v = handleChild(child)
            retval[k] = v
    return tag, retval

# Simple-minded check of URL
def head(url):
    req = urllib.request.Request(url, method="HEAD")
    try:
        resp = urllib.request.urlopen(req)
        return True
    except:
        return False

pmcs = {}
pmcDataUrls = {} # id -> url

# get PMC Data from /data/committees.xml
print("Reading PMC Data (/data/committees.xml)")
with open("../../data/committees.xml", "r") as f:
    xmldoc = minidom.parseString(f.read())
    f.close()

print("Extracting PMC DOAP file data for json/foundation/committees.json")
for loc in xmldoc.getElementsByTagName('location') :
    url = loc.childNodes[0].data
    try:
        if url.startswith('http'):
            rdf = urllib.request.urlopen(url).read()
        else:
            rdf = open("../../data/%s" % url, 'r', encoding='utf-8').read()
            url = "https://svn.apache.org/repos/asf/comdev/projects.apache.org/trunk/data/%s" % url
        rdfxml = ET.fromstring(rdf)
        rdfdata = rdfxml[0]
        expected = '{http://projects.apache.org/ns/asfext#}pmc'
        if not rdfdata.tag == expected:
            print("ERROR: unexpected tag value '%s' in '%s' (expecting %s)" % (rdfdata.tag, url, expected), file=sys.stderr)
            continue # No point proceeding further
        committeeId = rdfdata.attrib['{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about']
        if re.match("https?:", committeeId):
            print("ERROR: unexpected rdf:about value '%s' in '%s'" % (committeeId, url), file=sys.stderr)
            continue # No point proceeding further
        pmcDataUrls[committeeId] = url

        # transform PMC data RDF to json
        pmcjson = {
            'rdf': url
        }
        pmcname = None
        for el in rdfdata:
            k, v = handleChild(el)
            if k in pmcjson:
                # merge multiple values
                if type(pmcjson[k]) is str:
                    pmcjson[k] = "%s, %s" % (pmcjson[k], v)
                else:
                    for xk in v:
                        pmcjson[k][xk] = v[xk]
            else:
                pmcjson[k] = v

        pmcs[committeeId] = pmcjson

    except Exception as err:
        print("ERROR: %s processing %s" % (err, url), file=sys.stderr)

committeeCount = 0
committeesList = []
committeesMap = {}
addedCommittees = []

# temporary fix to ensure comparisons of generated files work better
# The original code relied on the order in the physical file
def keyorder(s):
#     print("key=%s" % s)
    if s == 'apr':
        return 'portableruntime'
    if s == 'climate':
        return 'openclimate'
    if s == 'comdev':
        return 'communitydevelopment'
    if s == 'httpd':
        return 'http' # so it sorts before HTTP Components (it's wrong in CI)
    if s == 'ws':
        return 'webservices'
    return s

# extract committees composition
print("Reading committee-info")
committees = committee_info.committees()

print("Writing generated doap/<committeeId>/pmc.rdf...")
for group in sorted(committees, key=keyorder):

#     if group == 'apr' or group == 'whimsy':
#         print("DEBUG: see what happens when CI entry %s is removed" % group)
#         continue
#     print(group)
    ctte = committees[group]
    fullName = ctte['fullname'] # Full name including Apache prefix
    if ctte['pmc']: # we only want PMCs
        if ctte['established']: # only want ones with entries in section 3
            # Fix up name where PMC RDF does not agree with LDAP group
            if group in group_ids:
                committeeId = group_ids[group]
            else:
                committeeId = group

            img = "http://www.apache.org/img/%s.jpg" % committeeId
            if not head(img):
                print("WARN: could not find logo: %s" % (img))
                
            committeeCount += 1
            committee={}
            committee['id'] = committeeId
            try:
                committee['chair'] = ctte['chair']['nick']
            except TypeError: # no chair present
                committee['chair'] = ''
            try:
                committee['reporting'] = ctte['reporting']
            except KeyError:
                pass
            committee['group'] = group
            committee['name'] = fullName
            committee['established'] = ctte['established']
            committee['roster'] = ctte['roster']
            homepage = None
            if group in homepages:
                homepage = homepages[group]
            else:
                if ctte['site']:
                    homepage = ctte['site']
                else:
                    homepage = 'http://%s.apache.org/' % group
            committee['homepage'] = homepage

            if ctte['description']:
                committee['shortdesc'] = ctte['description']
            else:
                # N.B. Whimsy parses index.html to generate the description entry in committee-info.json
                printMail("WARN: %s (%s) missing from http://www.apache.org/index.html#projects-list" % (group, fullName))

            if committeeId in pmcDataUrls:
                committee['rdf'] = pmcDataUrls[committeeId]
            else:
                printMail("WARN: %s (%s) missing from /data/committees.xml" % (fullName, committeeId))
                if os.path.isfile("../../data/committees/%s.rdf" % committeeId):
                    print("INFO: %s.rdf exists in data/committees/ but is not in /data/committees.xml" % committeeId)

            if committeeId in pmcs:
                if 'charter' in pmcs[committeeId]:
                    committee['charter'] = compress(pmcs[committeeId]['charter'])

            committeesList.append(committee)
            committeesMap[committeeId] = committee;
        else:
            print("INFO: %s ignored - not yet in section 3" % fullName)
    else:
        # Special Committee (Officer's, President's or Board)
        print("INFO: %s ignored - not a PMC" % fullName)


# detect retired committees to add to committees-retired.json
with open("../../site/json/foundation/committees-retired.json", "r") as f:
    committeesRetired = json.loads(f.read())
    f.close()

with open("../../site/json/foundation/committees.json", "r") as f:
    committeesPrevious = json.loads(f.read())
    f.close()

for currId in committeesMap:
    if not currId in [item['id'] for item in committeesPrevious]:
        addedCommittees.append(currId)

print("found %s new committees from %s committees in committee_info.txt" % (len(addedCommittees), committeeCount))
addedCommittees.sort()
for added in addedCommittees:
    print("- %s" % added)

for previous in committeesPrevious:
    prevId = previous['id']
    if not prevId in committeesMap:
        print("found retired committee: %s %s" % (prevId, previous['name']))
        previous['retired'] = datetime.date.today().strftime('%Y-%m')
        # remove data that is not useful in a retired committee
        previous.pop('chair', None)
        previous.pop('group', None)
        previous.pop('rdf', None)
        previous.pop('reporting', None)
        committeesRetired.append(previous)

print("Writing json/foundation/committees.json...")
with open("../../site/json/foundation/committees.json", "w") as f:
    json.dump(committeesList, f, sort_keys=True, indent=0)
    f.close()

print("Writing json/foundation/committees-retired.json...")
with open("../../site/json/foundation/committees-retired.json", "w") as f:
    json.dump(committeesRetired, f, sort_keys=True, indent=0)
    f.close()

print("All done")