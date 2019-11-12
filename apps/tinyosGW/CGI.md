#### Python CGI
- apache2 configuration for CGI
  - http://www.evernote.com/l/ABOLKkis29BDVYfV5b_HnJRsG_l3mthRQyA/
  - sudo a2enmod cgid
  - sudo a2enconf server-cgi-bin
  
- requirements
  - should have below in the .py file
    - #!/usr/bin/python
    - unix file type, if you have dos file type, should change dos2unix linux command
      - /r/n issue
    - check chmod for +x, eg) chmod 777 {filename}
    
#### CGI 설정 추가 정보
- https://github.com/jeonghoonkang/keti/blob/master/BootCamp/cschae/CGI/readme.md
- Rasbian 2019-07-10 (apache2 2.4.38) 기준 CGI 설정파일은 **/etc/apache2/conf-available/serve-cgi-bin.conf**
- 다음 예제는 ```http://<IP>/gw/``` 경로에 ```/home/pi/Documents/BerePi/apps/tinyosGW/``` 폴더를 cgi 로 추가한 설정
```apacheconf
        <IfDefine ENABLE_USR_LIB_CGI_BIN>
                ScriptAlias /cgi-bin/ /usr/lib/cgi-bin/
                <Directory "/usr/lib/cgi-bin">
                        AllowOverride None
                        Options +ExecCGI -MultiViews +SymLinksIfOwnerMatch
                        Require all granted
                </Directory>
                ScriptAlias /gw/ /home/pi/Documents/BerePi/apps/tinyosGW/
                <Directory "/home/pi/Documents/BerePi/apps/tinyosGW/">
                        AllowOverride None
                        Options +ExecCGI -MultiViews +SymLinksIfOwnerMatch
                        Require all granted
                </Directory>
        </IfDefine>
```


#### /usr/lib/cgi-bin 권한설정

<pre>
drwxr-xr-x  3 root root 4.0K  7월 24 23:47 ./
drwxr-xr-x 76 root root 4.0K  4월 29 23:36 ../
-rwxrwxr-x  1 root root 3.1K  7월 24 23:45 df_status.py
drwxrwxrwx  2 root root 4.0K  7월 24 23:47 out/
-rwxrwxrwx  1 root root  533  7월 24 23:42 simple.py
pi@odesk-motion /usr/lib/cgi-bin $
</pre>


### index.py

'CGI 설정 추가 정보' 에서 추가된 경로의 index.py 을 사용한 결과
(../../files/tinyosGW.index.py_1.png)
(../../files/tinyosGW.index.py_2.png)


#### rsync

ssh 포트를 사용하여 remote 서버로 tinyosGW 정보를 전송

```<tinyosGW hostname>_<정보>.log```
