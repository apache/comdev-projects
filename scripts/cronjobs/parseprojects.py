import errtee
import sys
if sys.hexversion < 0x03000000:
    raise ImportError("This script requires Python 3")
from xml.dom import minidom
import xml.etree.ElementTree as ET
import re, urllib.request
import urllib.error
import json
import os
from os.path import join
import traceback
import sendmail

"""

Reads:
../../data/projects.xml
parseprojects-failures.xml (if exists)
../../site/json/foundation/committees-retired.json

Writes:
../../site/json/foundation/projects.json
../../site/json/projects/%s.json
parseprojects-failures.xml (if failures occurred)

Deletes any obsolete files from:
../../site/json/projects/%s.json

"""

URL_TIMEOUT = 60.0 # timeout for URL requests (may need tweaking)

PROJECTS_DIR = '../../site/json/projects'

projectsList = "../../data/projects.xml";
PROJECTS_SVN = 'https://svn.apache.org/repos/asf/comdev/projects.apache.org/trunk/data/projects.xml'

save = True;
if os.path.exists("parseprojects-failures.xml"):
    # Only use restart data if requested (e.g. when running interactively)
    if 'restart' in sys.argv:
        projectsList = "parseprojects-failures.xml";
        save = False;
    else:
        print("Previous run failed, ignoring restart data")

with open(projectsList, "r") as f:
    data  = f.read()
    f.close()
xmldoc = minidom.parseString(data)
itemlist = xmldoc.getElementsByTagName('location') 

siteMap = {
    'hc': 'httpcomponents',
    'ws':'webservices'
}

# Print to log and send an email (intended for WARN messages)
def printMail(msg, file=sys.stdout, body=''):
    print(msg, file=file)
    if body == None: # sendmail barfs if body is missing
        body = ''
    if body == '':
        body=msg
    try:
        sendmail.sendMail(msg, body=body)
    except ConnectionRefusedError:
        print("*** Failed to send the email", file=file)

ATTIC = 'Attic <general@attic.apache.org>'
# Print to log and send a conditional email to Attic
def printAtticMail(msg, file=sys.stdout):
    print(msg, file=file)
    import datetime
    # Only send the mail once a month
    if datetime.datetime.now().day != 14:
        print("Not sending the email to '" + str(ATTIC) +"'" , file=file)
        return
    try:
        sendmail.sendMail(msg,recipients=ATTIC, replyTo=None)
    except ConnectionRefusedError:
        print("*** Failed to send the email to '" + str(ATTIC) +"'" , file=file)

def site2committee(s):
    if s in siteMap:
        return siteMap[s]
    return s

with open("../../site/json/foundation/committees-retired.json", "r") as f:
    committeesRetired = json.loads(f.read())
    f.close()
retired = []
for r in committeesRetired:
    retired.append(r['id'])

projects = {}
failures = []

# Convert project name to unique file name
def name2fileName(s, pmc):
    retval = None
    fn = s.strip().lower()
    fn = fn.replace(" %s " % pmc," ") # drop PMC name
    fn = fn.replace(' (incubating)','') # will be under the incubator PMC anyway
    fn = re.sub('^apache ', '', fn) # Drop leading Apache
    fn = re.sub(' library$', '', fn) # Drop trailing Library
    fn = fn.replace('.net','dotnet')
    fn = re.sub("[^a-z0-9+-]", "_", fn) # sanitise the name
    if fn == pmc:
        retval = pmc
    else:
        retval = "%s-%s" % (pmc, fn)
    #print("=========== %s, %s => %s " % (s,pmc,retval))
    return retval

# Process external PMC descriptor file to extract the PMC name
def getPMC(url):
    print("Parsing PMC descriptor file %s" % url)
    rdf = urllib.request.urlopen(url, timeout=URL_TIMEOUT).read()
    md = minidom.parseString(rdf)
    pmc = (md.getElementsByTagName('asfext:pmc') or md.getElementsByTagName('asfext:PMC'))[0]
    t = pmc.tagName.lower()
    a = pmc.getAttribute('rdf:about')
    md.unlink()
    if t == 'asfext:pmc':
        print("Found pmc: %s" % a)
        return a
    printMail("WARN: could not find asfext:pmc in %s " % url)
    return 'Unknown'

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
            if k == "location":
                retval = v
                break
    return tag, retval

