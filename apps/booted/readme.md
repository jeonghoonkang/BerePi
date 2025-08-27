# Booting 후 초기 작업

- Crontab -e3
  - @reboot sleep 5 && bash run.sh  


### MacOS 는 RaspberryPi 인터넷 공유 간편히 설정 가능함
- MacOS 설정에서 인터넷 공유
- 아래 설정 파일에서 IP 확인
  - sudo vim /var/db/dhcpd_leases
   
