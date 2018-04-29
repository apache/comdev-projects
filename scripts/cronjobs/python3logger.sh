# Script to redirect standard output of a python3 script to /var/log/www-data

# Output log file is named after the script file name plus the suffix _YYYY-MM
# This ensures that at most one month's data is in each log file

# Sample usage:
# cd .../scripts/cronjobs && ./python3logger.sh parsepmcs.py

SCRIPT=${1?Script name}

LOGDIR=/var/log/www-data

BASE=$(basename $SCRIPT .py)

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
echo
echo '>>>'
START=$(date)
echo "Starting $SCRIPT ($$) at $START"
export

ERRTEE=1 python3 -u $SCRIPT

echo "Completed $SCRIPT ($$) at $(date) (START $START)"
echo '<<<'
}  | tee ${LOGDIR}/${BASE}.log
# and last log in main directory