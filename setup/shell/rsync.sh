#!/bin/bash
#Author: https://github.com/jeonghoonkang

#입력인자 $1, 비교 -z 길이가 0인지 확인

if [ -z $1 ] ;
then
    rsync -avhz --progress --partial * tinyos@10.0.1.189:/var/www/webdav/data/send
else
    rsync -avhz -P $1 tinyos@10.0.1.189:/var/www/webdav/data/send
fi

