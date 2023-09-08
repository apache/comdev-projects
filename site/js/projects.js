/*

   Licensed to the Apache Software Foundation (ASF) under one
   or more contributor license agreements.  See the NOTICE file
   distributed with this work for additional information
   regarding copyright ownership.  The ASF licenses this file
   to you under the Apache License, Version 2.0 (the
   "License"); you may not use this file except in compliance
   with the License.  You may obtain a copy of the License at

       https://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing,
   software distributed under the License is distributed on an
   "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
   KIND, either express or implied.  See the License for the
   specific language governing permissions and limitations
   under the License.

*/

// ----- Global hashes used throughout the script ------ \\

var people = {}; // committer -> name lookups
var unixgroups = {}; // unix (ldap) groups (project -> committers lookup)
var committees = {}; // id -> committee info (chair, established, group, homepage, id, name, reporting, shortdesc) (current committees)
var committeesByName = {}; // name -> committee info
var retiredCommittees = {}; // retired committees information: id -> committee info (established, retired, homepage, id, name)
var projects = {}; // Projects
var podlings = {}; // current podlings
var podlingsHistory = {}; // Podlings history (now graduated or retired)
var repositories = {}; // source repositories id -> url

// --------- Global helpers ----------- \\

function includeJs(jsFilePath) {
    var js = document.createElement("script");

    js.type = "text/javascript";
    js.src = jsFilePath;

    document.head.appendChild(js);
}

includeJs("js/underscore-min.js");

function GetAsyncJSON(theUrl, xstate, callback) {
    var xmlHttp = null;
    if (window.XMLHttpRequest) {
        xmlHttp = new XMLHttpRequest();
    } else {
        xmlHttp = new ActiveXObject("Microsoft.XMLHTTP");
    }
    xmlHttp.open("GET", theUrl, true);
    xmlHttp.send(null);
    xmlHttp.onreadystatechange = function(state) {
        if (xmlHttp.readyState == 4 && xmlHttp.status == 200 || xmlHttp.status == 404) {
            if (callback) {
                if (xmlHttp.status == 404) {
                    callback({}, xstate);
                } else {
                    callback(JSON.parse(xmlHttp.responseText), xstate);
                }
            }
        }
    }
}

var urlErrors = []
var fetchCount = 0;
// Fetch an array of URLs, each with their description and own callback plus a final callback
// Used to fetch everything before rendering a page that relies on multiple JSON sources.
function GetAsyncJSONArray(urls, finalCallback) {
    var obj = document.getElementById('progress');
    if (fetchCount == 0 ) {
        fetchCount = urls.length;
    }

    if (urls.length > 0) {
        var a = urls.shift();
        var URL = a[0];
        var desc = a[1];
        var cb = a[2];
        var xmlHttp = null;
        if (window.XMLHttpRequest) {
            xmlHttp = new XMLHttpRequest();
        } else {
            xmlHttp = new ActiveXObject("Microsoft.XMLHTTP");
        }

        if (obj) { obj.innerHTML = "loading file #" + ( fetchCount - urls.length ) + " / " + fetchCount + "<br>" + desc }

        xmlHttp.open("GET", URL, true);
        xmlHttp.onreadystatechange = function(state) {
            if (xmlHttp.readyState == 4) {
                if (cb) {
                    if (xmlHttp.status == 200) {
                        cb(JSON.parse(xmlHttp.responseText));
                    } else {
                        urlErrors.push(URL)
                        cb({});
                    }
                }
                GetAsyncJSONArray(urls, finalCallback);
            }
        }
        xmlHttp.send(null);
    }
    else {
        if (obj) { obj.innerHTML = "building page content..." }
        finalCallback();
    }
}

// See project_editor.js (not currently used)

// ------------ Project information page ------------\\

function linkCommitterIndex(cid) {
    var fullname = people[cid];
    var cl = isMember(cid) ? "member" : "committer";
    return "<a class='" + cl + "' title='" + cid + "' href='https://home.apache.org/phonebook.html?uid=" + cid + "' target='_blank'>" + fullname + "</a>";
}

function appendElementWithInnerHTML(obj,type,html) {
    var child = document.createElement(type);
    child.innerHTML = html;
    obj.appendChild(child);
    return child;
}

function appendLiInnerHTML(ul,html) {
    return appendElementWithInnerHTML(ul,'li',html);
}

function projectIdToUnixGroup(projectId, pmcName) {
    // Rerig the unix name and committee id
    var unixgroup = projectId.split("-")[0];
    /*
      Temp hack for podling names. TODO need to sort out generated names
    */
    if (projectId.indexOf("incubator-") === 0) {
      unixgroup = projectId.split("-")[1]
    }
    // special cases
    if (unixgroup === "empire") unixgroup = "empire-db";
    if (unixgroup === "community") unixgroup = "comdev";
    if (pmcName === "attic") {
      unixgroup = "attic";
    }
    return unixgroup;
}

