SCRIPT=pubsubber.py

LOGDIR=/var/log/www-data

BASE=$(basename $SCRIPT .py)

YYMM=$(date '+%Y-%m')

exec  >>${LOGDIR}/${BASE}_${YYMM}_startup.log
echo
echo '>>>'
echo Starting $SCRIPT at $(date)
export

if [ "$1" = 'restart' ]
then
    python3 -u $SCRIPT stop
fi

if [ "$1" = 'stop' ]
then
    python3 -u $SCRIPT stop
    echo "Remember to start pubsubber again" >&2
else
    ERRTEE=1 LOGFILE=$LOGDIR/${BASE}_${YYMM}_daemon.log python3 -u $SCRIPT start \
       comdev/projects.apache.org/trunk /var/www/projects.apache.org/ \
       comdev/reporter.apache.org/trunk /var/www/reporter.apache.org/
fi

echo Completed $SCRIPT at $(date)
echo '<<<'
