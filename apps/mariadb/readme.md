# MariaDB 사용 방법
## 기본 포트 3306
- docker 실행시에 -p 옵션으로 포트 변경 가능, -p 3307:3306 
  - 3307 로컬호스트 포트
  - 3306 도커 컨테이너 포트 
## User 관리
- MariaDB [(none)]> create user 'jb'@'%' identified by '1234';
  - create user 계정이름@localhost identified by '비밀번호';   

- MariaDB [mysql]> drop user 'jb'@'%';

- mysql> SELECT host, user FROM mysql.user;
  - mysql> SELECT CONCAT(QUOTE(user),'@',QUOTE(host)) UserAccount FROM mysql.user;
  - mysql> SELECT host, user, password FROM mysql.user;
