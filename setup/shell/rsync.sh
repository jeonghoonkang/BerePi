if [ -z $1 ] ;
then
    rsync -avhz --progress * tinyos@10.0.1.189:/var/www/webdav/data/send
else
    rsync -avhz --progress $1 tinyos@10.0.1.189:/var/www/webdav/data/send
