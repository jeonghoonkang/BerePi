#-*-coding:utf8-*-

#!/usr/bin/python
# Author : Jeonghoonkang, github.com/jeonghoonkang

import sys, os
sys.path.insert(0, '/var/www/camera')
#import textindex

from time import strftime, localtime, sleep
import picamera
import datetime

pic = '/var/www/camera/%s_cam_shot.jpg'

if len(sys.argv) is 1:
	print '   *****'
	print '    A picture has default file name in default path.'
	print '     '+pic
	print '   *****'

elif len(sys.argv) > 2:
	print '   Insert only the file name with directory where you want to save a picture in'
	print '   default :'+pic

else:
	pic = sys.argv[1]


foto_cnt = 0

camera =  picamera.PiCamera() 
camera.resolution = (1024, 768)
camera.rotation = 180

while True:

    camera.start_preview()
    sleep(10)
    camera.stop_preview()

    time = strftime("%Y-%m%d-%H:%M", localtime())

    camera.capture(pic %time)
    print '\n A picture was saved at ' + pic %time 

    sleep(2.5)
