
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

#echo " PATH to me "${0}
#echo " FILENAME "${0##*/}

#export cmd='python /home/pi/devel/BerePi/apps/tinyosGW/publicip.py {ip or URL} {port} {ID} {password}'
export cmd101='python /home/pi/devel/BerePi/apps/tinyosGW/run_rpi_info.py'
export cmd102='python /home/pi/devel/BerePi/apps/tinyosGW/publicip.py '$ip' '$port' '$id' '$passwd' '
echo '[script file:] '${0##*/}
echo $cmd102 
$cmd102
sleep 2
echo $cmd101
$cmd101

