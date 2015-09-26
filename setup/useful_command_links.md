
## LINKS 
  - cygwin
    - https://github.com/digitallamb/apt-cyg


## COMMAND
> lsusb
> 타임존 설정 : sudo dpkg-reconfigure tzdata

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


# Stalk How To Use

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

