
# Localhost information through Telegram bot
- 텔레그램 봇 연결
- 메세지 전송

# 직접 실행
- python3 main.py

# 필요 
- python-telegram-bot
- python-nmap

# crontab 실행
<pre> * */8 * * * python3 /home/tinyos/devel/crontab/netreport/main.py > /home/tinyos/devel/crontab/netreport/err.txt 2>&1 </pre>