files = []
unreportedError = False # any errors not yet mailed?
for s in itemlist :
    url = s.childNodes[0].data
    try:
        rdf = urllib.request.urlopen(url, timeout=URL_TIMEOUT).read()
        rdfxml = ET.fromstring(rdf)
        project = rdfxml[0]
        pjson = {
            'doap': url
        }
        prname = None
        committeeId = None
        projectJsonFilename = None
        for el in project:
            k, v = handleChild(el)
            if not save:
                print("+ %s" % k);
            if k in pjson and not k in ['name','homepage']:
                if type(pjson[k]) is str:
                    pjson[k] = "%s, %s" % (pjson[k], v)
                else:
                    for xk in v:
                        pjson[k].append(v[xk])
            else:
                # Deal with multiple entry tags first
                if k in ['release', 'implements', 'repository', 'developer', 'maintainer', 'member', 'helper']:
                    pjson[k] = []
                    for xk in v:
                        pjson[k].append(v[xk])
                else:
                    pjson[k] = v

        if pjson['homepage']:
            homepage = pjson['homepage']
            m = re.match(r"https?://([^.]+)\.", homepage, re.IGNORECASE)
            if m:
                siteId = site2committee(m.group(1))
        else:
            printMail("WARN: no homepage defined in %s, pmc = %s" % (url, pjson['pmc']))

        pmc = 'Unknown'
        if not 'pmc' in pjson:
            printMail("WARN: no asfext:pmc in %s" % url)
        else:
            pmcrdf = pjson['pmc']
            pmcrdf = pmcrdf.replace('/anakia', '').replace('/texen', '') # temporary hack
            # Extract the pmc name if it is a shortcut
            m = re.match(r"https?://([^.]+)\.apache\.org/?$", pmcrdf, re.IGNORECASE)
            if m:
                pmc = m.group(1)
            else:
                # Not a shortcut, so read the descriptor file
                try:
                    pmc = getPMC(pmcrdf)
                except:
                    printMail("WARN: invalid asfext:pmc '%s' in %s" % (pmcrdf, url))
            
        if pjson['name']:
            projectJsonFilename = name2fileName(pjson['name'], pmc)
        else:
            printMail("WARN: no name defined in %s, pmc = %s" % (url, pjson['pmc']))

        committeeId = pmc

        if committeeId in retired:
            printAtticMail("WARN: project from a retired committee but PMC not changed to Attic in %s" % url)
            committeeId = 'attic'
        pjson['pmc'] = committeeId

        # replace category url with id, by removing https?://projects.apache.org/category/
        # They are not usable as URLs, but some projects have converted them from http:
        if 'category' in pjson:
            pjson['category'] = re.sub(r"https?://projects\.apache\.org/category/", "", pjson['category'])
            if committeeId == 'attic' and not 'retired' in pjson['category']:
                printAtticMail("WARN: project in Attic but not in 'retired' category: %s" % url)
                pjson['category'] = "%s, retired" % pjson['category']
        elif committeeId == 'attic' and not 'retired' in pjson['category']:
            printAtticMail("WARN: project in Attic but not in 'retired' category: %s" % url)
            pjson['category'] = "retired"
        if projectJsonFilename:
            #add = {}
            #for k in pjson:
            #    if pjson[k] != None and type(pjson[k]) is not str:
            #        for e in pjson[k]:
            #            add[e] = pjson[k][e]
            #        pjson[k] = None

            projects[projectJsonFilename] = pjson
            #for e in add:
            #    pjson[e] = add[e]
            name = "%s.json" % projectJsonFilename
            print("Writing projects/%s" % name)
            files.append(name)
            with open (join(PROJECTS_DIR, name), "w", encoding='utf-8') as f:
                json.dump(pjson, f, sort_keys=True, indent=0, ensure_ascii=False)
                f.close()
        else:
            printMail("WARN: project ignored since unable to extract project json filename from %s" % url)
    except Exception as err:
        if isinstance(err, OSError): # OSError is parent of HTTPError/URLError
            # Only mail 404 errors individually
            if isinstance(err, urllib.error.HTTPError) and err.code == 404:
                printMail("Cannot find doap file: %s" % url, file=sys.stderr,
                          body=("URL: %s\n%s\nSource: %s" % (url,str(err),PROJECTS_SVN)))
            else:
                print("Error when processing doap file %s:" % url, file=sys.stderr)
                unreportedError = True
        else:
            printMail("Error when processing doap file %s:" % url, file=sys.stderr,
                      body=("URL: %s\n%s\nSource: %s" % (url,str(err),PROJECTS_SVN)))
        print("-"*60, file=sys.stderr)
        traceback.print_exc()
        if isinstance(err, OSError): # OSError is parent of HTTPError/URLError 
            print("URL: '%s'" % err.filename, file=sys.stderr)
        print("-"*60, file=sys.stderr)
        failures.append(url)
        if rdf is not None:
            urlname = url.split('/')[-1]
            rem = re.search(r';f=([^;]+);.*',urlname) # better name for Git files
            if rem:
                urlname = rem.group(1)
            print("Saving invalid data in %s " % urlname)
            with open (urlname, "wb") as f:
                f.write(rdf)
                f.close()

if save:
    print("Writing foundation/projects.json...")
    with open ("../../site/json/foundation/projects.json", "w", encoding='utf-8') as f:
        json.dump(projects, f, sort_keys=True, indent=0, ensure_ascii=False)
        f.close()

# Drop any obsolete files
for f in os.listdir(PROJECTS_DIR):
    if re.match(r'.*\.json$', f) and not f in files:
        print("Deleting obsolete file projects/%s" %f)
        os.remove(join(PROJECTS_DIR,f))

if len(failures) > 0:
    with open ("parseprojects-failures.xml", "w") as f:
        f.write("<doapFiles>\n")
        for fail in failures:
            f.write("<location>%s</location>\n" % fail)
        f.write("</doapFiles>\n")
        f.close()
        if unreportedError:
            s = "\n".join(failures)
            printMail("ERROR: one or more errors detected - see also the parseprojects.py log file\nURLs:\n%s" % s)
else:
    if os.path.exists("parseprojects-failures.xml"):
        print("No failures detected, removing previous failure data")
        try:
            os.remove("parseprojects-failures.xml")
        except FileNotFoundError: # should not happen
            pass


print("Done!")
