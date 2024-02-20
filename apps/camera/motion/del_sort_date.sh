#!/bin/bash
#Author: github.com/jeonghoonkang

#14일된 파일 삭제
find /var/www/html/cam/motion/ -maxdepth 2 -type f -name '*.avi' -mtime +14 | xargs rm -f
find /var/www/html/cam/motion/ -maxdepth 2 -type f -name '*.jpg' -mtime +14 | xargs rm -f
find /var/www/html/cam/motion/ -maxdepth 2 -type f -name '*.avi' -mmin +10 | xargs rm -f


# find 후 삭제 방법
# find /path/to/files -type f -mtime +10 -delete
