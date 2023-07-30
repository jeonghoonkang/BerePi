#!/bin/bash

##################################################################
# A Project of TNET Services, Inc
#
# Title:     WiFi_Check
# Author:    Kevin Reed (Dweeber)
#            dweeber.dweebs@gmail.com
# add some comments and usage : https://github.com/jeonghoonkang
# Project:   Raspberry Pi Stuff
#
# Copyright: Copyright (c) 2012 Kevin Reed <kreed@tnet.com>
#            https://github.com/dweeber/WiFi_Check
#
# Purpose:
#
# Script checks to see if WiFi has a network IP and if not
# restart WiFi
#
# Uses a lock file which prevents the script from running more
# than one at a time.  If lockfile is old, it removes it
#
# Instructions:
#
# o Install where you want to run it from like /usr/local/bin
# o chmod 0755 /usr/local/bin/WiFi_Check
# o Add to crontab
# o sudo added
#
# Run Every 5 mins - Seems like ever min is over kill unless
# this is a very common problem.  If once a min change */5 to *
# once every 2 mins */5 to */2 ...
#
# */5 * * * * /usr/local/bin/WiFi_Check
#
# add by https://github.com/jeonghoonkang
# try : sudo crontab -e 
# */10 * * * * sudo sh /home/pi/devel/BerePi/setup/wifi_cron.sh
#
# crontab log check : sudo cat /var/log/syslog , find /crontab/
# 

##################################################################
# Settings
# Where and what you want to call the Lockfile
lockfile='/var/run/WiFi_Check.pid'
# Which Interface do you want to check/fix
wlan='wlan0'
##################################################################

echo
echo "Starting WiFi check for $wlan"
date
echo

# Check to see if there is a lock file
if [ -e $lockfile ]; then
    # A lockfile exists... Lets check to see if it is still valid
    pid=`cat $lockfile`
    if kill -0 &>1 > /dev/null $pid; then
        # Still Valid... lets let it be...
        #echo "Process still running, Lockfile valid"
        exit 1
    else
        # Old Lockfile, Remove it
        #echo "Old lockfile, Removing Lockfile"
        rm $lockfile
    fi
fi
# If we get here, set a lock file using our current PID#
#echo "Setting Lockfile"
echo $$ > $lockfile

# We can perform check wifi
echo "Performing Network check for $wlan"
if sudo ifconfig $wlan | grep -q "inet" ; then
    echo "Network is Okay"
else
    echo "Network connection down! Attempting reconnection."
    sudo ifdown $wlan
    sleep 5
    sudo ifup --force $wlan
    sudo ifconfig $wlan | grep "inet addr"
fi

echo
echo "Current Setting:"
sudo ifconfig $wlan | grep "inet addr:"
echo

# Check is complete, Remove Lock file and exit
#echo "process is complete, removing lockfile"
if [ -e $lockfile ]; then
    rm $lockfile
fi

exit 0

##################################################################
# End of Script
##################################################################
