
## 로그인 되자마자 종료되는 경우
- xrdp, ubuntu
- 윈도우 원격데스크탑 실행 오류 문제
  - https://github.com/neutrinolabs/xrdp/issues/2027
  - sudo apt install ubuntu-gnome-desktop

sudo nano /etc/xrdp/startwm.sh

<pre>

. /etc/X11/Xsession를 삭제 또는 주석 처리(맨앞에 #추가)하고 아래와 같이 수정한다.

#!/bin/sh

if [ -r /etc/default/locale ]; then
  . /etc/default/locale
  export LANG LANGUAGE
fi

#. /etc/X11/Xsession
. /usr/bin/startxfce4
</pre>

<pre>
test -x /usr/bin/startxfce4 && exec /usr/bin/startxfce4
exec /bin/sh /usr/bin/startxfce4
</pre>


- ubuntu 18 버전. 색상문제 (지속적 권한 입력)
  - sudo vim /etc/polkit-1/localauthority/50-local.d/45-allow-colord.pkla
<pre>
[Allow Colord all Users]
Identity=unix-user:*
Action=org.freedesktop.color-manager.create-device;org.freedesktop.color-manager.create-profile;org.freedesktop.color-manager.delete-device;org.freedesktop.color-manager.delete-profile;org.freedesktop.color-manager.modify-device;org.freedesktop.color-manager.modify-profile
ResultAny=no
ResultInactive=no
ResultActive=yes
</pre>


Ubuntu 20.10 - xrdp/remote access

Remote login, after 'apt install xrdp', gives a static grey screen. The following appears to be one way to solve the problem ...

- Code: Select all
- sudo apt install xrdp
- sudo systemctl status xrdp

# Remote grey screen problem and solution 

- Ubuntu 20 버전으로 넘어오면서 회색화면 이슈는 해결된것으로 보임 (2021.6 기준)

- 참고) 이전버전 경우, 
  - sudo adduser xrdp ssl-cert // not use
  - sudo systemctl restart xrdp
  - sudo apt-get install xfce4
  - echo xfce4-session > .xsession
  - https://corona-world.tistory.com/26

## macOS 에서 사용하는 방법
### 1 step
- XQuartz 설치 (https://www.xquartz.org)
### 2 step
- open XQuartz terminal and run
  - ssh -Y {ID}@{ADDRESS} -p {PORT} termit (google-chrome) 
  - <img width="800" alt="image" src="https://github.com/user-attachments/assets/46161c89-e4a6-411a-939d-449b55411926" />


# disable sleep hibernate / re-enable (시스템 shutdown 방지)
- On Ubuntu 16.04 LTS, I successfully used the following to disable suspend:
  - sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
- re-enable  
  - sudo systemctl unmask sleep.target suspend.target hibernate.target hybrid-sleep.target

