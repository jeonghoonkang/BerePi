#### Web server, 웹기반 서비스 제공

##### Web2Py
 - 다양한 Python code 를 실행시킬 수 있는 시스템
 - sensor LCD display
 - put / get interface 
  - put : input to DB
  - get : read from DB
 - www.web2py.com

##### Apache2
 - /var/www/html
 - sudo vim /etc/apache2/apache2.conf
 - sudo service apache2 restart
 - htpasswd -c /usr/uj/jurbanek/.htpasswd john
 - htpasswd /usr/uj/jurbanek/.htpasswd dave
 - 참고 : http://blog.yojm.net/?p=94
```
pi@mins-gate /var/www/html/pibox $ sudo vim /etc/apache2/apache2.conf
pi@mins-gate /var/www/html/pibox $ sudo service apache2 restar

pi@mins-gate /var/www/html/pibox $ cat .htaccess
AuthUserFile /home/pibox/.htpasswd
AuthType Basic
AuthName "PiBox"
Require valid-user

pi@mins-gate /var/www/html/pibox $ cat .htpasswd
tinyos:$apr1$GkRTSblj$4P5EScc1Ghfp91FM/nuuj0

pi@mins-gate /var/www/html/pibox $ cat /etc/apache2/apache2.conf

<Directory /var/www/>
        Options Indexes FollowSymLinks
        AllowOverride AuthConfig
        Require all granted
</Directory>

<Directory /home/pibox/>
        Options Indexes FollowSymLinks
        AllowOverride AuthConfig
        Require all granted
</Directory>
```
