# Booting 후 초기 작업

- Crontab -e
  - @reboot sleep 5 && bash run.sh  

## Pironman5 경우
- GPIO로 Fan(LED) 동작 컨트롤 가능
  - GPIOD 설치시, bash 상에서 제어
  - gpioset {--mode=exit, signal} gpiochip4 6=1
  - 일반 User ID가 해당 GPIO를 제어하려면, group 과 rule 파일 적용되어 있어야 함
  - 대부분 하드웨어는 --mode=exit 로 동작을 잘함
    - 일부 이상 동작하는 하드웨어는 crontab @reboot 에서 --mode=signal 로 실행해서 강제로 gpiochip4의 GIO6 을 High로 유지해야함   

### MacOS 는 RaspberryPi 인터넷 공유 간편히 설정 가능함
- MacOS 설정에서 인터넷 공유
- 아래 설정 파일에서 IP 확인
  - sudo vim /var/db/dhcpd_leases
   
