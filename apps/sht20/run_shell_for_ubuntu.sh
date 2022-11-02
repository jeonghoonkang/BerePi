s1="sudo python3 sht25class_ubuntu.py "
order=`date`;
START=`date`;
PERIOD=90;
when=$START
while true;
    do $order; echo ""; $s1;
        echo "---------- split line ----------  (info) "$PERIOD" secs peroid  ";
        echo " first-shot run time:"; echo $when; echo " ----loop end---- ";
        sleep $PERIOD;
    done;
