#!/usr/bin/env python3

"""
Updates a project to the attic:
- creates an override DOAP under data/projects-override
- updates projects.xml to point to the override DOAP
- moves data/committees/<pmc>.rdf to data/committees-retired/<pmc>.rdf
- updates data/committees.xml

Does not commit the changes.

N.B. The current implementation does not handle PMCs with multiple projects.

Updates:
data/projects.xml
data/committees.xml

Creates:
data/projects-override/<pmc>[_project].rdf

Moves:
data/committees/<pmc>.rdf
to
data/committees-retired/<pmc>.rdf

"""

import sys
from os.path import dirname, abspath, join
from inspect import getsourcefile
import os
import re
import subprocess

if len(sys.argv) == 1:
    print("Please provide a list of project ids")
    sys.exit(1)

OVERRIDE_DIR='https://svn.apache.org/repos/asf/comdev/projects.apache.org/trunk/data/projects-override'
MYHOME = dirname(abspath(getsourcefile(lambda:0)))
datadir = join(dirname(MYHOME),'data')

def update_pmc_xml(pmc):
    xmlfile = join(datadir,'committees.xml')
    xmlfilet = join(datadir,'committees.xml.t')
    print("Updating committees.xml")
    found = 0
    with open(xmlfile,'r', encoding='utf-8') as r, open(xmlfilet,'w', encoding='utf-8') as w:
        for l in r:
            m = re.search(r"^(\s+)<location>(.+)</location",l)
            if m:
                indent = m.group(1)
                url = m.group(2)
                # match one of:
                # committees/<pmc>.rdf
                # https://ofbiz.apache.org/<pmc>/...
                # http://svn.apache.org/repos/asf/<pmc>/...
                regex = r"^(committees/%s\.rdf|https?://%s\.apache\.org/.+|https?://svn.apache.org/repos/asf/%s/.+)$" % (pmc,pmc,pmc)
                if re.search(regex, url, flags=re.IGNORECASE):
                    print("Found %s at %s" % (pmc, url))
                    if url.startswith('committees/'):
                        new = url.replace('committees/','committees-retired/')
                        subprocess.run(["svn", "mv", "data/%s" % url, "data/%s" % new], check=True)
                        url = new
                    w.write("%s<!-- Retired: location>%s</location -->\n" % (indent, url))
                    found += 1
                    continue
            w.write(l) # write the original line
    if found == 1:
        print("Found OK")
        os.system("diff %s %s" % (xmlfile, xmlfilet))
        os.rename(xmlfilet, xmlfile)
    elif found > 1:
        print("Matched more than once %d" % found)
        os.remove(xmlfilet)
    else:
        print("Not found")
        os.remove(xmlfilet)

# update the DOAP to be an attic project
def update_doap(doap, source):
    infile = doap
    tmpfile = doap + '.t'
    catWrite = True
    with open(infile,'r', encoding='utf-8') as r, open(tmpfile,'w', encoding='utf-8') as w:
        for l in r:
            if re.search("<rdf:RDF",l):
                w.write("<!-- Copied from %s -->\n" % source)
            if re.search("<asfext:pmc rdf:resource=", l):
                w.write(re.sub("=['\"].+?['\"]",'="http://attic.apache.org/"',l))
                continue # don't write original line
            if catWrite and re.search("<category",l):
                catWrite = False
                w.write('    <category rdf:resource="http://projects.apache.org/category/retired" />\n')
            w.write(l) # write the original line

    os.system("diff %s*" % (infile))
    os.rename(tmpfile,infile)

def update_project_xml(pid):
    xmlfile = join(datadir,'projects.xml')
    xmlfilet = join(datadir,'projects.xml.t')
    doapfile = join(datadir,'projects-override',"%s.rdf" % pid)
    print("Updating projects.xml")
    found = 0
    source = None
    # match one of:
    # http://svn.apache.org/repos/asf/tomee/tomee/trunk/doap_tomee.rdf
    # https://gitbox.apache.org/repos/asf?p=trafficserver.git;
    # https://gitbox.apache.org/repos/asf?p=any23-committers.git;a=blob_plain;f=doap_Any23.rdf;hb=HEAD
    # https://raw.githubusercontent.com/apache/oodt/master/doap_oodt.rdf
    # https://raw.githubusercontent.com/apache/directory-site/master/static/doap_fortress.rdf
    # http://zookeeper.apache.org/doap.rdf
    # https://daffodil.incubator.apache.org/doap.rdf
    # Parse each line to extract the project name.
    repore = '([-a-z0-9]+)' # repo regex
    lines2match = [
        fr"^https?://svn\.apache\.org/repos/asf/{repore}/",
        fr"^https?://gitbox\.apache\.org/repos/asf\?p={repore}\.git",
        fr"^https?://raw\.githubusercontent\.com/apache/{repore}/",
        fr"^https?://{repore}(?:\.incubator)?\.apache\.org/",
    ]
    #                         1          2                      3                                                             4
    with open(xmlfile,'r', encoding='utf-8') as r, open(xmlfilet,'w', encoding='utf-8') as w:
        for l in r:
            m = re.search(r"^(\s+)<location>(.+)<",l)
            if m:
                indent = m.group(1)
                url = m.group(2)
                if '/data/projects-override/' in url: # already handled
                    w.write(l) # write the original line
                    continue
                m2 = None
                for line in lines2match:
                    m2 = re.search(line, url, flags=re.IGNORECASE)
                    if m2:
                        break
                if m2:
                    reponame = m2.group(1)
                    if reponame.startswith('empire-db'):
                        reponame = 'empire-db'
                    else:
                        reponame = reponame.split('-')[0]
                    if reponame == pid:
                        print("Found %s at %s" % (pid,url))
                        l = l.replace('<location>','<!-- retired: location>').replace('</location>','</location -->')
                        w.write(l) # write the original line
                        w.write("%s<location>%s/%s.rdf</location>\n" % (indent, OVERRIDE_DIR, pid))
                        found += 1
                        source = url
                        continue
                else:
                    print("??? cannot parse: "+url)
            w.write(l) # write the original line
    if found == 0:
        print("Could not find a match for %s" % pid)
        os.remove(xmlfilet)
    else:
        if "//svn.apache.org/" in source:
            os.system("svn cp %s %s" % (source.replace('http://','https://'), doapfile))
        else:
            os.system("wget -O %s '%s'" % (doapfile,source))
            os.system("svn add %s" % (doapfile))
        update_doap(doapfile, source)
        os.system("diff %s %s" % (xmlfile,xmlfilet))

        os.rename(xmlfilet,xmlfile)
        os.system("svn status %s" % dirname(doapfile))

for arg in sys.argv[1:]:
    print("Processing "+arg)
    if not re.search("^[-a-z0-9]+$",arg):
        print("Expecting lower-case, '-' or digits only")
    else:
        update_pmc_xml(arg)
        update_project_xml(arg)
