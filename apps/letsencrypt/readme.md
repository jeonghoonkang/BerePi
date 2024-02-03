# How to Let's Encrypt SSL
## 컨테이너를 활용한 SSL 실행, 갱신
  - https://velog.io/@wksmstkfka12/떠먹여주는-Nginx-Docker에-무료-SSL-적용
  - Nginx, Let's encrypt를 활용한 SSL 설정
### crontab
  - 분(0-59) 시(0-23) 일(1-31) 월(1-12) 요일(0-6, 0:Sun) 순서 
  - root 권한으로 crontab 수정을 실행시킨 후 편집기에 명령어를 입력하면 되는데,
  - 아래와 같이 설정함 (매월 1일 오전3시, 오후5시 실행)
  - 0 3,17 1 * * /usr/bin/certbot renew.sh
  - https://telegram.me/home_8881_bot
<pre>
30 4 2 * * echo "tinyos12()" | sudo -S bash /home/tinyos/devel/docker/nextcloud/renew.sh > /home/tinyos/devel/log/renew.log 2>&1
31 4 2 * * cat /home/tinyos/devel/log/renew.log | telegram-send --stdin
</pre>  
  
#### renw.sh
  - sudo docker exec nextcloud_letsencrypt-companion_1 /app/force_renew
  - sudo docker exec {실행중인 lets encypt 컨테이너} /app/force_renew

## Portainer scheme
- using linux server docker container image
- https://www.codesarang.com/33
- https://wooyg.com/archives/52
  
## using DNS cert, by Cerbot
- https://lynlab.co.kr/blog/72
