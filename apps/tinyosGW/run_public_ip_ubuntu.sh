#!/bin/bash
# Author : jeonghoonkang, https://github.com/jeonghoonkang

export ip=''
export port=''
export id=''
export passwd=''

export ip=$1
export port=$2
export id=$3
export passwd=$4

echo $ip
echo $port
echo $id
echo $passwd

#export cmd='python /home/pi/devel/BerePi/apps/tinyosGW/publicip.py {ip or URL} {port} {ID} {password}'
export cmd='python /home/tinyos/devel/BerePi/apps/tinyosGW/publicip.py '$ip' '$port' '$id' '$passwd
echo $cmd 
exec $cmd 

# crontab 입력
# */30 * * * * /bin/bash /home/tinyos/..../run_public_ip_ubuntu.sh
