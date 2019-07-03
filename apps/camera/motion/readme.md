# Motion detection S/W installation (Project : Motion)

## command
- sudo apt-get installl motion

## requirements
```
Debian/Ubuntu/Raspbian
Required
sudo apt-get install autoconf automake build-essential pkgconf libtool git libzip-dev libjpeg-dev gettext libmicrohttpd-dev
```
## configuration 
- /etc/modules
  - bcm2835-v4l2

## run / start / stop / daemon
- sudo systemctl status ( start / stop ) motion
- hostname
- crontab for maintanance
  - 9 2 * * * /var/www/html/cam/motion/cleanup_file.sh > /home/pi/devel/BerePi/apps/debug/debug_motion.log 2>&1
  - 30 */4 * * * /var/www/html/cam/motion/del_sort.sh > /home/pi/devel/BerePi/apps/debug/debug_motion.log 2>&1

## Performance, run fact-info
- 30 Min (DESK shot)
  - generation 69MB JPG files
  - 4351 pics
- One day in office 
  - light change effect : less 5 time or slightly more

# Resource
## Source code
- Motion Project Homepage 
  - https://motion-project.github.io/index.html
  - repo : https://github.com/Motion-Project/motion

## Links (howto)
- https://www.bouvet.no/bouvet-deler/utbrudd/building-a-motion-activated-security-camera-with-the-raspberry-pi-zero
  - https://learn.adafruit.com/cloud-cam-connected-raspberry-pi-security-camera?view=all
  - https://www.instructables.com/id/Raspberry-Pi-Motion-Detection-Security-Camera/#step5
