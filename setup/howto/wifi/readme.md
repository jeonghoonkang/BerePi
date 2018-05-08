
## Wi-Fi 설정 파일위치, 모델에 따라 상이한 결과 보임 
- 2018.5.9 작성
- 대상파일 
  - sudo /etc/vim /etc/wpa_supplicant/wpa_supplicant.conf

#### 라즈베리파이 3 모델B Plus 경우

- 동작안함
<pre>
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=GB

network={
    ssid="wall"
    scan_ssid=1
    psk=4548ff5e3723dc010afed1e0dc771a54e8a212c7c683845ed9a8e588100ebdd5
    priority=1
    id_str="office"
}

#network={
#   ssid="yebbi Secure"
#   psk=91188c0ea11c534843f8826e4db4f73c22d7122024c9badf98dc0b31d55a1365
#    priority=2
#    id_str="home"
#}
</pre>


#### 라즈베리파이 3 모델B 경우
- 동작안함 
<pre>
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
#country=GB

network={
        ssid="wall"
        scan_ssid=1
        psk=4548ff5e3723dc010afed1e0dc771a54e8a212c7c683845ed9a8e588100ebdd5
#        priority=1
#        id_str="office"
}

</pre?
