# Script to run "svn add" and redirect standard output to /var/log/www-data
# adds header and trailer to any output

# Output log file is named after the SVN directory name plus the suffix _YYYY-MM
# This ensures that at most one month's data is in each log file

# Sample crontab entry:
# 10 4 * * *      cd /var/www/projects.apache.org/scripts/cronjobs && ./svnadd.sh ../../site/json

STARTED=$(date '+%Y-%m-%d %H:%M:%S')

SVNDIR=${1?SVN directory}

LOGDIR=/var/log/www-data

BASE=$(basename $SVNDIR)

YYMM=$(date '+%Y-%m')

# Create the cumulative log dir if necessary
ARCHIVE_DIR=${LOGDIR}/${YYMM}
test -d ${ARCHIVE_DIR} || mkdir ${ARCHIVE_DIR}

ARCHIVE_NAME=${BASE}_${YYMM}.log

# Move any existing cumulative log to the correct place:
test -f ${LOGDIR}/${ARCHIVE_NAME} && mv ${LOGDIR}/${ARCHIVE_NAME} ${ARCHIVE_DIR}/${ARCHIVE_NAME}

# Create cumulative log in subdirectory
exec  >>${ARCHIVE_DIR}/${ARCHIVE_NAME}
{
svn status $SVNDIR | awk '/^\? / {print $2}' | xargs -r svn add | \
{
    # Read one line first
    IFS= read -r line && \
    {
        # add header
        echo
        echo '>>>'
        echo "Starting  'svn add $SVNDIR' at $STARTED"
        echo "$line"

        # read the rest of the lines
        while IFS= read -r line
        do
            echo "$line"
        done
        
        # add trailer
        echo "Completed 'svn add $SVNDIR' at $(date '+%Y-%m-%d %H:%M:%S')"
        echo '<<<'
    }
}
} | tee ${LOGDIR}/${BASE}.log
# and last log in main directory