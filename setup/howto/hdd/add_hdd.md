# HDD 추가하기
- /mnt  디렉토리 추가
  
## 파티션 만들기
- fdisk 실행후, n 명령 
- 2T 사이즈가 넘을때는, gpt 로 파티션 생성 해야함
- sudo parted /dev/sdh mklabel gpt
- gpt 경우는 sudo parted -a optimal /dev/sdh mkpart primary ext4 0% 100%
  
## 파티션 포맷
- mkfs.ext4 /dev/sd*


## 자동 마운트
- /etc/fstab
- UUID="f5778" /mnt/disk/disk01 ext4    defaults    0   0


