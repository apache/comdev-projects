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

// ------------ form data functions for project editor ------------\\

function addKeyVal(key, val) {
    var div = document.createElement('div')
    var left = document.createElement('div')
    var right = document.createElement('div')
    div.style = "width: 1020px; margin: 10px; overflow: auto;"
    left.style = "float: left; width: 300px; font-weight: bold"
    right.style = "float: left; width: 700px;"
    left.appendChild(document.createTextNode(key + ": "))
    right.appendChild(val)
    div.appendChild(left);
    div.appendChild(right)
    return div
}

function input(type, name, value) {
    var t = document.createElement('input');
    t.setAttribute("type", type)
    t.setAttribute("name", name)
    t.setAttribute("value", value)
    t.style.minWidth = "380px"
    return t;
}

function makeSelect(name, arr, sarr) {
    var sel = document.createElement('select');
    sel.setAttribute("name", name)
    for (i in arr) {
        var val = arr[i];
        var opt = document.createElement('option')
        opt.setAttribute("value", val)
        opt.innerHTML = val
        sel.appendChild(opt);
    }
    return sel
}

function postREST(json, oform) {
    var form = new FormData(oform)
    var xmlHttp = null;
    if (window.XMLHttpRequest) {
        xmlHttp = new XMLHttpRequest();
    } else {
        xmlHttp = new ActiveXObject("Microsoft.XMLHTTP");
    }
    for (i in json) {
        form.append(i, json[i])
    }
    xmlHttp.open("POST", "/edit/save.py", false);
    xmlHttp.send(form);
}

function editProject(json, project) {
    var obj = document.getElementById('contents');
    obj.innerHTML = "<a href='/edit/'><img src='/images/back.png' style='vertical-align: middle; margin-right: 10px;'/><b>Back to project list...</b></a><br/><h1>Project editor:</h1><p>Editing " + project + ".json:</p>"
    if (!json || !json.name) {
        json = projects[project] ? projects[project] : json
        json.name = json.name ? json.name : "Apache Foo";
    }
    if (json.category) {
        json.category = json.category.replace(/https:\/\/projects.apache.org\/category\//gi, "")
    }
    var form = document.createElement('form')
    form.appendChild(input("hidden", "file", project))
    var keys = ['name','pmc','homepage','shortdesc','description','category','programming-language','mailing-list', 'download-page','bug-database','SVNRepository','GitRepository']
    for (i in keys) {
        k = keys[i]
        if (k == 'description') {
            var txt = document.createElement('textarea');
            txt.setAttribute("name", "description")
            txt.style.width = "600px"
            txt.style.height = "140px"
            txt.innerHTML =  json[k] ? json[k] : "";
            form.appendChild(addKeyVal(k, txt))
        }
        else {
            form.appendChild(addKeyVal(k, input("text", k, json[k] ? json[k] : "")))
        }
    }
    var but = input("button", "submit", "Save changes")
    but.setAttribute("onclick", "postREST({}, this.form); alert('Changes saved!');")
    form.appendChild(but)
    obj.appendChild(form)
}

function editProjectPreload(project) {
    GetAsyncJSON("/json/projects/" + project + ".json?" + Math.random(), project, editProject);
}
function buildEditor(uid) {
    var obj = document.getElementById('contents');
    obj.innerHTML = "<h1>Project editor:</h1><h3>Select a project to edit:</h3><p>Only projects where you are in the sponsoring PMC can be edited</p>"
    for (i in projects) {
        var p = i.split("-")[0];
        if (projects[i].name.match(/incubating/i)) {
            p = 'incubator'
        }
        if (unixgroups[p+"-pmc"] && unixgroups[p+"-pmc"].indexOf(uid) >= 0) {
            obj.innerHTML += "<a href='javascript:void(0);' onclick='editProjectPreload(\"" + i + "\");'>" + projects[i].name + "</a><br/>"
        }

    }
    obj.innerHTML += "<hr/><h3>Or create a new project:</h3>"
    var form = document.createElement('form')
    var groups = []
    for (i in unixgroups) {
        for (x in unixgroups[i]) {
            if (unixgroups[i][x] == uid && i.match(/.+-pmc$/i)) {
                groups.push(i.replace("-pmc",""))
                break
            }
        }
    }
    form.appendChild(addKeyVal("PMC", makeSelect("pmc", groups, [])));
    form.appendChild(addKeyVal("Sub-project (if any) (a-z,0-9 only)", input("text", "sub", "")))
    var but = input("button", "submit", "Create project data file")
    but.setAttribute("onclick", "newProject(this.form);")
    form.appendChild(but)
    obj.appendChild(form)
}

function newProject(form) {
    filename = form.pmc.value
    if (form.sub.value.length > 0) {
        filename += "-" + form.sub.value.toLowerCase().replace(/[^-a-z0-9]/g, "")
    }
    editProject({'pmc': form.pmc.value, 'homepage': 'https://'+form.pmc.value+'.apache.org/'}, filename);
}
