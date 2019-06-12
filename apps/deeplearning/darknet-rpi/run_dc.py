## Crate by TJ

import serial,os,time
import sys
import RPi.GPIO as GPIO
import picamera
import subprocess
import datetime
import os

# check pin location
gled = 19
rled = 26

# HW setup, GPIO
GPIO.cleanup()
GPIO.setmode(GPIO.BCM)
GPIO.setup(rled, GPIO.OUT)
GPIO.setup(gled, GPIO.OUT)
time.sleep(1)

def ledr_on():
  GPIO.output(rled, True)
def ledr_off():
  GPIO.output(rled, False)
def ledg_on():
  GPIO.output(gled, True)
def ledg_off():
  GPIO.output(gled, False)

# init LED OFF
ledr_off()
ledg_off()
time.sleep(1)

with picamera.PiCamera() as camera:

  while True:
    camera.start_preview()
    ledg_on()

    camera.capture('./now.jpg')
    camera.stop_preview()

    result = subprocess.check_output(['./darknet detector test cfg/coco.data cfg/yolov3-tiny.cfg yolov3-tiny.weights now.jpg'], shell=True)
    percent = result.find("person")
    now =  datetime.datetime.now()
    nowdatetime = now.strftime('%Y-%m-%d_%H:%M:%S')

    i = 0
    f_percent = 0.0
    while percent > 0 :
      sub = result[percent:]
      percent2 = sub.find('%')
      temp_f =  float(sub[8:percent2])
      if f_percent < temp_f :
        f_percent = temp_f
        print str(i) + ' Percent value : ' +str(f_percent)
      else :
        print str(i) + ' Percent low'
      i = i + 1
      result = sub[percent2:]
      percent = result.find("person")

    if f_percent > 0 : # Person Key word OK
      if f_percent > 60 :
        print "Person OK: " + str(f_percent)
        #now =  datetime.datetime.now()
        #nowdatetime = now.strftime('%Y-%m-%d_%H:%M:%S')
        cmd = 'cp -f now.jpg ./screenshot/'+nowdatetime+'.jpg'
        print 'S:' + cmd
        os.system(cmd)
        #time.sleep(10)
      else :
        print "Person Not enough :" + str(f_percent)
        cmd = 'cp -f predictions.jpg ./errorshot/'+nowdatetime+'.jpg'
        print 'E1:' + cmd
        os.system(cmd)
        #time.sleep(10)
    else :
      print "Person is Not Here"
      cmd = 'cp -f predictions.jpg ./errorshot/'+nowdatetime+'.jpg'
      print 'E2:' + cmd
      os.system(cmd)
    ledg_off()
    time.sleep(60)

GPIO.cleanup()
