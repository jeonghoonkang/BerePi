## nextcloud 
### 내용
- 동작을 위한 docker-compose.yml 설정
- sudo docker-compose up -d 로 실행
- sudo docker-compose stop 으로 정지
## 설정
### 처음 port 설정
- 외부 http 요청이, nextcloud docker reverse proxy 의 80 포트로 포워딩 되어야 함
- 외부 https 요청이, nextcloud docker reverse proxy 의 443 포트로 포워딩 되어야 함


