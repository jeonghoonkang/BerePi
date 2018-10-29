# Installing Zabbix



## 0. Install required packages

```shell
sudo apt update
sudo apt install mysql-server apache2 php7.0 
```



## 1. zabbix server

### 0) initialize Mariadb (MySQL)

  ```SQL
  sudo mysql -u root -p
  > SELECT user, host, plugin FROM mysql.user;
  > UPDATE mysql.user SET plugin='';
  > UPDATE mysql.user SET password=PASSWORD("<password>") WHERE user='root';
  > FLUSH PRIVILEGES;
  > exit;
  ```

### 1) Create zabbix user and database on Mariadb (MySQL)

```SQL
mysql -u root -p
> CREATE USER 'zabbix'@'localhost' IDENTIFIED BY '<password>';
> CREATE DATABASE zabbix COLLATE = 'utf8_unicode_ci';
> GRANT ALL PRIVILEGES ON zabbix.* TO 'zabbix'@'localhost';
> FLUSH PRIVILEGES;
> exit;
```

### 2) Importing data

```Shell
wget https://github.com/ipmstyle/zabbix_on_raspberry_pi/raw/master/create.sql.gz
zcat create.sql.gz | mysql -u zabbix -p zabbix
```

### 3) Configure PHP

```Shell
sudo vi /etc/php/7.0/apache2/php.ini
```

```conf
[Date]
data.timezone = Asia/Seoul
```

### 4) Installing zabbix

```shell
git clone http://github.com/ipmstyle/zabbix_on_raspberry_pi
cd zabbix_on_raspberry_pi
sudo dpkg -i zabbix-release_3.4-1+stretch_all.deb
sudo dpkg -i zabbix-server-mysql_3.4.12-1+stretch_armhf.deb
sudo dpkg -i zabbix-agent_3.4.12-1+stretch_armhf.deb
sudo dpkg -i zabbix-frontend-php_3.4.12-1+stretch_all.deb
sudo dpkg -i zabbix-get_3.4.12-1+stretch_armhf.deb
sudo dpkg -i zabbix-sender_3.4.12-1+stretch_armhf.deb
```

### 5) Configure Zabbix server

```Shell
sudo vi /etc/zabbix/zabbix_server.conf
```

```conf
DBPassword=<password>
```

```Shell
sudo service zabbix-server restart
```



## 2. zabbix agent

### 1) Install

```shell
sudo dpkg –i zabbix-agent_3.4.12-1+stretch_armhf.deb
```

### 2) Configuration

```shell
cp /etc/zabbix/zabbix-agent.conf /etc/zabbix/zabbix-agent.conf.bak
sudo cp BerePi/apps/zabbix/conf/zabbix_agentd.rpi2.conf /etc/zabbix/zabbix-agent.conf
sudo vi /etc/zabbix/zabbix-agent.conf
```

```conf
Hostname=<host name>
```

### 3) Enable system service

```shell
sudo systemctl enable zabbix-agent.service
```

