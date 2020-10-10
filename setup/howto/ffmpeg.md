One method is a bash for loop.

<pre>
For converting only .mp4 files:

mkdir outputs
for f in *.mp4; do ffmpeg -i "$f" -c:a libmp3lame -b:a 256k "outputs/${f%.mp4}.mp3"; done
For converting .m4a, .mov, and .flac:

mkdir outputs
for f in *.{m4a,mov,flac}; do ffmpeg -i "$f" -c:a libmp3lame "outputs/${f%.*}.mp3"; done
For converting anything use the "*" wildcard:

mkdir outputs
for f in *; do ffmpeg -i "$f" -c:a libmp3lame "outputs/${f%.*}.mp3"; done
</pre>