function renderProjectPage(project, projectId) {
    var obj = document.getElementById('contents');

    if ((!project || !project.name) && projects[projectId]) {
        // no DOAP file but known project: podling (loaded from podlings.json)
        project = projects[projectId];
    }
    if (!project || !project.name) {
        obj.innerHTML = "<h2>Sorry, I don't have any information available about this project</h2>";
        return;
    }

    fixProjectName(project);
    var isIncubating = project && (project.podling || (project.pmc == 'incubator'));

    var unixgroup = projectIdToUnixGroup(projectId, project && project.pmc);

    var committeeId = isIncubating ? 'incubator' : unixgroup;
    if (!committees[unixgroup]) {
        // at least one committee has a unix group that is different from committee id: webservices (group=ws), see parsecommittees.py#group_ids
        // search instead of hard-coding the currently known case
        for (p in committees) {
            if (committees[p].group == unixgroup) {
                committeeId = p;
                break;
            }
        }
    }
    var committee = committees[committeeId];
    if (!committee) {
        obj.innerHTML = "<h2>Cannot find the PMC '" + committeeId + "' for this project. Check the DOAP is correct.</h2>";
        return;
    }

    // Start by splitting the name, thus fetching the root name of the project, and not the sub-project.
    var description = "";
    if (project) {
        if (!_.isEmpty(project.description)) {
            description = project.description;
        } else if (!_.isEmpty(project.shortdesc)) {
            description = project.shortdesc;
        } else if (!_.isEmpty(committee.shortdesc)) {
            description = committee.shortdesc;
        } else {
            description = "No description available";
        }
    }

    // Title + description
    obj.innerHTML = "<h1>" + project.name + " <font size='-1'>(a project managed by the <a href='committee.html?" + committeeId + "'>" + committee.name + " Committee</a>)</font></h1>";

    // project description
    appendElementWithInnerHTML(obj,'p',description.replace(/([^\r\n]+)\r?\n\r?\n/g,function(a) { return "<p>"+a+"</p>"}));

    var ul = document.createElement('ul');

    // Base data
    appendElementWithInnerHTML(obj,'h4',"Project base data:");

    if (project.description && project.shortdesc) {
        appendLiInnerHTML(ul, "<b>Short description:</b> " + project.shortdesc);
    }

    // Categories
    if (project.category) {
        var arr = project.category.split(/,\s*/);
        var pls = "";
        for (i in arr) {
            var cat = arr[i];
             // categories are downcased so fix up the anchor
            pls += "<a href='projects.html?category#" + cat.toLowerCase() + "'>" + cat + "</a> &nbsp; ";
        }
        appendLiInnerHTML(ul, "<b>Category:</b> " + pls);
    }

    // Website
    if (project.homepage) {
        appendLiInnerHTML(ul, "<b>Website:</b> <a href='" + project.homepage + "' target='_blank'>" + project.homepage + "</a>");
    }
    if (isIncubating) {
        appendLiInnerHTML(ul, "<b>Project status:</b> <span class='ppodling'>Incubating</span>");
    } else if (committeeId != 'attic') {
        appendLiInnerHTML(ul, "<b>Project status:</b> <span class='pactive'>Active</span>");
    } else {
        appendLiInnerHTML(ul, "<b>Project status:</b> <span class='pretired'>Retired</span>");
    }

    // Committers
    if (isIncubating && unixgroups[unixgroup]) {
        var commitl = [];
        var commitgroup = unixgroups[unixgroup];
        for (i in commitgroup) {
            commitl.push(linkCommitterIndex(commitgroup[i]));
        }
        appendLiInnerHTML(ul, "<b>Committers (" + commitgroup.length + "):</b> <blockquote>" + commitl.join(", &nbsp;") + "</blockquote>");
    }

    if (project.implements) {
        var stds = document.createElement('ul');
        var impl;
        for (impl in project.implements) {
            impl = project.implements[impl];
            var std = "";
            if (impl.body) {
                std += impl.body + ' ';
            }
            if (impl.id) {
                std += "<a href='" + impl.url + "'>" + impl.id + "</a>: " + impl.title;
            } else {
                std += "<a href='" + impl.url + "'>" + impl.title + "</a>";
            }
            appendLiInnerHTML(stds, std);
        }
        appendLiInnerHTML(ul, "<b>Implemented standards</b>").appendChild(stds);
    }

    // doap/rdf
    if (project.doap) {
        appendLiInnerHTML(ul, "<b>Project data file:</b> <a href='" + project.doap + "' target='_blank'>DOAP RDF Source</a> (<a href='json/projects/" + projectId + ".json'>generated json</a>)");
    } else {
        appendLiInnerHTML(ul, "<b>Project data file:</b> no <a href='https://projects.apache.org/create.html'>DOAP file</a> available");
    }
    // maintainer
    if (project.maintainer) {
        var mt;
        var maintainers = "";
        for (mt in project.maintainer) {
            mt = project.maintainer[mt];
            if (mt.mbox) {
                var id = mt.mbox;
                id = id.substr(id.indexOf(':') + 1);
                id = id.substr(0, id.indexOf('@'));
                if (people[id]) {
                    maintainers += linkCommitterIndex(id) + "&nbsp; ";
                } else {
                    maintainers += "<a href='" + mt.mbox + "'>" + mt.name + "</a>&nbsp; ";
                }
            } else {
                maintainers += mt.name + "&nbsp; ";
            }
        }
        appendLiInnerHTML(ul, "<b>Project data maintainer(s):</b> " + maintainers);
    }

    obj.appendChild(ul);

    // Code data
    appendElementWithInnerHTML(obj,'h4',"Development:");
    ul = document.createElement('ul');

    if (project['programming-language']) {
        var pl = project['programming-language'];
        var arr = pl.split(/,\s*/);
        var pls = "";
        for (i in arr) {
            pls += "<a href='projects.html?language#" + arr[i] + "'>" + arr[i] + "</a>&nbsp; ";
        }
        appendLiInnerHTML(ul, "<b>Programming language:</b> " + pls);
    }

    if (project['bug-database']) {
        var bd = project['bug-database'];
        var arr = bd.split(/,\s*/);
        var bds = "";
        for (i in arr) {
            bds += "<a href='" + arr[i] + "'>" + arr[i] + "</a>&nbsp; ";
        }
        appendLiInnerHTML(ul, "<b>Bug-tracking:</b> " + bds);
    }

    if (project['mailing-list']) {
        var ml = project['mailing-list'];
        var xml = ml;
        // email instead of link?
        if (ml.match(/@/)) {
            xml = "mailto:" + ml;
        }
        appendLiInnerHTML(ul, "<b>Mailing list(s):</b> <a href='" + xml + "'>" + ml + "</a>");
    }

    // repositories
    if (project.repository) {
        var r;
        for (r in project.repository) {
            r = project.repository[r];
            if (r.indexOf("svn") > 0) {
                appendLiInnerHTML(ul, "<b>Subversion repository:</b> <a target=*_blank' href='" + r + "'>" + r + "</a>");
            } else if (r.indexOf("git") > 0) {
                appendLiInnerHTML(ul, "<b>Git repository:</b> <a target=*_blank' href='" + r + "'>" + r + "</a>");
            } else {
                appendLiInnerHTML(ul, "<b>Repository:</b> <a target=*_blank' href='" + r + "'>" + r + "</a>");
            }
        }
    }

    obj.appendChild(ul);

    // releases
    appendElementWithInnerHTML(obj,'h4',"Releases <font size='-2'>(from DOAP)</font>:");
    ul = document.createElement('ul');
    if (project['download-page']) {
        appendLiInnerHTML(ul, "<b>Download:</b> <a href='" + project['download-page'] + "' target='_blank'>" + project['download-page'] + "</a>");
    }
    if (project.release) {
        project.release.sort(function(a,b){// reverse date order (most recent first)
            var ac = a.created ? a.created : '1970-01-01';
            var bc = b.created ? b.created : '1970-01-01';
            if(ac < bc) return 1;
            if(ac > bc) return -1;
            return 0;});
        var r;
        for (r in project.release) {
            r = project.release[r];
            var html = "<b>" + (r.revision ? r.revision : r.version) + "</b>";
            html += " (" + (r.created ? r.created : 'unknown') + ")";
            appendLiInnerHTML(ul, html + ": " + r.name);
        }
    }
    obj.appendChild(ul);
}


function buildProjectPage() {
    var projectId = document.location.search.substr(1);
    GetAsyncJSON("json/projects/" + projectId + ".json?" + Math.random(), projectId, renderProjectPage)
}

