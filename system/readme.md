# System 디렉토리
- 시스템 운영에 대한 실행 및 설정 파일을 담고 있습니다
- 부팅이후, 주기적인 실행은 crontab 에서 담당
  - sudo crontab -l 과 crontab -l 로 확인 
   
## 부팅 설정 파일
- crontab 용 환경변수 파일
  - .../BerePi/setup/.crontab_env
  - SONNO_HOME 환경변수가 정의하고 있는 경로 중요 
  - crontab은 주기적 실행 때 마다, 다른 shell 을 생성하여 실행하기 때문에, 매번 설정할 수 있도록 설정파일 연결, 실행하는 것이 중요함 

## 부팅시 초기화 및 초기 실행
-  부팅후 초기 실행하는 파일
  - .../BerePi/system/init_file/sonno_start.sh

## 로그파일
### 동작상태 등, 저장 로그
- .../BerePi/logs/berelogger.log 
  - 파일당 2MB, 9개까지 저장 (Rotate Log)
### 시스템 동작 로그
- .../BerePi/logs/berepi_sys_log.log

### sudo crontab
- 부팅 초기에 주기적으로 실행해야 하는 코드는 아래처럼 실행
  - <pre> */3 * * * * bash /home/tinyos/devel/BerePi/system/init_file/sonno_start.sh `sudo vcgencmd measure_temp` > /home/tinyos/devel/BerePi/logs/berepi_sys_log.log 2>&1 </pre>

### SSL 인증서 만기 알림
- openssl 로 인증서 만기일을 조회해 telegram-send 로 전송하는 스크립트
- 매달 1일 오전 9시에 실행하도록 설정 예시
  - <pre>0 9 1 * * bash /home/tinyos/devel/BerePi/setup/shell/monthly_ssl_expire_notice.sh example.com > /dev/null 2>&1</pre>
