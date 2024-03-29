#!/usr/bin/env python3

import errtee # pylint: disable=unused-import
from collections import defaultdict
import gzip
import json
from os.path import dirname, join, realpath
from urlutils import UrlCache

"""
Reads the list of files in https://downloads.apache.org/zzz/find-ls.gz

Creates:
../../site/json/foundation/releases.json
Format:
{ top-level dir: { release-id: date}, ... }

The release id is derived from the filename by removing common suffixes etc, see cleanFilename()
The date comes from the first entry

../../site/json/foundation/releases-files.json
Format:
{ top-level dir: { release-id: [list of files for that release-id]}, ... }

"""

# Listing generated by find(1) -ls
FIND_LS = 'https://downloads.apache.org/zzz/find-ls2.txt.gz'

# key: committee-id, value: dict(key: release version, value: date)
releases = defaultdict(dict)

# key: committee-id, value: dict(key: release version, value: list of file names for the release)
files = defaultdict(lambda: defaultdict(list))

def cleanFilename(filename):
    """
        Attempts to determine the release id to which a file belongs
        Strips extensions such as .tgz etc, then suffixes such as -sources
        Replaces qualifiers such as -assembly-, -parent- by '-'
        Returns the simplified filename .

        N.B. the ordering is significant, as the list is only scanned once
    """
    for suffix in ['-all', '-src', '_src', '.src', '-sources', '_sources', '-source', '-bin', '-dist',
                   '-source-release', '-source-relase', '-tests', '-test', '-debug', '-uber',
                   '-macosx', '-distribution', '-example', '-native', '-win', '-win32', '-linux', '-pack', '-packaged', '-current', '-embedded',
                   '-py', '-py2', '-py2.6', '-py2.7', '-no', 'unix-distro', 'windows-distro', 'with', '-dep', '-standalone', '-webapp', '-dom', '-om',
                   '-32bit', '-i386', '_i386', '.i386', '-minimal', '-jettyconfig', '-py2.py3-none-any', 'newkey', 'oldkey', 'jars', '-jre13', '-hadoop1', '-hadoop2', '-project',
                   '-with-dependencies', '-client', '-server', 'server-webapps', '-full', '-all', '-standard', '-for-javaee', '-for-tomcat',
                   'hadoop1-scala2', '-deployer', '-fulldocs', '-embed', '-apps', '-app', '-ref', '-installer', '-bundle', '-java']:
        # The above list could be simplified further
        if filename.endswith(suffix):
            filename = filename[0:len(filename)-len(suffix)]
    for repl in ['-assembly-', '-minimal-', '-doc-', '-src-', '-webapp-', '-standalone-', '-parent-', '-project-', '-win32-']:
        filename = filename.replace(repl, '-')
    return filename

def cleanReleases(committeeId):
    if len(releases[committeeId]) == 0:
        del releases[committeeId]
        del files[committeeId]

# all source releases must be one of these
VALID_TYPES = ['tgz', 'gz', 'zip', 'xz', 'bz2']

# for gz, xz and bz2, the next extension must be tar
TAR_TYPES = ['gz', 'xz', 'bz2']

# file name stems that finish with these strings are not source archives:
NON_SOURCE_ENDS = ['-amd64', '-aarch64',  '-arm64', '.bin', '-bin', '-binary', '-deps', '-docs', '-javadoc', '-doc',
                    '-lib', '-lib-debug', '-manual', '-site', '-x64', '-x86', 'x86_64', '-ia32', '-i64',
                    '-war', '-64bit', '-arm64bit', '-doc', '-apidocs', '-bundle']

# stems that match these strings are not source archives:
NON_SOURCE_MATCH = ['-bin-', '-binary-', '-docs-', 'x86-windows', 'x64-windows']
# Warning: beware of accidentally matching Maven plugins!

# filters for dirs, matches and ends that may only apply to certain PMCs
CTTEE_FILTERS = {
    "solr": {
        "ENDS": ['-slim'],
        "MATCH": [],
        "DIRS": ['helm-charts']
    }
}

# Don't visit these directories
SKIP_DIRS = ['META', 'aarch64current', 'bin', 'binaries', 'binary', 'changes', 'cpp', 'css', 'doc', 'docs',
             'eclipse', 'features', 'hidden', 'images', 'issuesfixed', 'notes', 'patches', 'php', 'py', 'py3',
             'repos', 'ruby', 'stable', 'stable1', 'stable2', 'styles', 'tmp', 'updatesite', 'website', 'wikipages']

def parseFile(committeeId, file, date, path):
    parts = file.split('.')
    ext = parts.pop() # final extension
    if not ext in VALID_TYPES or (ext in TAR_TYPES and parts.pop() != 'tar'):
        return
    stem = ".".join(parts) # the filename stem without the archive suffice(s)
    if (any(stem.endswith(end) for end in NON_SOURCE_ENDS + CTTEE_FILTERS.get(committeeId,{}).get('ENDS',[])) or 
        any(mat in stem for mat in NON_SOURCE_MATCH + CTTEE_FILTERS.get(committeeId,{}).get('MATCH',[]))):
        return
    filename = cleanFilename(stem)
    if len(filename) > 1:
        if filename not in releases[committeeId]:
            releases[committeeId][filename] = date
            files[committeeId][filename] = []
            print(f"                  - {filename}\t\t\t{file}")
        files[committeeId][filename].append(path)

def main():
    uc = UrlCache(silent=True)
    find_ls = uc.get(FIND_LS, name='find-ls2.txt.gz')
    #  -rw-rw-r--       1 svnwc svnwc           479 2022-06-17 12:55 UTC ./.htaccess
    #    0              1   2     3               4       5       6   7    8 
    with gzip.open(find_ls, mode='rt') as r:
        for l in r:
            fields = l.split() # split the find line (the split drops the final LF)
            if not fields[0].startswith('-'): # only want plain files
                continue
            path = fields[8][2:] # last entry on line is the path; also drop the ./ prefix
            segs = path.split('/')
            if len(segs) == 1: # ignore top level files
                continue
            file = segs.pop() # basename
            # Ignore invisible files
            if file.startswith('.') or file in ['favicon.ico', 'META']:
                continue
            committeeId = segs[0]
            if any( seg in SKIP_DIRS + CTTEE_FILTERS.get(committeeId,{}).get('DIRS',[])  for seg in segs):
                # print('SKIP', segs)
                continue
            if committeeId in ['zzz']:
                continue
            if committeeId == 'incubator':
                podling = segs[1]
                committeeId = f'incubator-{podling}'
            # Now store the info
            stamp = fields[5]
            parseFile(committeeId, file, stamp, path)

if __name__ == '__main__':
    mypath = realpath(__file__)
    assert '/scripts/cronjobs/' in mypath, "Expected this source file to be under scripts/cronjobs !"
    myhome = dirname(dirname(dirname(mypath))) # home dir is ../..
    jsondir = join(myhome, 'site', 'json', 'foundation') # where the JSON files go
    main()
    print("Writing releases.json")
    with open(join(jsondir, "releases.json"), "w", encoding='utf-8') as f:
        json.dump(releases, f, sort_keys=True, indent=0)
    print("Writing releases-files.json")
    with open(join(jsondir, "releases-files.json"), "w", encoding='utf-8') as f:
        json.dump(files, f, sort_keys=True, indent=0)
    print("All done!")
