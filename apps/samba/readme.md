#### file sharing via Samba
 - sudo service smbd restart
 - smbpasswd -a pi 
 - sudo vim /etc/samba/smb.conf
 - samba port is 139 
   
<pre> 
	[global]
	workgroup = WORKGROUP //네트워크 공유 그룹 설정
	encrypt password = true // 암호 설정
	unix charset = utf-8
	charset = utf-8
	#dos charset = cp949

	[pi]  # 추가한 계정
	comment = Raspberry pi
	path = /home   #공유할 폴더 경로
	valid user = pi  #smbpasswd 에서 설정한 유저
	browseable = yes 
	read only = no #읽기 전용 여부
	writable = yes #쓰기 권한 여부
	public = yes
	browsable = yes
	guest ok = no #게스트 계정 접근 허용 여부
</pre>

  - sudo smbpasswd {user, tinyos}
    - check option of -a 
  - sudo service smbd restart
  

smb.conf
yes, removing security = share and reinstalling fixed the problem

pi@mins-gate ~ $ sudo ufw allow 445
Rule added
Rule added (v6)

pi@mins-gate ~ $ sudo ufw status
Status: active
To                         Action      From
--                         ------      ----
23                         ALLOW       Anywhere
21                         ALLOW       Anywhere
22                         ALLOW       Anywhere
2181                       ALLOW       Anywhere
4242                       ALLOW       Anywhere
80                         ALLOW       Anywhere
139                        ALLOW       Anywhere
445                        ALLOW       Anywhere
23                         ALLOW       Anywhere (v6)
21                         ALLOW       Anywhere (v6)
22                         ALLOW       Anywhere (v6)
2181                       ALLOW       Anywhere (v6)
4242                       ALLOW       Anywhere (v6)
80                         ALLOW       Anywhere (v6)
139                        ALLOW       Anywhere (v6)
445                        ALLOW       Anywhere (v6)



- 서비스 시작
  - systemctl start [서비스명]

- 서비스 종료
  - systemctl stop [서비스명]

- 서비스 재시작
  - systemctl restart [서비스명]


