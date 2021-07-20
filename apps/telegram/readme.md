### 개요
- 운영중인 Ubuntu 시스템의 alive 상태를 telegram-bot 채팅을 통해 통보 받음
  1. 개인별 telegram bot 설정
  2. crontab 주기적인 동작에 따라 telegram-bot 으로 메세지 전송

### How to add Telegram message API 
  - http://python-telegram-bot.readthedocs.io/en/latest/index.html
  
### Crontab
- 15 */12 * * * python3 /home/tinyos/devel/crontab/diskreport/main.py > /home/tinyos/devel/crontab/diskreport/err.txt 2>&1
- #* * * * * python3 /home/tinyos/devel/crontab/diskreport/main.py > /home/tinyos/devel/crontab/diskreport/err.txt 2>&1


<pre>
import os
import time

def measure_temp():
        temp = os.popen("vcgencmd measure_temp").readline()
        return (temp.replace("temp=",""))

while True:
        print(measure_temp())
        time.sleep(1)
</pre>
