심볼릭링크 권한 변경
chown -h myuser:mygroup mysymbolic


Ubuntu 14.04에 새로운 하드디스크 추가 및 포맷후 자동 마운트 설정
Oct 3, 2015
우분투 머신에 하드디스크 추가 및 포맷 후 자동 마운트 설정하기
1. 하드디스크 설치2. 부팅 후 하드디스크 확인
> sudo fdisk -l
...
Disk /dev/sdb: 512.1 GB, 512110190592 bytes
255 heads, 63 sectors/track, 62260 cylinders, total 1000215216 sectors
Units = sectors of 1 * 512 = 512 bytes
Sector size (logical/physical): 512 bytes / 512 bytes
I/O size (minimum/optimal): 512 bytes / 512 bytes
Disk identifier: 0x88f488f4

Disk /dev/sdb doesn't contain a valid partition table
...
3. 파티션 생성
> sudo fdisk /dev/sdb
...
Command (m for help): n
Partition type:
p primary (0 primary, 0 extended, 4 free)
e extended
Select (default p): p
Partition number (1-4, default 1):
Using default value 1
First sector (2048-1000215215, default 2048):
Using default value 2048
Last sector, +sectors or +size{K,M,G} (2048-1000215215, default 1000215215):
Using default value 1000215215

Command (m for help): p

Disk /dev/sdb: 512.1 GB, 512110190592 bytes
255 heads, 63 sectors/track, 62260 cylinders, total 1000215216 sectors
Units = sectors of 1 * 512 = 512 bytes
Sector size (logical/physical): 512 bytes / 512 bytes
I/O size (minimum/optimal): 512 bytes / 512 bytes
Disk identifier: 0xe8bf195f

Device Boot Start End Blocks Id System
/dev/sdb1 2048 1000215215 500106584 83 Linux

Command (m for help): w
The partition table has been altered!
4. 포맷
> sudo mkfs.ext4 /dev/sdb1
mke2fs 1.42.9 (4-Feb-2014)
Discarding device blocks: done
Filesystem label=
OS type: Linux
...
Writing superblocks and filesystem accounting information: done
 4CF1B1AE-C625-3E49-ACC4-538DD21D2C71

/dev/sda2: UUID="bb53d74e-dbb5-44f2-8931-154a91fe653e" 
/dev/sdb1: UUID="4f23c9a4-79e6-420b-a3a5-2ddd7f2e8554" TYPE="ext4"
/dev/sdc1: UUID="66ab73cb-aba8-4747-b302-3980df0461dd" TYPE="ext4"


UUID=4ed753bb-b5db-f244-8931-154a91fe653e /hdd1 ext4 defaults 0 0
UUID=4f23c9a4-79e6-420b-a3a5-2ddd7f2e8554 /hdd2 ext4 defaults 0 0
UUID=66ab73cb-aba8-4747-b302-3980df0461dd /hdd3 ext4 defaults 0 0

5. 마운트
uuid 확인
> sudo blkid
...
/dev/sdb1: UUID="d2eac947-9407-40bb-96cb-acd22e9a57c3" TYPE="ext4"
...
fstab 파일에 파티션 추가
> sudo vi /etc/fstab
UUID=d2eac947-9407-40bb-96cb-acd22e9a57c3 /ssd2 ext4 defaults 0 0
마운트 및 확인
> sudo mkdir /ssd2
> sudo mount -a
> df -h
Filesystem Size Used Avail Use% Mounted on
...
/dev/sdb1 470G 70M 446G 1% /ssd2

