

*/30 * * * * bash /home/tinyos/cam.sh > /home/tinyos/devel_opment/log/crontab.camera.log 2>&1

# 아래 실행 명령은 crontab 에서는 동작하지 않음
# *.sh 파일로 저장하고 실행해야 함, 위 처럼, bash /home/tinyos/cam.sh 로 실행 
# fswebcam -r 1280*960 /home/tinyos/web/png/image_$(date '+%Y-%m-%d_%H:%M:%S').jpg


# cam.sh
# fswebcam -r 1280*960 /home/tinyos/web/png/image_$(date '+%Y-%m-%d_%H:%M:%S').jpg
# 
# @hourly echo "password" | sudo -S rm somefile
#
