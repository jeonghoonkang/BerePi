

*/20 * * * * fswebcam -r 1280*960 /home/tinyos/web/png/image_$(date '+%Y-%m-%d').jpg > /home/tinyos/devel_opment/log/crontab.camera.log 2>&1

#fswebcam -r 1280*960 /home/tinyos/web/png/image_$(date '+%Y-%m-%d').jpg
