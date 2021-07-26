### X forwarding for RaspberryPi (Xserver) (Xwindow)
- https://www.raspberrypi.org/documentation/remote-access/ssh/unix.md

### Windows 에서 원격 우분투 서버의 Xwindows GUI 실행 방법
- 로컬 윈도우즈에 xming 이나 X11 server가 설치되어 있어야 함 (VcXsrv)
- export DISPLAY=localhost:0.0
- ssh -Yf {}
- DISPLAY=localhost:0.0 ssh -Yf id@ipaddress {실행할 SW}

### MAC OSX
- https://www.xquartz.org/ 가 설치되어 있어야 함
- ssh -X ids@xxx.xxx.xxx.xxx -vvv -p72 xeyes

<pre>
( 이제는 아래 내용 사용하지 않아도 됨. )

OSX 터미널을 열어,

$ cd ~/.ssh
(만약 이 폴더가 없으면 ssh-keygen 명령을 수행하면 자동으로 만들어 진다)

$ vi config
host X11ubuntu
       Hostname ubuntu
       Port 22
       ForwardAgent yes
       ForwardX11 yes
</pre>

### 포트 확인
- netstat -tnlp
- nmap localhost
