
## LINKS 
  - cygwin
    - https://github.com/digitallamb/apt-cyg


## COMMAND
> lsusb

> 타임존 설정 : sudo dpkg-reconfigure tzdata

> IP 주소 중, gateway 주소확인 : ip route

> kill process
> ps -eaf PROCESS_NAME | grep -v grep|awk '{print "kill -TERM "$2}' | sh -x
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

## Cygwin 관련
  - http://egloos.zum.com/chanik/v/3785205
  - http://madoxo.blogspot.kr/2013/03/cygwin-bash.html

## Mint Linux
sudo cp -v /etc/apt/sources.list.d/official-package-repositories.list /etc/apt/sources.list.d/official-package-repositories.list.bak

sudo sed -i 's/rebecca/rafaela/g' /etc/apt/sources.list.d/official-package-repositories.list

sudo apt-get update

sudo apt-get dist-upgrade

