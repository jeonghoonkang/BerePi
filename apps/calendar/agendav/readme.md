- https://github.com/agendav/agendav/
- https://agendav.github.io/agendav/
- nagimov/agendav-docker

### 디버깅 방법
- (agenDAV 컨테이너 내부) tail -f /var/log/apache2/davi-error.log
  - DB, php 어떤 에러가 발생하는지 확인 필요
- (agenDAV 컨테이너 내부) 설정파일 내용 체크
  - root@50d456be1736:/# cat /var/www/agendav/web/config/settings.php
  - 도커컴포즈 실행에서 ynl 파일에 따라, 도커 컨테이너 내부 Shell 에 환경 변수 설정이 되었는지 확인하면서 진행 
    - env 
- (agenDAV 컨테이너 내부) 컨테이너 로그인 방법
  - sudo docker exec -it {컨테이너이름} /bin/bash 
    - sudo docker ps 로 컨테이너 이름 확인 
  
