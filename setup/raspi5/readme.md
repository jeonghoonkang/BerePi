# 2025년 7월 확인 내용
- RaspberryPi Imager 에 있는 Factory Default 디스크 생성으로 Boot Loader 변경
- 부트로더 변경후, NVME 부팅 원활함 
  - https://www.cytron.io/tutorial/raspberry-pi-imager-updating-bootloader?srsltid=AfmBOopZIn4vT6cRPlBKcjBlHBLHb_o_orkRwMAejoUGYyEe95qz4q8a


# 2025년 이전 버전
## Raspi5 nvme 부팅 
- Raspi Imager 로 Rasbian OS 를 SD에 설치
- SD 부팅후
- sudo rpi-eeprom-update -a 로 확인
- sudo rpi-eeprom-config -e 로 부팅 추가 (NVME)
- BOOT_ORDER=0xf416 (will add NVMe (6) as first boot device (boot order is right to left))

## 검색 내용 
<pre> 
  PCIE_PROBE=1
  POWER_OFF_ON_HALT=1
  BOOT_ORDER=0xf416
  
  will add NVMe (6) as first boot device (boot order is right to left) and will also reduce shutdown power consumption to around 0.01W
  PCIE_PROBE is required if using a non-HAT+ adapter
</pre>


### 설정 확인 커맨드 
- sudo vcgencmd get_throttled
- sudo vcgencmd pmic_read_adc 
