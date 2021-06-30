# -*- coding: utf-8 -*-
# Author : JeongooonKang (github.com/jeonghoonkang)

import json
import time
import local_port_scanning
import socket
import fcntl
import struct
import os


def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl (s.fileno(), 0x8915, 
        struct.pack('256s', bytes(ifname[:15], 'utf-8')))  
    return ''.join(['%d.' % b for b in info[20:24]])[:-1]

def get_free_space():
    ret = os.statvfs('./') 
    free_space = ret.f_frsize * ret.f_bfree / 1024 / 1024 / 1024 # 기가바이트 
    #print (free_space)
    retrun free_space

def local_port_scanning_job():
    message = local_port_scanning.make_message()
    local_port_scanning.send_message(token=token, chat_id=chat_id, message=message)


if __name__ == "__main__" :

    get_free_space()

    #local_ip = get_ip_address('enp1s0')
    # should check network device interface name by ifconfig

    #print (" open telegram config file, telegramconfig.json")

    #with open("telegramconfig.json") as f:
    #    settings = json.load(f)
    
    token = settings["telegram_bot_setting"]["token"]
    chat_id = settings["telegram_bot_setting"]["chat_id"]
        
    #message = local_port_scanning.make_message()
    #message = message + 'LOCAL IP address:' + local_ip
    #print (message)

    #local_port_scanning.send_message(token=token, chat_id=chat_id, message=message)


    print ("finish end of sending telegram message via Bot, good bye .... ")
    