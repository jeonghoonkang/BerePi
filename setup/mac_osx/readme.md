## MAC Pro 설정 관련 내용

### X-Windows System for Max OSX
- MAC OS 에서 X-윈도우 삭제되어서, 이제는 추가로 설치해야 함
  - X서버 설치필요 xQuartz 를 앱스토어에서 
- https://www.xquartz.org
- https://blog.boxcorea.com/wp/archives/1718


### Home Brew installation
- https://brew.sh/index_ko

### pip installation
- $ sudo easy_install pip

### SIP (....)
- /System , /bin , /sbin , /usr
- 부팅시 cmd + R
- 안전모드 진입
- 유틸리티 메뉴 , 터미널 실행
- <code> csrutil disable </code> 입력
- reboot

#### 문제발생
- /usr/bin 의 권한을 실수로 변경
  - renamed the login file to sth else so terminal would work again
  - started another terminal instance
  - reverted the name change (and kept the working terminal instance open)
  - in the working terminal:
  - "sudo chown root:wheel /usr/bin/login"
  - "sudo chmod 4755 /usr/bin/login"
