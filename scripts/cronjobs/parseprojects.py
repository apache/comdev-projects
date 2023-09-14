#!/usr/bin/env python3

"""

Reads:
../../data/projects.xml
parseprojects-failures.xml (if exists)
../../site/json/foundation/committees-retired.json

Writes:
../../site/json/foundation/projects.json
../../site/json/projects/%s.json
parseprojects-failures.xml (if failures occurred)
../../failures/%s.rdf (if failures occurred)

Deletes any obsolete files from:
../../site/json/projects/%s.json

"""

import errtee # N.B. this is imported for its side-effect
import sys
if sys.hexversion < 0x03000000:
    raise ImportError("This script requires Python 3")
from xml.dom import minidom
import xml.etree.ElementTree as ET
import re
import urlutils
import urllib.error
import json
import os
from os.path import join
import traceback
from datetime import datetime
import sendmail

URL_TIMEOUT = 60.0 # timeout for URL requests (may need tweaking)

PROJECTS_DIR = '../../site/json/projects'
SITEDIR = '../../site'
projectsList = "../../data/projects.xml"
PROJECTS_SVN = 'https://svn.apache.org/repos/asf/comdev/projects.apache.org/trunk/data/projects.xml'

FAILURES_DIR = '../../failures'

# grab the validation criteria
validation = {}
with open(os.path.join(SITEDIR, "validation.json")) as f:
    validation = json.loads(f.read())
langs = {}
lang = validation['languages'].keys()
cats = validation['categories'].keys()
# dict of lower-case names to canonical names
VALID_LANG = dict(zip([j.lower() for j in lang], lang))
VALID_CATS = dict(zip([j.lower() for j in cats], cats))

# Canonicalise without adding to suggested languages
VALID_LANG['bash'] = 'Bash'

SYNTAX_MSG = {
    "category": 'The expected syntax is <category rdf:resource="http://projects.apache.org/category/{category}" />'
            '\nEach category should be listed in a separate tag',
    "programming-language": 'The expected syntax is <programming-language>{language}</programming-language>'
            '\nEach language should be listed in a separate tag',
}
"""
Validate and canonicalise languages and categories

TODO send mails to projects when valid entries better established
"""
def validate(json, tag, valid, pid, url):
    if tag in json:
        outvals = []
        invals = re.split(r',\s*', json[tag]) # allow for missing space after comma
        for val in invals:
            canon = valid.get(val.lower())
            if canon is None:
                if len(val) > 30: # can this be a legal value?
                    # only warn the project once a week
                    if datetime.today().weekday() == 4: # Monday=0
                        topid = pid
                    else:
                        topid = None
                    printNotice(f"ERROR: illegal (overlong: {len(val)} >30) value '{val}' for {pid} in {url}",
                                body = f'Error in {url}\nUnexpected value:{val}\n{SYNTAX_MSG[tag]}',
                                project=topid)
                else:
                    print(f"WARN: unexpected value '{val}' for {pid} in {url}")#, project=pid)
                    outvals.append(val) # TODO flag this to show invalid entries
            elif canon != val:
                print(f"WARN: '{val}' should be '{canon}' for {pid} in {url}")
                outvals.append(canon)
            else:
                outvals.append(val)
        if outvals != invals:
            json[tag] = ", ".join(outvals)

save = True
if os.path.exists("parseprojects-failures.xml"):
    # Only use restart data if requested (e.g. when running interactively)
    if 'restart' in sys.argv:
        projectsList = "parseprojects-failures.xml"
        save = False
    else:
        print("Previous run failed, ignoring restart data")

filecache = None
if '--test' in sys.argv:
    import hashlib # for names
    import tempfile
    tmpdir = os.path.join(tempfile.gettempdir(), 'projects.apache.org')
    if not os.path.isdir(tmpdir):
        os.mkdir(tmpdir)
    print(f"Test mode; will cache DOAPs under {tmpdir}")
    filecache = urlutils.UrlCache(cachedir=tmpdir, interval=-1, silent=True)

with open(projectsList, "r") as f:
    data  = f.read()
    f.close()
