## Check this during Installation
- show databases;
- CREATE database nextcloud;
- SELECT User, Host FROM mysql.user;
- CREATE USER 'nextcloud'@'%' IDENTIFIED BY '****';
- GRANT ALL PRIVILEGES ON nextcloud.* TO 'nextcloud'@'%'; 
- FLUSH PRIVILEGES;
- EXIT;
