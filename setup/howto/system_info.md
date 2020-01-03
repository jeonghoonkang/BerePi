- OS 버전 운영체제 확인
  - cat /etc/os-release
  - uname -a

- Ubuntu 최초 설치 날짜
  - ll --time-style full-iso /var/log/installer/syslog
 
- 로그인 확인
  - last root
  - last -t 20120212040000 
    - YYYYMMDDHHMMSS(연월일시분초)
  - last -F
 
- 이전 Reboot 시간 확인
  - last reboot
  
 - Hardware 버전
   - pi2
```pi@raspberrypi ~ $ cat /proc/cpuinfo
processor : 0
model name : ARMv7 Processor rev 5 (v7l)
BogoMIPS : 38.40
Features : half thumb fastmult vfp edsp neon vfpv3 tls vfpv4 idiva idivt vfpd32 lpae evtstrm
CPU implementer : 0x41
CPU architecture: 7
CPU variant : 0x0
CPU part : 0xc07
CPU revision : 5processor : 1
model name : ARMv7 Processor rev 5 (v7l)
BogoMIPS : 38.40
Features : half thumb fastmult vfp edsp neon vfpv3 tls vfpv4 idiva idivt vfpd32 lpae evtstrm
CPU implementer : 0x41
CPU architecture: 7
CPU variant : 0x0
CPU part : 0xc07
CPU revision : 5processor : 2
model name : ARMv7 Processor rev 5 (v7l)
BogoMIPS : 38.40
Features : half thumb fastmult vfp edsp neon vfpv3 tls vfpv4 idiva idivt vfpd32 lpae evtstrm
CPU implementer : 0x41
CPU architecture: 7
CPU variant : 0x0
CPU part : 0xc07
CPU revision : 5processor : 3
model name : ARMv7 Processor rev 5 (v7l)
BogoMIPS : 38.40
Features : half thumb fastmult vfp edsp neon vfpv3 tls vfpv4 idiva idivt vfpd32 lpae evtstrm
CPU implementer : 0x41
CPU architecture: 7
CPU variant : 0x0
CPU part : 0xc07
CPU revision : 5Hardware : BCM2709
Revision : a21041
Serial : 00000000c15e9432 ```



