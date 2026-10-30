#!/usr/bin/env python3
"""
buildchooser.py - build the data behind the "Help me choose a project" page.

Reads the per-project JSON that the other cronjobs already generate and
writes a single file, site/json/foundation/chooser.json, containing:

  * "questions": the question set, with only those options that actually
    match at least MIN_OPTION_PROJECTS projects (so the tree adapts to the data)
  * "projects":  one compact record per active project/podling, with the
    facet values each question filters on

Nothing here is hand-maintained per project: when a PMC updates its DOAP
(programming-language, category, description), the next nightly run of
parseprojects.py + this script picks it up.

in:  site/json/foundation/projects.json
     site/json/foundation/committees.json
     site/json/foundation/podlings.json
     site/json/foundation/releases.json
     site/json/foundation/groups.json
out: site/json/foundation/chooser.json

Usage: python3 buildchooser.py   (run after parseprojects.py / parsereleases.py)
"""

import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
JSON = os.path.join(HERE, '..', '..', 'site', 'json', 'foundation')
OUT = os.path.join(JSON, 'chooser.json')

MIN_OPTION_PROJECTS = 3   # hide answers that would match fewer projects

# ---------------------------------------------------------------------------
# Normalisation tables. Edit these, not the per-project data.
# ---------------------------------------------------------------------------

LANGUAGES = {   # DOAP value (lowercase) -> bucket label
    'java': 'Java', 'jdbc': 'Java', 'groovy': 'Java',
    'scala': 'Scala',
    'python': 'Python',
    'c': 'C / C++', 'c++': 'C / C++', 'objective-c': 'C / C++',
    'javascript': 'JavaScript / TypeScript', 'typescript': 'JavaScript / TypeScript',
    'node.js': 'JavaScript / TypeScript',
    'go': 'Go', 'rust': 'Rust', 'c#': 'C# / .NET', 'ruby': 'Ruby',
    'perl': 'Perl', 'php': 'PHP', 'erlang': 'Erlang', 'r': 'R',
    'sql': 'SQL', 'lua': 'Lua',
}

# Interest areas: matched against DOAP categories AND description keywords,
# because categories alone are sparse.
AREAS = [
    ('Big data & analytics', ['big-data', 'hadoop', 'data-engineering'],
     r'\b(big data|analytics|olap|data lake|lakehouse|batch processing|warehouse)'),
    ('Databases & storage', ['database', 'nosql', 'sql', 'distributed-sql-database'],
     r'\b(database|key[/-]value|storage|nosql|sql engine|query engine)'),
    ('Streaming & messaging', [],
     r'\b(stream|messag|event[- ]driven|pub/?sub|queue|broker)'),
    ('Machine learning & AI', [],
     r'\b(machine learning|deep learning|\bml\b|\bai\b|neural|llm|inference|model training)'),
    ('Web, HTTP & APIs', ['web-framework', 'http', 'httpd-module', 'javaee'],
     r'\b(web framework|http|rest\b|api gateway|web application|servlet)'),
    ('Cloud & infrastructure', ['cloud', 'virtual-machine', 'observability'],
     r'\b(cloud|kubernetes|container|orchestrat|cluster management|monitoring|observability)'),
    ('Build, testing & dev tools', ['build-management', 'testing', 'ide'],
     r'\b(build tool|build system|testing|test framework|\bide\b|compiler)'),
    ('Content, search & documents', ['content', 'search', 'xml', 'html', 'templating'],
     r'\b(search|content management|document|\bpdf\b|\bxml\b|template|office)'),
    ('IoT & edge', ['iot', 'mobile'], r'\b(iot|internet of things|edge|device|embedded|mobile)'),
    ('Security & identity', ['security', 'identity-management', 'identity-provisioning'],
     r'\b(security|authenticat|authoriz|identity|crypto|encryption)'),
    ('Geospatial & science', ['geospatial', 'graphics', 'data-visualization'],
     r'\b(geospatial|spatial|gis\b|scientific|visuali[sz]ation|graphics)'),
    ('Integration & workflow', ['integration'],
     r'\b(integration|workflow|scheduler|\betl\b|pipeline|orchestration)'),
]

