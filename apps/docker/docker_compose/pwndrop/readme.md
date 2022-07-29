
# PWNDROP 파일 관리 시스템 

<pre>
version: '3'

services:

  pwndrop:
    image: lscr.io/linuxserver/pwndrop:latest
    container_name: pwndrop
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=KR/Seoul
      - SECRET_PATH=/pwndrop #optional
    volumes:
      - ./pwndrop:/config
    ports:
      - 5232:8080
    restart: unless-stopped
</PRE>