// extract committee name from repo name
function repoToCommittee(reponame) {
    if (reponame.startsWith('empire-db')) {
        return 'empire-db';
    }
    return reponame.split('-')[0];
}

function renderCommitteePage(committeeId) {
    var obj = document.getElementById('contents');

    if (!committees[committeeId]) {
        obj.innerHTML = "<h2>Sorry, I don't have any information available about this committee</h2>";
        return;
    }

    var unixgroup = committeeId; // there are probably a few exceptions...
    var committee = committees[committeeId];

    obj.innerHTML = "<h1>" + committee.name + " Committee <font size='-2'>(also called PMC or Top Level Project)</font></h1>";

    var description;
    if (!_.isEmpty(committee.shortdesc)) {
        description = committee.shortdesc;
    } else {
        description = "Missing from https://www.apache.org/#projects-list";
    }

    appendElementWithInnerHTML(obj, 'h4', "Description <font size='-2'>(from <a href='https://www.apache.org/#projects-list'>projects list</a>)</a>:");

    appendElementWithInnerHTML(obj,'p',description.replace(/([^\r\n]+)\r?\n\r?\n/g,function(a) { return "<p>"+a+"</p>"}));

    appendElementWithInnerHTML(obj, 'h4', "Charter <font size='-2'>(from PMC data file)</a>:");

    var charter;
    if (!_.isEmpty(committee.charter)) {
        charter = committee.charter;
    } else {
        charter = "Missing";
    }

    appendElementWithInnerHTML(obj,'p',charter.replace(/([^\r\n]+)\r?\n\r?\n/g,function(a) { return "<p>"+a+"</p>"}));

    var ul = document.createElement('ul');

    appendElementWithInnerHTML(obj, 'h4', "Committee data:");

    appendLiInnerHTML(ul, "<b>Website:</b> <a href='" + committee.homepage + "' target='_blank'>" + committee.homepage + "</a>");

    appendLiInnerHTML(ul, "<b>Committee established:</b> " + committee.established);

    // VP
    appendLiInnerHTML(ul, "<b>PMC Chair:</b> " + linkCommitterIndex(committee.chair));

    // Reporting cycle
    var cycles = ["every month", "January, April, July, October", "February, May, August, November", "March, June, September, December"];
    var minutes = committee.name.substr("Apache ".length).replace(/ /g, '_');
    // does not work for APR and Logging Services currently
    if (committeeId == 'apr') {
        minutes = 'Apr';
    } else if (committeeId == 'logging') {
        minutes = 'Logging';
    }
    appendLiInnerHTML(ul, "<b>Reporting cycle:</b> " + cycles[committee.reporting] + ", see <a href='https://whimsy.apache.org/board/minutes/" + minutes + ".html'>minutes</a>");

    // PMC
    if (committee.roster) { // check we have the data
        var pmcl = [];
        for (i in committee.roster) {
            pmcl.push(linkCommitterIndex(i));
        }
        if (pmcl.length > 0) {
            appendLiInnerHTML(ul, "<b>PMC Roster <font size='-1'>(from committee-info.txt)</font> (" + pmcl.length + "):</b> <blockquote>" + pmcl.join(",&nbsp; ") + "</blockquote>");
        } else {
            appendLiInnerHTML(ul, "<b>PMC Roster not found in committee-info.txt (check that Section 3 has been updated)</b>");
        }
    }

    // Committers
    if (unixgroups[unixgroup]) {
        var commitl = [];
        var commitgroup = unixgroups[unixgroup];
        for (i in commitgroup) {
            commitl.push(linkCommitterIndex(commitgroup[i]));
        }
        appendLiInnerHTML(ul, "<b>Committers (" + commitgroup.length + "):</b> <blockquote>" + commitl.join(",&nbsp; ") + "</blockquote>");
    }

    // rdf
    if (committee.rdf) {
        appendLiInnerHTML(ul, "<b>PMC data file:</b> <a href='" + committee.rdf + "' target='_blank'>RDF Source</a>");
    }

    obj.appendChild(ul);

    var subprojects = [];
    for (p in projects) {
        if (projects[p].pmc == committeeId) {
            subprojects.push(p);
        }
    }
    if (subprojects.length == 0) {
       if (committeeId != 'labs') {
           // if a committee did not declare any project, consider there is a default one with the id of the committee
            // only Labs doesn't manage projects
            subprojects.push({ 'id': committeeId, 'name': committee.name, 'pmc': committeeId });
        }
    } else {
        appendElementWithInnerHTML(obj, 'h4', "Projects managed by this Committee:");

        ul = document.createElement('ul');
        for (var p in subprojects.sort()) {
            p = subprojects[p];
            appendLiInnerHTML(ul, projectLink(p));
        }
        obj.appendChild(ul);
    }

    var repos = [];
    for (var r in repositories) {
        if (committeeId == repoToCommittee(r)) {
            repos.push(r);
        }
    }
    if (repos.length > 0) {
        appendElementWithInnerHTML(obj, 'h4', 
            "Repositories managed by this Committee <font size='-2'>" +
            "(from <a href='https://gitbox.apache.org/repositories.json'>ASF Git repos</a>" +
            " and <a href='https://svn.apache.org/repos/asf/'>ASF SVN repos</a>)</font>:");

        ul = document.createElement('ul');
        for (var r in repos.sort()) {
            r = repos[r];
            var url = repositories[r];
            appendLiInnerHTML(ul, r + ": <a href='" + url + "'>" + url + "</a>");
        }
        obj.appendChild(ul);
    }
}

function buildCommitteePage() {
    var committeeId = document.location.search.substr(1);
    renderCommitteePage(committeeId);
}


// ------------ Projects listing ------------\\

function camelCase(str) {
    return str.replace(/^([a-z])(.+)$/, function(c,a,b) { return a.toUpperCase() + b.toLowerCase() } );
}

function committeeIcon() {
     return "<img src='images/committee.png' title='Committee' style='vertical-align: middle; padding: 2px;'/> ";
}

function projectIcon() {
    return "<img src='images/project.png' title='Project' style='vertical-align: middle; padding: 2px;'/> "
}

function committeeLink(id) {
    var committee = committees[id];
    return "<a href='committee.html?" + id + "'>" + committee.name + "</a> - " + committee.shortdesc;
}

function projectLink(id) {
    var project = projects[id];
    if (!project) {
        // not project id: perhaps committee id
        project = committees[id];
    }
    return "<a href='project.html?" + id + "'>" + project.name + "</a>";
}

function isMember(id) {
    return _(unixgroups['member']).indexOf(id) >= 0;
}

