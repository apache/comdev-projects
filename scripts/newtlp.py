#!/usr/bin/env python3

"""

Reads:
data/committees/_template.rdf
committee-info.txt from Whimsy

Updates:
data/committees.xml

Creates:
data/committees/<pmc>.rdf

"""

import sys
import os.path
from string import Template
import re
import committee_info

# extract committees composition
print("Reading committee-info")
committees = committee_info.committees()

datadir = os.path.join(committee_info.COMDEV_HOME,'data')
rdfdir = os.path.join(datadir,'committees')


print("Reading _template.rdf")
tmpfile = os.path.join(rdfdir,'_template.rdf')
with open(tmpfile,'r') as t:
    template = Template(t.read())


def update_xml(pid):
    xmlfile = os.path.join(datadir,'committees.xml')
    xmlfilet = os.path.join(datadir,'committees.xml.t')
    print("Updating committees.xml")
    notYetFound = True
    with open(xmlfile,'r') as r, open(xmlfilet,'w') as w:
        for l in r:
            if notYetFound:
                m = re.search("^(\s+)<location>committees/(.+)\.rdf<",l)
                if m:
                    indent = m.group(1)
                    mid = m.group(2)
                    if mid > pid: # found insertion point
                        w.write("%s<location>committees/%s.rdf</location>\n" % (indent, pid))
                        notYetFound = False
                    elif mid == pid:
                        print("ERROR: File already contains %s" % pid)
                else:
                    if l.startswith("</list"): # EOF
                        w.write("%s<location>committees/%s.rdf</location>\n" % (indent, pid))
                        notYetFound = False
            w.write(l) # write the original line
    os.rename(xmlfilet,xmlfile)

for arg in sys.argv[1:]:
    print("Processing "+arg)
    try:
        cttee = committees[arg]
        data = {
            "id": arg,
            "site": cttee['site'],
            "fullname": cttee['fullname'],
            "description": cttee['description'],
        }
        out = template.substitute(data)
        outfile = os.path.join(rdfdir,"%s.%s"%(arg,'rdf'))
        print("Creating "+outfile)
        with open(outfile,'w') as o:
            o.write(out)
        update_xml(arg)
    except KeyError:
        print("Cannot find "+arg)