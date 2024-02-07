# Raspi5 nvme 부팅 
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

