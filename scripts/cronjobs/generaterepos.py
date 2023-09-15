#!/usr/bin/python3

"""

Reads:
https://svn.apache.org/repos/asf/
https://gitbox.apache.org/repositories.json

Updates:
../../site/json/foundation/repositories.json

"""

import json
import requests
from html.parser import HTMLParser

repos = {}

class SVNRepoParser(HTMLParser):
    handleProjectData = False

    def handle_starttag(self, tag, attrs):
        if tag == 'li':
            self.handleProjectData = True

    def handle_endtag(self, tag):
        self.handleProjectData = False

    def handle_data(self, data):
        if self.handleProjectData:
            committee = data.rstrip('/')
            repos[committee + '-svn'] = 'https://svn.apache.org/repos/asf/' + committee + '/'


# Parse svn repos
try:
    svnResponse = requests.get("https://svn.apache.org/repos/asf/", timeout=120)
    svnResponse.raise_for_status()

    parser = SVNRepoParser()
    parser.feed(svnResponse.content.decode("utf-8"))
except requests.exceptions.RequestException as e:  # This is the correct syntax
    print("ERROR: Unable to retrieve svn repos: %s", e)


# Parse git repos
try:
    gitResponse = requests.get("https://gitbox.apache.org/repositories.json", timeout=120)
    gitResponse.raise_for_status()
    gitData = json.loads(gitResponse.content.decode("utf-8"))
    
    for committee in gitData['projects']:
        for repo in gitData['projects'][committee]['repositories']:
            repos[repo] = 'https://gitbox.apache.org/repos/asf/' + repo + '.git'
except requests.exceptions.RequestException as e:  # This is the correct syntax
    print("ERROR: Unable to retrieve git repos: %s", e)

print("Writing json/foundation/repositories.json...")
with open("../../site/json/foundation/repositories.json", "w", encoding='utf-8') as f:
    json.dump(repos, f, sort_keys=True, indent=0)
    f.close()

print("All done!")

