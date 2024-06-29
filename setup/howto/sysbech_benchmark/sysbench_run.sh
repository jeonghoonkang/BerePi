s1="sysbench --test=cpu run" ;
s2="ioping -q -c 10 -s 8k -W ." ;
order='date';
START=`date`; PERIOD=10; 
when=$START
while true; do $order; echo ""; $s1; echo ""; $s2; 
echo "---------- split line ----------  (info)"$PERIOD" secs peroid  "; 
echo " first-shot run time:"; echo $when; echo " ----loop end---- "; 
echo " Raspi 3 - CPU speed events per second:  22.71"
echo " Raspi 4 - CPU speed events per second:  1749.76 "

sleep $PERIOD;


done; 