xmldoc = minidom.parseString(data)
itemlist = xmldoc.getElementsByTagName('location')

siteMap = {
    'hc': 'httpcomponents',
    'ws':'webservices'
}

# convert from project to mail domain
mailDomains = {
  'comdev': 'community',
  'httpcomponents': 'hc',
  'whimsy': 'whimsical'
}

# Print to log and send an email (intended for WARN messages)
def printMail(msg, file=sys.stdout, body='', project=None):
    print(msg, file=file)
    if body == None: # sendmail barfs if body is missing
        body = ''
    if body == '':
        body=msg
    recipients = sendmail.__RECIPIENTS__ # This is the default
    try:
        if project != None:
            domain = mailDomains.get(project, project)
            recipients = [f'private@{domain}.apache.org', sendmail.__RECIPIENTS__]
            sendmail.sendMail(msg, body=body, recipients=recipients)
        else:
            sendmail.sendMail(msg, body=body)
    except ConnectionRefusedError:
        print(f"*** Failed to send the email to {recipients}", file=file)

# Print to log and send a notice email
def printNotice(msg, file=sys.stdout, body='', project=None):
    print(msg, file=file)
    if body == None: # sendmail barfs if body is missing
        body = ''
    if body == '':
        body=msg
    recipients = 'notifications@community.apache.org'
    if project != None:
        domain = mailDomains.get(project, project)
        recipients = [f'private@{domain}.apache.org', recipients]
    try:
        sendmail.sendMail(msg, body=body, recipients=recipients)
    except ConnectionRefusedError:
        print(f"*** Failed to send the email to {recipients}", file=file)

ATTIC = 'Attic <general@attic.apache.org>'
# Print to log and send a conditional email to Attic
def printAtticMail(msg, file=sys.stdout):
    print(msg, file=file)
    import datetime
    # Only send the mail once a week
    if datetime.datetime.now().day % 7 != 0:
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
# @return None if not found in file
# @throws exceptions for missing and unparseable files
def getPMC(url):
    print("Parsing PMC descriptor file %s" % url)
    rdf = urlutils.URLopen(url).read()
    md = minidom.parseString(rdf)
    pmc = (md.getElementsByTagName('asfext:pmc') or md.getElementsByTagName('asfext:PMC'))[0]
    t = pmc.tagName.lower()
    a = pmc.getAttribute('rdf:about')
    md.unlink()
    if t == 'asfext:pmc':
        print("Found pmc: %s" % a)
        return a
    return None

# Try to convert URL to committeeeId
# @return None if not recognised
# Sample URLs:
# http://svn.apache.org/repos/asf/abdera/java/trunk/doap_Abdera.rdf
# https://accumulo.apache.org/doap/accumulo.rdf
# https://gitbox.apache.org/repos/asf?p=ant-ivy.git;
# https://raw.githubusercontent.com/apache/httpd-site/main/content/doap.rdf
# https://raw.githubusercontent.com/apache/vcl/master/doap_vcl.rdf
# https://svn.apache.org/repos/asf/comdev/projects.apache.org/trunk/data/projects-override/sqoop.rdf

REGEXES = (
    r"^https?://svn\.apache\.org/repos/asf/comdev/projects\.apache\.org/trunk/data/projects-override/([^.]+)\.rdf",
    r"^https?://svn\.apache\.org/repos/asf/([^/]+)/",
    r"^https?://gitbox\.apache\.org/repos/asf\?p=([^.;]+)\.git;",
    r"^https?://([^/]+)\.apache\.org/", # must be after svn and gitbox
    r"^https?://raw\.githubusercontent\.com/apache/([^/]+)/",
)

