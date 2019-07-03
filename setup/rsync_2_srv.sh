
echo "copying files to server"
dest="tinyos@192.168.0.17:webdav/media/send"
speed=$2
echo $dest 
echo $speed

rsync -avhz --progress --partial --bwlimit=$speed  --rsh='ssh -p22' $1 $dest 
