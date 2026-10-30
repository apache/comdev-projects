This directory contains Python 3 scripts for both importing and updating data from
various sources:

1. updating data (cronjobs)

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

- parsecatalog.py: builds project and release data from the ASF release catalog,
  which Tooling has designated the authoritative source. Replaces the old
  parseprojects.py and parsereleases.py. Until the crontab (Infra's P6 repo) is
  updated, those names are kept as shims: parseprojects.py runs parsecatalog.py
  then buildchooser.py; parsereleases.py does nothing.
  Edit project metadata in ATR: https://releases.apache.org/projects/<key>?tab=metadata
  (or via the project: metadata: block in .asf.yaml).
  Run after parsecommitteeinfo.py (uses committees.json / committees-retired.json).
  in: https://release-catalog.apache.org/project_releases.json
    + https://release-catalog.apache.org/podling_releases.json (current podlings, as incubator-<id>)
    + site/json/foundation/committees.json, committees-retired.json
    + site/validation.json (category/language spellings)
  out: site/json/projects/*.json - one file per catalog key
     + site/json/foundation/projects.json - combined listing
     + site/json/foundation/releases.json - { committee: { name-version: date } }
     + site/json/foundation/catalog-report.json - new/dropped ids, stubs, warnings
  Options: --dry-run (write nothing), --file X.json (use a local catalog copy)

- parsereleases.py (superseded by parsecatalog.py)
  in: http://www.apache.org/dist/
  out: json/foundation/releases.json
     + json/foundation/releases-files.json

- parseprojects.py (superseded by parsecatalog.py): Parses existing projects RDF(DOAP) files and turns them into JSON objects.
  in: data/projects.xml + projects' DOAP files
  out: site/json/projects/*.json - JSON versions of DOAP files
     + site/json/foundation/projects.json - combined listing of all projects
     + site/json/foundation/accounts-evolution2.json

- buildchooser.py: builds the data for the "Help me choose a project" page (site/chooser.html).
  Question options are derived from the data, so the question tree updates as PMCs edit DOAPs.
  Run after parsecatalog.py. Keeps one entry per committee (podlings separately).
  in: site/json/foundation/{projects,committees,podlings,releases,groups}.json
  out: site/json/foundation/chooser.json