function sortProjects() {
    var projectsSortedX = [];
    var projectsSorted = [];
    for (i in projects) {
        projectsSortedX.push([i, projects[i].name.toLowerCase()]);
    }
    // compare names (already lower-cased)
    projectsSortedX.sort(function(a,b) { return a[1] > b[1] ? 1 : a[1] < b[1] ? -1 : 0 })
    for (i in projectsSortedX) {
        projectsSorted.push(projectsSortedX[i][0]);
    }
    return projectsSorted;
}

function renderProjectsByName() {
    var obj = document.getElementById('list');
    obj.innerHTML = "";
    var projectsSorted = sortProjects();

    // Project list
    var ul = document.createElement('ul');
    for (var i in projectsSorted) {
        var project = projectsSorted[i];
        appendLiInnerHTML(ul, projectIcon(projects[project].name) + projectLink(project));
    }
    obj.appendChild(ul);
}

function renderProjectsByLanguage() {
    var obj = document.getElementById('list');
    obj.innerHTML = "";
    var projectsSorted = sortProjects();

    // Compile Language array
    var lingos = [];
    var lcount = {};
    var i;
    var x;
    for (i in projects) {
        if (projects[i]['programming-language']) {
            var a = projects[i]['programming-language'].split(/,\s*/);
            for (x in a) {
                a[x] = camelCase(a[x]);
                if (lingos.indexOf(a[x]) < 0) {
                    lingos.push(a[x]);
                    lcount[a[x]] = 0;
                }
                lcount[a[x]]++;
            }
        }
    }

    // Construct language list
    lingos.sort();
    var toc = document.createElement('p');
    var toch = document.createElement('h3');
    toch.textContent = 'TOC';
    toc.appendChild(toch);
    var ul = document.createElement('ul');

    var l;
    for (l in lingos) {
        var lang = lingos[l];
        var tocitem = document.createElement('a');
        tocitem.href="#" + lang;
        tocitem.innerHTML=lang;
        if (l > 0) { // divider
            toc.appendChild(document.createTextNode(', '));
        }
        toc.appendChild(tocitem);
        var li = document.createElement('li');
        li.innerHTML = "<h3><a id='" + lang + "'>" + lang + " (" + lcount[lang] + ")</a>"+linkToHere(lang)+":</h3>";
        var cul = document.createElement('ul');
        for (i in projectsSorted) {
            i = projectsSorted[i];
            if (projects[i]['programming-language']) {
                var a = projects[i]['programming-language'].split(/,\s*/);
                for (x in a) {
                    // Use same capitalisation as the language list
                    if (camelCase(a[x]) == lang) {
                        appendLiInnerHTML(cul, projectIcon(projects[i].name) + projectLink(i));
                    }
                }
            }
        }
        li.appendChild(cul);
        ul.appendChild(li);
    }

    obj.appendChild(toc);
    obj.appendChild(ul);

    if (location.hash.length > 1) {
        setTimeout(function() { location.href = location.href;}, 250);
    }
}

function renderProjectsByCategory() {
    var obj = document.getElementById('list');
    obj.innerHTML = "";
    var projectsSorted = sortProjects();

    var cats = [];
    var ccount = {};
    var i;
    for (i in projects) {
        if (projects[i].category) {
            var a = projects[i].category.split(/,\s*/);
            var x;
            for (x in a) {
                x = a[x].toLowerCase(); // must agree with downcase below
                if (cats.indexOf(x) < 0) {
                            cats.push(x);
                            ccount[x] = 0;
                }
                ccount[x]++;
                }
        }
    }
    cats.sort();

    // Construct category list
    var toc = document.createElement('p');
    var toch = document.createElement('h3');
    toch.textContent = 'TOC';
    toc.appendChild(toch);
    var ul = document.createElement('ul');

    var l;
    for (l in cats) {
        var cat = cats[l];
        var tocitem = document.createElement('a');
        tocitem.href="#" + cat;
        tocitem.innerHTML=cat;
        if (l > 0) { // divider
            toc.appendChild(document.createTextNode(', '));
        }
        toc.appendChild(tocitem);
        var li = document.createElement('li');
        li.innerHTML = "<h3><a id='" + cat + "'>" + cat + " (" + ccount[cat] + ")</a>"+linkToHere(cat)+":</h3>";
        var cul = document.createElement('ul');
        for (i in projectsSorted) {
            i = projectsSorted[i];
            var project = projects[i];
            if (project.category) {
                var a = project.category.split(/,\s*/);
                for (x in a) {
                    x = a[x].toLowerCase(); // must agree with downcase above
                    if (x == cat) {
                        appendLiInnerHTML(cul, projectIcon(project.name) + projectLink(i));
                    }
                }
            }
        }
        li.appendChild(cul);
        ul.appendChild(li);
    }

    obj.appendChild(toc);
    obj.appendChild(ul);

    if (location.hash.length > 1) {
        setTimeout(function() { location.href = location.href;}, 250);
    }
}

function renderProjectsByNumber() {
    var obj = document.getElementById('list');
    obj.innerHTML = "";
    var projectsSorted = sortProjects();

    var lens = [];
    var lcount = {};
    for (projectId in projects) {
        let unixGroup = projectIdToUnixGroup(projectId);
        if (unixgroups[unixGroup] && projectId !== 'incubator') {
            let len = unixgroups[unixGroup].length;
            if (lens.indexOf(len) < 0) {
                    lens.push(len);
                    lcount[len] = 0;
            }
            lcount[len]++;
        }
    }
    lens.sort(function(a,b) { return b - a });

    // Construct date list
    var ul = document.createElement('ul');

    for (l in lens) {
        var len = lens[l];
        var projectId;
        for (projectId in projectsSorted) {
            projectId = projectsSorted[projectId];
            let unixGroup = projectIdToUnixGroup(projectId);
            if (unixgroups[unixGroup]) {
                var xlen = unixgroups[unixGroup].length;
                if (xlen == len) {
                    var html = projectIcon(projects[projectId].name) + projectLink(projectId) + ": " + len + " committers";
                    if (unixgroups[unixGroup+'-pmc']) {
                        html += ", " + unixgroups[unixGroup+'-pmc'].length + " PMC members";
                    }
                    appendLiInnerHTML(ul,html);
                }
             }
        }
    }

    obj.appendChild(ul);
}

