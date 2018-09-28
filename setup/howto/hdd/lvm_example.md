# LVM TEST

## 1. LV 생성

1) 파티션 생성 (fdisk, gparted, disk...)

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

  - lvcreate -L 10GB -n [LV 이름] [VG 이름]
  - lvcreate -l 10%VG -n [LV 이름] [VG 이름]
  - lvcreate -l 100%FREE -n [LV 이름] [VG 이름] 

6) 디스크 포맷

  - mkfs, disk ...


## 2. LV 에 새로운 디스크 추가

  - `vgextend [VG 이름] [PV 이름]`


## 3. LV 용량 줄이기

1) 마운트 해제

2) 파일시스템 체크 

3) 파일시스템 리사이즈

4) LV 용량 줄이기

## 4. 스냅샷
