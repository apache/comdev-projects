import errtee
import sys
"""

Reads:
https://whimsy.apache.org/public/member_info.json
https://whimsy.apache.org/public/public_ldap_committees.json
https://whimsy.apache.org/public/public_ldap_groups.json
https://whimsy.apache.org/public/public_ldap_people.json
https://whimsy.apache.org/public/public_podling_status.json
https://whimsy.apache.org/public/public_ldap_projects.json

Creates:

../../site/json/foundation/people.json
- key: availid
  value: dict => {'groups': array, 'member': true/false, 'name': public name }

../../site/json/foundation/people_name.json

../../site/json/foundation/groups.json
- key: group name (-pmc suffix if relevant), value: array of availids
(partial inverse of people.json)

"""

import io
import json
from urlutils import UrlCache

uc = UrlCache(interval=0)

def loadJson(url):
    print("Reading " +url)
    resp = uc.get(url, name=None, encoding='utf-8', errors=None)
    try:
        content = resp.read() # json.load() does this anyway
        try:
            j = json.loads(content)
        except Exception as e:
            # The Proxy error response is around 4800 bytes
            print("Error parsing response:\n%s" % content[0:4800])
            raise e
    finally:
        resp.close()
    return j

people = {} # key: availid, value: array of groups to which the id belongs
groups = {} # key: group name (-pmc suffix if relevant), value: array of availids
people_name = {} # key: id, value: public name

def addPersonGroup(p, gname, gtype):
    if not p in ldappeople:
        print("ERROR: %s group '%s' has entry '%s' not in people LDAP group" % (gtype, gname, p), file=sys.stderr)
        name = '(Missing from LDAP people)'
    else:
        name = ldappeople[p]['name']
    # only add people to the name list if they are referenced
    if not p in people_name:
        people_name[p] = name
    if not p in people:
        people[p] = {'groups':[],
                     'member' : p in memberinfo,
                     'name': name
                     }
    return people[p]['groups']

# must be done first so the name can be used
ldappeople = loadJson('https://whimsy.apache.org/public/public_ldap_people.json')['people']
# Membership details also needed above
memberinfo = loadJson('https://whimsy.apache.org/public/member-info.json')['members']

# load the other required files
ldapgroups = loadJson('https://whimsy.apache.org/public/public_ldap_groups.json')['groups']
ldapprojects = loadJson('https://whimsy.apache.org/public/public_ldap_projects.json')['projects']
podlingstatus = loadJson('https://whimsy.apache.org/public/public_podling_status.json')['podling']

for g in ldapprojects:
    if not g == 'committers':
        members = ldapprojects[g]['members']
        groups[g] = members
        for p in members:
            addPersonGroup(p,g,'LDAP project').append(g)
        if g not in podlingstatus or podlingstatus[g] == 'graduated':
            owners = ldapprojects[g]['owners']
            groups[g+'-pmc'] = owners
            for p in owners:
                addPersonGroup(p,g,'LDAP committee').append(g+'-pmc')

# Other Unix groups (not all have been transferred yet)
for g in ldapgroups:
    if not g == 'committers' and not g == 'podlings' and not g in ldapprojects:
        groups[g] = ldapgroups[g]['roster']
        for p in ldapgroups[g]['roster']:
            addPersonGroup(p,g,'LDAP unix').append(g)

# Now sort the groups arrays
for p in people:
    people[p]['groups'].sort()

# Use utf-8 encoding for the file contents
print("Writing people.json")
with open("../../site/json/foundation/people.json", "w", encoding='utf-8') as f:
    json.dump(people, f, sort_keys=True, indent=0, ensure_ascii=False)
    f.close()

print("Writing people_name.json")
with open("../../site/json/foundation/people_name.json", "w", encoding='utf-8') as f:
    json.dump(people_name, f, sort_keys=True, indent=0, ensure_ascii=False)
    f.close()

print("Writing groups.json")
for g in groups:
    groups[g] = sorted(groups[g])
with open("../../site/json/foundation/groups.json", "w", encoding='utf-8') as f:
    json.dump(groups, f, sort_keys=True, indent=0, ensure_ascii=False)
    f.close()

print("All done!")