function renderProjectsByCommittee() {
    var obj = document.getElementById('list');
    obj.innerHTML = "";
    var projectsSorted = sortProjects();

    var dcount = {};
    for (var committee in committees) {
        dcount[committee] = 0;
    }
    for (var project in projects) {
        project = projects[project];
        if (committees[project.pmc]) {
            dcount[project.pmc]++;
        }
    }

    // Construct pmc list
    var ul = document.createElement('ul');

    var lpmc;
    for (lpmc in committees) {
        var c = dcount[lpmc];
        var li = document.createElement('li');
        var cul = document.createElement('ul');
        if (c == 0 && lpmc != 'labs') {
            appendLiInnerHTML(cul, projectIcon(committees[lpmc].name) + "<a href='project.html?" + lpmc + "'>" + committees[lpmc].name + "</a>");
            c = 1;
        } else {
            var i;
            for (i in projectsSorted) {
                i = projectsSorted[i];
                var project = projects[i];
                if (committees[project.pmc]) {
                    var xlpmc = project.pmc;
                    if (xlpmc == lpmc) {
                        if (project.doap) {
                            appendLiInnerHTML(cul, projectIcon(project.name) + projectLink(i));
                        } else {
                            c=0;
                            if (xlpmc == 'incubator') {
                                appendLiInnerHTML(cul, "<b>"+ project.name + ": please <a href='https://projects.apache.org/create.html'>create a DOAP</a> file</b>");
                            } else {
                                appendLiInnerHTML(cul, "<b>Please <a href='https://projects.apache.org/create.html'>create a DOAP</a> file</b>");
                            }
                        }
                    }
                }
            }
        }
        li.innerHTML = "<h3>" + committeeIcon() + "<a id='" + lpmc + "' href='committee.html?"+ lpmc + "'>" + committees[lpmc].name + " Committee</a>" + (c!=1?(" (" + c + ")"):"") + (c>0?":": "") + "</h3>";
        li.appendChild(cul);
        ul.appendChild(li);
    }

    obj.appendChild(ul);

    if (location.hash.length > 1) {
        setTimeout(function() { location.href = location.href;}, 250);
    }
}

function buildProjectsList() {
    var cat = document.location.search.substr(1);
    var types = {
        'name': [ 'name', renderProjectsByName ],
        'language': [ 'language', renderProjectsByLanguage ],
        'category': [ 'category', renderProjectsByCategory ],
        'number': [ 'number of committers', renderProjectsByNumber ],
        'pmc': [ 'Committee', renderProjectsByCommittee ],
        'committee': [ 'Committee', renderProjectsByCommittee ]
    }
    if ((cat.length == 0) || !(cat in types)) {
        cat = "name";
    }

    var type = types[cat];
    var obj = document.getElementById('title');
    obj.innerHTML = "<h1>Projects by " + type[0] + ":</h1>"

    preloadEverything(type[1]);
}

function sortCommittees() {
    var committeesSortedX = [];
    var committeesSorted = [];
    for (i in committees) {
        committeesSortedX.push([i, committees[i].name.toLowerCase()]);
    }
    // compare names (already lower-cased)
    committeesSortedX.sort(function(a,b) { return a[1] > b[1] ? 1 : a[1] < b[1] ? -1 : 0 })
    for (i in committeesSortedX) {
        committeesSorted.push(committeesSortedX[i][0]);
    }
    return committeesSorted;
}

function renderCommitteesByName() {
    var obj = document.getElementById('list');
    obj.innerHTML = "";
    var committeesSorted = sortCommittees();

    // Committee list
    var ul = document.createElement('ul');
    var i;
    for (i in committeesSorted) {
        appendLiInnerHTML(ul, committeeIcon() + committeeLink(committeesSorted[i]));
    }
    obj.appendChild(ul);
}

function renderCommitteesByDate() {
    var obj = document.getElementById('list');
    obj.innerHTML = "";

    var dates = [];
    var dcount = {};
    var i;
    for (i in committees) {
        var date = committees[i].established;
        if (dates.indexOf(date) < 0) {
            dates.push(date);
            dcount[date] = 0;
        }
        dcount[date]++;
    }
    dates.sort()

    // Construct date list
    var ul = document.createElement('ul');

    var l;
    for (l in dates) {
        var date = dates[l];
        var li = document.createElement('li');
        li.innerHTML = "<h3><a id='" + date + "'>" + date + " (" + dcount[date] + ")</a>:</h3>";
        var cul = document.createElement('ul');
        var i;
        for (i in committeesByName) {
            i = committeesByName[i];
            if (i.established == date) {
                appendLiInnerHTML(cul, committeeIcon() + committeeLink(i.id));
            }
        }
        li.appendChild(cul);
        ul.appendChild(li);
    }

    obj.appendChild(ul);

    if (location.hash.length > 1) {
        setTimeout(function() { location.href = location.href;}, 250);
    }
}

function buildCommitteesList() {
    var cat = document.location.search.substr(1);
    var types = {
        'name': [ 'name', renderCommitteesByName ],
        'date': [ 'founding date', renderCommitteesByDate ]
    }
    if ((cat.length == 0) || !(cat in types)) {
        cat = "name";
    }

    var type = types[cat];
    var obj = document.getElementById('title');
    obj.innerHTML = "<h1>Committees by " + type[0] + ":</h1>"

    preloadEverything(type[1]);
}


// Rendering project list using DataTables instead of the usual stuff:
function buildProjectListAsTable(json) {
    var arr = [];
    for (p in projects) {
        var project = projects[p];

        // Get name of PMC
        var pmc = committees[project.pmc] ? committees[project.pmc].name : "Unknown";

        // Get project type
        var type = "Sub-Project";
        var shortp = p.split("-")[0];
        if (unixgroups[shortp]) {
            type = "TLP";
            if ((!committeesByName[project.name] && committees[project.pmc]) || project.name.match(/incubating/i)) {
                type = "Sub-project";
            }
        } else {
            type = "Retired";
        }

        if (project.podling || project.name.match(/incubating/i)) {
            type = "Podling";
            pmc = "Apache Incubator";
        }

        // Programming language
        var pl = project['programming-language'] ? project['programming-language'] : "Unknown";

        // Shove the result into a row
        arr.push([ p, project.name, type, pmc, pl, project.category])
    }

    // Construct the data table
    $('#contents').html( '<table cellpadding="0" cellspacing="0" border="0" class="display" id="projectlist"></table>' );

    $('#projectlist').dataTable( {
        "data": arr,
        "columns": [
            { "title": "ID", "visible": false },
            { "title": "Name" },
            { "title": "Type" },
            { "title": "PMC" },
            { "title": "Programming Language(s)" },
            { "title": "Category" }
        ],
        "fnRowCallback": function( nRow, aData, iDisplayIndex, iDisplayIndexFull) {
                    jQuery(nRow).attr('id', aData[0]);
                    jQuery(nRow).css("cursor", "pointer");
                    return nRow;
                }
    } );

    $('#projectlist tbody').on('click', 'tr', function () {
        var name = $(this).attr('id');
        location.href = "project.html?" + name
    } );
}


function isCommittee(name) {
    return committeesByName[name];
}

// ------------ Front page rendering ------------\\

