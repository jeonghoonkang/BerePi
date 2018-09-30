#find ./ -name "*.cue" -print0 | xargs -0 -i -t shnsplit -f {} -t %n-%t -o flac {}.flac

shnsplit -f *.cue -t %n-%t -o flac *.flac
#find ./ -name "*.cue" -print0 | xargs -0 -i -t shnsplit -f {} -t %n-%t -o flac {}.flac
#find ./ -name "*.cue" -print0 | xargs -0 -i -t dirname {} | xargs -0 -i -t filename {}

#!/bin/bash
echo " if you want process specific 1 file, please input the name of file"
export ain=$1
echo $ain

if [ -z $ain ];
then
    find ./ -name "*.flac" -print0 | xargs -0 -i -t ffmpeg -i {} -codec:a libmp3lame -b:a 256k {}.mp3
else
    echo $ain
    find ./ -name "$ain" -print0 | xargs -0 -i -t ffmpeg -i {} -codec:a libmp3lame -b:a 256k {}.mp3
fi
