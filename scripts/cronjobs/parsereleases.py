import errtee
import re, urllib.request
import json
import os

"""
Reads the list of files in http://www.apache.org/dist/

Creates:
../../site/json/foundation/releases.json
Format:
{ top-level dir: { release-id: date}, ... }

The release id is derived from the filename by removing common suffixes etc, see cleanFilename()
The date comes from the first entry

../../site/json/foundation/releases-files.json
Format:
{ top-level dir: { release-id: [list of files for that release-id]}, ... }

TODO: it would probably be more efficient to parse the output of
svn ls -R https://dist.apache.org/repos/dist/release/
Could cache the output based on the last changed date

Or use an rsync listing:
rsync --list-only -r rsync.apache.org::apache-dist
Note that rsync excludes hashes, sigs and KEYS files; however they are not needed here.
"""

releases = {}
files = {}
mainurl = "http://www.apache.org/dist/"

x = 0

# don't try to maintain history for the moment...
#try:
#    with open("../../site/json/foundation/releases.json") as f:
#        releases = json.loads(f.read())
#        f.close()
#except Exception as err:
#    print("Could not read releases.json, assuming blank slate")

def getDirList(url):
    try:
        data = urllib.request.urlopen(url).read().decode('utf-8')
        for entry, xd, xdate in re.findall(r"<a href=\"([^\"/]+)(/?)\">.+</a>\s+(\d\d\d\d-\d\d-\d\d)", data, re.MULTILINE | re.UNICODE):
            yield(entry, xdate, xd)
    except:
        pass

def cleanFilename(filename):
    """
        Attempts to determine the release id to which a file belongs
        Strips extensions such as .tgz etc, then suffixes such as -sources
        Replaces qualifiers such as -assembly-, -parent- by '-'
        Returns the simplified filename .
    """
    for suffix in ['.tgz', '.gz', '.bz2', '.xz', '.zip', '.rar', '.tar', 'tar', '.deb', '.rpm', '.dmg', '.egg', '.gem', '.pom', '.war', '.exe',
                   '-scala2.11', '-cdh4', '-hadoop1', '-hadoop2', '-hadoop2.3', '-hadoop2.4', '-all',
                   '-src', '_src', '.src', '-sources', '_sources', '-source', '-bin', '-dist',
                   '-source-release', '-source-relase', '-apidocs', '-javadocs', '-javadoc', '_javadoc', '-tests', '-test', '-debug', '-uber',
                   '-macosx', '-distribution', '-example', '-manual', '-native', '-win', '-win32', '-linux', '-pack', '-packaged', '-lib', '-current', '-embedded',
                   '-py', '-py2', '-py2.6', '-py2.7', '-no', 'unix-distro', 'windows-distro', 'with', '-dep', '-standalone', '-war', '-webapp', '-dom', '-om', '-manual', '-site',
                   '-32bit', '-64bit', '-amd64', '-i386', '_i386', '.i386', '-x86_64', '-minimal', '-jettyconfig', '-py2.py3-none-any', 'newkey', 'oldkey', 'jars', '-jre13', '-hadoop1', '-hadoop2', '-project',
                   '-with-dependencies', '-client', '-server', '-doc', '-docs', 'server-webapps', '-full', '-all', '-standard', '-for-javaee', '-for-tomcat',
                   'hadoop1-scala2', '-deployer', '-fulldocs', '-windows-i64', '-windows-x64', '-embed', '-apps', '-app', '-ref', '-installer', '-bundle', '-java']:
        if filename[len(filename)-len(suffix):] == suffix:
            filename = filename[0:len(filename)-len(suffix)]
    for repl in ['-assembly-', '-minimal-', '-doc-', '-src-', '-webapp-', '-standalone-', '-parent-', '-project-', '-win32-']:
        filename = filename.replace(repl, '-')
    return filename

def cleanReleases(committeeId):
    if len(releases[committeeId]) == 0:
        del releases[committeeId]
        del files[committeeId]

def parseDir(committeeId, path):
    print("              %s..." % path)
    if len(path) > 100:
        print("WARN too long path: recursion?")
        return
    for f, d, xd in getDirList("%s/%s" % (mainurl, path)):
        if xd:
            if ("/%s" % f) not in path and f.lower() not in ['binaries', 'repos', 'updatesite', 'current', 'stable', 'stable1', 'stable2', 'binary', 'notes', 'doc', 'eclipse', 'patches', 'docs', 'changes', 'features', 'tmp', 'cpp', 'php', 'ruby', 'py', 'py3', 'issuesfixed', 'images', 'styles', 'wikipages']:
                parseDir(committeeId, "%s/%s" % (path, f))
        # Note: this eliminates binary archives; not sure whether that is intentional or not.
        elif not re.search(r"(MD5SUM|SHA1SUM|\.md5|\.mds|\.sh1|\.sh2|\.sha|\.asc|\.sig|\.bin|\.pom|\.jar|\.whl|\.pdf|\.xml|\.xsd|\.html|\.txt|\.cfg|\.ish|\.pl|RELEASE.NOTES|LICENSE|KEYS|CHANGELOG|NOTICE|MANIFEST|Changes|readme|x86|amd64|-manual\.|-docs\.|-docs-|-doc-|Announcement|current|-deps|-dependencies|binary|-bin-|-bin\.|-javadoc-|-distro|rat_report)", f, flags=re.IGNORECASE):
            filename = cleanFilename(f)
            if len(filename) > 1:
                if filename not in releases[committeeId]:
                    releases[committeeId][filename] = d
                    files[committeeId][filename] = []
                    print("                  - %s\t\t\t%s" % (filename, f))
                files[committeeId][filename].append("%s/%s" % (path, f))


for committeeId, d, xdir in getDirList(mainurl):
    if committeeId != 'incubator':
        if committeeId not in ['xml', 'zzz', 'maven-repository']:
            print("Parsing /dist/%s content:" % committeeId)
            releases[committeeId] = releases[committeeId] if committeeId in releases else {}
            files[committeeId] = {}
            parseDir(committeeId, committeeId)
            cleanReleases(committeeId)
    else:
        for podling, d, xd in getDirList("%s/incubator/" % mainurl):
            print("Parsing /dist/incubator-%s content:" % podling)
            committeeId = "incubator-%s" % podling
            releases[committeeId] = releases[committeeId] if committeeId in releases else {}
            files[committeeId] = {}
            parseDir(committeeId, "incubator/%s" % podling)
            cleanReleases(committeeId)

print("Writing releases.json")
with open("../../site/json/foundation/releases.json", "w") as f:
    json.dump(releases, f, sort_keys=True, indent=0)
    f.close()
with open("../../site/json/foundation/releases-files.json", "w") as f:
    json.dump(files, f, sort_keys=True, indent=0)
    f.close()

print("All done!")