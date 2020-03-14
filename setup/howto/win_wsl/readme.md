# Xserver for windows
## Installation & run
- Xserver 설치
- 해당 S/W 실행후
- WSL 터미널에서 DISPLAY 환경변수 지정
  - export DISPLAY=localhost:0.0
  - 실행 할때마다, DISPLAY=localhost:0.0 을 적어줘도 됨
  - ssh -Yf {}
  - (예) DISPLAY=localhost:0.0 ssh -Yf tinyos@***.***.***.*** -p 7022 xfce4-terminal  
  

# Crontab for windows
  - crontab 실행
    - sudo cron
  - sudoer 에게 crontab 실행 가능하도록 group 권한 추가
    - usermod -a -G crontab {username} # ubuntu user group change 변경 
  - 동작을 안하는 경우가 많은것 같음. 테스트 필요함
          
