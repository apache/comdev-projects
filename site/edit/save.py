#!/usr/bin/env python

import os
import cgi;
import json;
import smtplib;
import re
from email.mime.text import MIMEText
from subprocess import Popen, PIPE

print ("Content-Type: text/html\r\n\r\n")
print ("Received!")

try:
    form = cgi.FieldStorage();
    user = os.environ['HTTP_X_AUTHENTICATED_USER'] if 'HTTP_X_AUTHENTICATED_USER' in os.environ else "nobody"
    f = form['file'].value if 'file' in form else None


    if f and not re.search(r"([^-.a-zA-Z0-9])", f):
        project = f
        f = "%s.json" % f
        js = {}
        for k in form:
            js[k] = form[k].value
        with open("../json/projects/%s" % f, "w") as out:
            json.dump(js, out, sort_keys=True, indent=0)
            out.close()

        with open("../json/foundation/projects.json", "r") as g:
            gjson = json.loads(g.read())
            g.close()

            gjson[project] = js
            with open("../json/foundation/projects.json", "w") as og:
                json.dump(gjson, og, sort_keys=True, indent=0)
                og.close()


        text = """
    Hello,

    The following new base data was set for %s by %s:

%s

    With regards,
    projects.apache.org
    """ % (project, user, json.dumps(js, indent=4))

        msg = MIMEText(text)
        msg["From"] = "no-reply@projects.apache.org"
        msg["To"] = "dev@community.apache.org"
        msg["Reply-To"] = "dev@community.apache.org, %s@apache.org" % user
        msg["Subject"] = "Project base data change for project '%s'" % project
        p = Popen(["/usr/sbin/sendmail", "-t"], stdin=PIPE)
        p.communicate(msg.as_string())
        print("And saved!")
    else:
        print("But no valid JSON was present!")
except Exception as err:
    print("Exception: %s" % err)
