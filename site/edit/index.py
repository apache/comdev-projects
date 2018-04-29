#!/usr/bin/env python
import os, re
print ("Content-Type: text/html\r\n\r\n")

user = os.environ['HTTP_X_AUTHENTICATED_USER'] if 'HTTP_X_AUTHENTICATED_USER' in os.environ else ""
m = re.match(r"^([-a-zA-Z0-9_.]+)$", user)
groups = []
if m:
    uid = m.group(1)
    with open("index.html", "r") as f:
        data = f.read()
        f.close()
        print(data.replace("%name%", uid))
              
else:
    print("Unknown or invalid user id presented")
        
