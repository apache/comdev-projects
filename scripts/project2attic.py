#!/usr/bin/env python3

"""
Updates a project to the attic:
- creates an override DOAP under data/projects-override
- updates projects.xml to point to the override DOAP

Does not commit the changes.

N.B. The current implementation does not handle PMCs with multiple projects.

Updates:
data/projects.xml

Creates:
data/projects-override/<pmc>[_project].rdf

"""

import sys
from os.path import dirname, abspath, join
from inspect import getsourcefile
import os
import re

if len(sys.argv) == 1:
    print("Please provide a list of project ids")
    sys.exit(1)

OVERRIDE_DIR='https://svn.apache.org/repos/asf/comdev/projects.apache.org/trunk/data/projects-override'
MYHOME = dirname(abspath(getsourcefile(lambda:0)))
datadir = join(dirname(MYHOME),'data')

# update the DOAP to be an attic project
def update_doap(doap, source):
    infile = doap
    tmpfile = doap + '.t'
    catWrite = True
    with open(infile,'r') as r, open(tmpfile,'w') as w:
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
    
def update_xml(pid):
    xmlfile = join(datadir,'projects.xml')
    xmlfilet = join(datadir,'projects.xml.t')
    doapfile = join(datadir,'projects-override',"%s.rdf" % pid)
    print("Updating projects.xml")
    found = 0
    source = None
    with open(xmlfile,'r') as r, open(xmlfilet,'w') as w:
        for l in r:
            m = re.search("^(\s+)<location>(.+)<",l)
            if m:
                indent = m.group(1)
                url = m.group(2)
                # match one of:
                # http://svn.apache.org/repos/asf/tomee/tomee/trunk/doap_tomee.rdf
                # https://gitbox.apache.org/repos/asf?p=trafficserver.git;
                # http://zookeeper.apache.org/doap.rdf
                regex = "(repos/asf/%s/|p=%s\.git|^https?://%s\.apache)" % (pid,pid,pid)
                if re.search(regex,url,flags=re.IGNORECASE):
                    print("Found %s at %s" % (pid,url))
                    l = l.replace('<location>','<!-- retired: location>').replace('</location>','</location -->')
                    w.write(l) # write the original line
                    w.write("%s<location>%s/%s.rdf</location>\n" % (indent, OVERRIDE_DIR, pid))
                    found += 1
                    source = url
                    continue
            w.write(l) # write the original line
    if found != 1:
        print("Could not find a unique match for %s - found %d" % (pid,found))
    else:
        if re.search("//svn.apache.org/",source):
            os.system("svn cp %s %s" % (source.replace('http://','https://'), doapfile))
        else:
            os.system("wget -O %s '%s'" % (doapfile,source))
            os.system("svn add %s" % (doapfile))
            pass
        update_doap(doapfile, source)
        os.system("diff %s %s" % (xmlfile,xmlfilet))
        
        os.rename(xmlfilet,xmlfile)
        os.system("svn status %s" % dirname(doapfile))

for arg in sys.argv[1:]:
    print("Processing "+arg)
    if not re.search("^[-a-z0-9]+$",arg):
        print("Expecting lower-case, '-' or digits only")
    else:
        update_xml(arg)
