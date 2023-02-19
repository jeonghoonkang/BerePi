
dest=/home/~~~/path
fswebcam -r 1280*960 /home/{SRC_DIR}/image_$(date '+%Y-%m-%d_%H:%M:%S').jpg
sudo rsync -avhz --partial --progress {SRC} $dest
sudo docker exec -i -u 33 app_1 php occ files:scan --all

