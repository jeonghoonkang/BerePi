
cat ~/.ssh/id_rsa.pub | ssh -p 9999 tinyos@99.99.com 'cat>>/home/tinyos/.ssh/authorized_keys'

#!/bin/bash

export ain=$1
echo $ain

if [ -z $ain ];
then
    find ./ -name "*.flac" -print0 | xargs -0 -i -t ffmpeg -i {} -codec:a libmp3lame -b:a 256k {}.mp3
