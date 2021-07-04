
# Localhost information through Telegram bot
- 텔레그램 봇 연결
<pre>
- 1*****12:*************U9gvr3BtTbxJW*****
- https://api.telegram.org/bot*************U9gvr3BtTbxJW*****/getUpdates
- {"ok":true,"result":[{"update_id":280468502,
"message":{"message_id":4,"from":{"id":5165***,"is_bot":false,"first_name":" ","last_name":"K","username":"****","language_code":"ko"},"chat":{"id":51651***,"first_name":"oon","last_name":"K","username":"loyd","type":"private"},"date":1625000586,"text":"Tomorrow belongs to those who can hear it coming."}}]}
</pre>
- 메세지 전송

# 직접 실행
- python3 main.py

# 필요 
- python-telegram-bot

# crontab 실행
- * */8 * * * python3 /home/tinyos/devel/crontab/diskreport/main.py > /home/tinyos/devel/crontab/diskreport/err.txt 2>&1 
