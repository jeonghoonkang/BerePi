#!/bin/bash
echo "usage : sh key.sh {IP_ADD} {PORT}, {} : user should input"
export ip=$1
export port=$2

echo $ip, $port

if [ -z $ip ];
then #아규먼트가 없으면 실행
    echo "you need to input IP and port number"
#    find ./ -name "*.flac" -print0 | xargs -0 -i -t ffmpeg -i {}
#            -codec:a libmp3lame -b:a 256k {}.mp3
else #아규먼트가 있으면
    ssh-keygen
    cat ~/.ssh/id_rsa.pub | ssh -p $port tinyos@$ip 'cat>>/home/tinyos/.ssh/authorized_keys'
fi
