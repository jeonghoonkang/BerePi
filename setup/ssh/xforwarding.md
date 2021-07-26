### X forwarding for RaspberryPi (Xserver) (Xwindow)
- https://www.raspberrypi.org/documentation/remote-access/ssh/unix.md

### Windows 에서 원격 우분투 서버의 Xwindows GUI 실행 방법
- 로컬 윈도우즈에 xming 이나 X11 server가 설치되어 있어야 함 (VcXsrv)
- export DISPLAY=localhost:0.0
- ssh -Yf {}
- DISPLAY=localhost:0.0 ssh -Yf id@ipaddress {실행할 SW}
#### 우분투 터미널 WSL2 에서 사용하기 위한 설정
  - 아래 명령 실행으로 .bashrc 입력 필요
  - DISPLAY 환경변수에서 localhost 는 동작하지 않음. 기존 방법은 DISPLAY=localhost:0.0
  - env | grep DISPLAY 로 확인
  <pre> echo 'export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '"'"'{print $2}'"'"'):0.0' >> ~/.bashrc
 </pre>

  - Windows10 에서 설정
    - 제어판\시스템 및 보안\Windows Defender 방화벽
    - VcXsrv (또는 Xming) windows xserver 는 모두 허용으로 바꾸어야 함
    ![방화벽 설정](res/win_defender.png)


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
