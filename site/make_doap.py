#!/usr/bin/env python3

import datetime
import re
import cgi
import cgitb; cgitb.enable()  # for troubleshooting

# The master list of data and how we tranform it into the xml we need.
#  0 - the form fieldname
#  1 - the xml tag name to use
#  2 - attribute name if applicable
#  3 - whether it's a URL, 1 = yes (append http:// if rqd), 0 = no
#  4 - printf format string to use for data
#
formData = (
#  0:fieldname   1:xmltag        2:attname       3:URL?  4:Format
    [ 'name',     'name',          '',             0, 'Apache %s' ],
    [ 'homepage', 'homepage',      'rdf:resource', 1 ],
    [ 'pmc',      'asfext:pmc',    'rdf:resource', 0, 'http://%s.apache.org' ],
    [ 'sdesc',    'shortdesc' ],
    [ 'ldesc',    'description' ],
    [ 'bugdb',    'bug-database',  'rdf:resource', 1 ],
    [ 'mail',     'mailing-list',  'rdf:resource', 1 ],
    [ 'dl',       'download-page', 'rdf:resource', 1 ],
    [ 'lang',     'programming-language' ],
    [ 'cat',      'category',      'rdf:resource', 0, 'http://projects.apache.org/category/%s' ],
);

def addData(val, line):
    fields = len(line)
    print("    <%s" % line[1], end='')
    if fields > 2 and line[2]: # there is an attribute name
        print(" %s=\"" % line[2], end='')
    else:
        print(">", end='')
    if fields > 3 and line[3] == 1:
        val = makeURL(val)
    if fields > 4 and line[4]: # have format
        print(line[4] % val, end='')
    else:
        print(val, end='')
    if fields > 2 and line[2]: # there is an attribute name
        print("\" />")
    else:
        print("</%s>" % line[1])

def makeURL(s):
    if s.startswith('http') :
        return s
    return 'http://' + s

dt = '{:%Y-%m-%d}'.format(datetime.datetime.now())

form = cgi.FieldStorage()
projName = form.getvalue("name", "projectName")
# projName is used in the response headers; ensure the name is safe as a file name 
projName = re.sub(r"[^\w-]", '_', projName) + ".rdf"

thehomepage = makeURL(form.getvalue('homepage','www.apache.org'))

dict = {'projName' : projName, 'dt': dt, 'thehomepage': thehomepage}

print("""Content-type: application/rdf+xml
Content-Disposition: attachment; filename=doap_%(projName)s

<?xml version="1.0"?>
<?xml-stylesheet type="text/xsl"?>
<rdf:RDF xml:lang="en"
         xmlns="http://usefulinc.com/ns/doap#" 
         xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" 
         xmlns:asfext="http://projects.apache.org/ns/asfext#"
         xmlns:foaf="http://xmlns.com/foaf/0.1/">
<!--
    Licensed to the Apache Software Foundation (ASF) under one or more
    contributor license agreements.  See the NOTICE file distributed with
    this work for additional information regarding copyright ownership.
    The ASF licenses this file to You under the Apache License, Version 2.0
    (the "License"); you may not use this file except in compliance with
    the License.  You may obtain a copy of the License at
   
         http://www.apache.org/licenses/LICENSE-2.0
   
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
-->
  <Project rdf:about="%(thehomepage)s">
    <created>%(dt)s</created>
    <license rdf:resource="http://spdx.org/licenses/Apache-2.0" />""" % dict)

for line in formData:
    field = line[0]
    val = form.getvalue(field)
    if val:
        addData(val, line)

if form.getvalue('relname'):
    print("""    <release>
      <Version>
        <name>%s</name>
        <created>%s</created>
        <revision>%s</revision>
      </Version>
    </release>"""
    % (form.getvalue('relname'), form.getvalue('reldt'), form.getvalue('relvers')))

if form.getvalue('svnurl'):
    print("""    <repository>
      <SVNRepository>
        <location rdf:resource="%s"/>
        <browse rdf:resource="%s"/>
      </SVNRepository>
    </repository>"""
    % (makeURL(form.getvalue('svnurl')), makeURL(form.getvalue('svnhttp'))))

if form.getvalue('giturl'):
    print("""    <repository>
      <GitRepository>
        <location rdf:resource="%s"/>
        <browse rdf:resource="%s"/>
      </GitRepository>
    </repository>"""
    % (makeURL(form.getvalue('giturl')), makeURL(form.getvalue('githttp'))))

if form.getvalue('maintainer_name'):
    print("""    <maintainer>
      <foaf:Person>
        <foaf:name>%s</foaf:name>
          <foaf:mbox rdf:resource="mailto:%s"/>
      </foaf:Person>
    </maintainer>"""
    % (form.getvalue('maintainer_name'), form.getvalue('maintainer_email')))

if form.getvalue('std_title'):
    print("""    <asfext:implements><asfext:Standard>
      <asfext:title>%s</asfext:title>
      <asfext:body>%s</asfext:body>
      <asfext:id>%s</asfext:id>
      <asfext:url rdf:resource="%s"/>
    </asfext:Standard></asfext:implements>""" 
    % (form.getvalue('std_title'), form.getvalue('std_body'), form.getvalue('std_id'), makeURL(form.getvalue('std_url'))))

print("""  </Project>
</rdf:RDF>
""")