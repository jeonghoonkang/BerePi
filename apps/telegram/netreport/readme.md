
# Localhost information through Telegram bot
- 텔레그램 봇 연결
<pre>
- 1*****12:*************U9gvr3BtTbxJW*****
- https://api.telegram.org/bot*************U9gvr3BtTbxJW*****/getUpdates
- {"ok":true,"result":[{"update_id":280468502,
"message":{"message_id":4,"from":{"id":51651596,"is_bot":false,"first_name":"Jhoon","last_name":"K","username":"pinkfloyd","language_code":"ko"},"chat":{"id":51651596,"first_name":"Jhoon","last_name":"K","username":"pinkfloyd","type":"private"},"date":1625000586,"text":"Tomorrow belongs to those who can hear it coming."}}]}
</pre>
- 메세지 전송

# 직접 실행
- python3 main.py

# 필요 
- python-telegram-bot
- python-nmap

# crontab 실행
<pre> * */8 * * * python3 /home/tinyos/devel/crontab/netreport/main.py > /home/tinyos/devel/crontab/netreport/err.txt 2>&1 </pre>
