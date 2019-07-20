echo " Change *.flac.mp3 to *.mp3, delete '.flac' string 
find ./ -name "*.mp3" -print0 | xargs -0 -i -t rename -v 's/.flac//' {}
