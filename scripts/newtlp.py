#!/usr/bin/env python3

"""
Creates the initial RDF for a new TLP

Reads:
data/committees/_template.rdf
committee-info.json from Whimsy

Updates:
data/committees.xml
site/create.html

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
SITEDIR = os.path.join(committee_info.COMDEV_HOME,'site')


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

# <select name="pmc">
# ...
# <!-- B -->
# <option value="bahir">Bahir</option>
# ...
# </select>
def update_html(pid, name):
    FILE='create.html'
    htmlfile = os.path.join(SITEDIR,FILE)
    htmlfilet = os.path.join(SITEDIR,FILE+'.t')
    cap = pid[0:1].upper()
    print(f"Updating {FILE} to add {pid} under {cap}")
    notYetFound = True
    with open(htmlfile,'r') as r, open(htmlfilet,'w') as w:
        foundCap = False # look for the starting comment for the letter of the alphabet
        for l in r:
            w.write(l)
            if f"<!-- {cap} -->" in l:
                foundCap = True
                break
        if not foundCap:
            print(f"ERROR: {FILE} does not contain <!-- %s -->" % cap)
            w.close()
            os.remove(htmlfilet)
            return
        for l in r:
            if notYetFound:
                m = re.search("^(\\s+)<option value=\"(.+)\">", l)
                if m:
                    indent = m.group(1)
                    mid = m.group(2)
                    if mid > pid: # found insertion point
                        w.write("%s<option value=\"%s\">%s</option>\n" % (indent, pid, name))
                        notYetFound = False
                    elif mid == pid:
                        print(f"ERROR: {FILE} already contains %s" % pid)
                        w.close()
                        os.remove(htmlfilet)
                        return
                    else:
                        # print(l)
                        pass
                else:
                    if re.search("^\s*(</select>\s*)$", l): # EOS
                        w.write("%s<option value=\"%s\">%s</option\n" % (indent, pid, name))
                        notYetFound = False
            w.write(l) # write the original line
    os.rename(htmlfilet,htmlfile)

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
            update_html(arg, cttee['fullname'].replace('Apache ', ''))
        else:
            print("No description found for "+arg)
    except KeyError:
        print("Cannot find "+arg)

os.system("svn diff %s" % DATADIR)
