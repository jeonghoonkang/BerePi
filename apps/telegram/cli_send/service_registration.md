
### System Daemon 추가 
- sudo vi /etc/systemd/system/{서비스명}.service
- input text
- 항상 root 권한으로 실행됨. 다른 user id에서 서비스 등록하더라도, root 로 실행해야 함

  
<pre>
# 서비스. 
[Unit]
Description=telegram-send Reboot
After=multi-user.target
  
[Service]
ExecStart=/bin/bash /home/....절대경로/crontab_sh.sh tx 
#Restart=on-failure #restart 조건 (on-failure: 오류발생, 재시작, always: 항상)
#RestartSec=3600*6
#Restart=always
#RuntimeMaxSec=7d

[Install]
WantedBy=multi-user.target

</pre>


<pre>
# 타이머
[Unit]
Description=telegram send timer

[Timer]
OnBootSec=20sec
OnCalendar=0/6:27:00
Unit=telegram.send.service

[Install]
WantedBy=multi-user.target
</pre>


### Setup and Run service 
- sudo systemctl daemon-reload
- sudo systemctl enable /etc/systemd/system/{서비스명}.service
- sudo systemctl start /etc/systemd/system/{서비스명}.service

### 주의
- sudo telegram-send --configure 가 설정 되어 있어야 함

### Check service status

<pre>

서비스 상태

sudo systemctl status reboot.start.sw.service
  
○ reboot.start.sw.service - Reboot telegram send  
  Loaded: loaded (/etc/systemd/system/reboot.start.sw.service; enabled; preset: enabled)                                        
  Active: inactive (dead) since Wed 2024-01-31 20:46:24 KST; 793ms ago                                                                           
  Duration: 1.861s                                                                    
  Process: 1853 ExecStart=/bin/bash /home/tinyos/devel_opment/crontab_sh.sh tx (code=exited, status=0/SUCCESS)    
  Main PID: 1853 (code=exited, status=0/SUCCESS)                                                                                                                            
  CPU: 653ms     
  
Jan 31 20:46:22 tinyos-rpi5 systemd[1]: Started reboot.start.sw.service - Reboot telegram send.   
Jan 31 20:46:22 tinyos-rpi5 bash[1853]: help: bash {file.sh} 'tx' will send message to telegram   
Jan 31 20:46:22 tinyos-rpi5 bash[1853]: argument 1--> tx   
Jan 31 20:46:22 tinyos-rpi5 sudo[1856]:     root : PWD=/ ; USER=root ; COMMAND=/usr/bin/vcgencmd measure_temp    
Jan 31 20:46:22 tinyos-rpi5 sudo[1856]: pam_unix(sudo:session): session opened for user root(uid=0) by (uid=0)    
Jan 31 20:46:22 tinyos-rpi5 sudo[1856]: pam_unix(sudo:session): session closed for user root                                                                               Jan 31 20:46:24 tinyos-rpi5 bash[1853]: send done                                                                                                                           Jan 31 20:46:24 tinyos-rpi5 systemd[1]: reboot.start.sw.service: Deactivated successfully.    
</pre>

   

<pre>

Timer 상태
  
sudo systemctl status telegram.send.timer
  
● telegram.send.timer - telegram send timer
     Loaded: loaded (/etc/systemd/system/telegram.send.timer; enabled; preset: enabled)
     Active: active (waiting) since Fri 2024-02-09 16:59:03 KST; 37min ago
    Trigger: Fri 2024-02-09 18:17:00 KST; 40min left
   Triggers: ● telegram.send.service

 2월 09 16:59:03 selfmach-01 systemd[1]: Started telegram.send.timer - telegram send timer.  

</pre>
