## nextcloud 
- 주요 핵심 설정 방법은 https://github.com/nextcloud/docker/tree/master/.examples 참조
- docker-compose.yml 파일 내용을 이해 해야함
### 내용
- 동작을 위한 docker-compose.yml 설정
- sudo docker-compose up -d 로 실행
- sudo docker-compose stop 으로 정지
## 설정
### 처음 port 설정
- 외부 http 요청이, nextcloud docker reverse proxy 의 80 포트로 포워딩 되어야 함
- 외부 https 요청이, nextcloud docker reverse proxy 의 443 포트로 포워딩 되어야 함

### 초기 설치에서 grant access 가 동작  안하고
- endpoint http://URL/poll 에러가 발생 하는 경우
- /var/www/nextcloud/config/config.php 내 설정을 추가해줘야함
  - 원래 'over.write.url' => 'http://URL' 로 되어 있는 부분에 http 를 https 로 변경
  - https 설정 내용 추가 "overwriteprotocol" => "https"
