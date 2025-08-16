
## 파일 리스트 생성
<code> find {dir_location} -type f \( -name "*.mkv" -o -name "*.avi" -o -name "*.flv" \) > ./filelist.txt </code>
### 용량 크기 계산
-  du -ch $(< filelist.txt)
### 변환
- ffmpeg -i {media} -threads 2 -c:v libx264 -crf 18 -preset fast -c:a aac -b:a 192k -strict -2 {media}

### 파일 실행 방법 

## One method is a bash for loop.


### For converting only .mp4 files:

- mkdir outputs
  - for f in *.mp4; do ffmpeg -i "$f" -c:a libmp3lame -b:a 256k "outputs/${f%.mp4}.mp3"; done
  - For converting .m4a, .mov, and .flac:

- mkdir outputs
  - for f in *.{m4a,mov,flac}; do ffmpeg -i "$f" -c:a libmp3lame "outputs/${f%.*}.mp3"; done
  - For converting anything use the "*" wildcard:

- mkdir outputs
  - for f in *; do ffmpeg -i "$f" -c:a libmp3lame "outputs/${f%.*}.mp3"; done



