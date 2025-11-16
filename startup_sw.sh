#!/bin/bash
# Author : https://github.com/jeonghoonkang

alias sr='screen'


#sudo screen -dmS startup sudo sh /home/pi/devel/BerePi/apps/otsdb/local_start_tsdb.sh
#sudo screen -dmS lcd sudo python /home/pi/devel/BerePi/apps/lcd_berepi/watch.py -ip xxxxx
#/home/pi/devel/BerePi/apps/tinyosGW/run_public_ip.sh {ip/url} {port} {login id} {pw}

#### Please add below line on /etc/rc.local
# sudo sh /home/pi/devel/BerePi/this_startup_sw.sh
#### in other word,
# in /etc/rc.local
####
# startup software by BerePi
#sudo sh /home/pi/devel/BerePi/startup_sw.sh
#exit0
####


# externally managed Python environment 
# sudo mv /usr/lib/python3.11/EXTERNALLY-MANAGED /usr/lib/python3.11/EXTERNALLY-MANAGED_OLD

# alias
# alias dockerps='sudo docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"'

# visudo , sudoer 로 등록된 {user id}에 password 없어도 되도록 설정  
# sudo visudo 로 실행
# %sudo   ALL=(ALL:ALL) NOPASSWD: ALL
