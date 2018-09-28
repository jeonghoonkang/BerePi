# LVM TEST

## 1. LV 생성

  1) 파티션 생성
  - fdisk, gparted, disk...
  
  2) 디스크 정보확인 
  - `fdisk -l`
  
  3) pv 추가
  - `pvcreate [디스크 경로]`
  - ex) `sudo pvcreate /dev/sda1`
  
  4) vg 추가
  - `vgcreate [VG 이름] [PV 이름]`
  - ex) 1개의 pv 를 1개의 vg 로 추가 : `sudo vgcreate vg1 /dev/sda1`
  - ex) 2개의 pv 를 1개의 vg 로 추가 : `sudo vgcreate vg1 /dev/sda1 /dev/sda2`
  
  5) lv 추가
  - `lvcreate -L 10GB -n [LV 이름] [VG 이름]`
  - `lvcreate -l 10%VG -n [LV 이름] [VG 이름]`
  - `lvcreate -l 100%FREE -n [LV 이름] [VG 이름]`

  6) 디스크 포맷
  - mkfs, disk ...


## 2. LV 에 새로운 디스크 추가

  - `vgextend [VG 이름] [PV 이름]`


## 3. LV 용량 줄이기

  1) 마운트 해제
  - `umount [디스크 경로]
  - ex) `sudo umount /dev/mapper/lvm--disk-1lvm--1`

  2) 파일시스템 체크
  - `e2fsck -f [디스크 경로]`
  - ex) `sudo e2fsck -f /dev/mapper/lvm--disk-lvm--1`

  3) 파일시스템 리사이즈
  - `resize2fs [디스크 경로]`
  - ex) `sudo resize2fs /dev/mapper/lvm--disk-lvm--1 1G`

  4) LV 용량 줄이기
  - `lvreduce -L [용량]`
  - ex) `sudo lvreduce -L 2G /dev/lvm-disk/lvm-1`

## 4. 스냅샷

  - **복구 테스트 중 오류가 발생했음, 주의 필요**
  
  1) 스냅샷 지정
  - `lvcreate -s -L [용량] -n [스냅샷 이름] [대상]`
  
  2) lv 여유공간 생성 (lvm-1 의 용량을 1GB 줄인다)
  - `sudo lvreduce -L -1G /dev/lvm-disk/lvm-1`
  
  3) 스냅샷 생성 (LV "lvm-1" 에 1GB 용량의 "lvm1-snapshot" 스냅샷을 생성한다.
  - `sudo lvcreate -s -L 1G -n lvm-1-snapshot /dev/lvm-disk/lvm-1`
