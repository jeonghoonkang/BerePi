lsb_release -a
sudo apt update && sudo apt full-upgrade
sudo do-release-upgrade


### 커널 파티션 공간 문제
/boot 독립 파티션 안에 있는 파일들을 루트(/) 파티션으로 옮긴 후, 기존 /boot 독립 파티션을 해제(마운트 제거)하고 루트 내의 /boot 디렉토리를 사용하도록 설정하면 용량 문제(6.1TB 여유 공간 활용) 없이 커널 업그레이드가 가능해집니다.
다만, 부팅에 관련된 파일 위치가 바뀌기 때문에 fstab 수정과 GRUB(부트로더) 재설치 및 업데이트 과정을 정확하게 수행해야 다음 부팅 때 부팅 불능에 빠지지 않습니다.
이 작업은 안전하게 시스템을 전환할 수 있는 검증된 순서입니다.
/boot 파티션을 루트(/) 디렉토리 내부로 이관하는 방법
작업 전 혹시 모를 상황에 대비해 중요 데이터는 백업해 두시는 것을 권장합니다. 모든 작업은 root 권한(또는 sudo)으로 진행합니다.

1.새 임시 디렉토리로 현재 /boot 내용 복사:데이터 유실 방지.
현재 마운트된 /boot 파티션의 모든 내용(커널, initrd, grub 파일 등)을 루트 파티션 아래의 임시 디렉토리로 복사합니다.

Bash
# 임시 디렉토리 생성
sudo mkdir /boot_temp

# 권한 및 속성을 유지(p)하며 전체 복사(a, v)
sudo cp -av /boot/* /boot_temp/


확인 방법: ls -l /boot_temp 명령을 실행하여 vmlinuz, initrd.img, grub 폴더 등이 제대로 복사되었는지 확인합니다.

2.기존 /boot 파티션 마운트 해제:기존 파티션 분리.
현재 마운트되어 있는 별도의 /boot 파티션을 언마운트합니다.

Bash
sudo umount /boot


참고: 만약 target is busy 에러가 난다면 해당 디렉토리를 참조 중인 터미널이나 프로세스를 종료 후 다시 시도합니다.

3.복사해둔 내용을 실제 /boot 디렉토리로 이동:루트 파티션 내 /boot 활성화.
마운트가 해제되면 기존 / 파티션의 비어 있는 원래 /boot 디렉토리가 보입니다. 아까 복사해둔 내용을 이곳으로 옮깁니다.



Bash
sudo cp -av /boot_temp/* /boot/
sudo rm -rf /boot_temp


확인 방법: ls -l /boot를 했을 때 커널 파일들이 보이고, df -h /boot를 실행했을 때 독립 파티션이 아닌 루트 파티션(/dev/mapper/ubuntu--vg-root) 정보가 나오는지 확인합니다.

4.etc/fstab 파일 수정:자동 마운트 제거 (핵심).
부팅 시 기존의 별도 /boot 파티션을 마운트하지 않도록 /etc/fstab 설정 파일에서 해당 항목을 주석 처리해야 합니다.

Bash
sudo nano /etc/fstab


파일 내부에서 /boot 마운트 지점이 적힌 줄 찾기 (예: UUID=... /boot ext4 defaults 0 2 또는 /dev/sda1 /boot ... 형태)
해당 줄의 맨 앞에 #을 붙여 주석 처리하고 저장합니다.

Plaintext
# /boot was on /dev/sda1 during installation
# UUID=xxxx-xxxx-xxxx-xxxx /boot ext4 defaults 0 2  <-- 이처럼 # 추가



5.GRUB 부트로더 업데이트 및 재설치:부팅 경로 재설정 (핵심).
GRUB 부트로더에게 이제 커널 파일 위치가 독립 파티션이 아니라 루트 파티션의 /boot임을 알려주고 부팅 섹터(MBR/EFI)를 갱신합니다.

Bash
# GRUB 구성 파일 갱신
sudo update-grub

# 디스크 헤더(MBR)에 GRUB 재설치 (최초 부팅 디스크 지정, 보통 /dev/sda)
sudo grub-install /dev/sda


주의: 출력 결과에 Installation finished. No error reported. 문구가 나오는지 반드시 확인합니다.


6.재부팅 및 커널 업그레이드:최종 검증 및 작업.
시스템을 재부팅하여 정상적으로 루트 파티션의 /boot로 부팅되는지 확인합니다.

Bash
sudo reboot


재부팅 후 df -h를 실행했을 때 /boot가 별도 파티션으로 잡히지 않고 루트(/) 용량(6.1TB 여유)을 공유하는 상태가 되었다면 성공입니다! 이 상태에서는 용량 걱정 없이 커널 업데이트 및 배포판 업그레이드를 진행하실 수 있습니다.
요약 및 확인사항
위 작업이 완료되면 /boot는 별도의 472MB 공간이 아닌 6.1TB 여유가 남아있는 / (루트) LVM 파티션을 직접 사용하게 됩니다.
따라서 커널 업데이트를 아무리 여러 번 수행하더라도 용량이 부족해지는 현상은 완전히 해결됩니다.
