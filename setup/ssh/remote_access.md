- reverse proxy style , ssh forwarding 방법
  - autossh -M 20000 -N _*_@_*_._*_._*_._*_ -R 2222:localhost:22 -vvv
    - 20000: 관리포트 번호, 추가 필요한 포트번호는 20001 로 구성됨, 비워놔야함 
    - 2222: reverse 원격에서 접근할 포트
    - _*_@_*_._*_._*_._*_ 는 Reverse Proxy로 동작할 서버 및 해당 서버 ID
  - sudo vim /lib/systemd/system/reverseProxy.service
    - 서비스로 등록하고 시스템 재시작시에 실행. Daemon으로 등록, 실행
<pre>    
[Unit]
Description=SSH reverse tunneling 
After=network-online.target
 
[Service]
User=pi
ExecStart=/usr/bin/autossh -M 20000 -N ID@IP.IP.IP.IP -R 2222:localhost:22
   
[Install]
WantedBy=network-online.target
</pre>    

## 주요 설정
 - 단말기(현장 기기) - reverseProxy(클라우드 단말) 사이에는, ssh 키가 공유 되어서 로그인시에 password 입력이 필요없어야 함
   - 설정 방법
     - https://github.com/jeonghoonkang/BerePi/blob/master/setup/ssh/key.sh
    
  - sudo systemctl daemon-reload 
  - sudo systemctl restart reverseProxy.service
  - sudo systemctl status reverseProxy.service
  - sudo systemctl enable reverseProxy.service
    - reverseProxcy.service

- examples
  - systemctl list-units --type target
  - systemctl list-units --type target --all
  - systemctl enable {서비스이름}
  - systemctl disable {서비스이름}
  - systemctl is-enabled {서비스이름}
  - sudo systemctl list-units --state=failed
  - sudo systemctl list-units --state=active
  - sudo systemctl list-units --all --state=inactive
  - sudo systemctl list-units --type=service --state=running
