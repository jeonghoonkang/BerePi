## 사용방법
- sudo umount /mnt/c
- sudo mount -t drvfs d: /mnt/d -o metadata 

## umount 실행때, mount busy 에러 메세지 발생시 처리방법 
- umount -l /PATH/OF/BUSY-DEVICE
- umount -f /PATH/OF/BUSY-NFS (NETWORK-FILE-SYSTEM)

## 디렉토리 권한 설정 
![WsL 디렉토리 권한](디랙토리권한.png)
