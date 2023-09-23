# crontab of remote node info print out

<pre>

TOSPATH=/home/***/devel
TARGET=$TOSPATH/__info.txt

date > $TARGET  
  
echo "***" | suco -S vcgencmd measure_temp >> $TARGET  
echo "" >> $TARGET 
  
df >> $TARGET
echo " " >> $TARGET
ifconfig >> $TARGET 

if [$0 is "tx"] : 
  telegram-send -f $TARGET

echo "have sent msg for telegrma"
  
</pre>                                                    
