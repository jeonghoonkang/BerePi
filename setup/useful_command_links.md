
## Xubuntu 한글 설정
  - sudo apt install language-selector-gnome

## LINKS 
  - cygwin
    - https://github.com/digitallamb/apt-cyg


## COMMAND
> nmap -sT localhost

> lsusb

> 타임존 설정 : sudo dpkg-reconfigure tzdata

> IP 주소 중, gateway 주소확인 : ip route

> kill process
> ps -eaf {PROCESS_NAME} | grep -v grep|awk '{print "kill -TERM "$2}' | sh -x
<pre>
#!/bin/bash
killtree() {
    local _pid=$1
    local _sig=${2:-TERM}
    kill -stop ${_pid} # needed to stop quickly forking parent from producing child between child killing and parent killing
    for _child in $(ps -o pid --no-headers --ppid ${_pid}); do
        killtree ${_child} ${_sig}
    done
    kill -${_sig} ${_pid}
}
if [ $# -eq 0 -o $# -gt 2 ]; then
    echo "Usage: $(basename $0) <pid> [signal]"
    exit 1
fi
killtree $@
</pre>

<pre>
iwconfig

iwlist wlan0 scan
  Cell 01 - Address: 맥주소
    ESSID:"여기를 꼭 기억하세요"
    Protocol:IEEE 802.11bgn
wpa_passphrase SSID이름 암호 >> /etc/wpa_supplicant/wpa_supplicant.conf

network={
  ssid="여기에 접속하겠어"
  #psk="원래암호가 그대로 써있다"
  psk=암호화된내용
}
</pre>

1. cmdline.txt
  - /boot/cmdline.txt 에 고정 ip 를 쓰는 경우 dhcp 연결시 문제되는 경우가 있어 추천하지 않습니다.
  - /boot/cmdline.txt 는 외장메모리에 인식 가능한 파일이라 노트북 리더기로 수정 후 사용합니다.
2. 노트북 랜포트 다이렉트 연결
  - cmd 창에서 "arp -a" 를 사용하면 ip 확인이 가능합니다.
  - 맥/리눅스/PC 모두 같은 명령어를 사용합니다.

## VNC client
sudo apt-get install reminna

## Stalk How To Use

  - after installation
    - ssh 22 port is automatically registered to Server
  
  - list entries
    ```
    stalk status 
    ```
    
  - register server entry
    ```
    stalk server CHANNEL_NAME HOST_ADDR HOST_PORT
    (ex) stalk server my-resberry-web localhost 80
    ```
    
  - register client entry
    ```
    stalk client CHANNEL_NAME LOCAL_PORT
    (ex) stalk client my-rasberry-web 8000
    ```
  
  - cancel entry
    ```
    stalk kill ENTRY_ID
    (ex) stalk kill 17
    * ENTRY_ID is available via "stalk status" command.
    ```

channel server 는 kill 되면 다시 생성됨
ps -ax | grep  [c]hannelserver.py | awk '{print $1}' | xargs kill -9


## Cygwin 관련
  - http://egloos.zum.com/chanik/v/3785205
  - http://madoxo.blogspot.kr/2013/03/cygwin-bash.html

## Mint Linux
sudo cp -v /etc/apt/sources.list.d/official-package-repositories.list /etc/apt/sources.list.d/official-package-repositories.list.bak

sudo sed -i 's/rebecca/rafaela/g' /etc/apt/sources.list.d/official-package-repositories.list

sudo apt-get update

sudo apt-get dist-upgrade

## UI Project
  - http://webix.com/demos/
  - http://bokeh.pydata.org/en/latest/

### Git command
  - git clone https://github.com/username/username.github.io
  - git add --all
  - git config --global user.email "gadin.kang@gmail.com"
  - git commit -m "Initial commit"
  - git push -u origin master
  

### systemctl
  - sudo systemctl status networking.service
    - /lib/systemd/system/networking.service.d
    - |- network-pre.conf
    
  
### crontab reboot warning
  -  0   7  *   *   *    /sbin/shutdown -r +5
  - */7  *  *   *   *

### tabnanny python
  - python -m tabnanny -v 
  
  
### oracle jdk 7 installation error
  - sudo apt-get purge oracle-java7-installer
  - sudo apt-get autoremove
  - sudo apt-get install -f
  
### openTSDB  
  - https://github.com/zerover0/projects/blob/master/opentsdb/standalone_opentsdb_install_on_rpi.md
  

### 표준입출력 리디렉션
 '2>&1'과 같이 주면 표준 에러를 표준 출력과 같은 곳으로 보내라는 뜻이며, '1>&2'의 경우는 표준 출력을 표준 에러와 같은 곳으로 보내라는 뜻이다.
