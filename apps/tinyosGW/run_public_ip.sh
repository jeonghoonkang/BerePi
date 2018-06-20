#!/usr/bin/bash
# Author : jeonghoonkang, https://github.com/jeonghoonkang
export cmd='python /home/pi/devel/BerePi/apps/tinyosGW/publicip.py {ip or URL} {port} {ID} {password}'
echo cmd
exec cmd
