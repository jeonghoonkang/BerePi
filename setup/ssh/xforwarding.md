### X forwarding for RaspberryPi (Xserver) (Xwindow)
- https://www.raspberrypi.org/documentation/remote-access/ssh/unix.md

### Windows
- export DISPLAY=localhost:0.0
- ssh -Yf {}


### 포트 확인
- netstat -tnlp
- nmap localhost

### MAC OSX
OSX 터미널을 열어,
$ cd ~/.ssh
(만약 이 폴더가 없으면 ssh-keygen 명령을 수행하면 자동으로 만들어 진다)

$ vi config
host X11ubuntu
       Hostname ubuntu
       Port 22
       ForwardAgent yes
       ForwardX11 yes
