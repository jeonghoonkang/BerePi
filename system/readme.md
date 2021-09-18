# System 디렉토리
- 시스템 운영에 대한 설정, 실행 파일을 담고 있습니다
- 부팅이후, 주기적인 실행은 crontab 에서 담당
  - sudo crontab -l 과 crontab -l 로 확인해야 합니다
   
## 부팅 설정 파일
- crontab 용 환경변수 파일
  - .../BerePi/setup/.crontab_env
  - SONNO_HOME 환경변수가 정의하고 있는 경로 중요 

## 부팅시 초기화 및 초기 실행



