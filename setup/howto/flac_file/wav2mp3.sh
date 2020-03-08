#!/bin/bash
for i in *.wav; do ffmpeg -i "$i" -ab 320k "${i%.*}.mp3"; done


#
#
# cuebreakpoints foo.cue | shnsplit -o flac foo.wv -d __PATH__



# shnsplit -f /home/cuefile.cue -o flac __inputfile__2007.wv__ -t "%p-%a-%n-%t" -d __output_file_
