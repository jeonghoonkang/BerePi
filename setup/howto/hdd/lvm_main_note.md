## LVM ubuntu (main note)
- 초기 작성 내용
  - https://github.com/jeonghoonkang/keti/blob/master/BootCamp/Jin/About/abt_lvm.md

### LVM 생성 및 기존 파티션에 마운트 하기

- parted /dev/sdb
  - (parted) mklabel gpt
  - (parted) print                                                           
    <pre>
    Disk geometry for /dev/sdb: 0kB - 3701GB
    Disk label type: gpt
    Number  Start   End     Size    File system  Name  Flags
    </pre>
    - partition을 primary로 3701GB full로 설정 
  - (parted) mkpart primary 0 3701GB
    - mkpart primary ext4 1363149s 100% 
  - (parted) print    
    <pre>                                                      
    Disk geometry for /dev/sdb: 0kB - 3701GB
    Disk label type: gpt
    Number  Start   End     Size    File system  Name  Flags
    1       17kB    3701GB  3701GB                                    
    </pre>
  - (parted) quit                                                            
  
  - pv 생성 및 확인 
    - pvcreate /dev/sdb1
    - pvcreate /dev/sdb2
    - pvscan
    - pvdisplay

- vg 생성
  - vgcreate VG이름 /dev/sdb1 /dev/sdb2
  - vgscan
  - vgdisplay

- lv 생성
  - lvcreate -L 용량 (G,M,K) -n  LV이름 VG이름     <-- VG이름은 위에 vg 생성시 입력햇던 이름기입
    - lvcreate -l 100%FREE -n [LV 이름] [VG 이름] 
  - lvscan
  - lvdisplay 

- LVM 용량 수정(확장만 가능)
  - lvresize -L 용량 (G,M,K) LV경로
  - lvresize -L +3G /dev/vg00/lvol00
  - lvscan
    - 이상태에서 마운트 해봐야 lvdisplay  에서는 용량이 추가 되었지만 mount 시 용량은 변경이 없다.
  - sudo mkfs.ext3 /dev/vg/lv{lv 경로} 
    - (확인필요) e2fsck -f LV경로
    - (확인필요) resize2fs LV경로

  - 마운트 하기
    - sudo mkdir /mount_name; sudo chmod 777 /mount_name{마운트위치}
    - sudo apt install lvm2
    - sudo modprobe dm-mod
    - sudo vgscan 
      - Found volume group "vg-r440" using metadata type lvm2 
      - (volume group 이름 확인)
    - sudo vgchange -ay vg-r440{vg 이름}
      -   1 logical volume(s) in volume group "vg-r440" now active 
    - sudo fdisk -l
      - Disk /dev/mapper/vg--r440-lv--r440: 7.28 TiB, 8001528266752 bytes, 15627984896 sectors
    - sudo mount /dev/mapper/vg--r440-lv--r440 /mount_name{마운트위치}   
    - UUID 확인 
    <pre>
    $ sudo ls -l /dev/disk/by-uuid
    lrwxrwxrwx 1 root root 10  2월  1 13:39 65afb022-482b-4244-ba26-bc4d469ab131 -> ../../sda2
    lrwxrwxrwx 1 root root 10  2월  1 13:39 887e0e3f-9738-4221-9645-1a14e911d894 -> ../../dm-0
    lrwxrwxrwx 1 root root 10  2월  1 13:39 AD86-EBED -> ../../sda1
    </pre>
    - fstab 편집, sudo vim /etc/fstab
    <pre>
     # <file system> <mount point>   <type>  <options>       <dump>  <pass>
     UUID=887e0e3f-9738-4221-9645-1a14e911d894   /hdd_lvm    ext3    defaults    0   1
    </pre>
     
  - 참고 : https://devbrain.tistory.com/65

### LVM  용량 추가 (하드디스크 하나 추가 pv를 새로 생성) 내부 명령이. LVM새로 생성과 확장이 섞여 있음 

  - fdisk 로 파티션 생성 (용량이 2T 이상인 경우 parted, gparted 로 생성) 
  - file 타입을 linux LVM (8e) 로 변경
  - (예)parted /dev/sda
    - mkpart primary ext4 0 800GB 

  - pvcreate /dev/sdc1
  - pvdisplay
  
  - vgextend VG이름 /dev/sdc1
  - vgdisplay


  - lvcreate -L 용량 (G,M,K) -n  LV이름 VG이름     <-- VG이름은 위에 vg 생성시 입력햇던 이름기입
    - lvcreate -l 100%FREE -n [LV 이름] [VG 이름]
      
  - lvresize -L 용량 (G,M,K) LV이름{형식:/dev/ubuntu-vg/root}
  - lvscan
  - sudo mkfs.ext3 /dev/vg/lv{lv 경로}
    
  - e2fsck -f LV이름
  - resize2fs LV이름

  - 참고. lvm 을 해 하고자 하면 만든 순서의 반대로 진행

    - lvremove /dev/VG이름/LV이름
    - vgremove /dev/VG이름
    - pvremove /dev/sdb1 /dev/sdb2 /dev/sdc1

  
<pre>
sudo vgdisplay
sudo vgremove /dev/vgubuntu                                                                                                                                         
sudo vgextend ubuntu-vg /dev/sdb2                                                                                                                                
sudo vgscan                                                                                                                                                      
sudo lvdisplay                                                                                                                                                  
sudo lvextend -l +100%FREE /dev/ubuntu-vg/root                                                                                                                   
sudo resize2fs /dev/ubuntu-vg/root   
df -h                                                                                                                                                            
</pre>

## 
- https://dinggur.tistory.com/30

- 추가 사항
  - vgdisplay
    - vg 삭제는 vgreduce --select UUID 로 실행 
  - 한번 설정된 LVM 다시 설정하기
  - (참고) https://www.howtogeek.com/howto/40702/how-to-manage-and-use-lvm-logical-volume-management-in-ubuntu/
  
  
