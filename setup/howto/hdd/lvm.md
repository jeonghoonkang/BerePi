## LVM ubuntu
- https://github.com/jeonghoonkang/keti/blob/master/BootCamp/Jin/About/abt_lvm.md
- 추가 사항
  - pvdisplay
  - vgdisplay
    - vg 삭제는 vgreduce --select UUID 로 실행 
  - lvdisplay
- 한번 입력된 LVM 다시 설정하기
  - (참고) https://www.howtogeek.com/howto/40702/how-to-manage-and-use-lvm-logical-volume-management-in-ubuntu/
  
  
LVM 생성 및 용량 수정 , 용량 추가 ..

 

fdisk 로 파티션 생성 .. 

파일타입을  linux LVM (8e) 로 교체후 저장

 

pv 생성

pvcreate /dev/sdb1

pvcreate /dev/sdb2

pvscan

pvdisplay

 

vg 생성

vgcreate VG이름 /dev/sdb1 /dev/sdb2

vgscan

vgdisplay

 

lv 생성

lvcreate -L 용량 (G,M,K) -n  LV이름 VG이름     <-- VG이름은 위에 vg 생성시 입력햇던 이름기입

lvscan

lvdisplay 

LVM 용량 수정(확장만 가능)
  lvresize -L 용량 (G,M,K) LV경로
  lvresize -L +3G /dev/vg00/lvol00

lvscan

이상태에서 마운트 해봐야 lvdisplay  에서는 용량이 추가 되었지만 mount 시 용량은 변경이 없다.

e2fsck -f LV경로

resize2fs LV경로


* 수정 테스트시 mount 상태에서도 경고메세지만 나오고 이상없이 진행되었다. 

 

LVM  용량 추가 (하드디스크 하나 추가 - pv 가 새로 생성)

fdisk 로 파티션 생성

file 타입을 linux LVM (8e) 로 변경

pvcreate /dev/sdc1


vgextend VG이름 /dev/sdc1

vgdisplay

 

lvresize -L 용량 (G,M,K) LV이름

lvscan

이상태에서 마운트 해봐야 lvdisplay  에서는 용량이 추가 되었지만 mount 시 용량은 변경이 없다.

e2fsck -f LV이름

resize2fs LV이름

 

 

참고. 파티션 라벨명 변경 . e2label /파티션이름 /라벨명

참고2. lvm 을 해체하고자 하면 만든 순서의 반대로 진행

lvremove /dev/VG이름/LV이름

vgremove /dev/VG이름

pvremove /dev/sdb1 /dev/sdb2 /dev/sdc1



