"""
   Some utilities for working with URLs
   Works with Python2 and Python3
"""

import os
from os.path import dirname, abspath, join, getmtime, basename
import shutil
import io
import errno

# Allow for Python2/3 differences
try:
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError
    from urllib.parse import urlparse
    _PY3 = True
except:
    from urllib2 import urlopen, Request
    from urllib2 import HTTPError
    from urlparse import urlparse
    from io import open # needed for encoding
    _PY3 = False

import time
import calendar

# time format used in Last-Modified/If-Modified-Since HTTP headers
_HTTP_TIME_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'

# Allow callers to check HTTP code from Python2 and 3
def isHTTPNotFound(e):
    return type(e) == HTTPError and e.code == 404

def touchFile(f, t):
    if _PY3:
        os.utime(f, times=(t, t))
    else:
        os.utime(f, (t, t))

def mod_date(t):
    """
        get file mod date in suitable format for If-Modified-Since
        e.g. Thu, 15 Nov 2012 16:38:51 GMT
        @param t: the time in seconds
        @return:  None if t < 0
    """
    if t < 0:
        return None
    return time.strftime(_HTTP_TIME_FORMAT, time.gmtime(t))

def getIfNewer(url, sinceTime, encoding=None, errors=None, silent=False, debug=False):
    """
        Get a URL if it is not newer
    
        @param url: the url to fetch (required)
        @param sinceTime: the most recent Last-Modified string (required, format as per mod_date())
        @param encoding: the encoding to use (default 'None')
        @param errors: If encoding is provided, this specifies the on-error action (e.g. 'ignore')
        @return: (lastMod, response)
        - lastMod: the Last-Modified string (from sinceTime if the URL is not later) may be None
        - response: the HTTPResponse (encoding == None) or TextIOBase object.
         'None' if the URL is not newer
        @raise urllib.error.HTTPError: if URL not found or other error
    """
    if sinceTime:
        headers = {"If-Modified-Since" : sinceTime}
    else:
        headers = {}
    response = None
    try:
        if not silent: print("%s %s" % (url, headers))
        req = Request(url, headers=headers)
        resp = urlopen(req)
        # Debug - detect why json sometimes returned as HTML but no error code
        if debug and not silent: print("STATUS %s" % resp.getcode()) # Works for Py2/3
        if debug and not silent: print(resp.headers)
        try:
            lastMod = resp.headers['Last-Modified']
            if not lastMod: # e.g. responses to git blob-plain URLs don't seem to have dates
                lastMod = None
        except KeyError: # python2 raises this for missing headers
            lastMod = None
        if encoding:
            response = io.TextIOWrapper(resp, encoding=encoding, errors=errors)
        else:
            response = resp
    except HTTPError as err:
        if err.code == 304:
            lastMod = sinceTime # preserve timestamp
        else:
            raise
    return lastMod, response

def findRelPath(relpath):
    for d in ['./','../','../../']: # we may located at same level or 1 or 2 below
        dir = join(d,relpath)
        if os.path.isdir(dir):
            return dir
    raise OSError("Cannot find path " + path)

