rm *.png

sudo mplayer -vo png -frames 3 tv://
# 3 means number of capture shots

ffmpeg -i 00000001.png -vf "drawtext=fontfile=/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf: text='%{localtime}': x=(w-tw)/2: y=h-(2*lh): fontcolor=white: box=1: boxcolor=0x00000000@1: fontsize=30" -r 25 -t 5 00000001_text.png
ffmpeg -i 00000002.png -vf "drawtext=fontfile=/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf: text='%{localtime}': x=(w-tw)/2: y=h-(2*lh): fontcolor=white: box=1: boxcolor=0x00000000@1: fontsize=30" -r 25 -t 5 00000002_text.png
ffmpeg -i 00000003.png -vf "drawtext=fontfile=/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf: text='%{localtime}': x=(w-tw)/2: y=h-(2*lh): fontcolor=white: box=1: boxcolor=0x00000000@1: fontsize=30" -r 25 -t 5 00000003_text.png
