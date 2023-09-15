#!/usr/bin/env python3

# @(#) update create.html from JSON files

import os
import json
import re

# This currently reads data at load time
import committee_info
SITEDIR = os.path.join(committee_info.COMDEV_HOME, 'site')

validation = {}
with open(os.path.join(SITEDIR, "validation.json"), encoding='utf-8') as f:
    validation = json.loads(f.read())
lang = validation['languages']
cats = validation['categories']

createfile = os.path.join(SITEDIR, "create.html")
createfilet = os.path.join(SITEDIR, "create.html.t")
sections = 0
with open(createfile,'r', encoding='utf-8') as r, open(createfilet,'w', encoding='utf-8') as w:
    section = None
    line = 0
    for l in r:
        # start of a section?
        m = re.match(r'^\s+<select name="(cat|lang|pmc)"', l)
        if m:
            section = m.group(1)
            line = 0
            sections += 1
         # end of section, dump its data
        if section and '</select>' in l:
            if section == 'cat':
                for k, v in cats.items():
                    w.write(f'        <option value="{k}">{v}</option>\n')
            elif section == 'lang':
                for k, v in lang.items():
                    w.write(f'        <option value="{k}">{v}</option>\n')
            elif section == 'pmc':
                lastcap = ''
                for k,v in sorted(committee_info.pmcnames().items()):
                    cap = k[0].upper()
                    if cap != lastcap:
                        w.write(f"\n      <!-- {cap} -->\n")
                        lastcap = cap
                    w.write(f'        <option value="{k}">{v}</option>\n')
            else:
                print(f"unrecognised section {section}")
            section = None
            line = 0
        if section:
            line = line + 1
            if re.match(r'^\s*<option value="\w', l): # an existing option line
                continue # drop the line
            if section == 'pmc':
                if re.match("      <!-- [A-Z] -->", l) or (re.match(r"\s*$", l) and line > 2):
                    continue
        w.write(l) # write the original line
os.rename(createfilet, createfile)
assert sections == 3, f"Expected to find 3 sections, found {sections}"
print(f"All done, saw {sections} sections")
