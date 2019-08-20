
https://topis.me/109#patc



2. 파티션 삭제
$sudo fdisk /dev/sdb


리눅스에선 fdisk라는 명령으로 파티션을 관리한다. 이 명령의 옵션은 command (m for help) : 'm'을 입력해 보면 알 수있다. 위 그림처럼 지우는 옵션은 'd'이다.



'd'를 주자 어떠한 경고 메시지도 없이 지워준다. 4테라의 하드에 중요한 데이터가 잔뜩 있었으면 정말이지 '억~' 소리가 날 것임으로 파티션을 관리할 때는 특히 지우는 명령을 쓸 때에는 철처히 확인하고 또 확인해서 만약의 불상사에 대비하자.



'p' 명령으로 현재 선택한 hdd의 파티션 정보를 확인 할 수 있다.



리눅스에서 2테라 이상의 하드를 단일 용량으로 사용하기 위해서는 gpt파티션으로 잡아줘야 사용 가능하다. 필자는 이미 gpt로 라벨 생성을 한 상태임을 알 수 있다.

마지막으로 'w' 옵션으로 설정 값을 적용한다.

Command (m for help): w

The partition table has been altered.
Calling ioctl() to re-read partition table.
Syncing disks.

3. GPT 파티션을 삭제
GPT 파티션과 관련된 부분은 fdisk가 아닌 parted라는 툴을 사용해야 한다. GPT 파티션을 삭제하려고 한다면 다음과 같이 진행하면 된다.

$parted /dev/sdb
(parted) mklabel msdos                                                   

Warning: The existing disk label on /dev/sdb will be destroyed and all data on
this disk will be lost. Do you want to continue?

Yes/No? Yes


참고로 mklabel의 타입에는 bsd, loop (raw disk access), gpt, mac, msdos, pc98, sun 등이있다.

4. 2TB(테라바이트) 이상 GPT 파티션 생성하기
아래 명령으로 현재 파티션 정보를 확인한다.

$sudo fdisk -l
Device     Boot     Start       End   Sectors  Size Id Type

/dev/sda1  *         2048 457146367 457144320  218G 83 Linux
/dev/sda2       457148414 488396799  31248386 14.9G  5 Extended
/dev/sda5       457148416 488396799  31248384 14.9G 82 Linux swap / Solaris

Disk /dev/sdb: 3.7 TiB, 4000787030016 bytes, 7814037168 sectors
Units: sectors of 1 * 512 = 512 bytes
Sector size (logical/physical): 512 bytes / 4096 bytes
I/O size (minimum/optimal): 4096 bytes / 4096 bytes
Disklabel type: dos
Disk identifier: 0x244b96aa

4. GTP에 단일 볼륨 파티션 생성
fdisk에서 파티션을 생성할 하드를 선택한다.

$sudo fdisk /dev/sdb


위와 같이 DOS 파티션으로는 2테라까지만 지원하니 GPT로 포맷하라는 안내가 메세지가 나온다.

Command (m for help): g

Created a new GPT disklabel (GUID: 407846ED-3CF1-FD45-B299-FBFE6FC73D62).
The old dos signature will be removed by a write command.

Command (m for help): p

Disk /dev/sdb: 3.7 TiB, 4000787030016 bytes, 7814037168 sectors
Units: sectors of 1 * 512 = 512 bytes
Sector size (logical/physical): 512 bytes / 4096 bytes
I/O size (minimum/optimal): 4096 bytes / 4096 bytes
Disklabel type: gpt
Disk identifier: 407846ED-3CF1-FD45-B299-FBFE6FC73D62


gpt 파티션으로 변환 되었다. 새로운 파티션을 생성한다. 생성 과정은 'n'옵션을 주면 되고 파티션 넘버 '1'을 주었고 시작섹터는 2048(디폴트 값이 있을때는 엔터만 치면된다.) 끝나는 섹터는 7814037134(마찬가지로 엔터)이다. 

Command (m for help): n

Partition number (1-128, default 1): 1
First sector (2048-7814037134, default 2048): 
Last sector, +sectors or +size{K,M,G,T,P} (2048-7814037134, default 7814037134): 


마직막으로 현재 파티션이 ntfs볼륨인데 이 ntfs볼륨을 지우고 Linux filesystem으로 사용 하겠냐고 묻는다. 필자는 이 파티션을 최종 ntfs로 쓰려고 한다. 'N'선택하면 ntfs로 쓸 수 있지만 Linux filesystem에서 어떻게 ntfs 볼륨으로 변환하는지 그 과정을 보여 주기 위해 Linux filesystem을 선택했다.

Created a new partition 1 of type 'Linux filesystem' and of size 3.7 TiB.

Partition #1 contains a ntfs signature.

Do you want to remove the signature? [Y]es/[N]o: Y
The signature will be removed by a write command.


다시 파티션 정보를 확인한다.

Command (m for help): p

Disk /dev/sdb: 3.7 TiB, 4000787030016 bytes, 7814037168 sectors
Units: sectors of 1 * 512 = 512 bytes
Sector size (logical/physical): 512 bytes / 4096 bytes
I/O size (minimum/optimal): 4096 bytes / 4096 bytes
Disklabel type: gpt
Disk identifier: 407846ED-3CF1-FD45-B299-FBFE6FC73D62

Device     Start        End    Sectors  Size Type
/dev/sdb1   2048 7814037134 7814035087  3.7T Linux filesystem
Filesystem/RAID signature on partition 1 will be wiped.


리눅스 파일 시스템으로 잘 변환되었다. 'w'로 마무리한다.

Command (m for help): w

The partition table has been altered.
Calling ioctl() to re-read partition table.
Syncing disks.
