#################################################
# Pubsubber.py: a minimalistic svnwcsub program #
#################################################

from threading import Thread
from datetime import datetime
import os
import sys
import logging
import atexit
import signal
import json
import re
import time
import subprocess
import base64

version = 2
if sys.hexversion < 0x03000000:
    print("Using Python 2...")
    import httplib, urllib, urllib2, ConfigParser as configparser, socket
    socket._fileobject.default_bufsize = 0
else:
    print("Using Python 3")
    version = 3
    import http.client, urllib.request, urllib.parse, configparser


debug = False
logger = None
watching={} # dict: key = path to watch, value = set() of paths to update on match

############################################################
# Daemon class, courtesy of an anonymous good-hearted soul #
############################################################
class daemon:
        """A generic daemon class.

        Usage: subclass the daemon class and override the run() method."""

        def __init__(self, pidfile, logfile = None):
            self.pidfile = pidfile
            if logfile == None:
                self.logfile = os.devnull
            else:
                self.logfile = logfile
        
        def daemonize(self):
                """Daemonize class. UNIX double fork mechanism."""

                try: 
                        pid = os.fork() 
                        if pid > 0:
                                # exit first parent
                                sys.exit(0) 
                except OSError as err: 
                        sys.stderr.write('fork #1 failed: {0}\n'.format(err))
                        sys.exit(1)
        
                # decouple from parent environment
                os.chdir('/') 
                os.setsid() 
                os.umask(0) 
        
                # do second fork
                try: 
                        pid = os.fork() 
                        if pid > 0:

                                # exit from second parent
                                sys.exit(0) 
                except OSError as err: 
                        sys.stderr.write('fork #2 failed: {0}\n'.format(err))
                        sys.exit(1) 
        
                # redirect standard file descriptors
                sys.stdout.flush()
                sys.stderr.flush()
                si = open(os.devnull, 'r')
                so = open(self.logfile, 'a+')
                se = open(self.logfile, 'a+')

                os.dup2(si.fileno(), sys.stdin.fileno())
                os.dup2(so.fileno(), sys.stdout.fileno())
                os.dup2(se.fileno(), sys.stderr.fileno())
        
                # write pidfile
                atexit.register(self.delpid)

                pid = str(os.getpid())
                with open(self.pidfile,'w+') as f:
                        f.write(pid + '\n')
                logger.info("Created %s", self.pidfile)
        
        def delpid(self):
                logger.info("Removing %s", self.pidfile)
                os.remove(self.pidfile)

        def start(self):
                """Start the daemon."""

                # Check for a pidfile to see if the daemon already runs
                try:
                        with open(self.pidfile,'r') as pf:

                                pid = int(pf.read().strip())
                except IOError:
                        pid = None
        
                if pid:
                        message = "pidfile {0} already exist. " + \
                                        "Daemon already running?\n"
                        sys.stderr.write(message.format(self.pidfile))
                        sys.exit(1)
                
                # Start the daemon
                self.daemonize()
                self.run()

        def stop(self):
                """Stop the daemon."""

                # Get the pid from the pidfile
                try:
                        with open(self.pidfile,'r') as pf:
                                pid = int(pf.read().strip())
                except IOError:
                        pid = None
        
                if not pid:
                        message = "pidfile {0} does not exist. " + \
                                        "Daemon not running?\n"
                        sys.stderr.write(message.format(self.pidfile))
                        return # not an error in a restart

                # Try killing the daemon process        
                try:
                        # Try gentle stop first
                        os.kill(pid, signal.SIGINT)
                        time.sleep(0.2)
                        while 1:
                                os.kill(pid, signal.SIGTERM)
                                time.sleep(0.1)
                except OSError as err:
                        e = str(err.args)
                        if e.find("No such process") > 0:
                                if os.path.exists(self.pidfile):
                                        os.remove(self.pidfile)
                        else:
                                print (str(err.args))
                                sys.exit(1)

        def restart(self):
                """Restart the daemon."""
                self.stop()
                self.start()

        def run(self):
                """You should override this method when you subclass Daemon.
                
                It will be called after the process has been daemonized by 
                start() or restart()."""



####################
# Helper functions #
####################


# read_chunk: iterator for reading chunks from the stream
# since this is all handled via urllib now, this is quite rudimentary
def read_chunk(req):
    while True:
        try:
            line = req.readline().strip()
            if line:
                yield line
            else:
                print("No more lines?")
                break
        except Exception as info:
            
            break
    return

 
#########################
# Main listener program #
#########################

