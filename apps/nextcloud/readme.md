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
<pre> rsync -Aavx nextcloud/ nextcloud-dirbkp_`date +"%Y%m%d"`/ </pre>
<pre> mysqldump --single-transaction -h [server] -u [username] -p[password] [db_name] > nextcloud-sqlbkp_`date +"%Y%m%d"`.bak </pre>

<pre> rsync -Aax nextcloud-dirbkp/ nextcloud/ </pre>
<pre> mysql -h [server] -u [username] -p[password] -e "DROP DATABASE nextcloud"
mysql -h [server] -u [username] -p[password] -e "CREATE DATABASE nextcloud" 

mysql -h [server] -u [username] -p[password] -e "CREATE DATABASE nextcloud CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"</pre>