function renderFrontPage() {
    var numcommittees = 0;
    var i;
    for (i in committees) numcommittees++;
    var curPodlings = 0;
    for (i in podlings) curPodlings++;

    // The projects list contains 1 entry for each podling, as well as 1 entry for each DOAP.
    // Each podling relates to a single project, but a PMC may have one or more projects.
    // However not all projects may have registered DOAPs.
    // In order to find these missing projects, we need to find projects that have not registered DOAPs

    var projectsWithDoaps = {}; // ids of projects which have registered DOAPS
    var numProjects = 0; // total projects run by active PMCs
    for (j in projects) {
        i = projects[j];
        projectsWithDoaps[i.pmc] = 1; // which projects have got DOAPs
        if (i.pmc != 'attic' && i.pmc != 'incubator') {
            numProjects++; // found a project run by an active PMC (not podling or retired)
        }
    }
    var numprojectsWithDoaps = 0; // how many projects have registered DOAPs
    for (i in projectsWithDoaps) numprojectsWithDoaps++;
    numProjects += (numcommittees - numprojectsWithDoaps); // Add in projects without DOAPs
    var initiatives = numProjects + curPodlings; // both PMC and podlings
    initiatives -= initiatives % 50; // round down to nearest 50
    var obj = document.getElementById('details');
    obj.innerHTML = ""
    if (urlErrors.length > 0) {
        obj.innerHTML += "<p><span style='color: red'><b>Warning: could not load: "+urlErrors.join(', ')+"</b></span></p>"
    }
    obj.innerHTML
        += "<h3 style='text-align: center;'>There are currently <span style='color: #269;'>" + initiatives + "+</span> open source initiatives at the ASF:</h3>"
        + "<ul style='width: 400px; margin: 0 auto; font-size: 18px; color: #269; font-weight: bold;'>"
        + "<li>" + numcommittees + " committees managing " + numProjects + " projects</li>"
        + "<li>5 special committees*</li>"
        + "<li>" + curPodlings + " incubating podlings</li></ul>"
        + "<p><small>*Infrastructure, Travel Assistance, Security Team, Legal Affairs and Brand Management</small></p>";

    renderCommitteeEvolution();
    renderPodlingsEvolution();
    renderLanguageChart();
}


// ------------ Chart functions ------------\\

function htmlListTooltip(date,name,values) {
    return '<div style="padding:8px 8px 8px 8px;"><b>' + date + '</b>'
        + '<br/><b>' + values.length + '</b> ' + name + ((values.length > 1) ? 's:':':')
        + ((values.length > 0) ? '<br/>- '+values.join('<br/>- '):'')
        + '</div>';
}

function renderCommitteeEvolution() {
    var evo = {}; // 'year-month' -> { established: [], retired: [] }
    // init evo with empty content for the whole period
    var maxYear = new Date().getFullYear();
    for (var year = 1995; year <= maxYear; year++) {
        var maxMonth = (year < maxYear) ? 12 : (new Date().getMonth() + 1);
        for (var month = 1; month <= maxMonth; month++) {
            var key = year + '-' + (month < 10 ? '0':'') + month;
            evo[key] = { 'established': [], 'retired': [] };
        }
    }
    // add current committees
    var c;
    for (c in committees) {
        c = committees[c];
        if (evo[c.established]) {
            evo[c.established]['established'].push(c);
        } else {
            console.log(c.id + ": " + c.established + " is off(?!)");
        }
    }
    // add retired committees
    for (c in retiredCommittees) {
        c = retiredCommittees[c];
        if (evo[c.established] && evo[c.retired]) {
            evo[c.established]['established'].push(c);
            evo[c.retired]['retired'].push(c);

        } else {
            console.log(c.id + ": " + c.established + " or " + c.retired + " is off(?!)");
        }
    }
    // compute data
    var data = [];
    var cur = 0;
    var d;
    for (d in evo) {
        var established = evo[d]['established'];
        var retired = evo[d]['retired'];
        var estDisplay = [];
        for (c in established) {
            c = established[c];
            estDisplay.push(c.name + ((c.id in retiredCommittees) ? ' (retired ' + retiredCommittees[c.id]['retired'] + ')':''));
        }
        var retDisplay = [];
        for (c in retired) {
            c = retired[c];
            retDisplay.push(c.name + ' (established ' + c['established'] + ')');
        }
        cur += established.length - retired.length;
        data.push([d, established.length, htmlListTooltip(d, 'new committee', estDisplay), -1*retired.length, htmlListTooltip(d, 'retired committee', retDisplay), cur]);
    }
    //narr.sort(function(a,b) { return (b[1] - a[1]) });
    var dataTable = new google.visualization.DataTable();
    dataTable.addColumn('string', 'Month');
    dataTable.addColumn('number', "New committees");
    dataTable.addColumn({type: 'string', role: 'tooltip', 'p': {'html': true}});
    dataTable.addColumn('number', "Retired committees");
    dataTable.addColumn({type: 'string', role: 'tooltip', 'p': {'html': true}});
    dataTable.addColumn('number', 'Current committees');

    dataTable.addRows(data);

    var options = {
        title: "Committees evolution (also called PMCs or Top Level Projects)",
        isStacked: true,
        height: 320,
        width: 1160,
        seriesType: "bars",
        backgroundColor: 'transparent',
        series: {2: {type: "line", targetAxisIndex: 1}},
        tooltip: {isHtml: true},
        vAxes:[
            {title: 'Change in states', ticks: [-3,0,3,6,9]},
            {title: 'Current number of committees'}
        ]
    };
    var div = document.createElement('div');
    document.getElementById('details').appendChild(div);
    var chart = new google.visualization.ComboChart(div);
    chart.draw(dataTable, options);
}

