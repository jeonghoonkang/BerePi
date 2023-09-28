# crontab of remote node info print out

<pre> 30 */4 * * *	bash /home/***/***/crontab.sh tx > /home/***/***/err_crontab.err 2>&1 
/home/tinyos/devel/crontab.tinyos.sh: line 18: telegram-send: command not found 
</pre>


- 주의사항
  - crontab 에서 bash script 실행시 경로를 인식 못하는 경우가 있음. 설치시 경로 확인 필요
  - /home/tinyos/.local/bin/telegram-send
  - 직접 인스톨 시도 필요 pip3 install telegram-send

<pre>

echo "help: bash {file.sh} 'tx' will send message to telegram"
echo "argument 1-->" $1

TOSPATH=/home/***/devel
TARGET=$TOSPATH/__info.txt

date > $TARGET  
  
echo "***" | sudo -S vcgencmd measure_temp >> $TARGET  
echo "" >> $TARGET 
  
df -h >> $TARGET
echo " " >> $TARGET
ifconfig >> $TARGET 

if [[ $1 = 'tx' ]]
then
        telegram-send -f  $TARGET 
        echo "send done"
else
        echo "send failed, please input 'tx'"
fi
  
</pre>                                                    

<pre>
Operator	Description
! EXPRESSION	The EXPRESSION is false.
-n STRING	The length of STRING is greater than zero.
-z STRING	The lengh of STRING is zero (ie it is empty).
STRING1 = STRING2	STRING1 is equal to STRING2
STRING1 != STRING2	STRING1 is not equal to STRING2
INTEGER1 -eq INTEGER2	INTEGER1 is numerically equal to INTEGER2
INTEGER1 -gt INTEGER2	INTEGER1 is numerically greater than INTEGER2
INTEGER1 -lt INTEGER2	INTEGER1 is numerically less than INTEGER2
-d FILE	FILE exists and is a directory.
-e FILE	FILE exists.
-r FILE	FILE exists and the read permission is granted.
-s FILE	FILE exists and it's size is greater than zero (ie. it is not empty).
-w FILE	FILE exists and the write permission is granted.
-x FILE	FILE exists and the execute permission is granted.
</pre>

<img width="558" alt="image" src="https://github.com/jeonghoonkang/BerePi/assets/4180063/6bcab91f-3e4e-470d-85c5-286639d7327e">
