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
  - sudo service smbd restart
  