function renderPodlingsEvolution(obj) {
    var evo = {}; // 'year-month' -> { started: [], graduated: [], retired: [] }
    // init evo with empty content for the whole period
    var maxYear = new Date().getFullYear();
    for (var year = 2003; year <= maxYear; year++) {
        var maxMonth = (year < maxYear) ? 12 : (new Date().getMonth() + 1);
        for (var month = 1; month <= maxMonth; month++) {
            var key = year + '-' + (month < 10 ? '0':'') + month;
            evo[key] = { 'started': [], 'graduated': [], 'retired': [] };
        }
    }
    // add current podlings
    var p;
    for (p in podlings) {
        p = podlings[p];
        if (p['podling']) {
            evo[p.started]['started'].push(p);
        }
    }
    // add podlings history
    for (p in podlingsHistory) {
        p = podlingsHistory[p];
        evo[p.started]['started'].push(p);
        evo[p.ended][p.status].push(p);
    }
    // compute data
    var data = [];
    var cur = 0;
    var d;
    for (d in evo) {
        var started = evo[d]['started'];
        var graduated = evo[d]['graduated'];
        var retired = evo[d]['retired'];
        var startedDisplay = [];
        for (p in started) {
            p = started[p];
            startedDisplay.push(p.name + (p['ended'] ? ' (' + p.status + ' ' + p.ended + ')':''));
        }
        var graduatedDisplay = [];
        for (p in graduated) {
            p = graduated[p];
            graduatedDisplay.push(p.name + ' (started ' + p.started + ')');
        }
        var retiredDisplay = [];
        for (p in retired) {
            p = retired[p];
            retiredDisplay.push(p.name + ' (started ' + p.started + ')');
        }
        cur += started.length - graduated.length - retired.length;
        data.push([d, started.length, htmlListTooltip(d, 'new podling', startedDisplay),
            -1*graduated.length, htmlListTooltip(d, 'graduated podling', graduatedDisplay),
            -1*retired.length, htmlListTooltip(d, 'retired podling', retiredDisplay), cur]);
    }
    //narr.sort(function(a,b) { return (b[1] - a[1]) });
    var dataTable = new google.visualization.DataTable();
    dataTable.addColumn('string', 'Month');
    dataTable.addColumn('number', "New podlings");
    dataTable.addColumn({type: 'string', role: 'tooltip', 'p': {'html': true}});
    dataTable.addColumn('number', "Graduated podlings");
    dataTable.addColumn({type: 'string', role: 'tooltip', 'p': {'html': true}});
    dataTable.addColumn('number', "Retired podlings");
    dataTable.addColumn({type: 'string', role: 'tooltip', 'p': {'html': true}});
    dataTable.addColumn('number', 'Current podlings');

    dataTable.addRows(data);

    var coptions = {
        title: "Incubating projects evolution",
        isStacked: true,
        height: 320,
        width: 1160,
        seriesType: "bars",
        backgroundColor: 'transparent',
        colors: ['#3366cc', '#109618', '#dc3912', '#ff9900'],
        series: {3: {type: "line", targetAxisIndex: 1}},
        tooltip: {isHtml: true},
        vAxes: [
            {title: 'Change in states', ticks: [-6,-3,0,3,6]},
            {title: 'Current number of podlings'}
        ]
    };
    var div = document.createElement('div');
    document.getElementById('details').appendChild(div);
    var chart = new google.visualization.ComboChart(div);
    chart.draw(dataTable, coptions);
}

function renderLanguageChart() {
    var obj = document.getElementById('details');

    // Languages
    var lingos = [];
    var lcount = {};
    for (var i in projects) {
        i = projects[i];
        if (i['programming-language']) {
            var a = i['programming-language'].split(/,\s*/);
            for (var x in a) {
                x = a[x];
                if (lingos.indexOf(x) < 0) {
                    lingos.push(x);
                    lcount[x] = 0;
                }
                lcount[x]++;
            }
        }
    }


    var narr = [];
    for (i in lingos) {
        var lang = lingos[i];
        narr.push([lang, lcount[lang], 'Click here to view all projects using ' + lang]);
    }
    narr.sort(function(a,b) { return (b[1] - a[1]) });

    var data = new google.visualization.DataTable();
        data.addColumn('string', 'Language');
        data.addColumn('number', "Projects using it");
        data.addColumn({type: 'string', role: 'tooltip'});
        data.addRows(narr);

    var options = {
      title: 'Language distribution (click on a language to view all projects using it)',
      height: 400,
      backgroundColor: 'transparent'
    };

    var chartDiv = document.createElement('div');
    var chart = new google.visualization.PieChart(chartDiv);
    obj.appendChild(chartDiv);

    function selectHandlerLanguage() {
        var selectedItem = chart.getSelection()[0];
        if (selectedItem) {
          var value = data.getValue(selectedItem.row, 0);
          location.href = "projects.html?language#" + value;
        }
    }
    google.visualization.events.addListener(chart, 'select', selectHandlerLanguage);
    chart.draw(data, options);


    // Categories
    var cats = [];
    var ccount = {};
    for (i in projects) {
        i = projects[i];
        if (i.category) {
            var a = i.category.split(/,\s*/);
            for (x in a) {
                if (cats.indexOf(a[x]) < 0) {
                    cats.push(a[x]);
                    ccount[a[x]] = 0;
                }
                ccount[a[x]]++;
            }
        }
    }


    var carr = [];
    for (i in cats) {
        var cat = cats[i];
        carr.push([cat, ccount[cat], 'Click here to view all projects in the ' + cat + ' category'])
    }
    carr.sort(function(a,b) { return (b[1] - a[1]) });


    var data2 = new google.visualization.DataTable();
        data2.addColumn('string', 'Category');
        data2.addColumn('number', "Projects");
        data2.addColumn({type: 'string', role: 'tooltip'});
        data2.addRows(carr);

    var options2 = {
      title: 'Categories (click on a category to view projects within it)',
      height: 400,
      backgroundColor: 'transparent'
    };

    var chartDiv2 = document.createElement('div');
    var chart2 = new google.visualization.PieChart(chartDiv2);
    obj.appendChild(chartDiv2);


    function selectHandlerCategory() {
        var selectedItem = chart2.getSelection()[0];
        if (selectedItem) {
          var value = data2.getValue(selectedItem.row, 0);
          location.href = "projects.html?category#" + value;
        }
    }
    google.visualization.events.addListener(chart2, 'select', selectHandlerCategory);
    chart2.draw(data2, options2);
}

// This is the entry point from index.html and about.html

function buildFrontPage() {
    renderFrontPage({}, null)
}



// ------- Account creation chart function -------- \\

function drawAccountCreation(json) {
    var i;
    var j;
    var narr = [];
    var cdata = new google.visualization.DataTable();
    cdata.addColumn('string', 'Date');
    cdata.addColumn('number', 'New committers');
    cdata.addColumn('number', 'Total number of committers');
    var max = 0;
    var jsort = [];
    for (j in json) {
        jsort.push(j);
    }

    jsort.sort();
    var c = 0;
    for (i in jsort) {
        i = jsort[i];
        var entry = json[i];
        var arr = i.split("-");
        var d = new Date(parseInt(arr[0]), parseInt(arr[1]), 1);
        c += entry;
        narr.push([i, entry, c]);
        max = (max < entry) ? entry : max;
    }
    cdata.addRows(narr);

    var options = {
      title: ('Account creation timeline'),
      backgroundColor: 'transparent',
      height: 320,
      width: 1160,
      vAxes:[

      {title: 'New accounts', titleTextStyle: {color: '#0000DD'}, maxValue: Math.max(200,max)},
      {title: 'Total number of accounts', titleTextStyle: {color: '#DD0000'}},

      ],
      series: {
        1: {type: "line", pointSize:3, lineWidth: 3, targetAxisIndex: 1},
        0: {type: "bars", targetAxisIndex: 0}
        },
        seriesType: "bars",
      tooltip: {isHtml: true}
    };

    var obj = document.createElement('div');
    obj.style = "float: left; width: 1160px; height: 450px;";
    obj.setAttribute("id", 'accountchart');
    var contents = document.getElementById('contents');
    contents.innerHTML = "<h1>Timelines</h1>";
    contents.appendChild(obj);

    var chart = new google.visualization.ComboChart(obj);
    chart.draw(cdata, options);
}

