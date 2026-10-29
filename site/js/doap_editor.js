/*
 * doap_editor.js - client-side DOAP editor for create.html
 *
 *  - "Load an existing project" fills the form from a project's current DOAP
 *    (fetched directly; falls back to json/projects/<id>.json from this site).
 *  - Every DOAP element that may repeat (repository, release,
 *    standard, bug-database, download-page, mailing-list) is a repeatable group
 *    with "+ Add another" / remove buttons.
 *  - doap:maintainer is deliberately not supported: Apache projects are run
 *    by their PMC, not by named maintainers. It is dropped when loading.
 *  - Categories and languages are checkbox lists built from the hidden
 *    <select>s, which scripts/update_create.py still maintains.
 *  - The DOAP XML below the form is rebuilt on every change.
 */

var DOAP_NS = 'http://usefulinc.com/ns/doap#';
var RDF_NS = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#';
var ASFEXT_NS = 'http://projects.apache.org/ns/asfext#';
var FOAF_NS = 'http://xmlns.com/foaf/0.1/';

var keep = { created: null, license: null, about: null };   // preserved from a loaded file

function F() { return document.make_doap; }
function $(id) { return document.getElementById(id); }

function xmlEsc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function makeURL(s) {
    s = (s || '').trim();
    if (!s) return '';
    return /^(https?|mailto):/.test(s) ? s : 'https://' + s;
}
function stripScheme(s) { return (s || '').replace(/^https?:\/\//, ''); }
function today() { return new Date().toISOString().slice(0, 10); }

/* ------------------------------------------------------------------ */
/* Repeatable groups                                                  */
/* ------------------------------------------------------------------ */

// field: [key, label, size, type]  type 'select-repo' / 'select-std' / 'date'
var GROUPS = {
    repo:       [['type', '', 0, 'select-repo'], ['location', 'Location', 40], ['browse', 'Web view', 40]],
    bugdb:      [['url', '', 60]],
    dl:         [['url', '', 60]],
    mail:       [['url', '', 60]],
    release:    [['name', 'Name', 22], ['created', 'Date', 10, 'date'], ['revision', 'Version', 10]],
    standard:   [['title', 'Title', 22], ['body', 'Body', 0, 'select-std'], ['id', 'ID', 10], ['url', 'URL', 24]]
};

function addRow(group, values) {
    values = values || {};
    var box = document.querySelector('.repeat[data-group="' + group + '"]');
    var row = document.createElement('div');
    row.className = 'row';
    GROUPS[group].forEach(function (fd) {
        var key = fd[0], label = fd[1], size = fd[2], type = fd[3], el;
        if (type === 'select-repo') {
            el = document.createElement('select');
            ['GitRepository', 'SVNRepository'].forEach(function (t) {
                var o = document.createElement('option'); o.value = t; o.textContent = t.replace('Repository', ''); el.appendChild(o);
            });
            el.value = values.type || 'GitRepository';
        } else if (type === 'select-std') {
            el = $('std_body_tpl').cloneNode(true);
            el.removeAttribute('id'); el.style.display = '';
            el.value = values.body || '';
            if (values.body && el.value !== values.body) {     // keep unknown standards bodies
                var o = document.createElement('option'); o.value = o.textContent = values.body; el.appendChild(o); el.value = values.body;
            }
        } else {
            el = document.createElement('input');
            el.type = 'text'; el.size = size;
            if (type === 'date') el.placeholder = 'YYYY-MM-DD';
            el.value = values[key] || '';
        }
        el.setAttribute('data-key', key);
        if (label) {
            var l = document.createElement('label'); l.textContent = label + ' '; l.appendChild(el); row.appendChild(l);
        } else row.appendChild(el);
    });
    var rm = document.createElement('button');
    rm.type = 'button'; rm.className = 'rm'; rm.title = 'Remove'; rm.textContent = '\u2715';
    rm.onclick = function () { row.remove(); ensureOneRow(group); changed(); };
    row.appendChild(rm);
    box.appendChild(row);
    return row;
}

function ensureOneRow(group) {
    var box = document.querySelector('.repeat[data-group="' + group + '"]');
    if (!box.querySelector('.row')) addRow(group);
}

function rows(group) {
    var out = [];
    document.querySelectorAll('.repeat[data-group="' + group + '"] .row').forEach(function (row) {
        var v = {}, any = false;
        row.querySelectorAll('[data-key]').forEach(function (el) {
            v[el.getAttribute('data-key')] = el.value.trim();
            if (el.tagName === 'INPUT' && el.value.trim()) any = true;
        });
        if (any) out.push(v);
    });
    return out;
}

function setRows(group, list) {
    document.querySelector('.repeat[data-group="' + group + '"]').innerHTML = '';
    (list || []).forEach(function (v) { addRow(group, v); });
    ensureOneRow(group);
}

/* ------------------------------------------------------------------ */
/* Checkbox lists (categories, languages)                             */
/* ------------------------------------------------------------------ */

function buildChecks(name) {
    var sel = F()[name], box = document.querySelector('.checks[data-for="' + name + '"]');
    box.innerHTML = '';
    for (var i = 0; i < sel.options.length; i++) {
        var o = sel.options[i];
        if (!o.value) continue;
        var l = document.createElement('label'), c = document.createElement('input');
        c.type = 'checkbox'; c.value = o.value; c.setAttribute('data-check', name);
        l.appendChild(c); l.appendChild(document.createTextNode(' ' + o.textContent));
        box.appendChild(l);
    }
}

function checked(name) {
    var out = [];
    document.querySelectorAll('input[data-check="' + name + '"]:checked').forEach(function (c) { out.push(c.value); });
    return out;
}

// returns values that weren't in the standard list (they are added, marked, and kept)
function setChecked(name, values) {
    var extra = [];
    var all = document.querySelectorAll('input[data-check="' + name + '"]');
    all.forEach(function (c) { c.checked = false; if (c.parentNode.classList.contains('extra')) c.parentNode.remove(); });
    values.forEach(function (v) {
        if (!v) return;
        var hit = null;
        document.querySelectorAll('input[data-check="' + name + '"]').forEach(function (c) {
            if (c.value.toLowerCase() === String(v).toLowerCase()) hit = c;
        });
        if (!hit) {
            var l = document.createElement('label'); l.className = 'extra'; l.title = 'Not in the standard list';
            hit = document.createElement('input'); hit.type = 'checkbox'; hit.value = v; hit.setAttribute('data-check', name);
            l.appendChild(hit); l.appendChild(document.createTextNode(' ' + v + ' *'));
            document.querySelector('.checks[data-for="' + name + '"]').appendChild(l);
            extra.push(v);
        }
        hit.checked = true;
    });
    return extra;
}

/* ------------------------------------------------------------------ */
/* Generate DOAP XML                                                  */
/* ------------------------------------------------------------------ */

function buildDoap() {
    var f = F(), L = [];
    var homepage = makeURL(f.homepage.value) || 'https://www.apache.org';
    var tag = function (t, v) { L.push('    <' + t + '>' + xmlEsc(v) + '</' + t + '>'); };
    var res = function (t, v) { L.push('    <' + t + ' rdf:resource="' + xmlEsc(v) + '" />'); };

    L.push('<?xml version="1.0"?>');
    L.push('<?xml-stylesheet type="text/xsl"?>');
    L.push('<rdf:RDF xml:lang="en"');
    L.push('         xmlns="http://usefulinc.com/ns/doap#"');
    L.push('         xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"');
    L.push('         xmlns:asfext="http://projects.apache.org/ns/asfext#"');
    L.push('         xmlns:foaf="http://xmlns.com/foaf/0.1/">');
    L.push('<!--');
    L.push('    Licensed to the Apache Software Foundation (ASF) under one or more');
    L.push('    contributor license agreements.  See the NOTICE file distributed with');
    L.push('    this work for additional information regarding copyright ownership.');
    L.push('    The ASF licenses this file to You under the Apache License, Version 2.0');
    L.push('    (the "License"); you may not use this file except in compliance with');
    L.push('    the License.  You may obtain a copy of the License at');
    L.push('');
    L.push('         https://www.apache.org/licenses/LICENSE-2.0');
    L.push('');
    L.push('    Unless required by applicable law or agreed to in writing, software');
    L.push('    distributed under the License is distributed on an "AS IS" BASIS,');
    L.push('    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.');
    L.push('    See the License for the specific language governing permissions and');
    L.push('    limitations under the License.');
    L.push('-->');
    L.push('  <Project rdf:about="' + xmlEsc(keep.about || homepage) + '">');
    tag('created', keep.created || today());
    res('license', keep.license || 'https://spdx.org/licenses/Apache-2.0');
    if (f.name.value.trim()) tag('name', 'Apache ' + f.name.value.trim());
    res('homepage', homepage);
    if (f.pmc.value) res('asfext:pmc', 'https://' + f.pmc.value + '.apache.org');
    if (f.sdesc.value.trim()) tag('shortdesc', f.sdesc.value.trim());
    if (f.ldesc.value.trim()) tag('description', f.ldesc.value.trim());
    rows('bugdb').forEach(function (r) { res('bug-database', makeURL(r.url)); });
    rows('mail').forEach(function (r) { res('mailing-list', makeURL(r.url)); });
    rows('dl').forEach(function (r) { res('download-page', makeURL(r.url)); });
    checked('lang').forEach(function (v) { tag('programming-language', v); });
    checked('cat').forEach(function (v) { res('category', 'https://projects.apache.org/category/' + v); });

    rows('release').forEach(function (r) {
        L.push('    <release>');
        L.push('      <Version>');
        if (r.name) L.push('        <name>' + xmlEsc(r.name) + '</name>');
        if (r.created) L.push('        <created>' + xmlEsc(r.created) + '</created>');
        if (r.revision) L.push('        <revision>' + xmlEsc(r.revision) + '</revision>');
        L.push('      </Version>');
        L.push('    </release>');
    });
    rows('repo').forEach(function (r) {
        L.push('    <repository>');
        L.push('      <' + r.type + '>');
        if (r.location) L.push('        <location rdf:resource="' + xmlEsc(makeURL(r.location)) + '"/>');
        if (r.browse) L.push('        <browse rdf:resource="' + xmlEsc(makeURL(r.browse)) + '"/>');
        L.push('      </' + r.type + '>');
        L.push('    </repository>');
    });
    rows('standard').forEach(function (s) {
        L.push('    <asfext:implements><asfext:Standard>');
        if (s.title) L.push('      <asfext:title>' + xmlEsc(s.title) + '</asfext:title>');
        if (s.body) L.push('      <asfext:body>' + xmlEsc(s.body) + '</asfext:body>');
        if (s.id) L.push('      <asfext:id>' + xmlEsc(s.id) + '</asfext:id>');
        if (s.url) L.push('      <asfext:url rdf:resource="' + xmlEsc(makeURL(s.url)) + '"/>');
        L.push('    </asfext:Standard></asfext:implements>');
    });
    L.push('  </Project>');
    L.push('</rdf:RDF>');
    return L.join('\n') + '\n';
}

function doapFileName() {
    return 'doap_' + ((F().name.value.trim() || 'projectName').replace(/[^\w-]/g, '_')) + '.rdf';
}

var lastLines = null;

// Render the DOAP text one line per span, briefly highlighting lines that
// differ from the previous render. Changed lines are found by trimming the
// common prefix and suffix, so an inserted line doesn't flag everything below it.
function renderOutput(text) {
    var out = $('doap_output'), lines = text.replace(/\n$/, '').split('\n');
    var pre = 0, suf = 0;
    if (lastLines) {
        while (pre < lines.length && pre < lastLines.length && lines[pre] === lastLines[pre]) pre++;
        while (suf < lines.length - pre && suf < lastLines.length - pre &&
               lines[lines.length - 1 - suf] === lastLines[lastLines.length - 1 - suf]) suf++;
    }
    var first = null;
    out.innerHTML = lines.map(function (l, i) {
        var hot = lastLines && i >= pre && i < lines.length - suf;
        return '<span class="ln' + (hot ? ' flash' : '') + '">' + xmlEsc(l) + '</span>';
    }).join('');
    lastLines = lines;
    // keep the first changed line in view, without moving the page itself
    first = out.querySelector('.ln.flash');
    if (first && (first.offsetTop < out.scrollTop || first.offsetTop > out.scrollTop + out.clientHeight - 20))
        out.scrollTop = first.offsetTop - out.clientHeight / 3;
}

function changed() {
    renderOutput(buildDoap());
    $('doap_filename').textContent = doapFileName();
    document.querySelectorAll('td.selsum').forEach(function (td) {
        var v = checked(td.getAttribute('data-sel'));
        td.innerHTML = v.length ? '<b>Selected (' + v.length + '):</b><br>' + v.map(xmlEsc).join(', ') : '<i>None selected</i>';
    });
    updateHints();
    if ($('publish')) updateNextSteps();
}

/* ------------------------------------------------------------------ */
/* Suggestions column                                                 */
/* ------------------------------------------------------------------ */

function reEsc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

function hintVars() {
    var f = F(), pmc = f.pmc.value;
    var pmcLabel = pmc ? f.pmc.options[f.pmc.selectedIndex].text : '';
    var name = f.name.value.trim();
    var rest = pmcLabel ? name.replace(new RegExp('^' + reEsc(pmcLabel) + '\\s*', 'i'), '') : name;
    var sub = rest.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    if (sub === pmc) { sub = ''; rest = ''; }
    return {
        pmc: pmc || '[committee]', sub: sub,
        repo: (pmc || '[committee]') + (sub ? '-' + sub : ''),
        Name: 'Apache ' + (pmcLabel || '[Committee]') + (rest ? ' ' + rest : (name ? '' : ' [Subproject]'))
    };
}

function hintText(el, v) {
    return el.getAttribute('data-tpl').replace('{sub/}', v.sub ? v.sub + '/' : '')
        .replace('{pmc}', v.pmc).replace('{repo}', v.repo).replace('{Name}', v.Name);
}

// where a hint would go: plain field, or first empty matching cell of a group
function hintTarget(el) {
    var parts = el.getAttribute('data-for').split('.');
    if (parts.length === 1) return { el: F()[parts[0]] };
    var type = el.getAttribute('data-type'), cells = [];
    document.querySelectorAll('.repeat[data-group="' + parts[0] + '"] .row').forEach(function (row) {
        var t = row.querySelector('[data-key="type"]');
        if (type && t && t.value !== type) return;
        cells.push(row.querySelector('[data-key="' + parts[1] + '"]'));
    });
    return { cells: cells, group: parts[0], key: parts[1], type: type };
}

function updateHints() {
    var v = hintVars();
    document.querySelectorAll('code.hint').forEach(function (el) {
        var t = hintText(el, v), tg = hintTarget(el), used;
        el.textContent = t;
        if (tg.el) used = el.getAttribute('data-for') === 'name' || tg.el.value.trim() === stripScheme(t) || tg.el.value.trim() === t;
        else used = tg.cells.some(function (c) { return makeURL(c.value) === t; });
        el.classList.toggle('used', used || /\[/.test(t));
    });
}

function useHint(el) {
    if (el.classList.contains('used')) return;
    var t = el.textContent, tg = hintTarget(el);
    if (tg.el) tg.el.value = tg.el.name === 'homepage' ? stripScheme(t) : t;
    else {
        var cell = tg.cells.filter(function (c) { return !c.value.trim(); })[0];
        if (!cell) cell = addRow(tg.group, tg.type ? { type: tg.type } : {}).querySelector('[data-key="' + tg.key + '"]');
        cell.value = t;
    }
    changed();
}

/* ------------------------------------------------------------------ */
/* Load an existing project                                           */
/* ------------------------------------------------------------------ */

function emptyRecord() {
    return { name: '', pmc: '', homepage: '', about: '', shortdesc: '', description: '', bugdb: [], mail: [], dl: [],
             langs: [], cats: [], releases: [], repos: [], maintainers: [], standards: [], created: '', license: '' };
}
function catId(v) { return String(v || '').replace(/^.*\/category\//, '').replace(/\/$/, '').trim(); }
function pmcId(v) { var m = String(v || '').match(/^https?:\/\/([^.\/]+)\.apache\.org/i); return m ? m[1] : String(v || '').trim(); }

function recordFromDoap(text) {
    var doc = new DOMParser().parseFromString(text, 'application/xml');
    if (doc.getElementsByTagName('parsererror').length) throw new Error('not valid XML');
    var p = doc.getElementsByTagNameNS(DOAP_NS, 'Project')[0];
    if (!p) throw new Error('no doap:Project element');
    var R = emptyRecord();
    var kids = function (el, ns, name) {
        var out = [];
        for (var c = el.firstElementChild; c; c = c.nextElementSibling)
            if (c.namespaceURI === ns && c.localName === name) out.push(c);
        return out;
    };
    var txt = function (el, ns, name) { var k = kids(el, ns, name)[0]; return k ? k.textContent.trim() : ''; };
    var rsrc = function (el) { return el ? (el.getAttributeNS(RDF_NS, 'resource') || el.textContent.trim()) : ''; };
    var all = function (ns, name) { return kids(p, ns, name).map(rsrc).filter(Boolean); };

    R.about = p.getAttributeNS(RDF_NS, 'about') || '';
    R.name = txt(p, DOAP_NS, 'name');
    R.homepage = all(DOAP_NS, 'homepage')[0] || '';
    R.pmc = pmcId(all(ASFEXT_NS, 'pmc')[0]);
    R.shortdesc = txt(p, DOAP_NS, 'shortdesc');
    R.description = txt(p, DOAP_NS, 'description');
    R.bugdb = all(DOAP_NS, 'bug-database');
    R.mail = all(DOAP_NS, 'mailing-list');
    R.dl = all(DOAP_NS, 'download-page');
    R.created = txt(p, DOAP_NS, 'created');
    R.license = all(DOAP_NS, 'license')[0] || '';
    kids(p, DOAP_NS, 'programming-language').forEach(function (e) { R.langs.push(e.textContent.trim()); });
    kids(p, DOAP_NS, 'category').forEach(function (e) { R.cats.push(catId(rsrc(e))); });
    kids(p, DOAP_NS, 'release').forEach(function (rel) {
        var v = rel.firstElementChild; if (!v) return;
        R.releases.push({ name: txt(v, DOAP_NS, 'name'), created: txt(v, DOAP_NS, 'created'), revision: txt(v, DOAP_NS, 'revision') });
    });
    kids(p, DOAP_NS, 'repository').forEach(function (rep) {
        var v = rep.firstElementChild; if (!v) return;
        R.repos.push({ type: v.localName, location: rsrc(kids(v, DOAP_NS, 'location')[0]), browse: rsrc(kids(v, DOAP_NS, 'browse')[0]) });
    });
    R.maintainers = kids(p, DOAP_NS, 'maintainer');
    kids(p, ASFEXT_NS, 'implements').forEach(function (i) {
        var v = i.firstElementChild; if (!v) return;
        R.standards.push({ title: txt(v, ASFEXT_NS, 'title'), body: txt(v, ASFEXT_NS, 'body'),
                           id: txt(v, ASFEXT_NS, 'id'), url: rsrc(kids(v, ASFEXT_NS, 'url')[0]) });
    });
    return R;
}

function recordFromJson(j) {
    var R = emptyRecord();
    var list = function (v) { return !v ? [] : Array.isArray(v) ? v : String(v).split(',').map(function (s) { return s.trim(); }).filter(Boolean); };
    R.name = j.name || ''; R.pmc = j.pmc || ''; R.homepage = j.homepage || '';
    R.shortdesc = j.shortdesc || ''; R.description = j.description || '';
    R.bugdb = list(j['bug-database']); R.mail = list(j['mailing-list']); R.dl = list(j['download-page']);
    R.created = j.created || ''; R.license = j.license || '';
    R.langs = list(j['programming-language']);
    R.cats = list(j.category).map(catId);
    R.releases = (j.release || []).map(function (r) { return { name: r.name || '', created: r.created || '', revision: r.revision || '' }; });
    R.repos = (j.repository || []).map(function (r) {
        if (typeof r === 'object') return { type: 'GitRepository', location: r.location || '', browse: r.browse || '' };
        return { type: /svn\.apache\.org/.test(r) ? 'SVNRepository' : 'GitRepository', location: r, browse: '' };
    });
    R.maintainers = (j.maintainer || []).map(function (m) { return { name: m.name || '', mbox: m.mbox || '' }; });
    R.standards = (j.implements || []).map(function (s) { return { title: s.title || '', body: s.body || '', id: s.id || '', url: s.url || '' }; });
    return R;
}

function fillForm(R) {
    var f = F(), notes = [];
    f.pmc.value = R.pmc;
    if (R.pmc && f.pmc.value !== R.pmc) notes.push('PMC "' + R.pmc + '" is not in the committee list');
    f.name.value = (R.name || '').replace(/^Apache\s+/i, '');
    f.homepage.value = stripScheme(R.homepage);
    f.sdesc.value = R.shortdesc;
    f.ldesc.value = R.description.replace(/^\s+|\s+$/g, '').replace(/\n\s+/g, '\n');
    var u = function (x) { return { url: x }; };
    setRows('bugdb', R.bugdb.map(u)); setRows('mail', R.mail.map(u)); setRows('dl', R.dl.map(u));
    setRows('repo', R.repos);
    setRows('release', R.releases.slice().sort(function (a, b) { return (b.created || '').localeCompare(a.created || ''); }));
    if (R.maintainers.length) notes.push('Removed ' + R.maintainers.length + ' maintainer entr' + (R.maintainers.length > 1 ? 'ies' : 'y') + ': Apache projects are run by their PMC, so this field is no longer used.');
    setRows('standard', R.standards);
    var x1 = setChecked('lang', R.langs), x2 = setChecked('cat', R.cats);
    if (x1.length || x2.length) notes.push('Not in the standard lists (kept, marked *): ' + x1.concat(x2).join(', '));
    keep = { created: R.created || null, license: R.license || null, about: R.about || null };
    return notes;
}

function loadProject(id) {
    var status = $('load_status');
    if (!id) return;
    status.textContent = 'Loading\u2026';
    fetch('json/projects/' + encodeURIComponent(id) + '.json')
        .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(function (j) {
            var fromJson = function (why) {
                var notes = fillForm(recordFromJson(j));
                notes.unshift('Loaded from this site\'s nightly copy (' + why + '). Repository types and web-view URLs may be missing; check them.');
                done(notes, j.doap, false);
            };
            if (!j.doap) return fromJson('no DOAP URL on record');
            fetch(j.doap)
                .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); })
                .then(function (t) { done(fillForm(recordFromDoap(t)), j.doap, true); })
                .catch(function (e) { fromJson('could not read the DOAP file directly: ' + e.message); });
        })
        .catch(function (e) { status.textContent = 'Could not load project: ' + e.message; });

    function done(notes, url, live) {
        status.innerHTML = (live ? 'Loaded from ' : 'Original DOAP: ') +
            '<a href="' + xmlEsc(url) + '">' + xmlEsc(url) + '</a>' +
            (notes.length ? '<ul><li>' + notes.map(xmlEsc).join('</li><li>') + '</li></ul>' : '');
        changed();
    }
}

var PROJECTS = {};

// PMC dropdown, from the nightly committees.json (current committees only).
// This replaces the list scripts/update_create.py used to write into create.html.
function populatePmcList(committees) {
    var sel = F().pmc, keepVal = sel.value;
    sel.innerHTML = '<option value=""></option>';
    var list = (committees || []).filter(function (c) { return c.id && c.id !== 'attic'; })
        .map(function (c) { return { id: c.id, name: shortName(c.name || c.id) }; });
    if (!list.some(function (c) { return c.id === 'incubator'; })) list.push({ id: 'incubator', name: 'Incubator' });
    list.sort(function (a, b) { return a.name.toLowerCase().localeCompare(b.name.toLowerCase()); });
    var group = null, letter = '';
    list.forEach(function (c) {
        var L = c.name.charAt(0).toUpperCase();
        if (L !== letter) { letter = L; group = document.createElement('optgroup'); group.label = L; sel.appendChild(group); }
        var o = document.createElement('option'); o.value = c.id; o.textContent = c.name; group.appendChild(o);
    });
    sel.value = keepVal;
}

function shortName(n) { return String(n || '').replace(/^Apache\s+/i, '').trim(); }

// Project name suggestions: the projects this site already knows for the chosen PMC.
// It's a datalist, so a brand-new subproject name can still be typed.
// create.html?project=<id>  -> load that project's DOAP for editing
// create.html?pmc=<id>[&podling=<id>]  -> start a new file with best guesses
function applyQuery() {
    var q = new URLSearchParams(location.search);
    var id = q.get('project'), pmc = q.get('pmc'), pod = q.get('podling');
    if (id) {
        if (!PROJECTS[id] && PROJECTS[id.replace(/^incubator-/, '')]) id = id.replace(/^incubator-/, '');
        if (PROJECTS[id] && PROJECTS[id].doap) {
            $('load_project').value = id; loadProject(id); updateGuessBox(); setTimeout(updateNameList, 500);
            return;
        }
        pmc = pmc || (PROJECTS[id] && PROJECTS[id].pmc) || id;   // no DOAP after all: guess instead
        if (pmc === 'incubator') pod = pod || id;
    }
    if (pmc) {
        F().pmc.value = pmc;
        if (pmc === 'incubator' && pod) $('podling_pick').value = pod;
        updateGuessBox(); updateNameList();
        if (guessTarget()) fillGuesses();
    }
}

// Tailor the "Publish your file" section: existing file -> where to update it;
// new file -> put it on the website, then register it in projects.xml
function updateNextSteps() {
    var id = $('load_project').value, p = PROJECTS[id] || {}, f = F(), pmc = f.pmc.value;
    var url = id && p.doap ? p.doap : '';
    var gh = url.match(/^https:\/\/raw\.githubusercontent\.com\/apache\/([^\/]+)\/([^\/]+)\/(.+)$/);
    var gb = url.match(/gitbox\.apache\.org\/repos\/asf\?p=([^;]+)\.git;a=blob_plain;f=([^;]+)/);
    var edit = gh ? 'https://github.com/apache/' + gh[1] + '/edit/' + gh[2] + '/' + gh[3]
             : gb ? 'https://github.com/apache/' + gb[1] + '/blob/HEAD/' + gb[2] : '';

    $('pub_existing').style.display = url ? '' : 'none';
    $('pub_new').style.display = url ? 'none' : '';
    if (url) {
        $('pub_url').href = url; $('pub_url').textContent = url;
        $('pub_edit').innerHTML = edit ? ' (<a href="' + xmlEsc(edit) + '">open it on GitHub</a>)' : '';
    } else {
        var home = makeURL(f.homepage.value) || ('https://' + (pmc || '[committee]') + '.apache.org/');
        if (!/\/$/.test(home)) home += '/';
        var addr = home + doapFileName();
        $('pub_suggest').textContent = addr;
        $('pub_line').textContent = '  <location>' + addr + '</location>';
        var name = f.name.value.trim() ? 'Apache ' + f.name.value.trim() : 'our project';
        $('pub_ask').href = 'mailto:dev@community.apache.org?subject=' +
            encodeURIComponent('Please add the DOAP file for ' + name + ' to projects.apache.org') +
            '&body=' + encodeURIComponent('Hi,\n\nWe have published a DOAP file for ' + name + ' at:\n\n  ' + addr +
            '\n\nCould someone add it to data/projects.xml?\n\nThanks!\n');
    }

    var list = pmc === 'incubator' ? ($('podling_pick').value || (id || '').replace(/^incubator-/, '')) : pmc;
    var dom = list && list !== 'incubator' ? list + (pmc === 'incubator' ? '.incubator' : '') + '.apache.org' : '';
    $('next_dev').innerHTML = dom ? ' (<a href="mailto:dev@' + xmlEsc(dom) + '">dev@' + xmlEsc(dom) + '</a>)' : '';
    $('next_pr').innerHTML = edit ? ', or <a href="' + xmlEsc(edit) + '">suggest the change on GitHub</a>' : '';
}

function updateNameList() {
    var pmc = F().pmc.value, dl = $('name_list'), note = $('name_note');
    dl.innerHTML = '';
    if (!pmc) { note.textContent = ''; return; }
    var key = pmc === 'incubator' ? $('podling_pick').value : null;
    var names = Object.keys(PROJECTS).filter(function (k) {
        var p = PROJECTS[k];
        if ((p.category || []).indexOf('retired') >= 0 || k.indexOf('attic-') === 0) return false;
        return pmc === 'incubator' ? (key ? k === key : p.pmc === 'incubator') : p.pmc === pmc;
    }).map(function (k) { return { id: k, name: shortName(PROJECTS[k].name || k), doap: !!PROJECTS[k].doap }; })
      .sort(function (a, b) { return a.name.localeCompare(b.name); });
    names.forEach(function (n) {
        var o = document.createElement('option'); o.value = n.name;
        if (n.doap) o.label = 'has a DOAP file';
        dl.appendChild(o);
    });
    var typed = F().name.value.trim().toLowerCase();
    var hit = names.filter(function (n) { return n.name.toLowerCase() === typed; })[0];
    note.innerHTML = !names.length ? 'No known projects for this committee - type a name.'
        : hit && hit.doap && !$('load_project').value
            ? xmlEsc(hit.name) + ' already has a DOAP file. <a href="#" id="name_load">Load it instead</a>?'
        : names.length + ' known project' + (names.length > 1 ? 's' : '') + ' for this committee - pick one, or type a new subproject name.';
    var l = $('name_load');
    if (l) l.onclick = function (e) { e.preventDefault(); $('load_project').value = hit.id; loadProject(hit.id); updateGuessBox(); };
}   // json/foundation/projects.json + podlings, keyed by id

function populateProjectList() {
    var sel = $('load_project');
    Promise.all([
        fetch('json/foundation/projects.json').then(function (r) { return r.json(); }),
        fetch('json/foundation/podlings.json').then(function (r) { return r.json(); }).catch(function () { return {}; }),
        fetch('json/foundation/committees.json').then(function (r) { return r.json(); })
    ]).then(function (res) {
        var p = res[0], pods = res[1];
        populatePmcList(res[2]);
        Object.keys(pods).forEach(function (k) {
            if (!p[k] && !p['incubator-' + k]) p[k] = { name: pods[k].name, homepage: pods[k].homepage, pmc: 'incubator',
                                                       podling: true, description: pods[k].description, category: [] };
        });
        PROJECTS = p;
        Object.keys(p).filter(function (k) {
            return p[k].doap && (p[k].category || []).indexOf('retired') < 0 && k.indexOf('attic-') !== 0;
        }).sort(function (a, b) { return shortName(p[a].name || a).localeCompare(shortName(p[b].name || b)); })
          .forEach(function (k) {
              var o = document.createElement('option'); o.value = k; o.textContent = shortName(p[k].name || k); sel.appendChild(o);
          });
        // podlings with no DOAP, for the Incubator guess picker
        var pp = $('podling_pick');
        Object.keys(p).filter(function (k) { return p[k].podling && !p[k].doap; })
            .sort(function (a, b) { return (p[a].name || a).localeCompare(p[b].name || b); })
            .forEach(function (k) {
                var o = document.createElement('option'); o.value = k; o.textContent = shortName(p[k].name || k); pp.appendChild(o);
            });
        updateGuessBox();
        updateNameList();
        applyQuery();
    }).catch(function (e) { $('load_status').textContent = 'Could not load project list: ' + e.message; });
}

/* ------------------------------------------------------------------ */
/* Best guesses for a project with no DOAP file                       */
/* ------------------------------------------------------------------ */

function getJSON(url) {
    return fetch(url).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .catch(function () { return null; });
}

// e.g. "apache-kvrocks-2.10.0" -> "2.10.0", "apache-foo-1.2.0-incubating" -> "1.2.0-incubating"
function versionFrom(name) {
    var m = String(name).match(/-(v?\d+(?:\.\d+)*(?:[-.][A-Za-z0-9]+)*)$/);
    return m ? m[1].replace(/^v/, '') : name;
}

function guessRecord(id) {
    var p = PROJECTS[id] || {}, pmc = p.pmc || id, isPod = !!p.podling;
    var key = isPod ? id : pmc;     // name used for repos, lists, dist
    return Promise.all([
        getJSON('json/foundation/committees.json'),
        getJSON('json/foundation/repositories.json'),
        getJSON('json/foundation/releases.json'),
        getJSON('https://api.github.com/repos/apache/' + encodeURIComponent(key) + '/languages')
    ]).then(function (res) {
        var c = (res[0] || []).filter(function (x) { return x.id === pmc; })[0] || {};
        var repos = res[1] || {}, rels = (res[2] || {})[id] || (res[2] || {})[key] || {}, gh = res[3];
        var R = emptyRecord(), guessed = [];
        var home = (p.homepage || c.homepage || 'https://' + key + (isPod ? '.incubator' : '') + '.apache.org').replace(/\/?$/, '/');

        R.name = p.name || c.name || 'Apache ' + id;
        R.pmc = pmc;
        R.homepage = home;
        R.shortdesc = c.shortdesc || '';
        R.description = p.description || c.charter || '';
        if (R.shortdesc) guessed.push('short description (from the committee record)');
        if (!p.description && c.charter) guessed.push('long description (from the PMC charter - reword it to describe the software)');

        // repositories: every gitbox repo named key or key-*, website repos last
        Object.keys(repos).filter(function (r) { return r === key || r.indexOf(key + '-') === 0; })
            .sort(function (a, b) { return (/site|website/.test(a) - /site|website/.test(b)) || a.localeCompare(b); })
            .forEach(function (r) {
                R.repos.push({ type: /svn\.apache\.org/.test(repos[r]) ? 'SVNRepository' : 'GitRepository',
                               location: repos[r], browse: 'https://github.com/apache/' + r });
            });
        if (R.repos.length) guessed.push(R.repos.length + ' repositor' + (R.repos.length > 1 ? 'ies' : 'y') + ' (remove any that aren\'t part of this project)');

        R.bugdb = ['https://github.com/apache/' + key + '/issues'];
        R.mail = [home + 'community/'];
        R.dl = [home + 'download/'];
        guessed.push('bug tracker, download and mailing list URLs (conventional paths - check they exist; many projects use JIRA)');

        // releases from dist.apache.org, newest 5
        var rl = Object.keys(rels).map(function (n) { return { name: R.name, created: rels[n], revision: versionFrom(n) }; })
            .sort(function (a, b) { return b.created.localeCompare(a.created); });
        R.releases = rl.slice(0, 5);
        if (rl.length) guessed.push('the ' + R.releases.length + ' newest of ' + rl.length + ' releases found on dist.apache.org');

        if (gh) {
            var total = 0; Object.keys(gh).forEach(function (l) { total += gh[l]; });
            // languages making up at least 5% of the main repo, per GitHub
            R.langs = Object.keys(gh).filter(function (l) { return gh[l] / total >= 0.05; })
                .filter(function (l) { return ['Shell', 'Makefile', 'CMake', 'Dockerfile', 'HTML', 'CSS', 'Batchfile'].indexOf(l) < 0; });
            if (R.langs.length) guessed.push('languages (from GitHub\'s statistics for apache/' + key + ')');
        }
        R.created = (c.established ? c.established + '-01' : '') || '';
        return { record: R, guessed: guessed };
    });
}

/* ------------------------------------------------------------------ */
/* Guess box under the PMC select (new DOAP files)                    */
/* ------------------------------------------------------------------ */

// which project would we guess for, given the current PMC choice?
function guessTarget() {
    var pmc = F().pmc.value;
    if (!pmc) return null;
    if (pmc === 'incubator') return $('podling_pick').value || null;
    return pmc;
}

function updateGuessBox() {
    var pmc = F().pmc.value, box = $('guess_box');
    // only offer guesses when we're not editing a loaded DOAP
    box.style.display = (pmc && !$('load_project').value) ? '' : 'none';
    $('podling_wrap').style.display = pmc === 'incubator' ? '' : 'none';
    var t = guessTarget(), p = PROJECTS[t] || {};
    $('guess_btn').disabled = !t;
    $('guess_note').textContent = !t ? 'Choose a podling first.'
        : p.doap ? 'Note: this project already has a DOAP file - you probably want to load it above instead.'
        : 'Fills in the form from foundation records, dist.apache.org and GitHub.';
}

function fillGuesses() {
    var id = guessTarget(), status = $('load_status');
    if (!id) return;
    if (!PROJECTS[id]) PROJECTS[id] = { pmc: F().pmc.value };
    status.textContent = 'Gathering best guesses\u2026';
    guessRecord(id).then(function (g) {
        var pmcKeep = F().pmc.value, podKeep = $('podling_pick').value;
        var notes = fillForm(g.record);
        F().pmc.value = pmcKeep; $('podling_pick').value = podKeep;
        keep.created = null;   // a new file: created = today
        notes.unshift('These are best guesses for a new DOAP file. Check every field, and pick categories yourself. Guessed: ' + g.guessed.join('; ') + '.');
        status.innerHTML = '<b>New DOAP file for ' + xmlEsc(g.record.name) + '</b><ul><li>' + notes.map(xmlEsc).join('</li><li>') + '</li></ul>';
        changed();
        updateGuessBox();
    });
}

function resetForm() {
    F().reset();
    keep = { created: null, license: null, about: null };
    Object.keys(GROUPS).forEach(function (g) { setRows(g, []); });
    setChecked('lang', []); setChecked('cat', []);
    $('load_project').value = '';
    $('load_status').textContent = '';
    $('podling_pick').value = '';
    changed();
    updateGuessBox();
    updateNameList();
}

function copyDoap() {
    var text = buildDoap();
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject())
        .catch(function () {
            var t = document.createElement('textarea');
            t.value = text; document.body.appendChild(t); t.select();
            document.execCommand('copy'); document.body.removeChild(t);
        });
    var b = $('copy_btn'), old = b.value;
    b.value = 'Copied!'; setTimeout(function () { b.value = old; }, 1500);
}

function downloadDoap() {
    var blob = new Blob([buildDoap()], { type: 'application/rdf+xml' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = doapFileName();
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
}

document.addEventListener('DOMContentLoaded', function () {
    var f = F();
    buildChecks('cat'); buildChecks('lang');
    Object.keys(GROUPS).forEach(ensureOneRow);
    document.querySelectorAll('button.add').forEach(function (b) {
        b.addEventListener('click', function () { addRow(b.getAttribute('data-add')).querySelector('input,select').focus(); changed(); });
    });
    document.querySelectorAll('code.hint').forEach(function (el) {
        el.addEventListener('click', function () { useHint(el); });
    });
    // one delegated listener covers static fields, checkboxes and added rows
    f.addEventListener('input', changed);
    f.addEventListener('change', changed);
    f.addEventListener('click', function (e) { if (e.target.type === 'checkbox') setTimeout(changed, 0); });
    $('load_project').addEventListener('change', function () { loadProject(this.value); updateGuessBox(); setTimeout(updateNameList, 500); changed(); });
    f.pmc.addEventListener('change', function () { updateGuessBox(); updateNameList(); });
    $('podling_pick').addEventListener('change', function () { updateGuessBox(); updateNameList(); });
    f.name.addEventListener('input', updateNameList);
    $('guess_btn').addEventListener('click', fillGuesses);
    populateProjectList();
    changed();
});
