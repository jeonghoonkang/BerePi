# -*- coding: utf-8 -*-

import requests
# Sending e-mail
def send_email():
  return requests.post(
    "https://api.mailgun.net/v3/sandboxa4e92f05144a3973f6f8031849e3.mailgun.org/messages",
    auth=("api", "key-3fb9acb996e674af4816df1055a7"),
    data={"from": "BerePi/TinyOS<sensormail@sky>",
    "to": ["gadin.kang@gmail.com"],
    "subject": "[SensorMail] Sensor mail running",
    "text": "Know Yourself !"})

if __name__ == "__main__" :
    send_email()
