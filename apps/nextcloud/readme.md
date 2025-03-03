# Nextcloud File Syncronization System

## Nextcloud server by docker-compose 
- 설치 및 설정
  - https://github.com/jeonghoonkang/BerePi/tree/master/apps/docker/docker_compose/nextcloud
  - 도커 컴포즈를 이용한 웹 서비스 실행 

## Nextcloud 클라이언트 설정
- ubuntu 클라이언트 
  - sudo apt install nextcloud-desktop
  - https://launchpad.net/~nextcloud-devs/+archive/ubuntu/client

## Nextcloud 서버 설정
- ...volume/config/config.php 내용 확인해야 함
- https://github.com/jeonghoonkang/BerePi/blob/0859bd0b6fe43aa6982d82b13f55e97919e72120/setup/howto/nextcloud_config_php.md
  <pre>'overwrite.cli.url' => 'https://***.***.***:***',
  'overwriteprotocol' => 'https', </pre>


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
- 컨테이너 내부에서 mysqldump 하여 오류없이 백업함 

</pre>

### Nextcloud restore
<pre>
rsync -Aax nextcloud-dirbkp/ nextcloud/ 

   (참고) DB 컨테이너 IP Address 확인 방법
         sudo docker inspect {컨테어너명} | grep IP

mysql -h [server] -u [username] -p[password] -e "DROP DATABASE nextcloud" 
mysql -h [server] -u [username] -p[password] -e "CREATE DATABASE nextcloud" 

## using UTF8
mysql -h [server] -u [username] -p[password] -e "CREATE DATABASE nextcloud CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
mysql -h [server] -u [username] -p[password] [db_name] < nextcloud-sqlbkp.bak -v 

mysql -h localhost -u nextcloud -p** nextcloud < db.bak -v

sudo docker exec -it -u 33 {컨테이너 이름} php occ upgrade

     version' => '21.0.2.1',
</pre>
  
### CPU 플랫폼 이슈
- 업그레이드 불가능한 앱은 disable 시켜야 함
  - sudo docker exec -it -u 33 {컨테이너 이름} php occ app:list
  - sudo docker exec -it -u 33 {컨테이너 이름} php occ app:disable richdocumentscode 
- 참고 : https://docs.nextcloud.com/server/15/admin_manual/configuration_server/occ_command.html#apps-commands
  

## rysnc 이후 file scan
- sudo docker exec -it -uroot nextcloud /bin/bash
  - apt update, apt install vim
  - vim ./config/config.php
  - 만약 sudo 없으면 apt update; apt install sudo 로 설치 
  - add line " 'filelocking.enabled' => false, " 
- sudo docker exec -it -u 33 nextcloud php occ files:scan --all

## docker 명령어
- docker exec --it {컨테이너 이름} /bin/bash 
- docker stats {컨테이너 이름}




