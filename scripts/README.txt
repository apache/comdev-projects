This directory contains Python 3 scripts for both importing and updating data from
various sources:

1. updating data (cronjobs)

- countaccounts.py: Extract from LDAP monthly statistics on Unix accounts created
  in:  site/json/foundation/accounts-evolution.json
     + https://whimsy.apache.org/public/public_ldap_people.json
  out: site/json/foundation/accounts-evolution.json (updated)

- parsecommitteeinfo.py: Parses committee-info.json to detect new and retired committees
  and imports PMC data (RDF) from PMC data files
  in: site/json/foundation/committees.json
    + site/json/foundation/committees-retired.json
    + https://whimsy.apache.org/public/committee-info.json (via committee_info.py)
    + data/committees.xml - list of where to find PMC description RDF files
    + data/committees/*.rdf - local PMC description RDF files
  out: site/json/foundation/committees.json (updated)
     + site/json/foundation/committees-retired.json (updated)

- parsecommitters.py: extracts the committer & group details as follows:
  in: https://whimsy.apache.org/public/member_info.json
    + https://whimsy.apache.org/public/public_ldap_people.json
    + https://whimsy.apache.org/public/public_podling_status.json
    + https://whimsy.apache.org/public/public_ldap_projects.json

  out: site/json/foundation/people.json - committers with reference to groups
     + site/json/foundation/people_name.json - converts availid to Public Name
     + site/json/foundation/groups.json - groups with corresponding committers
  TODO get this from LDAP, asf-authorization-template and Whimsy (committee-info.json) instead
  
- podlings.py: Reads podlings.xml from the incubator site and creates a JSON
  with history data, as well as current podling projects information.
  in: http://incubator.apache.org/podlings.xml
  out: site/json/foundation/podlings.json + site/json/foundation/podlings-history.json
  Current list of podlings (podlings.json) and ended podlings (podlings-history.json)

- parsereleases.py
  in: http://www.apache.org/dist/
  out: json/foundation/releases.json
     + json/foundation/releases-files.json

- parseprojects.py: Parses existing projects RDF(DOAP) files and turns them into JSON objects.
  in: data/projects.xml + projects' DOAP files
  out: site/json/projects/*.json - JSON versions of DOAP files
     + site/json/foundation/projects.json - combined listing of all projects
