
find ./ -name "*.mp3" -print0 | xargs -0 -i -t rename -v 's/.flac//' {}
