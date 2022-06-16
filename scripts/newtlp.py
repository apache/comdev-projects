#!/usr/bin/env python3

"""
Creates the initial RDF for a new TLP

Reads:
data/committees/_template.rdf
committee-info.json from Whimsy

Updates:
data/committees.xml

Creates:
data/committees/<pmc>.rdf

"""

import sys
import os.path
import os
from string import Template
import re

if len(sys.argv) == 1:
    print("Please provide a list of project ids")
    sys.exit(1)

# This currently reads data at load time
import committee_info

# extract committees composition
print("Reading committee-info")
committees = committee_info.committees()

DATADIR = os.path.join(committee_info.COMDEV_HOME,'data')
RDFDIR = os.path.join(DATADIR,'committees')
RETIREDDIR = os.path.join(DATADIR,'committees-retired')
OVERRIDEDIR = os.path.join(DATADIR,'projects-override')


print("Reading _template.rdf")
tmpfile = os.path.join(RDFDIR,'_template.rdf')
with open(tmpfile,'r') as t:
    template = Template(t.read())


def update_xml(pid):
    xmlfile = os.path.join(DATADIR,'committees.xml')
    xmlfilet = os.path.join(DATADIR,'committees.xml.t')
    print("Updating committees.xml")
    notYetFound = True
    with open(xmlfile,'r') as r, open(xmlfilet,'w') as w:
        for l in r:
            if notYetFound:
                m = re.search("^(\\s+)<location>committees/(.+)\\.rdf<",l)
                if m:
                    indent = m.group(1)
                    mid = m.group(2)
                    if mid > pid: # found insertion point
                        w.write("%s<location>committees/%s.rdf</location>\n" % (indent, pid))
                        notYetFound = False
                    elif mid == pid:
                        print("ERROR: committees.xml already contains %s" % pid)
                        w.close()
                        os.remove(xmlfilet)
                        return
                else:
                    if l.startswith("</list"): # EOF
                        w.write("%s<location>committees/%s.rdf</location>\n" % (indent, pid))
                        notYetFound = False
            w.write(l) # write the original line
    os.rename(xmlfilet,xmlfile)

for arg in sys.argv[1:]:
    print("Processing "+arg)
    outfile = os.path.join(RDFDIR,"%s.%s"%(arg,'rdf'))
    if os.path.exists(outfile):
        print("RDF file for %s already exists!" % arg)
        continue
    oldrdf = os.path.join(RETIREDDIR,"%s.%s"%(arg,'rdf'))
    if os.path.exists(oldrdf):
        print("%s exists - sorry cannot handle exit from Attic" % oldrdf)
        continue
    oldrdf = os.path.join(OVERRIDEDIR,"%s.%s"%(arg,'rdf'))
    if os.path.exists(oldrdf):
        print("%s exists - sorry cannot handle exit from Attic" % oldrdf)
        continue
    try:
        cttee = committees[arg]
        if cttee['description']:
            data = {
                "id": arg,
                "site": cttee['site'],
                "fullname": cttee['fullname'],
                "description": cttee['description'],
            }
            out = template.substitute(data)
            print("Creating "+outfile)
            with open(outfile,'w') as o:
                o.write(out)
            os.system("svn add %s" % outfile)
            update_xml(arg)
        else:
            print("No description found for "+arg)
    except KeyError:
        print("Cannot find "+arg)

os.system("svn diff %s" % DATADIR)