class UrlCache(object):
    """
        Creates a cache for URLs.
        The file modification time is set to the Last-Modified header of the URL (if any)
        If a check interval is specified (>0),
        a hidden marker file is used to record the last check time (unless useFileModTime==True)

        @param cachedir: the cache directory to use 
            (default data/cache; this is assumed to be at the current directory, its parent or grandparent)
        @param interval: minimum interval between checks for updates to the URL (default 300 secs)
            if set to -1, never checks (intended for testing only)  
            if set to 0, always checks (primarily intended for testing, also useful where URLs support If-Modified-Since)
        @return: the instance to use with the get() method
    """
    # get file mod_date
    def __file_mtime(self, filename):
        try:
            t = getmtime(filename)
        except OSError as e:
            if not e.errno == errno.ENOENT:
                raise e
            t = -1 # so cannot be confused with a valid mtime
        return t

    def __init__(self, cachedir=None, interval=300, silent=False, debug=False):
        __CACHE = 'data/cache'
        self.__interval = interval
        self.__cachedir = None
        self.__silent = silent
        self.__debug = debug and not silent # don't allow debug if silent
        if cachedir: # assumed to be correct
            self.__cachedir = cachedir
        else:
            self.__cachedir = __CACHE # will be overwritten if actually found
            self.__cachedir = findRelPath(__CACHE)
        
        if os.path.isdir(self.__cachedir):
            if not self.__silent: print("Cachedir: %s" % self.__cachedir)
        else:
            raise OSError("Could not find cache directory '%s'" % self.__cachedir)

    def __getname(self, name):
        return join(self.__cachedir, name)

    def __getMarker(self, name):
        return join(self.__cachedir, '.' + name)

    def _deleteCacheFile(self, name):# intended mainly for debug use
        path = self.__getname(name)
        try:
            os.remove(path)
        except OSError as e:
            if not e.errno == errno.ENOENT:
                raise e
        dotpath = self.__getMarker(name)
        try:
            os.remove(dotpath)
        except OSError as e:
            if not e.errno == errno.ENOENT:
                raise e

    def get(self, url, name, encoding=None, errors=None, useFileModTime=False):
        """
            Check if the filename exists in the cache.
            If it does not, or if it does and the URL has not been checked recently,
            then try to download the URL using If-Modified-Since.
            The URL is downloaded to a temporary file and renamed to the filename
            to reduce the time when the file is being updated.
            The interval parameter is used to determine how often to check if the URL has changed.
            (this is mainly intended to avoid excess URL requests in unit testing).
            If this is set to -1, then the URL will only be downloaded once. 
            @param url: the url to fetch (required)
            @param name: the name to use in the cache (required)
            @param encoding: the encoding to use (default None)
            @param errors: If encoding is provided, this specifies the on-error action (e.g. 'ignore')
                        (default None)
            @param useFileModTime: whether to use the file modification time as the last check time
            If not, a hidden marker file is used (default false). Set this to true for URLs that don't
            provide a Last-Modified header
            @return: the opened stream, using the encoding if specified. Otherwise opened in binary mode. 
        """
        if name == None:
            name = basename(urlparse(url).path)
        target=self.__getname(name)
        fileTime = self.__file_mtime(target)
        if useFileModTime:
            check = self.__getname(name)
        else:
            check = self.__getMarker(name)
        upToDate = False
        if fileTime >= 0:
            if self.__interval == -1:
                if not self.__silent: print("File %s exists and URL check has been disabled" % name)
                upToDate = True
            elif self.__interval == 0:
                if not self.__silent: print("File %s exists and check interval is zero" % name)
            else:
                checkTime = self.__file_mtime(check)
                now = time.time()
                diff = now - checkTime
                if diff < self.__interval:
                    if not self.__silent: print("Recently checked: %d < %d, skip check for %s" % (diff, self.__interval, name))
                    upToDate = True
                else:
                    if checkTime >= 0:
                        if not self.__silent: print("Not recently checked: %d > %d (%s)" % (diff, self.__interval, name))
                    else:
                        if not self.__silent: print("Not recently checked (%s)" % name)
        else:
            if not self.__silent: print("Not found %s " % name)

        if not upToDate:
            sinceTime = mod_date(fileTime)
            lastMod, response = getIfNewer(url, sinceTime, silent=self.__silent, debug=self.__debug)
            if response: # we have a new version
                if lastMod:
                    try:
                        lastModT = calendar.timegm(time.strptime(lastMod, _HTTP_TIME_FORMAT))
                    except ValueError:
                        lastModT = 0
                else:
                    lastModT = 0
                
                tmpFile = target + ".tmp"
                with open(tmpFile,'wb') as f:
                    shutil.copyfileobj(response, f)
                if not useFileModTime:
                    # store the last mod time as the time of the file
                    touchFile(tmpFile, lastModT)
                os.rename(tmpFile, target) # seems to preserve file mod time
                if lastMod:
                    if fileTime > 0:
                        if not self.__silent: print("Downloaded new version of %s (%s > %s)" % (name, lastMod, sinceTime))
                    else:
                        if not self.__silent: print("Downloaded new version of %s (%s)" % (name, lastMod))
                else:
                    if not self.__silent: print("Downloaded new version of %s (undated)" % (name))
            else:
                if not self.__silent: print("Cached copy of %s is up to date (%s)" % (name, lastMod))

    
            if self.__interval > 0: # no point creating a marker file if we won't be using it
                if useFileModTime:
                    os.utime(check, None) # touch the marker file
                else:
                    with open(check,'a'):
                        os.utime(check, None) # touch the marker file

        if encoding:
            return open(target, 'r', encoding=encoding, errors=errors)
        else:
            return open(target, 'rb')

if __name__ == '__main__':
    try:
        fc = UrlCache(cachedir='x')
        raise Error("Expected OSError")
    except OSError as e:
        print('Expected: %s' % e)
    fc = UrlCache(interval=0)
    name = "_wao.html"
    fc._deleteCacheFile(name)
    icla_info = fc.get("http://www.apache.org/", name, encoding='utf-8')
    print(icla_info.readline().rstrip())
    print(icla_info.readline().rstrip())
    print(icla_info.readline().rstrip())
    print(icla_info.readline().rstrip())
    icla_info = fc.get("http://www.apache.org/", name, encoding='utf-8')
    fc._deleteCacheFile(name)
