# -*- coding: utf-8 -*-
# Author : JeongooonKang (github.com/jeonghoonkang)

import json
import time
import socket
import fcntl
import struct
import os
import sys

import datetime

import telegram
#pip install python-telegram-bot

import requests
from pytz import timezone

LOG_PATH="/home/tinyos/devel/BerePi/logs/berelogger.log"


def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl (s.fileno(), 0x8915,
        struct.pack('256s', bytes(ifname[:15], 'utf-8')))
    return ''.join(['%d.' % b for b in info[20:24]])[:-1]

def get_free_space():
    ret = os.statvfs('./')
    free_space = ret.f_frsize * ret.f_bfree / 1024 / 1024 / 1024 # 기가바이트 
    #print (free_space)
    return free_space

def send_message(token, chat_id, message):
    """
    Sends a message to a specified Telegram chat.

    Args:
        token (str): The API token for the Telegram bot.
        chat_id (str): The unique identifier for the target chat.
        message (str): The message text to be sent.

    Returns:
        None
    """
    bot = telegram.Bot(token=token)
    bot.sendMessage(chat_id=chat_id, text=message, parse_mode="markdown")


def make_message():
    monitoring_time = datetime.datetime.now(timezone("Asia/Seoul"))
    result_message = f""" * 서버 상태 모니터링* _{monitoring_time}_ """

    result_message += "----------------------------------------------------\n"

    return result_message

def add_usr_func():
    with open("/home/tinyos/devel/BerePi/logs/berelogger.log") as m:
        msg = m.read() 
    #print (msg)
    return msg



if __name__ == "__main__" :


    _limit = sys.argv[1]
    monitoring_time = datetime.datetime.now(timezone("Asia/Seoul"))
    message = f"""{monitoring_time}"""
    message += ' \n(pir2pi-nc8882)서버 동작중, HDD 잔여용량 ' + str(int(get_free_space())) + 'GByte  IP주소: '
    local_ip = get_ip_address('eth0')
    message += local_ip + '\n'
    #add message 
    retm = add_usr_func()
    index = retm.rfind("PM2.5 Dust ")

    print (index)
    if index < 0 :
        exit( " can not find string in log file")

    retm_pre = retm[index+12:index+18]
    if retm_pre[-1:] == '(':
        retm_pre = retm_pre[:-1]
    measure_val = (retm_pre)
    message += 'Sensor Value from log file is ' + measure_val
    
    #print (_limit)
    #print (int(dust))

    if int(measure_val) < int(_limit): 
        print (' measure is under limit < ', _limit)
        exit(1)


    print (message)
    print ("finish end of sending telegram message via Bot, good bye .... ")


#https://api.telegram.org/bot5049312606:AAFjPh0VYhpxgh-J2VJsjGzP8NW7HAxzxng/sendMessage?chat_id=-1001170927838&text=%EA%B7%B8%EB%A3%B9
#https://api.telegram.org/bot5049312606:AAFjPh0VYhpxgh-J2VJsjGzP8NW7HAxzxng/getUpdates