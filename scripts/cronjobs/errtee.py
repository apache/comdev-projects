"""
    Class to copy stderr to stdout.

    This is intended for use in cronjobs,
    where it is useful to have both stderr and stdout in the log file
    but still have stderr so that the mailer gets any errors
    The main script should be run unbuffered (-u)

    Unfortunately Python does not seem to offer the equivalent of:
    perl -[mM][-]module  execute "use/no module..." before executing program
    ruby -rlibrary       require the library before executing your script
    lua  -l name         require library 'name'
    Thus the module has to be explicitly imported by the user script,
    and the user must defing the 'ERRTEE' environment variable to enable it
  
"""
import sys
import os

class ErrTee(object):
    def write(self, buf):
        sys.__stderr__.write(buf)
        sys.stdout.write(buf)
    def flush(self):
        sys.__stderr__.flush()

# only enable the override if it is needed
if 'ERRTEE' in os.environ:
    sys.stderr=ErrTee()

if __name__ == '__main__': # simple test
    print("STDOUT1")
    sys.stderr.write("STDERR2\n")
    sys.stderr=ErrTee() # enable for testing
    sys.stderr.write("STDERR3 (should also appear on STDOUT)\n")
    raise Exception("STDERR4 (should also appear on STDOUT)")