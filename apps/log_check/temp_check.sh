# CPU Temp Log

sdate=$1

while [ 1 ]; do sudo vcgencmd measure_temp > ~/temp_$sdate.log; sleep 5; done;
