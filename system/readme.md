# System 디렉토리
- 시스템 운영에 대한 설정, 실행 파일을 담고 있습니다
- 부팅이후, 주기적인 실행은 crontab 에서 담당
  - sudo crontab -l 과 crontab -l 로 확인해야 합니다
   
## 부팅 설정 파일
- crontab 용 환경변수 파일
  - .../BerePi/setup/.crontab_env
  - SONNO_HOME 환경변수가 정의하고 있는 경로 중요 
  - crontab은 주기적 실행 때 마다, 다른 shell 을 생성하여 실행하기 때문에, 매번 설정할 수 있도록 설정파일 연결, 실행하는 것이 중요함 

## 부팅시 초기화 및 초기 실행
-  부팅후 초기 실행하는 파일
  - .../BerePi/system/init_file/sonno_start.sh