def getPMCfromURL(url):
    for regex in REGEXES:
        m = re.search(regex, url, flags=re.IGNORECASE)
        if m:
            pmc = m.group(1)
            # PMC names cannot contain '-' apart from empire-db
            # so anything after '-' must be a sub-repo
            if pmc.startswith('empire-db'):
                pmc = 'empire-db' # allow for empire-db sub repos
            elif '-' in pmc:
                pmc = pmc.split('-',1)[0]
            return pmc
    return None

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
    # init variables here to avoid stale contents if read or parsing fails
    rdf = None
    prname = None
    committeeId = None
    projectJsonFilename = None
    try:
        if filecache:
            tmp = hashlib.sha256(url.encode()).hexdigest()
            rdf = filecache.get(url, tmp).read()
        else:
            rdf = urlutils.URLopen(url).read()
        rdfxml = ET.fromstring(rdf)
        project = rdfxml[0]
        pjson = {
            'doap': url
        }
        for el in project:
            k, v = handleChild(el)
            if not save:
                print("+ %s" % k)
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
                    for xk in sorted(v):
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

        projectid = getPMCfromURL(url) # default id for emails
        if not 'pmc' in pjson:
            printMail("WARN: no asfext:pmc in %s" % url, project=projectid)
        else:
            pmcrdf = pjson['pmc']
            pmcrdf = pmcrdf.replace('/anakia', '').replace('/texen', '') # temporary hack
            # Extract the PMC name if it is a shortcut
            m = re.match(r"https?://([^.]+)\.apache\.org/?$", pmcrdf, re.IGNORECASE)
            if m:
                committeeId = m.group(1)
            else:
                # Not a shortcut, so read the descriptor file
                try:
                    committeeId = getPMC(pmcrdf)
                    if not committeeId:
                        printMail("WARN: could not find asfext:pmc in %s " % url, project=projectid)
                except Exception as e:
                    printMail("WARN: invalid asfext:pmc '%s' in %s (%s)" % (pmcrdf, url, e), project=projectid)

        projectid = committeeId or projectid # use committeeId if set
        if 'name' in pjson:
            projectJsonFilename = name2fileName(pjson['name'], committeeId)
        else:
            printMail("WARN: no name defined in %s, pmc = %s" % (url, pjson['pmc']), project=projectid)

        if committeeId in retired:
            printAtticMail("WARN: project from a retired committee (%s) but PMC not changed to Attic in %s" % (committeeId, url))
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

            validate(pjson, 'category', VALID_CATS, projectid, url)
            validate(pjson, 'programming-language', VALID_LANG, projectid, url)
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
            printMail("WARN: project ignored since unable to extract project json filename from %s" % url, project=projectid)
    except Exception as err:
        if isinstance(err, OSError): # OSError is parent of HTTPError/URLError
            # Only mail 404 errors individually
            if isinstance(err, urllib.error.HTTPError) and err.code == 404:
                printMail("Cannot find doap file: %s" % url, file=sys.stderr,
                        body=("URL: %s\n%s\nSource: %s" % (url,str(err),PROJECTS_SVN)),
                        project=projectid # project is ignored if it is None
                        )
            else: # This is likely to be a transient error
                print("Error when processing doap file %s:" % url, file=sys.stderr)
                unreportedError = True
        else:
            printMail("Error when processing doap file %s:" % url, file=sys.stderr,
                body=("URL: %s\n%s\nSource: %s" % (url,str(err),PROJECTS_SVN)),
                project=projectid # project is ignored if it is None
                )
        print("-"*60, file=sys.stderr)
        traceback.print_exc()
        if isinstance(err, OSError): # OSError is parent of HTTPError/URLError
            print("URL: '%s'" % err.filename, file=sys.stderr)
        print("-"*60, file=sys.stderr)
        failures.append(url)
        if rdf is not None:
            # TODO better conversion to file name
            urlname = url.split('/')[-1]
            rem = re.search(r';f=([^;]+);',urlname) # better name for Git files
            if rem:
                urlname = rem.group(1)
            urlname = urlname.split(';')[0] # trim any trailing qualifiers
            urlname = join(FAILURES_DIR, urlname)
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
    if re.match(r'.*\.json$', f) and f not in files:
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
            printMail("ERROR: one or more errors detected - see also the parseprojects.py log file",
                      body="URLs:\n%s" % s)
else:
    if os.path.exists("parseprojects-failures.xml"):
        print("No failures detected, removing previous failure data")
        try:
            os.remove("parseprojects-failures.xml")
        except FileNotFoundError: # should not happen
            pass


print("Done!")
