### nextcloud 파일 관리 
- 강제 삭제 파일 작업
  - sudo rm www/html/nextcloud/data/***/files/Backup_EV_center_ori_dir/image.png
- Rescan 후, nextcloud WEB 인터페이스에 적용 (php8.0은 아직 지원이 안되어서. 7.4버전으로 occ 실행해야함 ) (2023.05)
  - sudo -u www-data php7.4 /var/www/html/nextcloud/occ files:scan --all
