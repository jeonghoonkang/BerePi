# crontab of remote node info print out

<pre>

PATH=/home/***/devel
TARGET=$PATH/__info.txt

sudo vcgencmd measure_temp > $TARGET  
echo "" >> $TARGET 
df >> $TARGET
echo " " >> $TARGET
ifconfig >> $TARGET 
telegram-send -f $TARGET

echo "have sent msg for telegrma"
  
</pre>                                                    
