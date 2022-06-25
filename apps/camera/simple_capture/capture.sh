rm *.png

sudo mplayer -vo png -frames 3 tv://

readarray -d '' pngarray < <(find . -type f -name '*.png' -print0 )

for f in "${pngarray[@]}";
do  echo $f; ffmpeg -i $f -vf "drawtext=fontfile=/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf: text='%{localtime}': x=(w-tw)/2: y=h-(2*lh): fontcolor=white: box=1: boxcolor=0x00000000@1: fontsize=30" -r 25 -t 5 "${f%%.png}_text.png";
done;
# 3 means number of capture shots

readarray -d '' array < <(find . -type f -name '*_text.png' -print0 )

dt=$(date "+%Y_%m%d-%H%M_%S")
for i in "${array[@]}";
do ii=${i##*/} && ii=${ii%%_text.png} && echo $ii && echo mv "$i" "u-$ii-$dt.png" && mv "$i" "u-$ii-$dt.png";
done;



#for i do
#    d=$(dirname "$i")
#    [ "$d" = / ] && d=

#ffmpeg -i 00000003.png -vf "drawtext=fontfile=/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf: text='%{localtime}': x=(w-tw)/2: y=h-(2*lh): fontcolor=white: box=1: boxcolor=0x00000000@1: fontsize=30" -r 25 -t 5 00000003_text.png

#readarray -d '' array < <(find . -type f -name '*.png' -print0 ) && for i in "${array[@]}"; do echo $i; done;

#${string##substring} Deletes longest match of $substring from front of $string.
#${string%%substring} Deletes longest match of $substring from back of $string.
#disk="/dev/sda"
#local dev_node=${disk##*/}
#substring matching */ from /dev/sda results in sda
