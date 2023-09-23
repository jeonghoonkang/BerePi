# crontab of remote node info print out

<pre>

PATH=/home/***/devel_opment
  
df > $PATH/__info.txt
echo "" >> $PATH/__info.txt
ifconfig >> $PATH/__info.txt
telegram-send -f $PATH/__info.txt
echo "have sent msg for telegrma"
</pre>                                                    
