# Mplayer
## usage
- mplayer -dumpaudio $INPUT -dumpfile $OUTPUT
- ls *.avi | while read INPUT; do mplayer -dumpaudio "$INPUT" -dumpfile "${INPUT/%.avi/.mp3}"; done
- ffmpeg -i video.avi -acodec copy audio.mp3


