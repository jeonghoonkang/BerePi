s1="ls" ;
s2="ioping -q -c 10 -s 8k -W ." ;
order='date';
START=`date`; PERIOD=5; 
when=$START
while true; do $order; echo ""; date; echo "";  
echo " first-shot run time:"; echo $when; echo " ----loop end---- "; 

sleep $PERIOD;


done; 
