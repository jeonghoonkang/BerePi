#!/bin/bash
#Author: github.com/jeonghoonkang
#for RaspberryPi, should use \;

rsync -avhz --partial '--rsh=ssh -p PORTNUM' /var/lib/motion/*.jpg tinyos@IP or URL:webdav/gw/cam

#rm /home/pi/cam_data/*.*
#find /var/lib/motion/ -type f -mtime 0 -maxdepth 1 -name '*.jpg' -exec cp '{}' /home/pi/cam_data \;
#rsync -avhz '--rsh=ssh -p2' /home/pi/cam_data/*.jpg ID@IP:webdav/gw/cam/motion


#참고
#  rsync -avhzu --progress -e 'ssh -p 22' id@ip:webdav/bk_office /home/tinyos/work_win
