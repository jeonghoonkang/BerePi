# -*- coding: utf-8 -*-
# Author : JeongooonKang (github.com/jeonghoonkang)

import json
import time
import socket
import fcntl
import struct
import os
import datetime
import telegram
import requests
from pytz import timezone

def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl (s.fileno(), 0x8915, 
        struct.pack('256s', bytes(ifname[:15], 'utf-8')))  
    return ''.join(['%d.' % b for b in info[20:24]])[:-1]

def get_free_space():
    ret = os.statvfs('./') 
    free_space = ret.f_frsize * ret.f_bfree / 1024 / 1024 / 1024 # 기가바이트 
    return free_space

def send_message(token, chat_id, message):
    bot = telegram.Bot(token=token)
    bot.sendMessage(chat_id=chat_id, text=message, parse_mode="markdown")


if __name__ == "__main__" :

    monitoring_time = datetime.datetime.now(timezone("Asia/Seoul"))
    message = f"""{monitoring_time}"""
    message += ' \n(****)서버 동작중, HDD 잔여용량 ' + str(int(get_free_space())) + 'GByte  IP주소: '
    local_ip = get_ip_address('enp1s0')
    message += local_ip

    with open("telegramconfig.json") as f:
        settings = json.load(f)
    
    for x,y in settings.items():
        #print (x, y)
        if x == "telegram_bot_setting":
            for sub in y:
                #print (sub)
                token = sub["token"]
                chat_id = sub["chat_id"]
                send_message(token=token, chat_id=chat_id, message=message)

    print ("finish end of sending telegram message via Bot, good bye .... ")
