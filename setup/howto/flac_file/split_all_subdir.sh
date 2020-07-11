find ./ -type f -name *.cue | while read file; do
DIR=`dirname "$file"`
NAME=`basename "$file" .cue`
#cuebreakpoints "${DIR}/${NAME}.cue" | shnsplit -o flac "$file" -d "$DIR"
CUR=`pwd`

cd "$DIR"
#rm *.flac

shnsplit -f "${NAME}.cue" -t %n_%t_%a_%p -o flac "${NAME}.flac"
#cuetag "${NAME}.cue" *.flac

cd "$CUR"
done
