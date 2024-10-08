## Nextcloud 설치방법
- 주요 핵심 설정 방법은 https://github.com/nextcloud/docker/tree/master/.examples 참조 (docker-compose 부분)
  - https://github.com/nginx-proxy/docker-letsencrypt-nginx-proxy-companion
- docker-compose.yml 파일의 라인별 세부 내용을 이해 해야함
### 내용
- 동작을 위한 docker-compose.yml 설정
- sudo docker-compose up -d 로 실행
- sudo docker-compose stop 으로 정지
## 설정
### Version
- '3' 을 '2'로 바꾸어서 실행한 경우 있음. '3'인 경우 에러 발생
### DNS 설정
- IPTIME에서 제공하는 DDNS로도 사용을 잘 하고 있음
### 처음 port 설정
- 외부 http 요청이, nextcloud docker reverse proxy 의 80 포트로 포워딩 되어야 함
- 외부 https 요청이, nextcloud docker reverse proxy 의 443 포트로 포워딩 되어야 함
### 외부 마운트 파일 권한 설정
- 초기 실행이 잘 안되어서, devel/docker/ 내부의 마운트포인트 파일들을 다 지우고, 권한은 chgrp www-data 로 모두 변경함 
### 초기 설치에서 grant access 가 동작  안하는 경우 
- endpoint http://URL/poll 에러가 발생 하는 경우
- /var/www/nextcloud/config/config.php 내 설정을 추가해줘야함
  - 원래 'over.write.url' => 'http://URL' 로 되어 있는 부분에 http 를 https 로 변경
  - https 설정 내용 추가 "overwriteprotocol" => "https"
- 어떤 경우, http:// 로도 사용을 할 수 있는 경우가 있었음 
### 초기 설정 입력 사항
- DB 사용자, DB 이름, 패스워드는 db.env 내의 내용을 작성
- Database 의 호스트:포트 를 적는 제일 마지막에는 docker-compose.yml 의 MariaDB를 포인팅하는 "db" 입력 

## SSL 인증서 갱신
- Let's Encrypt 사용시, 90일마다 expire
- 30일 남았을때 부터 renewal 가능
  - letsencrypt 실행중인 컨테이너에서 실행
  - 80, 443 포트는 열려 있어야 함 (공유기 설정)
  - docker exec nginx-letsencrypt /app/force_renew
    - history | grep renew 로 검색 가능 
<pre>
- sudo docker exec {letsencrypt-companion_1} /app/force_renew
- {컨테이너 이름}
/etc/nginx/certs/~~.~~.~~ /app
Creating/renewal t.iptime.org certificates... (bigsoft.iptime.org)
2021-01-03 00:57:04,884:INFO:simp_le:1450: Generating new certificate private key
2021-01-03 00:57:09,978:INFO:simp_le:401: Saving key.pem
2021-01-03 00:57:09,978:INFO:simp_le:401: Saving chain.pem
2021-01-03 00:57:09,978:INFO:simp_le:401: Saving fullchain.pem
2021-01-03 00:57:09,998:INFO:simp_le:401: Saving cert.pem
/app
Reloading nginx proxy (481d0570d02db1a14a6316ee543a45fa56cad26b961d9004a6ee0ad1187f7f50)...
2021/01/03 00:57:12 Generated '/etc/nginx/conf.d/default.conf' from 4 containers
2021/01/03 00:57:12 [notice] 108#108: signal process started  
</pre>
    
    
  - 인증서 기간 확인
    - echo | openssl s_client -connect #호스트주소DDNS#:443 2>/dev/null | openssl x509 -noout -dates
    - cert_status

#### 추가정보
- 이미 apache2 가 설치되어 동작되고 있는 경우
  - sudo update-rc.d apache2 disable 로 시작할때 실행 순서에서 제외
  - sudo update-rc.d apache2 enable 
  - sudo update-rc.d apache2 remove 로 등록 상태를 해지
  - sudo update-rc.d apache2 defaults 다시 등록
  - crontab 실행
    - sudo docker-compose -f /home/tinyos/devel/BerePi/apps/docker/docker_compose/nextcloud/docker-compose.yml up -d

#### lets encrypt renew 메세지
<pre>
tinyos@toshome-fit001:~/devel/docker/nextcloud$ sudo docker exec letsencrypt-companion_1 /app/force_renew
Creating/renewal domain.domain.com certificates... (domain.domain.com)
[Sat Jul 10 02:53:12 UTC 2021] Using CA: https://acme-v02.api.letsencrypt.org/directory
[Sat Jul 10 02:53:12 UTC 2021] Creating domain key
[Sat Jul 10 02:53:17 UTC 2021] The domain key is here: /etc/acme.sh/n.@ail.com/s.oo.com/s.m.com.key
[Sat Jul 10 02:53:17 UTC 2021] Single domain='o.o.com'
[Sat Jul 10 02:53:17 UTC 2021] Getting domain auth token for each domain
[Sat Jul 10 02:53:20 UTC 2021] Getting webroot for domain='o.o.com'
[Sat Jul 10 02:53:20 UTC 2021] Verifying: o.o.com
[Sat Jul 10 02:53:24 UTC 2021] Pending
[Sat Jul 10 02:53:27 UTC 2021] Pending
</pre>
