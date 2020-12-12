
echo "copying files to server"
dest="tinyos@192.168.0.17:webdav/media/send"
speed=$2
echo $dest 
echo $speed

rsync -avhz --progress --partial --bwlimit=$speed  -e'ssh -p22' $1 $dest 
