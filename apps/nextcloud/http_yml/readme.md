## Check this during Installation
- sudo chown -R 33:33 ./data
### database
- sudo docker exec -it nextcloud_db_http /bin/bash 
- show databases;
- CREATE database nextcloud;
- SELECT User, Host FROM mysql.user;
- CREATE USER 'nextcloud'@'%' IDENTIFIED BY '****';
- GRANT ALL PRIVILEGES ON nextcloud.* TO 'nextcloud'@'%'; 
- FLUSH PRIVILEGES;
- EXIT;
