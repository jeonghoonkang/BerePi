echo "help: bash {file.sh} 'tx' will send message to telegram"
echo "argument 1-->" $1

TOSPATH=/home/***/devel_opment
TARGET=$TOSPATH/__info.txt

date > $TARGET  
  
echo "***" | sudo -S vcgencmd measure_temp >> $TARGET  
echo "" >> $TARGET 
  
df -h >> $TARGET
echo " " >> $TARGET
ifconfig >> $TARGET 

if [[ $1 = 'tx' ]]
then
        #telegram-send -f  $TARGET 
        head -n70 $TARGET | grep -v 'inet6' | grep -v 'tmpfs' | grep -e dev -e temp -e inet -e KST | telegram-send --stdin
          echo "send done"
else
        echo "send failed, please input 'tx'"
fi
