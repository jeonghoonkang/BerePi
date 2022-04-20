### 디버깅 방법
- tail -f /var/log/apache2/davi-error.log
- 설정확인
  - root@50d456be1736:/# cat /var/www/agendav/web/config/settings.php
- 컨테이너 로그인 방법
  - sudo docker exec -it {컨테이너이름} /bin/bash
  
