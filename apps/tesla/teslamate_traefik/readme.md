## Teslamate with Traefik
- It gives many benefit of secure, port forwarding and flexibility
- 기본 누구에게나 공개되는 Teslamate 에, Traefik 서비스를 연결하여 Teslamate 연결시, htaccess 형태의 암호를 요구합니다 (초기 설정은 tesla/ktesla 입니다)
  - docker-compose.yml 파일 내부에 새로운 암호로 변경할 수 있습니다   
### How to install and run
- copy docker-compose.yml .env file to your machine
- sudo docker-compose up -d 

### to Connect to Teslamate
- you should input (tesla/ktesla)

### Access to webservice
- http://HOSTMACH:4000 (for TeslaMate)
- http://HOSTMACH:8080 (for Traefik access)
- HOSTMACH 는 .env 파일내에 있는 주소 입니다. DDNS 또는 IP 주소 입력 하십시오

