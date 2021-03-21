# Nextcloud Sync System

## Nextcloud server
- 설정
  - https://github.com/jeonghoonkang/BerePi/tree/master/apps/docker/docker_compose/nextcloud
  - 도커 컴포즈를 이용한 서비스 실행 

## Nextcloud 클라이언트 설정
- ubuntu 클라이언트 
  - sudo apt install nextcloud-desktop
  - https://launchpad.net/~nextcloud-devs/+archive/ubuntu/client


## 커맨드라인 명령어
- 서버 파일 추가후, 리스캔 & 등록
  - sudo docker exec -it -u 33 nextcloud_app_1 php occ files:scan --all 

## Nextcloud Backup 
- <code> rsync -Aavx nextcloud/ nextcloud-dirbkp_`date +"%Y%m%d"`/ </code>
- <code> mysqldump --single-transaction -h [server] -u [username] -p[password] [db_name] > nextcloud-sqlbkp_`date +"%Y%m%d"`.bak </code>