// called by timelines.html

function buildTimelines() {
    GetAsyncJSON("json/foundation/accounts-evolution.json", null, drawAccountCreation);
}


// called by timelines2.html

function buildTimelines2() {
    GetAsyncJSON("json/foundation/accounts-evolution2.json", null, drawAccountCreation);
}


// ------------ Search feature for the site ------------\\

function searchProjects(str) {
    var obj = document.getElementById('contents');

    str = str.toLowerCase();
    var hits = {};
    var hitssorted = [];

    // Search committees
    for (p in projects) {
        var project = projects[p];
        for (key in project) {
            if (typeof project[key] == "string") {
                var val = project[key].toLowerCase();
                if (val.indexOf(str) >= 0 && val.substr(0,1) != "{") {
                    if (!hits[p]) {
                        hits[p] = [];
                    }
                    var estr = new RegExp(str, "i");
                    hits[p].push({
                    'key': key,
                    'val': project[key].replace(estr, function(a) { return "<u style='color: #963;'>"+a+"</u>"}, "img")
                    });
                    if (hitssorted.indexOf(p) < 0) {
                        hitssorted.push(p);
                    }
                }
            }
        }
    }

    var title = "Search results for '" + str + "' (" + hitssorted.length + "):";
    obj.innerHTML = "";
    var h2 = document.createElement('h2');
    h2.appendChild(document.createTextNode(title));
    obj.appendChild(h2);
    hitssorted.sort(function(a,b) { return hits[b].length - hits[a].length });
    var ul = document.createElement('ul');

    var h;
    for (h in hitssorted) {
        h = hitssorted[h];
        var project = hits[h];
        var html = "<h4><a href='project.html?" + h + "'>" + projects[h].name + "</a> (" + project.length + " hit(s)):</h4>";
        for (x in project) {
            html += "<blockquote><b>" + project[x].key + ":</b> " +  project[x].val + "</blockquote>";
        }
        appendLiInnerHTML(ul,html);
    }
    if (hitssorted.length == 0) {
            obj.innerHTML += "No search results found";
    }
    obj.appendChild(ul);
}



// Key press monitoring for search field
function checkKeyPress(e, txt) {
    if (!e) e = window.event;
    var keyCode = e.keyCode || e.which;
    if (keyCode == '13'){
            searchProjects(txt.value);
    }
}


// ------------ Weave functions ------------\\

function weaveById(list,mapById) {
    for (var i in list) {
        var o = list[i];
        mapById[o.id] = o;
    }
}

function fixProjectName(project) {
    // fix attic and incubator project names if necessary
    if (project.pmc == "attic") {
        project.name += " (in the Attic)";
    } else if ((project.pmc == "incubator") && !project.name.match(/incubating/i)) {
        project.name += " (Incubating)";
    }
    return project;
}

// Add content by id to projects
function weaveInProjects(json, pfx) {
    if (!pfx) { pfx='' }
    for (p in json) {
        // Since podlings are loaded first, DOAPs take precedence
        projects[pfx+p] = fixProjectName(json[p]);
    }
}

function weaveInRetiredCommittees(json) {
    weaveById(json, retiredCommittees);
    var p;
    var projectsPmcs = {};
    for (p in projects) {
        projectsPmcs[projects[p].pmc] = p;
    }
    var c;
    for (c in committees) {
        c = committees[c];
        if (!projectsPmcs[c.id] && c.id != 'attic') {
            // no DOAP file written by the PMC: creating default content
            projects[c.id] = {
                'name': c.name,
                'homepage': c.homepage,
                'pmc': c.id
            }
        }
    }
}

function setCommittees(json, state) {
    weaveById(json, committees);
    var c;
    for (c in json) {
        c = json[c];
        // committeesByName = { name -> committee }
        committeesByName[c.name] = c;
    }
    if (state) {
        state();
    }
}

// Render releases using datatables
function renderReleases(releases) {
    var arr = [];
    for (p in releases) {
        var releasedata = releases[p];

        for (filename in releasedata) {
            var date = releasedata[filename];
            // Shove the result into a row
            arr.push([ p, p, date, filename]);
        }
    }

    // Construct the data table
    $('#contents2').html( '<table cellpadding="0" cellspacing="0" border="0" class="display" id="releases"></table>' );

    $('#releases').dataTable( {
        "data": arr,
        "columns": [
            { "title": "ID", "visible": false },
            { "title": "Name" },
            { "title": "Date" },
            { "title": "Release name" }
        ],
        "fnRowCallback": function( nRow, aData, iDisplayIndex, iDisplayIndexFull) {
                    jQuery(nRow).attr('id', aData[0]);
                    jQuery(nRow).css("cursor", "pointer");
                    return nRow;
                }
    } );

    $('#releases tbody').on('click', 'tr', function () {
        var name = $(this).attr('id').replace("incubator-","incubator/");
        location.href = "https://www.apache.org/dist/" + name;
    } );
}

// Generate a 'Link to here' pop-up marker
function linkToHere(id) {
    return "<a class='sectionlink' href='#"+id+"' title='Link to here'>&para;</a>"
}

// Called by releases.html

function buildReleases() {
    GetAsyncJSON("json/foundation/releases.json?" + Math.random(), null, renderReleases);
}

// ------------ Async data fetching ------------\\
// This function is the starter of every page, and preloads the needed files
// before running the final page renderer. This is roughly 1 mb of JSON, but as
// it gets cached after first run, it's not really a major issue.

function preloadEverything(callback) {
    // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/startsWith
    if (!String.prototype.startsWith) {
        String.prototype.startsWith = function (searchString, position) {
            position = position || 0;
            return this.substr(position, searchString.length) === searchString;
        };
    }
    GetAsyncJSONArray([
        ["json/foundation/committees.json", "committees", setCommittees],
        ["json/foundation/groups.json", "groups", function(json) { unixgroups = json; }],
        ["json/foundation/people_name.json", "people", function(json) { people = json; }],
        ["json/foundation/podlings.json", "podlings", function(json) { podlings = json; weaveInProjects(json,'incubator-')}], // do this first
        ["json/foundation/projects.json", "projects", weaveInProjects], // so can replace with DOAP data where it exists
        ["json/foundation/committees-retired.json", "retired committees", weaveInRetiredCommittees],
        ["json/foundation/podlings-history.json", "podlings history", function(json) { podlingsHistory = json; }],
        ["json/foundation/repositories.json", "repositories", function(json) { repositories = json; }]
        ],
        callback);
}
