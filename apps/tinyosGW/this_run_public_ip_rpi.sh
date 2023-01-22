#!/bin/bash
# Author : jeonghoonkang, https://github.com/jeonghoonkang

echo " Plaase check the PATH to this file"
echo " Run argument {0} =>  "${0}
this_path=${0}
echo " using this path => "$this_path
#echo " Input Argument "${0##*/}

head_path='/home/tinyos/devel_opment'
tail_path='/BerePi/apps/tinyosGW'
run_cmd='python '$head_path$tail_path' this_run_public_rpi.sh'

#export ip=''
#export port=''
#export id=''
#export passwd=''
export ip=$1
export port=$2
export id=$3
export passwd=$4

echo $ip $port $id $passwd

export cmd='python '$head_path$tail_path'/publicip.py '$ip' '$port' '$id' '$passwd
echo ' now run it => '$cmd 
$cmd 

# export cmd='python /home/pi/devel/BerePi/apps/tinyosGW/publicip.py {ip or URL} {port} {ID} {password}'
