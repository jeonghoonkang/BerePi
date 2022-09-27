- 디버깅 로깅 bash shell 쉘 cli log

<pre> 
START=`date`; PERIOD=30; 
while true; do $1;   date; 
echo "---------- split line ----------  (info)"$PERIOD" secs peroid  "; 
echo "  start time: "$START; echo " "; 
sleep $PERIOD; 
done; 
</pre>
