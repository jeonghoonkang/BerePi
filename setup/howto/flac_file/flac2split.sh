shnsplit -f *.cue -t %n-%t -o flac *.flac
#find ./ -name "*.cue" -print0 | xargs -0 -i -t shnsplit -f {} -t %n-%t -o flac {}.flac
#find ./ -name "*.cue" -print0 | xargs -0 -i -t dirname {} | xargs -0 -i -t filename {}

