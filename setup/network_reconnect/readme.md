
## 네트워크 케이블 연결 해제후, 다시 연결시 네트워크 활성화 하기 위해
- Network-Management Tool 을 사용함
  - http://www.intellamech.com/RaspberryPi-projects/rpi_nmcli.html
    - sudo apt-get update
    - sudo apt-get install network-manager
    - sudo apt-get install network-manager-gnome

- dhcp 클라이언트 실행 
  - sudo dhclient eth0
  - sudo systemctl restart dhcpcd
  
   
