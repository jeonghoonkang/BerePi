s1="sysbench --test=cpu run" ;
s2="ioping -q -c 10 -s 8k -W ." ;
order='date';
START=`date`; PERIOD=10; 
when=$START
while true; do $order; echo ""; $s1; echo ""; $s2; 
echo "---------- split line ----------  (info)"$PERIOD" secs peroid  "; 
echo " first-shot run time:"; echo $when; echo " ----loop end---- "; 
sleep $PERIOD; 
done; 