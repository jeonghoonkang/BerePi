# -*- coding: utf-8 -*-
#Author : JeonghoonKang (github.com/jeonghoonkang)
#         Thinklim (github.com/thinklim)

import datetime
import telegram
import requests
from pytz import timezone
import nmap

IP_API_URL = "https://api.ipify.org"


def send_message(token, chat_id, message):
    bot = telegram.Bot(token=token)
    bot.sendMessage(chat_id=chat_id, text=message, parse_mode="markdown")


def make_message():
    monitoring_time = datetime.datetime.now(timezone("Asia/Seoul"))
    result_message = f""" * 서버 상태 모니터링* _{monitoring_time}_ """

    nm = nmap.PortScanner()
    nm.scan(arguments="-sV -T5")

    for host in nm.all_hosts():
        public_ip = requests.get(IP_API_URL).text
        result_message += "----------------------------------------------------\n"
        result_message += f"Host-Public IP : {public_ip}\n"
        result_message += f"State : {nm[host].state()}\n"

        for protocol in nm[host].all_protocols():
            result_message += "----------\n"
            result_message += f"Protocol : {protocol}\n"
            port_list = nm[host][protocol].keys()

            for port in port_list:
                result_message += f'port : {port}, name : {nm[host][protocol][port]["name"]}, state : {nm[host][protocol][port]["state"]}\n'

    return result_message
