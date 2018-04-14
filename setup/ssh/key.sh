#!/bin/bash

export ain=$1
echo $ain

if [ -z $ain ];
then #아규먼트가 없으면 실행
    echo "you need to input IP and port number"
#    find ./ -name "*.flac" -print0 | xargs -0 -i -t ffmpeg -i {} -codec:a libmp3lame -b:a 256k {}.mp3

else #아규먼트가 있으면
    cat ~/.ssh/id_rsa.pub | ssh -p 9999 tinyos@99.99.com 'cat>>/home/tinyos/.ssh/authorized_keys'
fi
