#!/usr/bin/env python3
"""
Builds the projects.apache.org project and release data from the ASF
release catalog, which Tooling has designated the authoritative source:

    https://release-catalog.apache.org/project_releases.json

This replaces two older pipelines:
  - parseprojects.py  (data/projects.xml -> each project's DOAP file)
  - parsereleases.py  (scraping downloads.apache.org/zzz/find-ls2.txt.gz)

It writes the same files, in the same formats, so the web pages and
buildchooser.py need no changes:

  ../../site/json/foundation/projects.json   { id: project, ... }
  ../../site/json/projects/<id>.json         one project
  ../../site/json/foundation/releases.json   { committee: { "<name>-<version>": date } }
  ../../site/json/foundation/catalog-report.json  coverage/diff report (see below)

Still needed from elsewhere (the catalog doesn't carry these):
  committees.json / committees-retired.json  <- parsecommitteeinfo.py (Whimsy)
  people/groups                              <- parsecommitters.py (Whimsy)
  podlings                                   <- podlings.py (Incubator)

Usage:
  parsecatalog.py                 fetch the catalog and write everything
  parsecatalog.py --file X.json   use a local copy of the catalog (testing)
  parsecatalog.py --dry-run       report what would change; write nothing
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from os.path import dirname, join, realpath

CATALOG_URL = 'https://release-catalog.apache.org/project_releases.json'
# Podlings are in a separate file, keyed by podling id
PODLING_CATALOG_URL = 'https://release-catalog.apache.org/podling_releases.json'
# ATR's project list carries status (active / retired / standing), which the catalog lacks
ATR_LIST_URL = 'https://releases.apache.org/api/projects/list'

HOME = dirname(dirname(dirname(realpath(__file__))))
SITE = join(HOME, 'site')
FOUNDATION = join(SITE, 'json', 'foundation')
PROJECTS_DIR = join(SITE, 'json', 'projects')
CACHE = join(HOME, 'data', 'cache', 'project_releases.json')
PODLING_CACHE = join(HOME, 'data', 'cache', 'podling_releases.json')
ATR_CACHE = join(HOME, 'data', 'cache', 'atr_projects_list.json')

# Fields projects.js treats as lists
LIST_FIELDS = {'category', 'programming-language', 'repository', 'release', 'implements'}
# Fields stored as lists of plain strings that may arrive comma-separated
SPLIT_FIELDS = {'category', 'programming-language'}
# Placeholder values that mean "nothing known"
PLACEHOLDERS = {'new_category', 'no-tlp-doap', ''}
# Owners in the catalog that are not PMCs but are not retired either
NON_PMC_OWNERS = {'tooling'}


def load_json(path, default=None):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def fetch_catalog(local_file=None, url=CATALOG_URL, cache=CACHE, minimum=100):
    """Return the catalog dict. Falls back to the last good cached copy."""
    if local_file:
        return load_json(local_file)
    CATALOG_URL, CACHE = url, cache  # noqa: N806 (shadow the module names below)
    try:
        req = urllib.request.Request(CATALOG_URL, headers={'User-Agent': 'projects.apache.org'})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode('utf-8'))
        if not isinstance(data, dict) or len(data) < minimum:
            raise ValueError('catalog looks truncated (%d entries)' % len(data or {}))
        os.makedirs(dirname(CACHE), exist_ok=True)
        with open(CACHE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        return data
    except Exception as e:  # network trouble: keep yesterday's data rather than blanking the site
        print('WARN: could not fetch %s (%s); using cached copy' % (CATALOG_URL, e))
        data = load_json(CACHE)
        if data is None:
            if url != globals()['CATALOG_URL']:
                return {}        # podling file is optional
            sys.exit('ERROR: no catalog and no cached copy')
        return data


def fetch_atr_status():
    """Return {key: status} from ATR. Falls back to the cached copy; {} if none."""
    try:
        req = urllib.request.Request(ATR_LIST_URL, headers={'User-Agent': 'projects.apache.org'})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode('utf-8'))
        if len(data.get('projects', [])) < 100:
            raise ValueError('ATR list looks truncated')
        os.makedirs(dirname(ATR_CACHE), exist_ok=True)
        with open(ATR_CACHE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception as e:
        print('WARN: could not fetch %s (%s); using cached copy' % (ATR_LIST_URL, e))
        data = load_json(ATR_CACHE, {})
    return {p['key']: p.get('status') for p in data.get('projects', []) if p.get('key')}


def as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def canonical(values, valid):
    """Split comma-separated strings, drop placeholders, fix case against validation.json."""
    out = []
    for v in as_list(values):
        for part in str(v).split(','):
            part = part.strip()
            if part.lower() in PLACEHOLDERS:
                continue
            part = re.sub(r'https?://projects\.apache\.org/category/', '', part)
            part = valid.get(part.lower(), part)
            if part not in out:
                out.append(part)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--file', help='read the catalog from a local file instead of fetching it')
    ap.add_argument('--dry-run', action='store_true', help='report only; write nothing')
    args = ap.parse_args()

    catalog = fetch_catalog(args.file)
    atr_status = fetch_atr_status()
    # Current podlings come from the podling catalog, as incubator-<id>
    # (graduated/retired podlings are in it too; those are skipped)
    podlings = load_json(join(FOUNDATION, 'podlings.json'), {}) or {}
    podling_catalog = {} if args.file else fetch_catalog(url=PODLING_CATALOG_URL, cache=PODLING_CACHE, minimum=5)
    for pid, entry in (podling_catalog or {}).items():
        if pid in podlings and isinstance(entry, dict):
            entry = dict(entry, pmc='incubator')
            catalog['incubator-' + pid] = entry
    validation = load_json(join(SITE, 'validation.json'), {})
    valid_cats = {k.lower(): k for k in validation.get('categories', {})}
    valid_langs = {k.lower(): k for k in validation.get('languages', {})}
    committees = {c['id']: c for c in load_json(join(FOUNDATION, 'committees.json'), [])}
    retired = {c['id'] for c in load_json(join(FOUNDATION, 'committees-retired.json'), [])}
    old_projects = load_json(join(FOUNDATION, 'projects.json'), {})

    projects = {}
    releases = defaultdict(dict)
    warnings = []
    old_pmcs = defaultdict(int)   # pre-Whimsy retired committees mapped to attic

    for key, entry in sorted(catalog.items()):
        p = {k: v for k, v in entry.items() if v not in (None, '', [])}
        pmc = p.get('pmc') or key.split('-')[0]
        if pmc in NON_PMC_OWNERS:
            pass                      # real owner, just not a PMC (e.g. Tooling)
        elif pmc in retired or (committees and pmc not in committees and pmc not in ('attic', 'incubator')):
            # Retired committee. Some (avalon, java, xml, zest) retired before
            # Whimsy's retired list begins, so "not a current committee" counts too.
            if pmc not in retired:
                old_pmcs[pmc] += 1
            pmc = 'attic'
        p['pmc'] = pmc
        p['category'] = canonical(p.get('category'), valid_cats)
        status = atr_status.get(key) or ('retired' if pmc == 'attic' else 'active')
        if pmc == 'attic':
            status = 'retired'
        p['status'] = status             # active / retired / standing (from ATR)
        if status == 'retired' and 'retired' not in p['category']:
            p['category'].append('retired')
        p['programming-language'] = canonical(p.get('programming-language'), valid_langs)
        for k in LIST_FIELDS:
            if k in p and k not in SPLIT_FIELDS:
                p[k] = as_list(p[k])
        for k in list(p):
            if p[k] == []:
                del p[k]
        rel = sorted(as_list(p.get('release')), key=lambda r: r.get('created') or '', reverse=True)
        if rel:
            p['release'] = rel
        p['source'] = 'release-catalog'
        projects[key] = p

        # releases.json keeps its old shape, keyed by committee (podlings as incubator-<id>)
        rkey = pmc
        if pmc == 'incubator':
            rkey = 'incubator-' + re.sub(r'^incubator-', '', key)
        for r in rel:
            if r.get('created'):
                rid = '%s-%s' % (re.sub(r'^Apache ', '', r.get('name') or p.get('name', key)).replace(' ', '-'),
                                 r.get('revision', ''))
                releases[rkey][rid] = r['created'][:10]

        if 'name' not in p:
            warnings.append('%s: no name' % key)

    # Committees with no catalog entry still need a stub, as parseprojects.py did
    have = {p['pmc'] for p in projects.values()}
    for cid, c in committees.items():
        if cid not in have and cid not in projects:
            cname = c.get('name') or cid.capitalize()
            if not cname.startswith('Apache '):
                cname = 'Apache ' + cname
            projects[cid] = {'name': cname,
                             'homepage': c.get('homepage') or 'https://%s.apache.org' % cid,
                             'pmc': cid, 'category': ['no-catalog-entry'], 'source': 'committees.json'}

    added = sorted(set(projects) - set(old_projects))
    dropped = sorted(set(old_projects) - set(projects))
    report = {
        'catalog_entries': len(catalog),
        'projects_written': len(projects),
        'stub_committees': sorted(k for k, v in projects.items() if v.get('source') != 'release-catalog'),
        'new_ids': added,
        'dropped_ids': dropped,
        'pre_whimsy_retired_to_attic': dict(old_pmcs),
        'status_counts': {s: sum(1 for p in projects.values() if p.get('status') == s)
                          for s in sorted({p.get('status') for p in projects.values() if p.get('status')})},
        'retired_in_active_committees': sorted(k for k, p in projects.items()
                                               if p.get('status') == 'retired' and p['pmc'] != 'attic'),
        'warnings': warnings,
    }
    print('Catalog entries: %d; projects: %d; stubs: %d; new ids: %d; dropped ids: %d; warnings: %d'
          % (len(catalog), len(projects), len(report['stub_committees']), len(added), len(dropped), len(warnings)))
    if old_pmcs:
        print('Moved to attic (committee not current, not in retired list):',
              ', '.join('%s (%d)' % kv for kv in sorted(old_pmcs.items())))
    if dropped:
        print('Dropped ids (project pages that would disappear):', ', '.join(dropped[:40]),
              '...' if len(dropped) > 40 else '')
    if args.dry_run:
        print(json.dumps(report, indent=1)[:4000])
        return

    def dump(path, obj):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(obj, f, sort_keys=True, indent=0, ensure_ascii=False)

    os.makedirs(PROJECTS_DIR, exist_ok=True)
    for key, p in projects.items():
        dump(join(PROJECTS_DIR, key + '.json'), p)
    for f in os.listdir(PROJECTS_DIR):
        if f.endswith('.json') and f[:-5] not in projects:
            print('Deleting obsolete projects/%s' % f)
            os.remove(join(PROJECTS_DIR, f))
    dump(join(FOUNDATION, 'projects.json'), projects)
    dump(join(FOUNDATION, 'releases.json'), releases)
    dump(join(FOUNDATION, 'catalog-report.json'), report)
    print('Done.')


if __name__ == '__main__':
    main()
