# Nextcloud File Syncronization System

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

## Nextcloud Backup & Restore

### Nextcloud backup
<pre> 
rsync -Aavx -e 'ssh -p22' --progress --partial nextcloud/ nextcloud-dirbkp_`date +"%Y%m%d"`/ 
mysqldump --single-transaction -h [server] -u [username] -p[password] [db_name] > nextcloud-sqlbkp_`date +"%Y%m%d"`.bak 
    ex) mysqldump --single-transaction -h {IP} -u nextcloud -p{PW} nextcloud > nextcloud_sql_bk_new.bak 
    ex) sudo docker inspect nextcloud_db_1 | grep IP 

- mysqldump --single-transaction -v -h localhost -u** -p** nextcloud > /var/lib/mysql/**_nextcloud-sqlbkp_`date +"%Y%m%d"`.bak

</pre>

### Nextcloud restore
<pre> rsync -Aax nextcloud-dirbkp/ nextcloud/ 

mysql -h [server] -u [username] -p[password] -e "DROP DATABASE nextcloud" 

mysql -h [server] -u [username] -p[password] -e "CREATE DATABASE nextcloud" 
mysql -h [server] -u [username] -p[password] -e "CREATE DATABASE nextcloud CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
mysql -h [server] -u [username] -p[password] [db_name] < nextcloud-sqlbkp.bak -v 

sudo docker exec -it -u 33 compose_script_app_1 php occ upgrade

</pre>



