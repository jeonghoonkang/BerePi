## Video_converter
- It runs the sub dir video search and convert files to mp4
- check out, video_convert.conf video_convert.sh
- Have to re-write precise dir location on the Head of video_convert.conf
  
## Mplayer
### usage
- mplayer -dumpaudio $INPUT -dumpfile $OUTPUT
- ls *.avi | while read INPUT; do mplayer -dumpaudio "$INPUT" -dumpfile "${INPUT/%.avi/.mp3}"; done
- ffmpeg -i video.avi -acodec copy audio.mp3