KINDS = [   # (label, categories, description regex)
    ('A library or framework I embed in my code', ['library', 'web-framework', 'xml'],
     r'\b(library|framework|toolkit|sdk|api)\b'),
    ('A server or platform I run', ['network-server', 'database', 'cloud', 'big-data'],
     r'\b(server|platform|engine|service|system)\b'),
    ('A tool I use from the command line or IDE', ['build-management', 'testing', 'ide', 'network-client'],
     r'\b(tool|command[- ]line|cli\b|plugin)'),
]

SKIP_CATEGORIES = {'retired'}

# ---------------------------------------------------------------------------


def load(name):
    with open(os.path.join(JSON, name), encoding='utf-8') as f:
        return json.load(f)


def as_list(v):
    if not v:
        return []
    if isinstance(v, str):
        v = v.split(',')
    return [s.strip() for s in v if s and s.strip()]


def classify(cats, text, table):
    text = text.lower()
    out = []
    for label, catlist, rx in table:
        if set(cats) & set(catlist) or (rx and re.search(rx, text)):
            out.append(label)
    return out


def size_bucket(n):
    if n is None:
        return None
    if n < 25:
        return 'small'
    if n < 70:
        return 'medium'
    return 'large'


def activity_bucket(last, today):
    if not last:
        return 'quiet'
    days = (today - last).days
    if days <= 180:
        return 'very'
    if days <= 540:
        return 'active'
    return 'quiet'


