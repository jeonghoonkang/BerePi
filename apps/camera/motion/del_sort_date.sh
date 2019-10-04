#!/bin/bash
#Author: github.com/jeonghoonkang

#14일된 파일 삭제
find /var/www/html/cam/motion/ -maxdepth 2  -name '*.avi' -mtime +14 | xargs rm -f
find /var/www/html/cam/motion/ -maxdepth 2  -name '*.jpg' -mtime +14 | xargs rm -f

