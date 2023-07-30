echo ""
echo "### You should run '' bash beating.sh > ./beating_log_rec.txt 2>&1''"
s1="ls" ;
s2="ioping -q -c 10 -s 8k -W ." ;
order='date';
START=`date`; PERIOD=5; 
when=$START
while true; do echo "";  echo "";  
echo " first-shot run time:"; echo $when; echo; echo " now:"; date > log.txt 2>&1; date ; echo " ----loop end---- "; 

sleep $PERIOD;

done; 

# should run " bash beating.sh 2>&1 ./beating_log_rec.txt"
