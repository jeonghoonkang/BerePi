

*/30 * * * * bash /home/tinyos/cam.sh > /home/tinyos/devel_opment/log/crontab.camera.log 2>&1

#fswebcam -r 1280*960 /home/tinyos/web/png/image_$(date '+%Y-%m-%d_%H:%M:%S').jpg


# cam.sh
# fswebcam -r 1280*960 /home/tinyos/web/png/image_$(date '+%Y-%m-%d_%H:%M:%S').jpg

