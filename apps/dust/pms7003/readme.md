## PMS 7003

### installation
- pip3 install pyserial

### run


### crontab 

- dust report repeatly if PM2.5 is over 25
  - \*/3 * * * * python3 /home/******/beating/telegram_report.py 25
  - this is using Telegram messaging system for Channel (needs quite more time to develop)

- for sudo run
  - echo {password} | sudo -S python3 /home/***/***/BerePi/apps/dust/pms7003/dust_get.py