def main():
    projects = load('projects.json')
    committees = {c['id']: c for c in load('committees.json')}
    podlings = load('podlings.json')
    releases = load('releases.json')
    groups = load('groups.json')
    today = datetime.date.today()

    def last_release(key):
        dates = []
        for d in (releases.get(key) or {}).values():
            try:
                dates.append(datetime.date.fromisoformat(d[:10]))
            except (ValueError, TypeError):
                pass
        return max(dates) if dates else None

    # The release catalog has one entry per releasable component (100+ for
    # Maven or Sling). A newcomer chooses a community, not a plugin, so keep
    # one entry per committee: the one keyed by the committee id, else the
    # one with the most releases. Podlings are their own committee here.
    def owner(pid, p):
        pmc = p.get('pmc', '')
        return pid if pmc == 'incubator' else pmc
    best = {}
    for pid, p in projects.items():
        if p.get('status') == 'retired':
            continue                    # never pick a retired component as the committee's entry
        o = owner(pid, p)
        rels = p.get('release') or []
        score = (pid == o, len(rels) if isinstance(rels, list) else 1, -len(pid))
        if o not in best or score > best[o][0]:
            best[o] = (score, pid)
    keep = {pid for _, pid in best.values()}
    projects = {pid: p for pid, p in projects.items() if pid in keep}

    records = []
    seen_pmcs = set()
    for pid, p in projects.items():
        cats = [c.lower() for c in as_list(p.get('category'))]
        pmc = p.get('pmc', '')
        if (SKIP_CATEGORIES & set(cats) or pid.startswith('attic-') or pmc == 'attic'
                or p.get('status') == 'retired'):
            continue
        if pmc not in committees and pmc != 'incubator':
            continue      # retired committee
        seen_pmcs.add(pmc)
        text = ' '.join(str(p.get(k) or '') for k in ('name', 'shortdesc', 'description'))
        langs = sorted({LANGUAGES.get(l.lower(), 'Other')
                        for l in as_list(p.get('programming-language'))})
        committers = len(groups.get(pmc, [])) or None
        est = (committees.get(pmc) or {}).get('established', '')
        rel = last_release(pmc) or last_release(pid)   # newest release of anything the committee ships
        records.append({
            'id': pid,
            'name': p.get('name', pid),
            'desc': (p.get('shortdesc') or p.get('description') or '').strip()[:300],
            'homepage': p.get('homepage'),
            'pmc': pmc,
            'language': langs,
            'area': classify(cats, text, AREAS),
            'kind': classify(cats, text, KINDS),
            'maturity': ['incubating'] if pmc == 'incubator' else
                        (['young'] if est and est[:4] >= str(today.year - 5) else ['established']),
            'size': [size_bucket(committers)] if committers else [],
            'activity': [activity_bucket(rel, today)],
            'lastRelease': rel.isoformat() if rel else None,
            'committers': committers,
        })

    # Podlings without a DOAP: description-only record
    for pid, p in podlings.items():
        if any(r['id'] == pid or r['id'] == 'incubator-' + pid for r in records):
            continue
        text = (p.get('name') or '') + ' ' + (p.get('description') or '')
        records.append({
            'id': pid, 'name': p.get('name', pid),
            'desc': ' '.join((p.get('description') or '').split())[:300],
            'homepage': p.get('homepage'), 'pmc': 'incubator', 'podling': True,
            'language': [], 'area': classify([], text, AREAS), 'kind': classify([], text, KINDS),
            'maturity': ['incubating'], 'size': [], 'activity': [],
            'lastRelease': None, 'committers': None,
        })

    def opts(field, labels):
        res = []
        for value, label in labels:
            n = sum(1 for r in records if value in r[field])
            if n >= MIN_OPTION_PROJECTS:
                res.append({'value': value, 'label': label, 'count': n})
        return res

    lang_labels = sorted({l for r in records for l in r['language']} - {'Other'})
    # Order matters: the page asks the first two in this order, then picks
    # the rest adaptively. Problems first; code is just one way to help.
    questions = [
        {'id': 'area', 'text': 'What kind of problems do you enjoy working on?',
         'multi': True, 'options': opts('area', [(a[0], a[0]) for a in AREAS])},
        # Not a filter: every project needs all of these. It shapes which
        # later questions are asked and the "how to get started" advice.
        {'id': 'contribute', 'text': 'How would you like to contribute?',
         'multi': True, 'filter': False, 'options': [
             {'value': 'code', 'label': 'Writing code'},
             {'value': 'docs', 'label': 'Documentation and tutorials'},
             {'value': 'users', 'label': 'Helping users and answering questions'},
             {'value': 'testing', 'label': 'Testing, bug reports and release verification'},
             {'value': 'design', 'label': 'Design, UX and websites'},
             {'value': 'translate', 'label': 'Translation and localisation'},
             {'value': 'outreach', 'label': 'Talks, blog posts, events and outreach'},
             {'value': 'unsure', 'label': "I'm not sure yet"},
         ]},
        {'id': 'language', 'text': 'Which programming languages are you comfortable in?',
         'multi': True, 'requires': {'contribute': ['code']},
         'options': opts('language', [(l, l) for l in lang_labels] + [('Other', 'Something else')])},
        {'id': 'kind', 'text': 'What sort of software do you want to work on?',
         'multi': True, 'options': opts('kind', [(k[0], k[0]) for k in KINDS])},
        {'id': 'size', 'text': 'What size of community appeals to you?', 'multi': False,
         'options': opts('size', [('small', 'Small - where every contribution is noticed'),
                                  ('medium', 'Medium'),
                                  ('large', 'Large - lots of people to learn from')])},
        {'id': 'maturity', 'text': 'Do you prefer a new project or an established one?', 'multi': False,
         'options': opts('maturity', [('incubating', 'Brand new (in the Incubator)'),
                                      ('young', 'Young - graduated in the last 5 years'),
                                      ('established', 'Established and battle-tested')])},
        {'id': 'activity', 'text': 'How busy should the project be?', 'multi': False,
         'options': opts('activity', [('very', 'Very active - released in the last 6 months'),
                                      ('active', 'Active - released in the last 18 months'),
                                      ('quiet', 'Quieter - could use new energy')])},
    ]
    questions = [q for q in questions if len(q['options']) >= 2]

    out = {'generated': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
           'questions': questions,
           'projects': sorted(records, key=lambda r: r['name'].lower())}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, sort_keys=False)
    print('Wrote %s: %d projects, %d questions' % (OUT, len(records), len(questions)),
          file=sys.stderr)


if __name__ == '__main__':
    main()
