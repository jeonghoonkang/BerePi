#!/bin/bash
for i in *.wav; do ffmpeg -i "$i" -ab 320k "${i%.*}.mp3"; done


#
#
# cuebreakpoints foo.cue | shnsplit -o flac foo.wv -d __PATH__
