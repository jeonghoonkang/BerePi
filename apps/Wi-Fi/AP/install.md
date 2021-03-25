# 라즈베리파이 AP 설정

구성도
<pre>
(공유기) --<유선>-- (라즈베리파이)···<무선>···(Device)
</pre>

## 1. 액세스 포인트 설치
  
  ``` bash
  sudo apt update
  sudo apt install hostapd
  
  sudo systemctl unmask hostapd
  sudo systemctl enable hostapd
  
  sudo apt install dnsmasq
  sudo DEBIAN_FRONTEND=noninteractive apt install -y netfilter-persistent iptable-persistent
  ```
  
## 2. 라우터 설정
  
  ``` bash
  sudo vim /etc/dhcpcd.conf
  ```
  
  ``` conf
  interface wlan0
      static ip_addredd=192.168.1.1/24
      nohook wpa_supplicant
  ```
  
## 3. IP MASQUERADING
  
  - routed-ap.conf 파일을 다음 경로에 생성하고 내용을 추가한다.
  
  ``` bash
  sudo vim /etc/sysctl.d/routed-ap.conf
  ```
  
  - 아래 내용을 추가
  
  ``` conf
  net.ipv4.ip_forward=1
  ```
  
  - 방화벽 규칙 추가
  
  ``` bash
  sudo iptables -t nat -A POSTROUTING -p eth0 -j MASQUERADE
  sudo netfilter-persistent save
  ```
## 4. DHCP, DNS 구성
  
  ``` bash
  sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.bak
  sudo vim /etc/dnsmasq.conf
  ```
  
  ``` conf
  interface=wlan0
  dhcp-range=192.168.1.2, 192.168.1.255, 255, 255.255.255.0, 24h
  domain=wlan
  address=/gw.wlan/192.168.1.1
  ```

 
## 5. AP 구성
  
  ``` bash
  sudo vim /etc/hostapd/hostapd.conf
  ```
  
  - 아래 내용을 그대로 사용하면, SSID : RaspiAP 에 0123456789 로 접속할 수 있다.
  - 수정해서 사용한다.
    
  ``` conf
  country_code=US
  interface=wlan0
  ssid=RaspiAP
  hw_mode=g
  channel=7
  macaddr_acl=0
  auth_algs=1
  ignore_broadcast_ssid=0
  wpa=2
  wpa_passphrase=0123456789
  wpa_key_mgmt=WPA-PSK
  wpa_pairwise=TKIP
  rsn_pairwise=CCMP
  ```
      
  ※ 참고 : hw_mode 설정값
  - a = IEEE 802.11a (5GHz)
  - b = IEEE 802.11b (2.4GHz)
  - g = IEEE 802.11g (2.4GHz)
  - ad = IEEE 802.11ad (60GHz)
