#!/bin/bash

export ain=$1
echo $ainc
eho "starting fiac file"
if [ -z $ain ];
then
    find ./ -name "*.flac" -print0 | xargs -0 -i -t ffmpeg -i {} -codec:a libmp3lame -b:a 256k {}.mp3
else
    echo $ain
    find ./ -name "$ain" -print0 | xargs -0 -i -t ffmpeg -i {} -codec:a libmp3lame -b:a 256k {}.mp3
fi
