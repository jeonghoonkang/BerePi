## LVM 개요
- 하나의 버추얼 하드디스크로 용량을 통합하여 사용
- 물리 하드디스크의 용량을 연속 연결하여, 하나의 논리 드라이브로 사용
- lsblk 으로 물리 드라이브의 마운트 위치 확인 가능
<pre>
NAME                  MAJ:MIN RM   SIZE RO TYPE MOUNTPOINT
sdd                     8:48   0   1.8T  0 disk 
├─sdd2                  8:50   0   1.8T  0 part 
│ ├─vgubuntu-root     253:2    0   1.8T  0 lvm  
│ └─vgubuntu-swap_1   253:3    0   976M  0 lvm  
└─sdd1                  8:49   0   512M  0 part 
sdb                     8:16   0   3.7T  0 disk 
├─sdb2                  8:18   0   3.7T  0 part 
│ └─ubuntu--vg-root   253:0    0   4.5T  0 lvm  /
└─sdb1                  8:17   0   512M  0 part 
sr0                    11:0    1  1024M  0 rom  
sdc                     8:32   0   1.8T  0 disk 
├─sdc2                  8:34   0     2G  0 part 
├─sdc5                  8:37   0   1.8T  0 part 
├─sdc3                  8:35   0     1K  0 part 
└─sdc1                  8:33   0   2.4G  0 part 
sda                     8:0    0 931.5G  0 disk 
├─sda2                  8:2    0     1K  0 part 
├─sda5                  8:5    0   931G  0 part 
│ ├─ubuntu--vg-swap_1 253:1    0  23.9G  0 lvm  [SWAP]
│ └─ubuntu--vg-root   253:0    0   4.5T  0 lvm  /
└─sda1                  8:1    0   487M  0 part /boot
</pre>

## 설치 방법
- 우분투 설치시에 LVM 옵션 선택으로 설치 가능
  - 하나의 디스크만으로 설치 후에, 여러개 추가하는 방법은 성공함
  - 주의: 한번 설치하면 (설치 중단 포함), 다음에 설치할때는 파티션을 지워주고 진행해야 함
    - LVM 설치가 실패, 중단된 경우, 새로 설치시에 중복된 VG volume group 이름이 있다고 나옴 
    - 이런 경우, 일단 try ubuntu 로 vgremove , lvremove 로 삭제후 설치해야함, fdisk로는 삭제가 안됨
    
### 기존 단점
- 16T 한계
  - 32Bit 단위로 LVM SW가 개발되어 있어서 그런것 같음. 몇가지 방법을 적용하면 그 이상도 가능하다고 함
  - 큰 문제는, 이런 상황에서 lgextend 를 실행하면 아무 문제없이 16T 이상으로 세팅이 되는데, resize2fs 가 동작을 하지 않는다
  - 이후, 사이즈를 줄이기 위해 LV를 minus 동작을 수행할 수가 없는데, umount 후에 해줘야 한다. 부팅 디스크인 LVM 를 umount 하고 작업하려면, 부팅 디스크를 이용해야 하는 불편함이 있음
  - lvgextend 를 사용할때는 신중하게 16T가 넘지 않도록 주의해야 함
