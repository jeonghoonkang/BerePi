#!/bin/bash
# -*- coding: utf-8 -*-
# Author : https://github.com/jeonghoonkang

alias sr='screen'
#sudo screen -dmS startup sudo bash /home/pi/devel/BerePi/apps/otsdb/start_tsdb.sh
#sudo screen -dmS lcd sudo python /home/pi/devel/BerePi/apps/lcd_berepi/watch.py -ip xxxxx
sudo /home/pi/devel/BerePi/apps/tinyosGW/run_public_ip.sh tinyos.iptime.org 22 pi tinyos0
