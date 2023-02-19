
*/30 * * * * bash /home/cam.sh > /home/.../.../log/crontab.camera.log 2>&1

# 아래 실행 명령은 crontab 에서는 동작하지 않음
# *.sh 파일로 저장하고 실행해야 함, 위 처럼, bash /home/tinyos/cam.sh 로 실행 
# fswebcam -r 1280*960 /home/.../web/png/image_$(date '+%Y-%m-%d_%H:%M:%S').jpg

# cam.sh
#
#dest='{SRC}'
#
# fswebcam -r 1280*960 /home/.../web/png/image_$(date '+%Y-%m-%d_%H:%M:%S').jpg
# 
# @hourly echo "password" | sudo -S rm somefile
# sudo chowm www-data -R /home/.../web/png
# sudo find /home/.../web/png -name image_* -mtime +14 -delete
# sudo rsync -avhz --partial --progress /home/.../web/png $dest
# sleep 30
# sudo docker exec -it -u 33 ..._app_1 php occ files:scan --all
#
# sudo chown www-data -R /home/tinyos/devel_opment/nextcloud/volume/nextcloud_volume/data/tinyos/files/Photos/office
# dest='/home/...id.../devel_opment/nextcloud/volume/nextcloud_volume/data/...id.../files/Photos'
# (참고) rsync --rsh="sshpass -p myPassword ssh -l username" server.example.com:/var/www/html/ /backup/

