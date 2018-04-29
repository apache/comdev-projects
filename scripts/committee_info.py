"""

Module to give access to data from committee-info.json

This module acts as the gatekeeper for all access to committee-info.json
which is cached from https://whimsy.apache.org/public/committee-info.json

"""

import sys
if sys.hexversion < 0x03000000:
    raise ImportError("This script requires Python 3")
import os
from os.path import dirname, abspath, join
from inspect import getsourcefile
import urllib.request
import time
import calendar
import json

MYHOME = dirname(abspath(getsourcefile(lambda:0))) # automatically work out home location so can run the code anywhere
# we assume that this script is located one level below the top
COMDEV_HOME=dirname(MYHOME)
CACHE_DIR=join(COMDEV_HOME,'data','cache')
URL='https://whimsy.apache.org/public/committee-info.json'
NAME='committee-info.json'
FILE=join(CACHE_DIR, NAME)
print(FILE)
INTERVAL=300 # code won't recheck for updated HTTP file until this number of seconds has elapsed

# time format used in Last-Modified/If-Modified-Since HTTP headers
HTTP_TIME_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'

cidata = {} # The data read from the file

# get file mod date in suitable format for If-Modified-Since
def mod_date(t):
    return time.strftime(HTTP_TIME_FORMAT, time.gmtime(t))

# get file mod_date
def file_mtime(filename):
    try:
        t = os.path.getmtime(filename)
    except FileNotFoundError:
        t = -1 # distinguish from no modTime in http response
    return t

# download url as file if the cached copy is too old
def get_url_if_newer(url, dir, name):
    path=join(dir,name)
    fileTime = file_mtime(path)
    check = join(dir,".checked_"+name)
    if fileTime >= 0:
        checkTime = file_mtime(check)
        now = time.time()
        if checkTime > (now - INTERVAL):
            print("Recently checked %d\n%d\n%d, skip check" % (INTERVAL, checkTime, now))
            return
        else:
            print("Not recently checked\n%d\n%d" % (checkTime, now))
    else:
        print("Not found %s" % name)

    sinceTime = mod_date(fileTime)
    headers = {"If-Modified-Since" : sinceTime}

    req = urllib.request.Request(url, headers=headers)
    try:
        response = urllib.request.urlopen(req)
        lastMod = response.headers['Last-Modified']
        lastModT = calendar.timegm(time.strptime(lastMod, HTTP_TIME_FORMAT))
        outFile = path + ".tmp"
        with open(outFile,'wb') as f:
            f.write(response.read())
            f.close()

        # store the last mod time as the time of the file
        os.utime(outFile, times=(lastModT, lastModT))
        os.rename(outFile, path) # seems to preserve file mod time
        print("Downloaded new version of %s " % path)
    except urllib.error.HTTPError as err:
        if not err.code == 304:
            raise
        else:
            print("Cached copy of %s is up to date" % path)

    with open(check,'a'):
        os.utime(check, None) # touch the marker file

def update_cache():
    global cidata # Python defaults to creating a local variable
    get_url_if_newer(URL, CACHE_DIR, NAME)
    with open(FILE, "r", encoding='utf-8') as f:
        cidata = json.loads(f.read())
        f.close()

update_cache() # done when loading

def chairs():

    committees = cidata['committees']

    chairjson={}
    for ctte in committees:
        c = committees[ctte]
        if not c['pmc']:
            continue
        chs = c['chair']
        ch = None
        for ch in chs: # allow for multiple chairs
            break
        name = 'Apache %s' % c['display_name']
        if ch:
            chairjson[name] = chs[ch]['name']

    return chairjson

def cycles():

    committees = cidata['committees']

    cycles={}
    for ctte in committees:
        c = committees[ctte]
        if not c['pmc']:
            continue
        cycles[ctte] = c['report']
        # Duplicate some entries for now so the code can find them (the existing json has the duplicates)
        if ctte == 'ws': # Special processing
            cycles['webservices'] = cycles[ctte]
        if ctte == 'httpd': # Special processing
            cycles['http server'] = cycles[ctte]
    return cycles

"""
Returns an array of entries of the form:

    "abdera": {
      "fullname": "Apache Abdera",
      "mail_list": "abdera",
      "established": "2008-11",
      "report": [
        "February",
        "May",
        "August",
        "November"
      ],
       "reporting": 2,
      "chair": {
        "nick": "antelder",
        "name": "Ant Elder"
        },
      "pmc": true
      },

"""
def committees():

    committees = {}
    cttes = cidata['committees']
    for ent in cttes:
        ctte = cttes[ent]
        c = {}
        for key in ctte:
            # some keys need special processing
            if key == 'display_name':
                basename = ctte['display_name']
                c['fullname'] = "Apache %s" % ('mod_perl' if basename == 'Perl' else basename)
            elif key == 'chair':
                c['chair'] = None
                for ch in ctte['chair']:
                    c['chair'] = {
                    'nick': ch,
                    'name': ctte['chair'][ch]['name']}
            elif key == 'established':
                value = ctte[key]
                if value:
                    value = "%s-%s" % (value[3:7], value[0:2]) # extract year and month
                c[key] = value
            elif key == 'report':
                c[key] = ctte[key] # save original values
                value = ctte[key]
                if 'January' in value:
                    c['reporting'] = 1
                elif 'February' in value:
                    c['reporting'] = 2
                elif 'March' in value:
                    c['reporting'] = 3
                elif 'Every month' in value:
                    c['reporting'] = 0
            else:
                c[key] = ctte[key]
        committees[ent]=c
    return committees

def pmcdates():
    dates = {}
    
    cttes = cidata['committees']
    for ent in cttes:
        ctte = cttes[ent]
        if not ctte['pmc']:
            continue
        roster = ctte['roster']
        est = ctte['established']
        date = 0
        if not est == None:
            # convert mm/yyyy to date (drop any subsequent text)
            try:
                date = calendar.timegm(time.strptime(est[0:7], '%m/%Y'))
            except Exception as e:
                print("Date parse error for %s: %s %s" % (ent, est, e))
                pass
        dates[ent] = {'pmc': [est, date], 'roster': {} }
        ids = {}
        for id in roster:
            rid = roster[id]
            try:
                date = calendar.timegm(time.strptime(rid['date'], '%Y-%m-%d'))
            except:
                date = 0
            ids[id] = [rid['name'], date]
        dates[ent]['roster'] = ids
        # The 'CI' internal name for Web Services is 'ws' but reporter code originally used 'webservices'
        if ent == 'ws':
            dates['webservices'] = dates[ent]
    return dates