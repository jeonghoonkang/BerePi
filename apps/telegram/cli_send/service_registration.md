
### System Daemon 추가 
- sudo vi /etc/systemd/system/{서비스명}.service
- input text
<pre>
[Unit]
Description= ***** ex) Configure Wake-up on LAN

[Service]
Type=oneshot
ExecStart=**** ex) /sbin/ethtool -s 인터페이스명(eth0) wol g

[Install]
WantedBy=basic.target
</pre>

### Setup and Run service 
- sudo systemctl enable /etc/systemd/system/{서비스명}.service
