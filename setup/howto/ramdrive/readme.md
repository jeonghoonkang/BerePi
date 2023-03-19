
## RAM Drive / RAM Disk (ramdisk, ramdrive)

- https://hiseon.me/linux/linux-ramdisk/
- $ sudo mount -t [TYPE] -o size=[SIZE] [FSTYPE] [MOUNTPOINT]
- $ sudo mount -t tmpfs -o size=1G tmpfs /mnt/ramdisk

- sudo mount -t tmpfs -o size=64M tmpfs /media/ramdisk

- 마운트 체크
  - sudo mount -av
- 마운트 재시작 (R Only 문제해결)
  -  mount -o remount,rw /
  
  
<pre>
>.  하나. 장치명을 레이블명으로 표현하기
[root@os1 /]# cat /etc/fstab
LABEL=/                 /                       ext3    defaults        1 1
LABEL=/boot             /boot                   ext3    defaults        1 2
tmpfs                   /dev/shm                tmpfs   defaults        0 0
devpts                  /dev/pts                devpts  gid=5,mode=620  0 0
sysfs                   /sys                    sysfs   defaults        0 0
proc                    /proc                   proc    defaults        0 0
LABEL=SWAP-sda2      swap                  swap    defaults        0 0
 
>.  두울. 장치명으로 직접 표현하기
[root@os1 /]# cat /etc/fstab
/dev/sda3               /                       ext3    defaults        1 1
/dev/sda1               /boot                   ext3    defaults        1 2
tmpfs                   /dev/shm                tmpfs   defaults        0 0
devpts                  /dev/pts                devpts  gid=5,mode=620  0 0
sysfs                   /sys                    sysfs   defaults        0 0
proc                    /proc                   proc    defaults        0 0
/dev/sda2             swap                    swap    defaults        0 0
 
위의 두 경우는 리눅스시스템에서 파일시스템을 읽어들여 마운트할때 결과가 같다.
위의 방법은 파일시스템에 설정된 레이블명으로 마운트할때 사용되는것이고
아래방법은 파일시스템에 대한 장치명으로 바로 마운트할때 사용되는것이다.

춠처 : https://m.blog.naver.com/dudwo567890/130156449983

</pre>
