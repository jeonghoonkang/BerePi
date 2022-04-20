- https://github.com/agendav/agendav/
- https://agendav.github.io/agendav/
- nagimov/agendav-docker

### 디버깅 방법
- tail -f /var/log/apache2/davi-error.log
- 설정파일 내용 체크
  - root@50d456be1736:/# cat /var/www/agendav/web/config/settings.php
  - 파일에 따라, Shell 에 환경 변수 설정이 되었는지 확인 
    - env 
- 컨테이너 로그인 방법
  - sudo docker exec -it {컨테이너이름} /bin/bash
  
