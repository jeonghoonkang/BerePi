
MariaDB [(none)]> create user 'jb'@'%' identified by '1234';
create user 계정이름@localhost identified by '비밀번호';   

MariaDB [mysql]> drop user 'jb'@'%';

mysql> SELECT host, user FROM mysql.user;

>> mysql> SELECT CONCAT(QUOTE(user),'@',QUOTE(host)) UserAccount FROM mysql.user;
>> mysql> SELECT host, user, password FROM mysql.user;