# PubSub class: handles connecting to a pubsub service and checking commits
class PubSubClient(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.setDaemon(True)

    def run(self):
        logger.info("Watching %s", watching)
        while True:
            
            self.req = None
            while not self.req:
                try:
                    if version == 3:
                        self.req = urllib.request.urlopen(self.url, None, 30)
                    else:
                        self.req = urllib2.urlopen(self.url, None, 30)
                    
                    logger.info("Connected to %s", self.url)
                except:
                    logger.warn("Failed to connect to %s", self.url)
                    time.sleep(30)
                    continue
                
            for line in read_chunk(self.req):
                if version == 3:
                    line = str( line, encoding='ascii' ).rstrip('\r\n,').replace('\x00','') # strip away any old pre-0.9 commas from gitpubsub chunks and \0 in svnpubsub chunks
                else:
                    line = str( line ).rstrip('\r\n,').replace('\x00','') # strip away any old pre-0.9 commas from gitpubsub chunks and \0 in svnpubsub chunks
                try:
                    obj = json.loads(line)
                    if "commit" in obj and "repository" in obj['commit']:
                        # If it's our public svn repo, then...
                        if obj['commit']['repository'] == "13f79535-47bb-0310-9956-ffa450edef68":
                            #Grab some vars
                            commit = obj['commit']
                            # e.g. {"committer": "sebb", "log": "Ensure we exit on control+C", "repository": "13f79535-47bb-0310-9956-ffa450edef68", "format": 1, 
                            # "changed": {"comdev/reporter.apache.org/trunk/scandist.py": {"flags": "U  "}}, 
                            # "date": "2015-07-13 13:38:33 +0000 (Mon, 13 Jul 2015)", "type": "svn", "id": 1690668}
                            svnuser = commit['committer']
                            revision = commit['id']
                            filePaths = set()
                            # e.g. {"comdev/reporter.apache.org/trunk/scandist.py": {"flags": "U  "}}
                            for path in commit['changed']:
                                for watchPath in watching:
                                    # Check if the commit is for our part of the repo
                                    match = re.match("^%s" % watchPath, path)
                                    if match:
                                        filePath = str(watching[watchPath])
                                        if debug:
                                            print("Matched '" + path + "' against '" + watchPath + "'; would run 'svn up " + filePath + "'")
                                        filePaths.update(watching[watchPath])
                            if filePaths:
                                for filePath in filePaths:
                                    if debug:
                                        print("Matched 'r" + str(revision) + "'; would run 'svn up " + filePath + "'")
                                    else:
                                        time.sleep(3)
                                        logger.info("svn up %s", filePath)
                                        subprocess.call(['svn','up', filePath])
                            else:
                                logger.debug("Did not match 'r" + str(revision) + "' against ' " + str(watching.keys()) + "'")
                                if debug:
                                    print("Did not match 'r" + str(revision) + "' against ' " + str(watching.keys()) + "'")
                    

                except ValueError as detail:
                    continue
            




################         
# Main program #
################
"""
According to https://svn.apache.org/repos/asf/subversion/trunk/tools/server-side/svnpubsub/svnpubsub/server.py

#   URLs are constructed from 3 parts:
#       /${notification}/${optional_type}/${optional_repository}
#
#   Notifications can be sent for commits or metadata (e.g., revprop) changes.
#   If the type is included in the URL, you will only get notifications of that type.
#   The type can be * and then you will receive notifications of any type.
#
#   If the repository is included in the URL, you will only receive
#   messages about that repository.  The repository can be * and then you
#   will receive messages about all repositories.

"""

def main():
    if debug:
        print("Foreground test mode enabled, no updates will be made")
        for watchPath in watching:
            print("Watching: '" + watchPath + "' for updates to '" + str(watching[watchPath]) + "'")
        
  
    
    # Start the svn thread
    svn_thread = PubSubClient()
    svn_thread.url = "http://svn-master.apache.org:2069/commits/*"
    svn_thread.start()
    
    while True:
        try:
            time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Detected shutdown interrupt")
            pass

##############
# Daemonizer #
##############
class MyDaemon(daemon):
    def run(self):
        main()

def usage():
    print("usage: %s start|stop|restart|foreground ([repo-path] [file-path])*" % sys.argv[0])
    print("for example: %s start comdev/projects.apache.org /var/www/projects.apache.org"  % sys.argv[0])

def handle_args(args):
    if len(args) %  2 != 0:
        usage()
        sys.exit("Need an even number of repo/file paths, found "+str(len(args)))
    else:
        for i in range(0, len(args), 2):
            try:
                watching[args[i]].update(args[i+1])
            except KeyError:
                watching[args[i]] = set([args[i+1]])

if __name__ == "__main__":
        logger = logging.getLogger('pubsubber')
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        logfile = os.environ.get('LOGFILE')
        logger.info("LOGFILE=%s", logfile)
        daemon = MyDaemon('/tmp/pubsubber.pid', logfile)
        if len(sys.argv) >= 2:
                if 'start' == sys.argv[1]:
                    handle_args(sys.argv[2:])
                    daemon.start()
                elif 'stop' == sys.argv[1]:
                    daemon.stop()
                elif 'restart' == sys.argv[1]:
                    daemon.restart()
                elif 'foreground' == sys.argv[1]:
                    debug = True
                    handle_args(sys.argv[2:])
                    main()
                else:
                    usage()
                    sys.exit(2)
                sys.exit(0)
        else:
                usage()
                sys.exit(2)

